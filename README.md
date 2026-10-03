# OT Modbus Lab: Simulated Water-Tank PLC with Attack Detection

A small, self-contained lab that shows why unauthenticated industrial protocols are risky and how a simple monitor can catch misuse. It simulates a water-tank controller speaking Modbus/TCP, an operator screen, and a detector that reads the controller's request log and raises alerts.

Everything runs on `localhost` using only the Python standard library. No real equipment is involved and nothing is exposed to a network.

## Why this project

Modbus is widely used in industrial control systems. By design it has no authentication, no encryption, and no integrity checks, so any host that can reach a device can read or change its values. This lab reproduces that weakness safely and demonstrates a defensive response: logging every request and alerting on suspicious ones.

## Architecture

```
 hmi_poll.py  --Modbus/TCP-->  plc_sim.py  --writes-->  events.log  --read by-->  detector.py  -->  alerts.log
 (operator screen)             (simulated PLC)          (request log)              (monitor)
```

| File | Role |
|------|------|
| `plc_sim.py` | Simulated water-tank PLC on `127.0.0.1:5020`. Supports Modbus function codes 0x03 (read holding registers) and 0x06 (write single register). Logs every request. |
| `hmi_poll.py` | Simple operator screen. Polls the tank once a second, or writes a register with `--write ADDR VALUE`. |
| `detector.py` | Reads `events.log` and writes alerts to `alerts.log`. Can run once or watch live with `--follow`. |

### Registers

| Address | Meaning |
|---------|---------|
| 0 | Tank level (0-100) |
| 1 | Pump command (0 = off, 1 = on) |
| 2 | High-level alarm (set by the PLC at level >= 90) |

## Running it

Requires Python 3.10+ (developed and tested on Windows with Python 3.14). No packages to install.

1. Start the simulated PLC (leave this window open):
   ```
   py plc_sim.py
   ```
2. In a second window, start the operator screen:
   ```
   py hmi_poll.py
   ```
3. In a third window, send an unauthorized-style command that turns the pump off:
   ```
   py hmi_poll.py --write 1 0
   ```
4. Run the detector over the log, or watch live:
   ```
   py detector.py
   py detector.py --follow
   ```

## Detection rules

| Rule | Severity | Why it matters |
|------|----------|----------------|
| Write to the pump register (1) | HIGH | Directly changes physical process behavior |
| Write to any other register | MEDIUM | Writes are rare in normal monitoring traffic |
| Read outside known registers | MEDIUM | Resembles scanning or probing |
| Unsupported function code | MEDIUM | Resembles probing for device capabilities |
| More than 5 requests in one second from one source | LOW | Resembles scanning or flooding |

## Example result

After turning the pump off with `--write 1 0`, the detector reports:

```
[HIGH] 2026-10-03 15:50:57,569  Write from 127.0.0.1: register 1 set to 0
```

The controller accepted the command without asking who sent it. That is the core weakness this lab demonstrates.

## ATT&CK for ICS mapping

The behavior in this lab lines up with MITRE ATT&CK for ICS techniques such as *Unauthorized Command Message* (T0855) and *Manipulation of Control* (T0831). Verify current technique IDs at https://attack.mitre.org/matrices/ics/.

## Limitations

- The detector runs after the fact on a log file. It is a teaching tool, not a production monitor.
- Source IPs are all `127.0.0.1` in this lab, so rules cannot yet distinguish an authorized engineering workstation from an intruder. A real deployment would use an allowlist of approved sources.
- Thresholds are simple fixed values chosen for the demo.

## Next steps

- Add a source allowlist and flag writes from unknown hosts
- Add an attack script that forces the pump on to overflow the tank, and measure time-to-detection
- Capture the traffic with Wireshark and compare packets to the log
- Port detection rules to Suricata or Zeek

## Safety note

This project is for learning and defensive research. The simulator binds only to localhost. Do not point these tools at systems you do not own or have permission to test.
