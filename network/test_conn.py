import socket
import sys

def test_connection(host, port=8000):
    print(f"Testing connection to {host}:{port}...")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect((host, port))
        print(f"SUCCESS: Connected to {host}:{port}")
        s.close()
        return True
    except Exception as e:
        print(f"FAILED: Could not connect to {host}:{port}")
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    host = "localhost"
    if len(sys.argv) > 1:
        host = sys.argv[1]
    port = 8001
    if len(sys.argv) > 2:
        port = int(sys.argv[2])    
    test_connection(host, port)