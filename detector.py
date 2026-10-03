"""Detector for plc_sim.py. Standard library only.

Reads events.log and raises alerts for:
  1. Any WRITE command (in real plants, writes from unexpected sources are rare)
  2. Reads outside the known registers 0-2 (looks like someone scanning)
  3. Unsupported function codes (looks like probing)
  4. Request bursts: more than 5 requests from one source within one second

  py detector.py             check the whole log once
  py detector.py --follow    keep watching the log live (Ctrl+C to stop)
"""
import argparse
import re
import time
from collections import defaultdict, deque
from datetime import datetime

LOG_FILE = "events.log"
ALERT_FILE = "alerts.log"
KNOWN_REGISTERS = range(0, 3)
BURST_LIMIT, BURST_SECONDS = 5, 1.0

LINE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d+) src=(\S+) (.*)$")
READ = re.compile(r"fc=3 read addr=(\d+) qty=(\d+)")
WRITE = re.compile(r"fc=6 WRITE addr=(\d+) value=(\d+)")
UNSUPPORTED = re.compile(r"unsupported fc=(\d+)")

recent = defaultdict(deque)  # source -> timestamps of its recent requests


def alert(when, severity, message):
    text = f"[{severity}] {when}  {message}"
    print(text)
    with open(ALERT_FILE, "a") as f:
        f.write(text + "\n")


def check(line):
    m = LINE.match(line.strip())
    if not m:
        return
    when, src, rest = m.groups()
    ts = datetime.strptime(when, "%Y-%m-%d %H:%M:%S,%f").timestamp()

    w = WRITE.search(rest)
    if w:
        addr, value = int(w.group(1)), int(w.group(2))
        severity = "HIGH" if addr == 1 else "MEDIUM"  # register 1 is the pump
        alert(when, severity, f"Write from {src}: register {addr} set to {value}")

    r = READ.search(rest)
    if r:
        addr, qty = int(r.group(1)), int(r.group(2))
        if any(a not in KNOWN_REGISTERS for a in range(addr, addr + qty)):
            alert(when, "MEDIUM", f"Read outside known registers from {src}: addr={addr} qty={qty}")

    u = UNSUPPORTED.search(rest)
    if u:
        alert(when, "MEDIUM", f"Unsupported function code {u.group(1)} from {src}")

    q = recent[src]
    q.append(ts)
    while q and ts - q[0] > BURST_SECONDS:
        q.popleft()
    if len(q) > BURST_LIMIT:
        alert(when, "LOW", f"Request burst from {src}: {len(q)} requests in {BURST_SECONDS:.0f}s")
        q.clear()  # avoid repeating the same alert for every extra request


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--follow", action="store_true", help="keep watching the log")
    args = parser.parse_args()
    with open(LOG_FILE) as f:
        for line in f:
            check(line)
        if args.follow:
            print("Watching for new events... (Ctrl+C to stop)")
            while True:
                line = f.readline()
                if line:
                    check(line)
                else:
                    time.sleep(0.5)
