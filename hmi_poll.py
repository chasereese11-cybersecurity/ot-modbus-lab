"""Simple HMI for plc_sim.py. Standard library only.

  python hmi_poll.py                  poll and print the tank every second
  python hmi_poll.py --write 1 0      write value 0 to register 1 (pump off)
"""
import argparse
import socket
import struct
import time

HOST, PORT = "127.0.0.1", 5020


def recv_exact(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("server closed the connection")
        data += chunk
    return data


def request(sock, pdu, tid=1, unit=1):
    sock.sendall(struct.pack(">HHHB", tid, 0, len(pdu) + 1, unit) + pdu)
    _, _, length, _ = struct.unpack(">HHHB", recv_exact(sock, 7))
    return recv_exact(sock, length - 1)


def read_registers(sock, addr, qty):
    resp = request(sock, struct.pack(">BHH", 0x03, addr, qty))
    if resp[0] & 0x80:
        raise RuntimeError(f"Modbus exception code {resp[1]}")
    return list(struct.unpack(f">{qty}H", resp[2:2 + resp[1]]))


def write_register(sock, addr, value):
    resp = request(sock, struct.pack(">BHH", 0x06, addr, value))
    if resp[0] & 0x80:
        raise RuntimeError(f"Modbus exception code {resp[1]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", nargs=2, type=int, metavar=("ADDR", "VALUE"))
    args = parser.parse_args()
    with socket.create_connection((HOST, PORT), timeout=3) as s:
        if args.write:
            write_register(s, *args.write)
            print(f"Wrote {args.write[1]} to register {args.write[0]}")
        else:
            while True:
                level, pump, alarm = read_registers(s, 0, 3)
                print(f"level={level:3d}%  pump={'ON ' if pump else 'OFF'}  alarm={'!!' if alarm else 'ok'}")
                time.sleep(1)
