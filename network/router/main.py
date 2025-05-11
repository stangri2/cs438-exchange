# main.py
import socket
import json
import os
import threading
import time
import logging
import random
import requests
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("router_agent")

class RouterAgent:
    def __init__(self, router_id, table_path, listen_port=9000):
        self.router_id = router_id
        self.table_path = table_path
        self.listen_port = listen_port
        self.routing_table = self.load_routing_table()
        self.refresh_thread = None
        self.neighbor_connections = {}  # Store connections to neighbors
        self.connection_lock = threading.Lock()  # Lock for thread-safe access
        self.running = True  # Flag to control connection threads
        
    def load_routing_table(self):
        """Load routing table from the shared volume"""
        try:
            with open(self.table_path, 'r') as f:
                table = json.load(f)
                logger.info(f"Loaded routing table for {self.router_id} with {len(table.get('routes', []))} routes")
                return table
        except Exception as e:
            logger.error(f"Error loading routing table: {e}")
            return {"interfaces": {}, "routes": [], "flow_table": []}
    
    def get_neighbors(self):
        """Extract neighbors from interfaces in routing table"""
        neighbors = []
        for router_id, interface_info in self.routing_table.get('interfaces', {}).items():
            if router_id != self.router_id:  # Skip self
                neighbors.append(router_id)
        return neighbors
    
    def start_periodic_table_refresh(self):
        """Start a thread to periodically refresh the routing table"""
        def refresh_routine():
            while self.running:
                try:
                    old_table = self.routing_table
                    self.routing_table = self.load_routing_table()
                    # Check for new neighbors after refresh
                    old_neighbors = set(old_table.get('interfaces', {}).keys())
                    new_neighbors = set(self.routing_table.get('interfaces', {}).keys())
                    
                    if old_neighbors != new_neighbors:
                        logger.info(f"Neighbor change detected. Updating connections.")
                        self.update_neighbor_connections()
                        
                    logger.info(f"Refreshed routing table for {self.router_id}")
                except Exception as e:
                    logger.error(f"Error refreshing routing table: {e}")
                time.sleep(10)  # Refresh every 10 seconds
        
        self.refresh_thread = threading.Thread(target=refresh_routine, daemon=True)
        self.refresh_thread.start()
        logger.info("Started periodic routing table refresh")
    
    def establish_neighbor_connection(self, neighbor_id):
        """Establish a TCP connection with a neighbor"""
        if neighbor_id == self.router_id:
            return  # Skip self-connection
            
        interface = self.routing_table.get('interfaces', {}).get(neighbor_id, {})
        ip_address = interface.get('ip_address')
        
        if not ip_address:
            logger.error(f"No IP address found for neighbor {neighbor_id}")
            return
        
        def connection_handler():
            retries = 0
            max_retries = 10
            backoff_time = 2  # Initial backoff time in seconds
            
            while self.running and retries < max_retries:
                try:
                    # Don't create a new connection if one already exists
                    with self.connection_lock:
                        if neighbor_id in self.neighbor_connections and self.neighbor_connections[neighbor_id].get('status') == 'connected':
                            break
                    
                    # Create socket for connection
                    neighbor_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    neighbor_socket.settimeout(5)  # Set timeout for connection attempts
                    
                    logger.info(f"Attempting to connect to neighbor {neighbor_id} at {ip_address}:{self.listen_port}")
                    neighbor_socket.connect((ip_address, self.listen_port))
                    
                    # Send hello message
                    hello_msg = {
                        "type": "hello",
                        "source": self.router_id,
                        "destination": neighbor_id,
                        "payload": {"type": "connection_request"}
                    }
                    neighbor_socket.send(json.dumps(hello_msg).encode('utf-8'))
                    
                    # Wait for response
                    response = neighbor_socket.recv(4096)
                    if response:
                        response_data = json.loads(response.decode('utf-8'))
                        logger.info(f"Connection established with {neighbor_id}, response: {response_data}")
                        
                        # Store connection info
                        with self.connection_lock:
                            self.neighbor_connections[neighbor_id] = {
                                'socket': neighbor_socket,
                                'ip': ip_address,
                                'status': 'connected',
                                'last_activity': time.time()
                            }
                        
                        # Start heartbeat for this connection
                        threading.Thread(target=self.connection_heartbeat, 
                                        args=(neighbor_id,), 
                                        daemon=True).start()
                        
                        break  # Connection successful
                    else:
                        neighbor_socket.close()
                        logger.warning(f"No response from {neighbor_id}, will retry")
                        
                except Exception as e:
                    logger.warning(f"Failed to connect to {neighbor_id}: {e}, will retry in {backoff_time}s")
                    # Exponential backoff
                    time.sleep(backoff_time)
                    backoff_time = min(backoff_time * 2, 30)  # Cap at 30 seconds
                    retries += 1
            
            if retries >= max_retries:
                logger.error(f"Failed to establish connection with {neighbor_id} after {max_retries} attempts")
                with self.connection_lock:
                    if neighbor_id in self.neighbor_connections:
                        self.neighbor_connections[neighbor_id]['status'] = 'failed'
        
        # Start connection attempt in a separate thread
        threading.Thread(target=connection_handler, daemon=True).start()
    
    def connection_heartbeat(self, neighbor_id):
        """Send periodic heartbeats to maintain the connection"""
        while self.running:
            try:
                # Sleep between heartbeats - much longer interval
                time.sleep(120)  # Reduced from 30s to 120s (2 minutes)
                
                with self.connection_lock:
                    if neighbor_id not in self.neighbor_connections or self.neighbor_connections[neighbor_id]['status'] != 'connected':
                        break
                    
                    # Get connection info
                    conn_info = self.neighbor_connections[neighbor_id]
                    socket_obj = conn_info['socket']
                
                # Prepare heartbeat message
                heartbeat = {
                    "type": "heartbeat",
                    "source": self.router_id,
                    "destination": neighbor_id,
                    "timestamp": time.time()
                }
                
                # Send heartbeat
                socket_obj.send(json.dumps(heartbeat).encode('utf-8'))
                logger.debug(f"Sent heartbeat to {neighbor_id}")
                
                # Wait for response, but don't block for too long
                socket_obj.settimeout(5)
                try:
                    response = socket_obj.recv(4096)
                    
                    if response:
                        # Update last activity timestamp
                        with self.connection_lock:
                            if neighbor_id in self.neighbor_connections:
                                self.neighbor_connections[neighbor_id]['last_activity'] = time.time()
                                logger.debug(f"Received heartbeat response from {neighbor_id}")
                    else:
                        logger.warning(f"Empty heartbeat response from {neighbor_id}")
                except socket.timeout:
                    logger.warning(f"Heartbeat timeout from {neighbor_id}, but keeping connection")
                    # Don't close the connection immediately on timeout
                    continue
                
            except Exception as e:
                logger.warning(f"Error in heartbeat with {neighbor_id}: {e}")
                # Close connection and try to reestablish only if it's a serious error
                if isinstance(e, (ConnectionResetError, ConnectionRefusedError, ConnectionAbortedError)):
                    with self.connection_lock:
                        if neighbor_id in self.neighbor_connections:
                            try:
                                self.neighbor_connections[neighbor_id]['socket'].close()
                            except:
                                pass
                            self.neighbor_connections[neighbor_id]['status'] = 'disconnected'
                    
                    # Try to reconnect
                    self.establish_neighbor_connection(neighbor_id)
                break
    
    def update_neighbor_connections(self):
        """Update connections based on current routing table"""
        neighbors = self.get_neighbors()
        logger.info(f"Updating neighbor connections. Current neighbors: {neighbors}")
        
        # Close connections to routers that are no longer neighbors
        with self.connection_lock:
            for neighbor_id in list(self.neighbor_connections.keys()):
                if neighbor_id not in neighbors:
                    logger.info(f"Closing connection to {neighbor_id} as it's no longer a neighbor")
                    try:
                        self.neighbor_connections[neighbor_id]['socket'].close()
                    except:
                        pass
                    del self.neighbor_connections[neighbor_id]
        
        # Establish connections to new neighbors
        for neighbor_id in neighbors:
            with self.connection_lock:
                if neighbor_id not in self.neighbor_connections or self.neighbor_connections[neighbor_id]['status'] != 'connected':
                    # Start a new connection
                    self.establish_neighbor_connection(neighbor_id)
    
    def start_tcp_server(self):
        """Start TCP server to listen for incoming packets"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('0.0.0.0', self.listen_port))
        server_socket.listen(10)  # Increased backlog for more connections
        
        logger.info(f"Router {self.router_id} listening on port {self.listen_port}")
        
        while self.running:
            try:
                # Accept incoming connection
                client_socket, addr = server_socket.accept()
                logger.info(f"Accepted connection from {addr}")
                
                # Handle the connection in a new thread
                threading.Thread(target=self.handle_connection, 
                                args=(client_socket, addr)).start()
            except Exception as e:
                logger.error(f"Error accepting connection: {e}")
                if not self.running:
                    break
    
    def handle_connection(self, client_socket, addr):
        """Handle an incoming connection - could be a packet or a connection request"""
        try:
            # Receive data
            data = client_socket.recv(4096)
            if not data:
                client_socket.close()
                return
                
            # Parse packet
            packet = json.loads(data.decode('utf-8'))
            logger.info(f"Received data: {packet}")
            
            # Check packet type
            packet_type = packet.get('type', 'data')
            
            if packet_type == 'hello':
                # This is a connection request from another router
                source_router = packet.get('source')
                if source_router:
                    # Check if this is a self-connection and reject it
                    if source_router == self.router_id:
                        logger.warning(f"Rejecting self-connection request from {source_router}")
                        response = {
                            "type": "hello_ack",
                            "source": self.router_id,
                            "destination": source_router,
                            "status": "rejected",
                            "reason": "self-connection"
                        }
                        client_socket.send(json.dumps(response).encode('utf-8'))
                        client_socket.close()
                        return
                    
                    logger.info(f"Received connection request from {source_router}")
                    
                    # Send acknowledgment
                    response = {
                        "type": "hello_ack",
                        "source": self.router_id,
                        "destination": source_router,
                        "status": "accepted"
                    }
                    client_socket.send(json.dumps(response).encode('utf-8'))
                    
                    # Store connection
                    with self.connection_lock:
                        self.neighbor_connections[source_router] = {
                            'socket': client_socket,
                            'ip': addr[0],
                            'status': 'connected',
                            'last_activity': time.time()
                        }
                    
                    # Start heartbeat monitoring in a separate thread
                    threading.Thread(target=self.monitor_connection, 
                                    args=(source_router, client_socket), 
                                    daemon=True).start()
                    
                    return  # Keep connection open
            
            elif packet_type == 'heartbeat':
                # Respond to heartbeat
                source_router = packet.get('source')
                if source_router:
                    response = {
                        "type": "heartbeat_ack",
                        "source": self.router_id,
                        "destination": source_router,
                        "timestamp": time.time()
                    }
                    client_socket.send(json.dumps(response).encode('utf-8'))
                    return  # Keep connection open
            
            # If not a connection request or heartbeat, treat as a data packet
            self.handle_packet(client_socket, packet)
            
        except Exception as e:
            logger.error(f"Error handling connection: {e}")
            try:
                client_socket.close()
            except:
                pass
    
    def monitor_connection(self, router_id, client_socket):
        """Monitor an established connection from another router"""
        last_activity = time.time()
        
        while self.running:
            try:
                # Check if we should close this connection
                with self.connection_lock:
                    if router_id not in self.neighbor_connections or self.neighbor_connections[router_id]['status'] != 'connected':
                        break
                
                # Set timeout for receiving data
                client_socket.settimeout(5)
                
                # Try to receive data
                data = client_socket.recv(4096)
                if not data:
                    logger.warning(f"Connection closed by {router_id}")
                    break
                
                # Process received data
                packet = json.loads(data.decode('utf-8'))
                packet_type = packet.get('type', 'data')
                
                if packet_type == 'heartbeat':
                    # Respond to heartbeat
                    response = {
                        "type": "heartbeat_ack",
                        "source": self.router_id,
                        "destination": router_id,
                        "timestamp": time.time()
                    }
                    client_socket.send(json.dumps(response).encode('utf-8'))
                    
                    # Update last activity
                    with self.connection_lock:
                        if router_id in self.neighbor_connections:
                            self.neighbor_connections[router_id]['last_activity'] = time.time()
                
                elif packet_type == 'data':
                    # Handle data packet
                    threading.Thread(target=self.handle_packet, 
                                    args=(client_socket, packet)).start()
                
                # Update last activity time
                last_activity = time.time()
                
            except socket.timeout:
                # Connection is idle but still open
                continue
                
            except Exception as e:
                logger.error(f"Error monitoring connection to {router_id}: {e}")
                break
                
            # Check for inactivity timeout (5 minutes)
            if (time.time() - last_activity) > 300:
                logger.warning(f"Connection to {router_id} timed out due to inactivity")
                break
                
            time.sleep(1)  # Sleep to avoid busy waiting
        
        # Clean up connection
        try:
            client_socket.close()
        except:
            pass
            
        with self.connection_lock:
            if router_id in self.neighbor_connections:
                self.neighbor_connections[router_id]['status'] = 'disconnected'
                logger.info(f"Closed connection to {router_id}")
    
    def handle_packet(self, client_socket, packet):
        """Handle a data packet"""
        try:
            # Get packet info
            destination = packet.get('destination')
            
            # Check if this router is the destination
            if destination == self.router_id:
                logger.info(f"Packet reached destination: {self.router_id}")
                # Process packet locally
                payload = packet.get('payload', {})
                
                # Handle based on packet type
                if isinstance(payload, dict) and payload.get('type') == 'ping':
                    response = {
                        "status": "delivered", 
                        "router": self.router_id,
                        "timestamp": time.time(),
                        "message": f"Ping received by {self.router_id}"
                    }
                else:
                    response = {
                        "status": "delivered", 
                        "router": self.router_id,
                        "timestamp": time.time()
                    }
                    
                client_socket.send(json.dumps(response).encode('utf-8'))
            else:
                # Forward packet
                logger.info(f"Forwarding packet to {destination}")
                next_hop = self.get_next_hop(destination)
                if next_hop:
                    forward_result = self.forward_packet(packet, next_hop)
                    response = {
                        "status": "forwarded", 
                        "next_hop": next_hop, 
                        "result": forward_result,
                        "router": self.router_id
                    }
                else:
                    response = {
                        "status": "error", 
                        "message": f"No route to destination {destination}",
                        "router": self.router_id
                    }
                
                client_socket.send(json.dumps(response).encode('utf-8'))
                
        except Exception as e:
            logger.error(f"Error handling packet: {e}")
            try:
                error_response = {
                    "status": "error",
                    "message": str(e),
                    "router": self.router_id
                }
                client_socket.send(json.dumps(error_response).encode('utf-8'))
            except:
                pass
    
    def get_next_hop(self, destination):
        """Determine next hop for a destination using routing table"""
        for route in self.routing_table.get('routes', []):
            if route.get('destination') == destination:
                return route.get('next_hop')
        return None
    
    def forward_packet(self, packet, next_hop):
        """Forward packet to next hop using existing connection if available"""
        # Check if we have an active connection to this neighbor
        with self.connection_lock:
            if next_hop in self.neighbor_connections and self.neighbor_connections[next_hop]['status'] == 'connected':
                try:
                    # Use existing connection
                    neighbor_socket = self.neighbor_connections[next_hop]['socket']
                    
                    # Track hop in route if not already present
                    if 'route' not in packet:
                        packet['route'] = []
                    if self.router_id not in packet['route']:
                        packet['route'].append(self.router_id)
                    
                    # Set packet type to data for proper handling
                    packet['type'] = 'data'
                    
                    # Send packet
                    neighbor_socket.send(json.dumps(packet).encode('utf-8'))
                    
                    # Wait for acknowledgment with timeout
                    neighbor_socket.settimeout(5)
                    response = neighbor_socket.recv(4096)
                    
                    if response:
                        response_data = json.loads(response.decode('utf-8'))
                        logger.info(f"Forward response: {response_data}")
                        return True
                    return False
                    
                except Exception as e:
                    logger.error(f"Error using existing connection to {next_hop}: {e}")
                    # Connection might be broken, mark it as disconnected
                    self.neighbor_connections[next_hop]['status'] = 'disconnected'
                    try:
                        self.neighbor_connections[next_hop]['socket'].close()
                    except:
                        pass
                    
                    # Try to establish a new connection in the background
                    self.establish_neighbor_connection(next_hop)
        
        # Fall back to a new connection if needed
        interface = self.routing_table.get('interfaces', {}).get(next_hop, {})
        ip_address = interface.get('ip_address')
        
        if not ip_address:
            logger.error(f"No IP address found for {next_hop}")
            return False
        
        # Connect to next hop
        forward_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            logger.info(f"Forwarding to {next_hop} at {ip_address}:{self.listen_port} (new connection)")
            forward_socket.connect((ip_address, self.listen_port))
            
            # Track hop in route if not already present
            if 'route' not in packet:
                packet['route'] = []
            if self.router_id not in packet['route']:
                packet['route'].append(self.router_id)
            
            # Set packet type to data
            packet['type'] = 'data'
            
            # Send packet
            forward_socket.send(json.dumps(packet).encode('utf-8'))
            
            # Wait for acknowledgment
            response = forward_socket.recv(4096)
            if response:
                response_data = json.loads(response.decode('utf-8'))
                logger.info(f"Forward response: {response_data}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error forwarding to {next_hop}: {e}")
            return False
        finally:
            forward_socket.close()
    
    def print_neighbor_status(self):
        """Periodically print the status of all neighbor connections"""
        while self.running:
            try:
                with self.connection_lock:
                    if self.neighbor_connections:
                        connected = []
                        disconnected = []
                        
                        for neighbor_id, conn_info in self.neighbor_connections.items():
                            if conn_info['status'] == 'connected':
                                connected.append(neighbor_id)
                            else:
                                disconnected.append(neighbor_id)
                        
                        logger.info(f"===== ROUTER {self.router_id} CONNECTION STATUS =====")
                        logger.info(f"Connected neighbors ({len(connected)}): {', '.join(connected) if connected else 'None'}")
                        if disconnected:
                            logger.info(f"Disconnected neighbors ({len(disconnected)}): {', '.join(disconnected)}")
                    else:
                        logger.info(f"Router {self.router_id} has no neighbor connections")
            
            except Exception as e:
                logger.error(f"Error printing neighbor status: {e}")
            
            # Sleep for a while before the next status update
            time.sleep(60)  # Print status every 60 seconds
    
    def generate_random_metrics(self):
        """Generate random metrics for links to neighbors"""
        metrics = {}
        neighbors = self.get_neighbors()
        
        for neighbor in neighbors:
            # Generate random metric between 1 and 10
            metrics[neighbor] = random.randint(1, 1000)
        
        return metrics

    def report_metrics_to_sdn(self):
        """Periodically report metrics to the SDN controller"""
        while self.running:
            try:
                # Wait for a random interval (30-60 seconds)
                time.sleep(30 + 30 * random.random())
                
                # Generate random metrics
                metrics = self.generate_random_metrics()
                logger.info(f"Generated metrics: {metrics}")
                
                # Send to SDN controller
                sdn_url = "http://sdn_controller:8000/sdn_controller/update_link_metrics/" + self.router_id
                
                # Create a socket connection to the SDN controller
                # try:
                    # Use requests library if availableX
                response = requests.post(sdn_url, json=metrics, timeout=5)
                if response.status_code == 200:
                    logger.info(f"Successfully reported metrics to SDN controller")
                else:
                    logger.error(f"Failed to report metrics: {response.status_code} - {response.text}")
                # except ImportError:
                #     # Fallback to using socket directly
                #     sdn_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                #     sdn_socket.connect(("sdn_controller", 8000))
                    
                #     # Create HTTP POST request
                #     metrics_json = json.dumps(metrics)
                #     http_request = (
                #         f"POST /sdn_controller/update_link_metrics/{self.router_id} HTTP/1.1\r\n"
                #         f"Host: sdn_controller:8000\r\n"
                #         f"Content-Type: application/json\r\n"
                #         f"Content-Length: {len(metrics_json)}\r\n"
                #         f"\r\n"
                #         f"{metrics_json}"
                #     )
                #     sdn_socket.send(http_request.encode('utf-8'))
                    
                    # Get response
                    # response = sdn_socket.recv(4096).decode('utf-8')
                    # logger.info(f"SDN response: {response}")
                    # sdn_socket.close()
                    
            except Exception as e:
                logger.error(f"Error reporting metrics to SDN: {e}")
    
    def run(self):
        """Run the router agent"""
        logger.info(f"Starting router agent for {self.router_id}")
        
        # Start periodic routing table refresh
        self.start_periodic_table_refresh()
        
        # Clean up any self-connections
        # self.cleanup_self_connections()
        
        # Establish initial connections to neighbors
        self.update_neighbor_connections()
        
        # Start TCP server
        server_thread = threading.Thread(target=self.start_tcp_server, daemon=True)
        server_thread.start()
        
        # Start periodic connection status reporting
        status_thread = threading.Thread(target=self.print_neighbor_status, daemon=True)
        status_thread.start()
        
        # Start periodic metrics reporting to SDN controller
        metrics_thread = threading.Thread(target=self.report_metrics_to_sdn, daemon=True)
        metrics_thread.start()
        
        try:
            # Keep the main thread alive
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down router agent")
            self.running = False
            
            # Close all connections
            with self.connection_lock:
                for neighbor_id, conn_info in self.neighbor_connections.items():
                    try:
                        if 'socket' in conn_info:
                            conn_info['socket'].close()
                    except:
                        pass

if __name__ == "__main__":
    # Debug prints
    print("Environment variables:")
    print(f"ROUTER_ID: {os.environ.get('ROUTER_ID')}")
    print(f"PORT: {os.environ.get('PORT')}")
    
    # Try to get router ID from environment variables
    router_id = os.environ.get('ROUTER_ID')
    port = int(os.environ.get('PORT'))
    table_path = f"/shared/{router_id}_table.json"
    
    # Wait for the routing table to be created
    retries = 0
    max_retries = 30  # Wait up to 30 seconds
    while not os.path.exists(table_path) and retries < max_retries:
        logger.info(f"Waiting for routing table at {table_path}...")
        time.sleep(1)
        retries += 1
    
    if not os.path.exists(table_path):
        logger.warning(f"Routing table not found at {table_path} after {max_retries} seconds. Will continue and rely on periodic refresh.")
    
    # Start router agent
    logger.info(f"Initializing router agent with ID={router_id}, port={port}, table_path={table_path}")
    agent = RouterAgent(router_id, table_path, port)
    agent.run()