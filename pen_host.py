"""
pen_host.py  —  runs on the Mac host (NOT in Docker)
Connects to the LAMY/Neo pen via Bluetooth and writes stroke
events to /tmp/inktutor/strokes.jsonl so the container can read them.

Install deps on host:
    pip install bleak

Run:
    python pen_host.py
"""

import asyncio
import json
import time
from pathlib import Path

from bleak import BleakClient, BleakScanner

# Neo smartpen BLE service/characteristic UUIDs
# These are the standard Neo protocol UUIDs
PEN_DATA_SERVICE = "19f1bf80-b251-4b3f-8b1c-5b0bbd538d3e"
PEN_DATA_CHAR = "19f1bf82-b251-4b3f-8b1c-5b0bbd538d3e"
PEN_CONTROL_CHAR = "19f1bf81-b251-4b3f-8b1c-5b0bbd538d3e"

STROKE_FILE = Path("/tmp/inktutor/strokes.jsonl")
try:
    STROKE_FILE.parent.mkdir(parents=True, exist_ok=True)
except OSError as e:
    print(f"Warning: could not create stroke directory: {e}")


def parse_dot(data: bytearray) -> dict | None:
    """Parse a raw Neo pen dot packet into a stroke event dict."""
    # Neo protocol: each dot packet contains x, y, pressure, timestamp
    # Exact byte layout from Neo SDK documentation
    if len(data) < 12:
        return None
    try:
        return {
            "x": int.from_bytes(data[0:4], "big"),
            "y": int.from_bytes(data[4:8], "big"),
            "pressure": int.from_bytes(data[8:10], "big"),
            "ts": time.time(),
            "type": "dot",
        }
    except Exception as e:
        print(f"Warning: could not parse dot packet: {e}")
        return None


async def run():
    print("Scanning for Neo smartpen...")
    try:
        devices = await BleakScanner.discover(timeout=10.0)
    except Exception as e:
        print(f"Bluetooth scan failed: {e}")
        return

    pen = next((d for d in devices if d.name and "NEO" in d.name.upper()), None)

    if not pen:
        print("No Neo pen found. Make sure it's on and nearby.")
        return

    print(f"Found pen: {pen.name} ({pen.address})")

    def on_dot(_, data: bytearray):
        dot = parse_dot(data)
        if dot:
            try:
                with open(STROKE_FILE, "a") as f:
                    f.write(json.dumps(dot) + "\n")
            except OSError as e:
                print(f"Warning: could not write dot to file: {e}")

    try:
        async with BleakClient(pen.address) as client:
            print("Connected. Start writing...")
            await client.start_notify(PEN_DATA_CHAR, on_dot)
            await asyncio.sleep(3600)  # stream for up to 1 hour
    except Exception as e:
        print(f"Bluetooth connection error: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nDisconnected.")
