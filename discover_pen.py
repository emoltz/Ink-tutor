"""
discover_pen.py  —  run on Mac host to enumerate all BLE services/characteristics
on the LAMY pen so we can find the correct UUIDs.

Usage:
    python discover_pen.py
"""

import asyncio
from bleak import BleakClient, BleakScanner


async def run():
    print("Scanning for Neo/LAMY smartpen...")
    devices = await BleakScanner.discover(timeout=10.0)

    pen = next((d for d in devices if d.name and ("NEO" in d.name.upper() or "LAMY" in d.name.upper())), None)

    if not pen:
        print("No pen found. Make sure it's on and nearby.")
        return

    print(f"\nFound: {pen.name} ({pen.address})\n")

    async with BleakClient(pen.address) as client:
        print("Connected. Enumerating services and characteristics...\n")
        for service in client.services:
            print(f"SERVICE: {service.uuid}")
            print(f"         {service.description}")
            for char in service.characteristics:
                props = ", ".join(char.properties)
                print(f"  CHAR:  {char.uuid}  [{props}]")
                print(f"         {char.description}")
                # Try to read readable characteristics
                if "read" in char.properties:
                    try:
                        val = await client.read_gatt_char(char.uuid)
                        print(f"         Value: {val.hex()} ({val})")
                    except Exception:
                        pass
            print()


if __name__ == "__main__":
    asyncio.run(run())