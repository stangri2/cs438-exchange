"""
End-to-end flow test for the exchange server.

Requires:
  • pytest  (pip install pytest)
  • Python ≥ 3.7
"""
import os
import socket
import struct
import subprocess
import time
import signal
import pytest

# ------------------------------------------------------------------ #
#  helpers to craft / parse packets                                   #
# ------------------------------------------------------------------ #
def pkt_new(client, oid, side, price, qty):
    """Return raw bytes for NEW message (26 B)."""
    return struct.pack("<B I Q B q I",
                       0,            # msg type NEW
                       client,
                       oid,
                       side,         # 0 = BID, 1 = ASK
                       price,
                       qty)

def read_exact(sock, n):
    data = b''
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("socket closed")
        data += chunk
    return data

def decode_ack(buf):
    typ = buf[0:1]
    oid = struct.unpack("<Q", buf[1:9])[0]
    return typ, oid

def decode_trade(buf):
    _, maker, taker, price, qty = struct.unpack("<B Q Q q I", buf)
    return maker, taker, price, qty

# ------------------------------------------------------------------ #
#  pytest fixture to start / stop the server                          #
# ------------------------------------------------------------------ #
PORT = 9101
EXECUTABLE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../build/src/exchange")
)

@pytest.fixture(scope="module")
def server():
    proc = subprocess.Popen([EXECUTABLE, str(PORT)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            preexec_fn=os.setsid)          # group for SIGTERM
    time.sleep(0.3)  # give it time to bind
    yield
    os.killpg(proc.pid, signal.SIGTERM)
    proc.wait(timeout=5)

# ------------------------------------------------------------------ #
#  actual test case                                                   #
# ------------------------------------------------------------------ #
def test_crossing_flow(server):
    s = socket.create_connection(("127.0.0.1", PORT))

    # 1. post resting ASK (id 100)
    s.sendall(pkt_new(7, 100, 1, 105, 5))     # side 1 = ASK
    ack = read_exact(s, 9)
    typ, oid = decode_ack(ack)
    assert typ == b'A' and oid == 100

    # 2. aggressive BID that crosses (id 200)
    s.sendall(pkt_new(8, 200, 0, 110, 5))     # side 0 = BID
    # We expect ACK (9 B) + TRADE (1+8+8+8+4 = 29 B)
    ack2  = read_exact(s, 9)
    trade = read_exact(s, 29)

    typ2, oid2 = decode_ack(ack2)
    assert typ2 == b'A' and oid2 == 200

    maker, taker, price, qty = decode_trade(trade)
    assert maker == 100
    assert taker == 200
    assert price == 105
    assert qty   == 5

    s.close()

