# main.py
import socket
import json
import os
import threading
import time
import logging

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
    
    def start_periodic_table_refresh(self):
        """Start a thread to periodically refresh the routing table"""
        def refresh_routine():
            while True:
                try:
                    self.routing_table = self.load_routing_table()
                    logger.info(f"Refreshed routing table for {self.router_id}")
                except Exception as e:
                    logger.error(f"Error refreshing routing table: {e}")
                time.sleep(10)  # Refresh every 10 seconds
        
        self.refresh_thread = threading.Thread(target=refresh_routine, daemon=True)
        self.refresh_thread.start()
        logger.info("Started periodic routing table refresh")
    
    def start_tcp_server(self):
        """Start TCP server to listen for incoming packets"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('0.0.0.0', self.listen_port))
        server_socket.listen(5)
        
        logger.info(f"Router {self.router_id} listening on port {self.listen_port}")
        
        while True:
            # Accept incoming connection
            client_socket, addr = server_socket.accept()
            logger.info(f"Accepted connection from {addr}")
            
            # Handle the connection in a new thread
            threading.Thread(target=self.handle_packet, 
                            args=(client_socket, addr)).start()
    
    def handle_packet(self, client_socket, addr):
        """Handle an incoming packet"""
        try:
            # Receive data
            data = client_socket.recv(4096)
            if not data:
                return
                
            # Parse packet
            packet = json.loads(data.decode('utf-8'))
            logger.info(f"Received packet: {packet}")
            
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
        finally:
            client_socket.close()
    
    def get_next_hop(self, destination):
        """Determine next hop for a destination using routing table"""
        for route in self.routing_table.get('routes', []):
            if route.get('destination') == destination:
                return route.get('next_hop')
        return None
    
    def forward_packet(self, packet, next_hop):
        """Forward packet to next hop"""
        # Get IP and port for next hop
        interface = self.routing_table.get('interfaces', {}).get(next_hop, {})
        ip_address = interface.get('ip_address')
        
        if not ip_address:
            logger.error(f"No IP address found for {next_hop}")
            return False
        
        # Connect to next hop
        forward_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            logger.info(f"Forwarding to {next_hop} at {ip_address}:{self.listen_port}")
            forward_socket.connect((ip_address, self.listen_port))
            
            # Track hop in route if not already present
            if 'route' not in packet:
                packet['route'] = []
            if self.router_id not in packet['route']:
                packet['route'].append(self.router_id)
            
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
    
    def run(self):
        """Run the router agent"""
        logger.info(f"Starting router agent for {self.router_id}")
        # Start periodic routing table refresh
        self.start_periodic_table_refresh()
        # Start TCP server
        self.start_tcp_server()

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