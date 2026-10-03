"""Simulated water-tank PLC speaking Modbus/TCP. Standard library only.

Holding registers:
  0 = tank level (0-100)
  1 = pump command (0 = off, 1 = on)
  2 = high-level alarm (0/1, set by the PLC when level >= 90)

Supports function codes 0x03 (read holding registers) and 0x06 (write single
register). Every request is logged to events.log so a detector can use it later.
Run it, then point hmi_poll.py at it. Localhost only - this is a lab toy.
"""
import logging
import socketserver
import struct
import threading
import time

HOST, PORT = "127.0.0.1", 5020  # >1024 so no admin rights are needed on Windows

registers = {0: 50, 1: 1, 2: 0}
lock = threading.Lock()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[logging.FileHandler("events.log"), logging.StreamHandler()],
)


def process_loop():
    """Once a second: level rises if the pump is on, falls if off."""
    while True:
        time.sleep(1)
        with lock:
            level = registers[0] + (5 if registers[1] == 1 else -2)
            registers[0] = max(0, min(100, level))
            registers[2] = 1 if registers[0] >= 90 else 0


def exception(unit, tid, fc, code):
    pdu = struct.pack(">BB", fc | 0x80, code)
    return struct.pack(">HHHB", tid, 0, len(pdu) + 1, unit) + pdu


class Handler(socketserver.BaseRequestHandler):
    def recv_exact(self, n):
        data = b""
        while len(data) < n:
            chunk = self.request.recv(n - len(data))
            if not chunk:
                raise ConnectionError
            data += chunk
        return data

    def handle(self):
        ip = self.client_address[0]
        try:
            while True:
                tid, proto, length, unit = struct.unpack(">HHHB", self.recv_exact(7))
                pdu = self.recv_exact(length - 1)
                fc = pdu[0]
                if fc == 0x03 and len(pdu) == 5:
                    addr, qty = struct.unpack(">HH", pdu[1:5])
                    logging.info("src=%s fc=3 read addr=%d qty=%d", ip, addr, qty)
                    if qty < 1 or any(a not in registers for a in range(addr, addr + qty)):
                        self.request.sendall(exception(unit, tid, fc, 0x02))
                        continue
                    with lock:
                        vals = [registers[a] for a in range(addr, addr + qty)]
                    body = struct.pack(">BB", fc, qty * 2) + struct.pack(f">{qty}H", *vals)
                elif fc == 0x06 and len(pdu) == 5:
                    addr, value = struct.unpack(">HH", pdu[1:5])
                    logging.info("src=%s fc=6 WRITE addr=%d value=%d", ip, addr, value)
                    if addr not in registers:
                        self.request.sendall(exception(unit, tid, fc, 0x02))
                        continue
                    with lock:
                        registers[addr] = value
                    body = pdu  # a write response echoes the request
                else:
                    logging.info("src=%s unsupported fc=%d", ip, fc)
                    self.request.sendall(exception(unit, tid, fc, 0x01))
                    continue
                self.request.sendall(struct.pack(">HHHB", tid, 0, len(body) + 1, unit) + body)
        except (ConnectionError, struct.error):
            pass


if __name__ == "__main__":
    threading.Thread(target=process_loop, daemon=True).start()
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer((HOST, PORT), Handler) as server:
        logging.info("PLC simulator listening on %s:%d", HOST, PORT)
        server.serve_forever()
