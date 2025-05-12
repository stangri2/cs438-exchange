#!/usr/bin/env python3
"""
Single-threaded load driver for the exchange.

• Uses one TCP socket.
• Simulates many clients by varying the client-ID field.
• Sends a NEW every INTERVAL_MS; prices alternate so trades happen.
"""

import os, sys, socket, struct, time, random

# ────────── parameters you can tweak ───────────────────────────────
HOST        = sys.argv[1]
PORT        = int(sys.argv[2])
NUM_CLIENTS = 5
INTERVAL_MS = 250
BASE_PRICE  = 100_00          # integer cents (100.00)
SPREAD      = 15              # +/- cents around base
MAX_QTY     = 10
START_OID   = 10_000

# ────────── binary helpers (same layout as server) ─────────────────
def pkt_new(cid, oid, side, px, qty):
    return struct.pack("<B I Q B q I", 0, cid, oid, side, px, qty)

def read_exact(sock, n):
    data = b''
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("socket closed")
        data += chunk
    return data

def decode_acks(sock):
    """Drain all pending ACK/CXL/MOD/TRADE messages and print them."""
    sock.setblocking(False)
    try:
        while True:
            typ = sock.recv(1)
            if not typ:
                break
            if typ in (b'A', b'M', b'C', b'R'):
                oid = struct.unpack("<Q", read_exact(sock, 8))[0]
                print(f"{typ.decode()} id={oid}")
            elif typ == b'T':
                maker, taker, price, qty = struct.unpack(
                    "<Q Q q I", read_exact(sock, 28))
                print(f"TRADE maker={maker} taker={taker} "
                      f"px={price/100:.2f} qty={qty}")
    except BlockingIOError:
        pass
    finally:
        sock.setblocking(True)

# ────────── main loop ──────────────────────────────────────────────
def main():
    sock = socket.create_connection((HOST, PORT))
    next_oid     = START_OID
    side_toggle  = 0           # 0=BID, 1=ASK (alternate)
    client_cycle = list(range(1, NUM_CLIENTS + 1))
    price_offset = -SPREAD     # so first order rests, second crosses

    print(f"Connected to {HOST}:{PORT}. Sending orders… Ctrl-C to stop")
    try:
        while True:
            cid  = client_cycle[ next_oid % NUM_CLIENTS ]
            side = 1 if side_toggle else 0
            px   = BASE_PRICE + price_offset
            qty  = random.randint(1, MAX_QTY)

            sock.sendall(pkt_new(cid, next_oid, side, px, qty))
            print(f"SENT NEW  id={next_oid} cid={cid} "
                  f"{'ASK' if side else 'BID'} px={px/100:.2f} qty={qty}")

            next_oid    += 1
            side_toggle ^= 1
            price_offset = -price_offset    # flip sign so next order crosses

            # read whatever the server already produced
            decode_acks(sock)

            time.sleep(INTERVAL_MS / 1000)

    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        sock.close()

if __name__ == "__main__":
    main()

