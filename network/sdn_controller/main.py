from fastapi import FastAPI, HTTPException
import json
import os
from typing import Dict, List, Optional
import logging
import uvicorn
import yaml
import networkx as nx
import re
import matplotlib.pyplot as plt
import io
import base64
from fastapi.responses import HTMLResponse
from fastapi.responses import Response
import time
import threading
from datetime import datetime

# Setuplogging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SDN Controller API")

ROUTER_TABLES_DIR = "/shared/"
DOCKER_COMPOSE_PATH= "/app/docker-compose.yml"

# Global network graph
network_graph = nx.Graph()

# Store node positions to keep graph layout consistent
node_positions = {}

# Directory to save graph snapshots
GRAPH_SNAPSHOTS_DIR = "/shared/snapshots/"

def parse_docker_compose():
    """Parse docker-compose.yml to build network topology graph"""
    try:
        # Check if file exists in shared directory or try relative path
        if os.path.exists(DOCKER_COMPOSE_PATH):
            compose_path = DOCKER_COMPOSE_PATH
        else:
            logger.error("docker-compose.yml not found")
            return
        
        logger.info(f"Parsing docker-compose.yml from {compose_path}")
        with open(compose_path, 'r') as file:
            compose_data = yaml.safe_load(file)
        
        # Clear existing graph
        network_graph.clear()
        
        # Get all networks that represent links between routers
        link_networks = {}
        for network_name, network_config in compose_data.get('networks', {}).items():
            # Look for networks with names like 'link-X-Y'
            if network_name.startswith('link-'):
                subnet = None
                if 'ipam' in network_config and 'config' in network_config['ipam']:
                    for config in network_config['ipam']['config']:
                        if 'subnet' in config:
                            subnet = config['subnet']
                            break
                
                link_networks[network_name] = {'subnet': subnet}
                logger.info(f"Found network: {network_name}, subnet: {subnet}")
        
        # Get all routers and their connections
        routers = {}
        for service_name, service_config in compose_data.get('services', {}).items():
            # Skip non-router services like the SDN controller
            if service_name.startswith('router'):
                router_id = service_name
                router_networks = {}
                router_ports = {}
                
                # Extract port mappings
                if 'ports' in service_config:
                    for port_mapping in service_config['ports']:
                        if isinstance(port_mapping, str):
                            # Format like "8001:8000"
                            host_port, container_port = port_mapping.split(':')
                            router_ports[container_port] = host_port
            
                
                # Get networks this router is connected to
                if 'networks' in service_config:
                    for network_name, network_config in service_config['networks'].items():
                        if network_name.startswith('link-'):
                            ip_address = None
                            if isinstance(network_config, dict) and 'ipv4_address' in network_config:
                                ip_address = network_config['ipv4_address']
                            
                            router_networks[network_name] = ip_address
                
                routers[router_id] = {
                    'networks': router_networks,
                    'ports': router_ports
                }
                
                # Add router node to graph with both network and port information
                network_graph.add_node(
                    router_id, 
                    ip_addresses=router_networks,
                    ports=router_ports
                )
                logger.info(f"Added router: {router_id} with networks: {router_networks} and ports: {router_ports}")
        
        # Create links between routers
        for network_name, network_info in link_networks.items():
            # Extract router IDs from link names (e.g., 'link-1-2' → routers 1 and 2)
            match = re.search(r'link-(\d+)-(\d+)', network_name)
            if match:
                router1_id = f"router{match.group(1)}"
                router2_id = f"router{match.group(2)}"
                
                # Check if both routers exist
                if router1_id in routers and router2_id in routers:
                    subnet = network_info.get('subnet')
                    router1_ip = routers[router1_id]['networks'].get(network_name)
                    router2_ip = routers[router2_id]['networks'].get(network_name)
                    
                    # Add edge between routers
                    network_graph.add_edge(
                        router1_id, 
                        router2_id, 
                        subnet=subnet,
                        network=network_name,
                        router1_ip=router1_ip,
                        router2_ip=router2_ip,
                        weight=calculate_link_weight(network_name, router1_id, router2_id)
                    )
                    logger.info(f"Added link between {router1_id} and {router2_id} on network {network_name}")

        logger.info(f"Network graph built with {len(network_graph.nodes)} nodes and {len(network_graph.edges)} edges")
        
        # Generate initial routing tables based on the topology
        generate_routing_tables()

        # Calculate flow tables for optimal routing
        calculate_flow_tables()
        
    except Exception as e:
        logger.error(f"Error parsing docker-compose.yml: {str(e)}")

def generate_routing_tables():
    """Generate routing tables for all routers based on the network graph"""
    for router_id in network_graph.nodes:
        routing_table = {
            "router_id": router_id,
            "interfaces": {},
            "flow_table": [],
            "routes": [],
            "ports": network_graph.nodes[router_id].get('ports', {})
        }
        
        # Add interfaces (direct connections)
        for neighbor in network_graph.neighbors(router_id):
            edge_data = network_graph.get_edge_data(router_id, neighbor)
            network_name = edge_data.get('network')
            subnet = edge_data.get('subnet')
            
            # Get IP address for this router on this network
            router_ip_key = f"{router_id}_ip".replace('router', 'router')
            ip_address = edge_data.get(router_ip_key)
            
            # If not found in edge data, try node data
            if not ip_address and 'ip_addresses' in network_graph.nodes[router_id]:
                ip_address = network_graph.nodes[router_id]['ip_addresses'].get(network_name)
            
            routing_table["interfaces"][neighbor] = {
                "network": network_name,
                "subnet": subnet,
                "ip_address": ip_address
            }
        
        # Generate routes to all possible destinations (shortest path)
        for target in network_graph.nodes:
            if target == router_id:
                continue  # Skip self
                
            try:
                path = nx.shortest_path(network_graph, router_id, target)
                if len(path) > 1:
                    next_hop = path[1]  # The next router in the path
                    
                    # Get the subnet for the target
                    edge_data = network_graph.get_edge_data(path[-2], target)
                    target_subnet = edge_data.get('subnet', '')
                    
                    # Create a route entry
                    routing_table["routes"].append({
                        "destination": target,
                        "destination_subnet": target_subnet,
                        "next_hop": next_hop,
                        "metric": len(path) - 1
                    })
            except nx.NetworkXNoPath:
                logger.warning(f"No path from {router_id} to {target}")
        
        # Save router table to shared volume
        save_router_table(router_id, routing_table)

def save_router_table(router_id, table):
    """Save router table to JSON file in shared volume"""
    file_path = os.path.join(ROUTER_TABLES_DIR, f"{router_id}_table.json")
    with open(file_path, 'w') as file:
        json.dump(table, file, indent=2)
    logger.info(f"Saved routing table for {router_id}")

def calculate_flow_tables():
    """Calculate and populate flow tables for all routers using Dijkstra's algorithm"""
    logger.info("Calculating optimal paths for all router pairs...")
    
    # For each router, calculate shortest paths to all destinations
    for source in network_graph.nodes:
        # Get shortest paths from this source to all destinations using weights
        # Format: {destination: (distance, path)}
        paths_with_distances = nx.single_source_dijkstra(network_graph, source, weight='weight')
        # Unpack into separate dictionaries
        distances, paths = paths_with_distances
        
        # Get the router's current table
        file_path = os.path.join(ROUTER_TABLES_DIR, f"{source}_table.json")
        try:
            with open(file_path, "r") as file:
                router_data = json.load(file)
        except FileNotFoundError:
            logger.error(f"Table for router {source} not found")
            continue
            
        # Reset flow table
        router_data['flow_table'] = []
        
        # Create flow entries for each destination
        for destination, path in paths.items():
            if source == destination:
                continue  # Skip self
                
            if len(path) > 1:
                next_hop = path[1]  # Next router in the path
                distance = distances[destination]  # Total path cost
                
                # Create a flow entry
                flow_entry = {
                    "match": {
                        "destination": destination
                    },
                    "action": {
                        "forward_to": next_hop
                    },
                    "priority": 100,
                    "path": path,
                    "metric": distance  # Use actual distance now instead of hop count
                }
                
                router_data['flow_table'].append(flow_entry)
        
        # Save updated router table
        save_router_table(source, router_data)
        logger.info(f"Updated flow table for {source} with {len(router_data['flow_table'])} entries")

def calculate_link_weight(network_name, router1_id, router2_id):
    """Calculate default weight for a link"""
    # Default base weight
    return 1.0

@app.get("/sdn_controller/health")
def service_health():
    return {
        "status": "running", 
        "service": "SDN Controller"
    }

@app.get("/sdn_controller/topology")
def get_topology():
    """Return the current network topology"""
    nodes = [{
        "id": node, 
        "ip_addresses": data.get('ip_addresses', {}),
        "ports": data.get('ports', {})
    } for node, data in network_graph.nodes(data=True)]
    
    links = [{"source": u, "target": v, "subnet": data.get('subnet')} 
             for u, v, data in network_graph.edges(data=True)]
    
    return {
        "nodes": nodes,
        "links": links
    }

@app.get("/sdn_controller/routers/flow_table/{router_id}")
def get_flow_table(router_id: str):
    file_path = os.path.join(ROUTER_TABLES_DIR, f"{router_id}_table.json")
    try:
        with open(file_path, "r") as file:
            router_data = json.load(file)
    except FileNotFoundError:
        logger.error(f"Table for router {router_id} not found")
        return {
            "router_id": router_id,
            "flow_table": [],
            "interfaces": {}
        }
    return router_data.get('flow_table', [])

@app.get("/sdn_controller/routers/routing_table/{router_id}")
def get_routing_table(router_id: str):
    """Get the full routing table for a router"""
    file_path = os.path.join(ROUTER_TABLES_DIR, f"{router_id}_table.json")
    try:
        with open(file_path, "r") as file:
            router_data = json.load(file)
    except FileNotFoundError:
        logger.error(f"Table for router {router_id} not found")
        return {
            "router_id": router_id,
            "flow_table": [],
            "interfaces": {},
            "routes": []
        }
    return router_data

@app.get("/sdn_controller/rebuild_topology")
def rebuild_topology():
    """Manually trigger rebuilding the topology from docker-compose.yml"""
    parse_docker_compose()
    return {"status": "topology rebuilt"}


@app.get("/sdn_controller/graph", response_class=Response)
def network_graph_image():
    """Return just a PNG image of the network graph"""
    try:
        # Create figure
        plt.figure(figsize=(10, 8))
        
        # Use a deterministic layout
        pos = nx.spring_layout(network_graph, seed=42)
        
        # Draw nodes with different colors for routers
        nx.draw_networkx_nodes(network_graph, pos, 
                              node_size=1000, 
                              node_color="skyblue")
        
        # Draw edges
        nx.draw_networkx_edges(network_graph, pos, width=2)
        
        # Create clear labels for nodes
        labels = {}
        for node in network_graph.nodes():
            labels[node] = node
        nx.draw_networkx_labels(network_graph, pos, labels, font_size=12, font_weight='bold')
        
        # Add subnet information on edges
        edge_labels = {}
        for u, v, data in network_graph.edges(data=True):
            if 'subnet' in data:
                edge_labels[(u, v)] = data['subnet']
        nx.draw_networkx_edge_labels(network_graph, pos, edge_labels=edge_labels)
        
        plt.title("Network Topology")
        plt.axis('off')  # Turn off axis
        
        # Save to bytes buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150)
        plt.close()
        
        # Return the image
        buf.seek(0)
        return Response(content=buf.getvalue(), media_type="image/png")
    
    except Exception as e:
        logger.error(f"Error generating graph image: {str(e)}")
        # Return error message as plain text
        return Response(content=f"Error generating graph: {str(e)}", media_type="text/plain")

def generate_graph_snapshots():
    """Thread function to generate graph snapshots every 4 seconds"""
    # Ensure snapshots directory exists
    os.makedirs(GRAPH_SNAPSHOTS_DIR, exist_ok=True)
    logger.info(f"Starting graph snapshot thread - saving to {GRAPH_SNAPSHOTS_DIR}")
    
    snapshot_count = 0
    
    while True:
        try:
            # Generate timestamp for filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            snapshot_count += 1
            filename = f"network_graph_{timestamp}_{snapshot_count:04d}.png"
            filepath = os.path.join(GRAPH_SNAPSHOTS_DIR, filename)
            
            # Create figure
            plt.figure(figsize=(12, 10))
            
            # Use the stored node positions for consistent layout
            global node_positions
            if not node_positions or set(node_positions.keys()) != set(network_graph.nodes):
                node_positions = nx.spring_layout(network_graph, seed=42)
            
            # Get router1's path to router10 from flow table
            path_to_highlight = []
            try:
                file_path = os.path.join(ROUTER_TABLES_DIR, f"router1_table.json")
                with open(file_path, "r") as file:
                    router_data = json.load(file)
                    # Find flow entry for router10
                    for entry in router_data.get('flow_table', []):
                        match_info = entry.get('match', {})
                        if match_info.get('destination') == 'router10':
                            path_to_highlight = entry.get('path', [])
                            break
            except Exception as e:
                logger.error(f"Error reading router1 flow table: {e}")
            
            # Create edge lists for normal and highlighted paths
            regular_edges = []
            highlighted_edges = []
            
            for u, v, data in network_graph.edges(data=True):
                # Check if this edge is in the path
                edge_in_path = False
                if path_to_highlight:
                    for i in range(len(path_to_highlight) - 1):
                        if (u == path_to_highlight[i] and v == path_to_highlight[i+1]) or \
                          (v == path_to_highlight[i] and u == path_to_highlight[i+1]):
                            edge_in_path = True
                            break
                
                if edge_in_path:
                    highlighted_edges.append((u, v))
                else:
                    regular_edges.append((u, v))
            
            # Draw nodes
            nx.draw_networkx_nodes(network_graph, node_positions, 
                                  node_size=1000, 
                                  node_color="skyblue")
            
            # Draw regular edges
            nx.draw_networkx_edges(network_graph, node_positions, 
                                  edgelist=regular_edges,
                                  width=2,
                                  edge_color='gray',
                                  alpha=0.7)
            
            # Draw highlighted edges
            if highlighted_edges:
                nx.draw_networkx_edges(network_graph, node_positions, 
                                      edgelist=highlighted_edges,
                                      width=4,
                                      edge_color='red',
                                      alpha=1.0)
            
            # Create clear labels for nodes
            labels = {}
            for node in network_graph.nodes():
                labels[node] = node
            nx.draw_networkx_labels(network_graph, node_positions, labels, font_size=12, font_weight='bold')
            
            # Add weight information on all edges
            edge_labels = {}
            for u, v, data in network_graph.edges(data=True):
                weight = data.get('weight', 1.0)
                edge_labels[(u, v)] = f"{weight:.1f}"  # Format to 1 decimal place
                
            nx.draw_networkx_edge_labels(network_graph, node_positions, 
                                        edge_labels=edge_labels, 
                                        font_size=10,
                                        font_color='black')
            
            # Add title with timestamp
            plt.title(f"Network Topology - {timestamp}")
            
            # Add legend as text in the corner
            legend_text = "Red edges: Path from router1 to router10"
            plt.figtext(0.02, 0.02, legend_text, fontsize=10, 
                       bbox=dict(facecolor='white', alpha=0.8, boxstyle='round'))
            
            plt.axis('off')  # Turn off axis
            
            # Save to file
            plt.savefig(filepath, format='png', dpi=150)
            plt.close()
            
            logger.info(f"Saved graph snapshot to {filepath}")
            
            # If we have too many snapshots, we could implement cleanup here
            
        except Exception as e:
            logger.error(f"Error generating graph snapshot: {e}")
        
        # Sleep for 4 seconds
        time.sleep(4)
@app.on_event("startup")
async def startup_event():
    """Parse the docker-compose.yml on startup"""
    logger.info("SDN Controller starting up")
    
    # Make sure the shared directory exists
    logger.info("Making sure the shared directory exists")
    os.makedirs(ROUTER_TABLES_DIR, exist_ok=True)
    
    # Clean up previous snapshots
    snapshots_dir = os.path.join(GRAPH_SNAPSHOTS_DIR)
    if os.path.exists(snapshots_dir):
        logger.info(f"Cleaning up previous snapshots from {snapshots_dir}")
        try:
            for filename in os.listdir(snapshots_dir):
                if filename.startswith('network_graph_') and filename.endswith('.png'):
                    file_path = os.path.join(snapshots_dir, filename)
                    os.remove(file_path)
            logger.info("Successfully removed previous snapshots")
        except Exception as e:
            logger.error(f"Error cleaning up snapshots: {e}")
    
    # Ensure the snapshots directory exists
    os.makedirs(GRAPH_SNAPSHOTS_DIR, exist_ok=True)
    
    # Parse docker-compose and build the network graph
    logger.info("Beginning docker-compose parsing")
    parse_docker_compose()

    source_router = os.environ.get('SOURCE_ROUTER')
    destination_router = os.environ.get('DESTINATION_ROUTER')
    logger.info(f"Setting up priority path from {source_router} to {destination_router}")
    

    # Start graph snapshot thread
    try:
        snapshot_thread = threading.Thread(target=generate_graph_snapshots, daemon=True)
        snapshot_thread.start()
        logger.info("Started graph snapshot thread")
    except Exception as e:
        logger.error(f"Error starting graph snapshot thread: {e}")

@app.post("/sdn_controller/update_link_metrics/{router_id}")
def update_link_metrics(router_id: str, metrics: Dict[str, float]):
    """
    Update link weights based on router metrics
    
    router_id: The ID of the router reporting metrics
    metrics: Dictionary with keys as neighbor router IDs and values as metric weights
    """
    try:
        logger.info(f"Received metrics from {router_id}: {metrics}")
        
        # Validate router exists
        if router_id not in network_graph.nodes:
            raise HTTPException(status_code=404, detail=f"Router {router_id} not found")
        
        # Update weights for each reported link
        for neighbor_id, metric in metrics.items():
            if neighbor_id not in network_graph.nodes:
                logger.warning(f"Neighbor {neighbor_id} does not exist in network graph")
                continue
                
            if not network_graph.has_edge(router_id, neighbor_id):
                logger.warning(f"No direct link between {router_id} and {neighbor_id}")
                continue
                
            # Update the edge weight
            current_weight = network_graph[router_id][neighbor_id].get('weight', 1.0)
            
            # You could use different strategies here:
            # 1. Replace the weight: network_graph[router_id][neighbor_id]['weight'] = metric
            # 2. Add to the weight: network_graph[router_id][neighbor_id]['weight'] = current_weight + metric
            # 3. Use weighted average: network_graph[router_id][neighbor_id]['weight'] = 0.7*current_weight + 0.3*metric
            
            # For now, we'll use option 2: add to the weight
            # network_graph[router_id][neighbor_id]['weight'] = current_weight + metric
            network_graph[router_id][neighbor_id]['weight'] = metric
            logger.info(f"Updated link {router_id}-{neighbor_id} weight to {network_graph[router_id][neighbor_id]['weight']}")
        
        # Recalculate flow tables with updated weights
        calculate_flow_tables()
        
        return {
            "status": "success", 
            "message": f"Updated metrics for {router_id}",
            "updated_links": len(metrics)
        }
        
    except Exception as e:
        logger.error(f"Error updating metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    logger.info("Starting SDN Controller server")
    
    # Use the module:app format for uvicorn to properly handle lifecycle events
    uvicorn.run("main:app", host="0.0.0.0", port=8000, log_level="info")