"""
pen_host.py  —  runs on the Mac host (NOT in Docker)
Connects to the LAMY Safari NWP-F80 pen via BLE and writes stroke
events to /tmp/inktutor/strokes.jsonl so the container can read them.

Install deps on host:
    pip install bleak

Run:
    python pen_host.py
"""

import asyncio
import json
import struct
import time
from pathlib import Path

from bleak import BleakClient, BleakScanner

# LAMY Safari NWP-F80 BLE UUIDs (discovered via discover_pen.py)
PEN_DATA_SERVICE = "4f99f138-9d53-5bfa-9e50-b147491afe68"
PEN_DATA_CHAR = "64cd86b1-2256-5aeb-9f04-2caf6c60ae57"  # notify/indicate — pen → host
PEN_CONTROL_CHAR = "8bc8cc7d-88ca-56b0-af9a-9bf514d0d61a"  # write — host → pen
PEN_PASSWORD = "9999"
STROKE_FILE = Path("/tmp/inktutor/strokes.jsonl")

# ── Neo V2 protocol constants ────────────────────────────────────────────────

PK_STX = 0xC0  # start of packet
PK_ETX = 0xC1  # end of packet
PK_DLE = 0x7D  # escape prefix

# Commands (host → pen)
CMD_VERSION_REQUEST = 0x01
CMD_PASSWORD_REQUEST = 0x02
CMD_SETTING_INFO_REQUEST = 0x04
CMD_ONLINE_DATA_REQUEST = 0x11

# Responses / events (pen → host)
RSP_VERSION = 0x81
RSP_PASSWORD = 0x82
RSP_SETTING_INFO = 0x84
RSP_ONLINE_DATA = 0x91  # response to CMD_ONLINE_DATA_REQUEST (0x11)
EVT_PEN_UPDOWN = 0x63
EVT_DOT = 0x65  # older dot format
EVT_NEW_PAPER = 0x6B
EVT_NEW_DOT = 0x6C  # current dot format


# ── Packet helpers ───────────────────────────────────────────────────────────

def _escape(data: bytes) -> bytes:
    out = bytearray()
    for b in data:
        if b in (PK_STX, PK_ETX, PK_DLE):
            out.append(PK_DLE)
            out.append(b ^ 0x20)
        else:
            out.append(b)
    return bytes(out)


def _unescape(data: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(data):
        if data[i] == PK_DLE and i + 1 < len(data):
            out.append(data[i + 1] ^ 0x20)
            i += 2
        else:
            out.append(data[i])
            i += 1
    return bytes(out)


def _build(cmd: int, payload: bytes = b"") -> bytes:
    header = bytes([cmd]) + struct.pack("<H", len(payload)) + payload
    return bytes([PK_STX]) + _escape(header) + bytes([PK_ETX])


def _version_request() -> bytes:
    app_ver = b"InkTutor\x00\x00\x00\x00\x00\x00\x00\x00"  # 16 bytes
    proto_ver = b"2.12\x00\x00\x00\x00"  # 8 bytes
    payload = (b"\x00" * 16) + bytes([0x12, 0x01]) + app_ver + proto_ver
    return _build(CMD_VERSION_REQUEST, payload)


def _password_request(pwd: str = PEN_PASSWORD) -> bytes:
    """Send password as uint32 little-endian integer (e.g. '9999' → 0f 27 00 00 ...)."""
    try:
        payload = struct.pack("<I", int(pwd)).ljust(16, b"\x00")
    except ValueError:
        payload = pwd.encode().ljust(16, b"\x00")[:16]
    print(f"  sending password as integer bytes: {payload.hex()}")
    return _build(CMD_PASSWORD_REQUEST, payload)


def _password_request_ascii(pwd: str) -> bytes:
    """Send password as ASCII/UTF-8 string (e.g. '9999' → 39 39 39 39 ...)."""
    payload = pwd.encode("utf-8").ljust(16, b"\x00")[:16]
    print(f"  sending password as ASCII bytes:   {payload.hex()}")
    return _build(CMD_PASSWORD_REQUEST, payload)


# ── Protocol state machine ───────────────────────────────────────────────────

class PenProtocol:
    def __init__(self, password: str = PEN_PASSWORD):
        self._buf = bytearray()
        self._writes: asyncio.Queue = asyncio.Queue()
        self._client = None
        self._password = password
        self._tried_ascii = False

    def attach(self, client: BleakClient):
        self._client = client

    # Called by bleak on every BLE notification
    def on_notify(self, _, data: bytearray):
        self._buf.extend(data)
        self._drain_buffer()

    def _drain_buffer(self):
        while True:
            start = self._buf.find(PK_STX)
            if start == -1:
                self._buf.clear()
                return
            if start > 0:
                self._buf = self._buf[start:]
            end = self._buf.find(PK_ETX, 1)
            if end == -1:
                return  # incomplete packet — wait for more data
            raw = _unescape(bytes(self._buf[1:end]))
            self._buf = self._buf[end + 1:]
            if len(raw) >= 3:
                self._dispatch(raw)

    def _dispatch(self, data: bytes):
        cmd = data[0]
        length = struct.unpack_from("<H", data, 1)[0]
        payload = data[3:3 + length]

        if cmd == RSP_VERSION:
            print("Handshake OK — requesting pen settings...")
            self._writes.put_nowait(_build(CMD_SETTING_INFO_REQUEST))

        elif cmd == RSP_SETTING_INFO:
            print(f"  settings payload hex: {payload.hex()}")
            # Byte layout: [0-3] header, [4-11] 64-bit timestamp, [12-15] settings,
            # [16] lockEnabled, [17] passwordRetries, ...
            locked = len(payload) > 16 and payload[16] != 0
            if locked:
                pwd = self._password or PEN_PASSWORD
                print(f"Pen is password-locked (byte[16]=0x{payload[16]:02x}) — trying '{pwd}'...")
                self._writes.put_nowait(_password_request(pwd))
            else:
                print("Pen ready — enabling dot streaming. Start writing!")
                self._writes.put_nowait(_build(CMD_ONLINE_DATA_REQUEST))

        elif cmd == RSP_PASSWORD:
            print(f"  RSP_PASSWORD payload ({len(payload)}b): {payload.hex()}")
            # Attempt dot streaming regardless — pen will respond with error if auth failed
            print("  Attempting ONLINE_DATA_REQUEST regardless — logging all responses...")
            self._writes.put_nowait(_build(CMD_ONLINE_DATA_REQUEST))

        elif cmd == RSP_ONLINE_DATA:
            ok = not payload or payload[0] == 0
            if ok:
                print("Streaming enabled — start writing on Ncode paper!")
            else:
                print(f"  Streaming request failed (payload: {payload.hex()})")

        elif cmd in (EVT_DOT, EVT_NEW_DOT):
            self._handle_dot(payload)

        elif cmd == EVT_PEN_UPDOWN and payload:
            print("Pen", "DOWN" if payload[0] == 0 else "UP")

        else:
            print(f"  UNKNOWN cmd=0x{cmd:02x} payload({len(payload)}b): {payload.hex()}")

    def _handle_dot(self, payload: bytes):
        # ONLINE_NEW_PEN_DOT_EVENT payload:
        #   1 byte  event count
        #   1 byte  time delta
        #   2 bytes pressure  (little-endian, 0-4095)
        #   2 bytes X integer (little-endian)
        #   2 bytes Y integer (little-endian)
        #   1 byte  X fractional (0-99)
        #   1 byte  Y fractional (0-99)
        if len(payload) < 10:
            return
        offset = 1  # skip event count
        _tdelta = payload[offset];
        offset += 1
        pressure = struct.unpack_from("<H", payload, offset)[0];
        offset += 2
        xi = struct.unpack_from("<H", payload, offset)[0];
        offset += 2
        yi = struct.unpack_from("<H", payload, offset)[0];
        offset += 2
        xf = payload[offset];
        offset += 1
        yf = payload[offset]

        dot = {
            "x": xi + xf * 0.01,
            "y": yi + yf * 0.01,
            "pressure": pressure,
            "ts": time.time(),
            "type": "dot",
        }
        print(f"DOT  x={dot['x']:7.2f}  y={dot['y']:7.2f}  p={pressure}", flush=True)
        try:
            with STROKE_FILE.open("a") as f:
                f.write(json.dumps(dot) + "\n")
        except OSError as e:
            print(f"Warning: write error: {e}")

    async def write_loop(self):
        """Drains pending outgoing packets to the pen."""
        while True:
            packet = await self._writes.get()
            try:
                await self._client.write_gatt_char(PEN_CONTROL_CHAR, packet, response=True)
            except Exception as e:
                print(f"BLE write error: {e}")


# ── Main ─────────────────────────────────────────────────────────────────────

async def run(password: str = PEN_PASSWORD):
    print("Scanning for LAMY/Neo smartpen...")
    try:
        devices = await BleakScanner.discover(timeout=10.0)
    except Exception as e:
        print(f"Bluetooth scan failed: {e}")
        return

    pen = next(
        (d for d in devices if d.name and ("NEO" in d.name.upper() or "LAMY" in d.name.upper())),
        None,
    )
    if not pen:
        print("No pen found. Make sure the pen is on and Bluetooth is enabled.")
        return

    print(f"Found: {pen.name} ({pen.address})")
    STROKE_FILE.parent.mkdir(parents=True, exist_ok=True)

    proto = PenProtocol(password=password)

    async with BleakClient(pen.address) as client:
        proto.attach(client)
        await client.start_notify(PEN_DATA_CHAR, proto.on_notify)
        print("Connected — starting handshake...")
        await client.write_gatt_char(PEN_CONTROL_CHAR, _version_request(), response=True)

        write_task = asyncio.create_task(proto.write_loop())
        try:
            await asyncio.sleep(3600)  # stream for up to 1 hour
        finally:
            write_task.cancel()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--password", default=PEN_PASSWORD, help=f"Pen password (default: {PEN_PASSWORD})")
    args = parser.parse_args()
    try:
        asyncio.run(run(password=args.password))
    except KeyboardInterrupt:
        print("\nDisconnected.")
