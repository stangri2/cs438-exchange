"""
End-to-end flow tests for the exchange server.

Requires:
  pip install pytest
"""
import os, socket, struct, subprocess, time, signal, pytest

# ───────── helpers ──────────────────────────────────────────────────
def pkt_new(cli, oid, side, px, qty):
    return struct.pack("<B I Q B q I", 0, cli, oid, side, px, qty)

def pkt_modify(oid, new_qty):
    dummy = 0
    return struct.pack("<B I Q I", 1, dummy, oid, new_qty)

def pkt_cancel(oid):
    dummy = 0
    return struct.pack("<B I Q", 2, dummy, oid)

def read_exact(sock, n):
    buf = b''
    while len(buf) < n:
        chunk = sock.recv(n-len(buf))
        if not chunk: raise ConnectionError("closed")
        buf += chunk
    return buf

def ack_id(buf):                # 9-byte ack/confirm
    return buf[0:1], struct.unpack("<Q", buf[1:9])[0]

def decode_trade(buf):
    _, maker, taker, price, qty = struct.unpack("<B Q Q q I", buf)
    return maker, taker, price, qty

# ───────── fixture: start / stop server ─────────────────────────────
PORT = 9101
EXE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../build/src/exchange")
)

@pytest.fixture                # <─ remove scope="module"
def server():
    proc = subprocess.Popen([EXE, str(PORT)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            preexec_fn=os.setsid)
    time.sleep(0.3)            # give it time to listen
    yield                      # run the test
    os.killpg(proc.pid, signal.SIGTERM)
    proc.wait(timeout=5)

# ───────── test cases ───────────────────────────────────────────────
def test_crossing_flow(server):
    s = socket.create_connection(("127.0.0.1", PORT))
    s.sendall(pkt_new(7, 100, 1, 105, 5))
    assert ack_id(read_exact(s, 9)) == (b'A', 100)

    s.sendall(pkt_new(8, 200, 0, 110, 5))
    assert ack_id(read_exact(s, 9)) == (b'A', 200)

    maker, taker, price, qty = decode_trade(read_exact(s, 29))
    assert (maker, taker, price, qty) == (100, 200, 105, 5)
    s.close()

def test_partial_fill(server):
    s = socket.create_connection(("127.0.0.1", PORT))
    s.sendall(pkt_new(1, 300, 1, 120, 2))      # small ask
    read_exact(s, 9)

    s.sendall(pkt_new(2, 301, 0, 130, 5))      # bid bigger qty
    read_exact(s, 9)                            # ack bid
    tr = decode_trade(read_exact(s, 29))
    assert tr[3] == 2                           # qty == 2
    s.close()

def test_fifo_same_price(server):
    s = socket.create_connection(("127.0.0.1", PORT))
    # two asks at same px
    s.sendall(pkt_new(3, 400, 1, 140, 3)); read_exact(s, 9)
    s.sendall(pkt_new(4, 401, 1, 140, 4)); read_exact(s, 9)

    # one big crossing bid
    s.sendall(pkt_new(5, 402, 0, 150, 6)); read_exact(s, 9)
    t1 = decode_trade(read_exact(s, 29))
    t2 = decode_trade(read_exact(s, 29))
    assert t1[0] == 400 and t2[0] == 401        # maker order ids FIFO
    assert t1[3] == 3 and t2[3] == 3            # 3 from first, 3 from second
    s.close()

def test_cancel_then_cross(server):
    s = socket.create_connection(("127.0.0.1", PORT))
    s.sendall(pkt_new(6, 500, 1, 160, 2)); read_exact(s, 9)

    # cancel it
    s.sendall(pkt_cancel(500))
    typ, _ = ack_id(read_exact(s, 9))
    assert typ == b'C'

    # crossing bid should NOT trade
    s.sendall(pkt_new(7, 501, 0, 170, 2)); read_exact(s, 9)
    s.settimeout(0.2)
    with pytest.raises(socket.timeout):
        s.recv(1)           # no trade expected
    s.close()

def test_modify_qty_down(server):
    s = socket.create_connection(("127.0.0.1", PORT))
    s.sendall(pkt_new(8, 600, 1, 180, 10)); read_exact(s, 9)

    # shrink qty to 4
    s.sendall(pkt_modify(600, 4))
    typ, _ = ack_id(read_exact(s, 9))
    assert typ == b'M'

    s.sendall(pkt_new(9, 601, 0, 200, 10)); read_exact(s, 9)
    maker, _, _, qty = decode_trade(read_exact(s, 29))
    assert maker == 600 and qty == 4             # only 4 filled
    s.close()

