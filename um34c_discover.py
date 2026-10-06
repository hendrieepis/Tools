"""Diagnostik: scan device UM34C dan tampilkan peta GATT (service/characteristic).

Pemakaian:
    python um34c_discover.py

Gunakan script ini jika:
- monitor tidak menemukan device (cek device sedang advertise & tidak nyangkut)
- ingin memastikan GATT handle masih sama (mis. setelah ganti firmware/unit)
"""
import asyncio

from bleak import BleakClient, BleakScanner

ADDR = "00:15:A3:00:43:9A"


async def main():
    print("Scanning 10s...")
    found = await BleakScanner.discover(timeout=10, return_adv=True)
    target = None
    for addr, (dev, adv) in found.items():
        marker = "  <-- UM34C" if addr.upper() == ADDR else ""
        print(f"  {addr}  name={adv.local_name!r}  rssi={adv.rssi}{marker}")
        if addr.upper() == ADDR:
            target = dev
            print(f"    service_uuids={adv.service_uuids}")
            print(f"    manufacturer_data="
                  f"{{ {', '.join(f'0x{k:x}: {v.hex()}' for k, v in adv.manufacturer_data.items())} }}")
    if not target:
        print("UM34C tidak ditemukan (tidak advertise / nyangkut / terlalu jauh)")
        return
    print("Connecting...")
    async with BleakClient(target, timeout=30) as client:
        print("connected:", client.is_connected)
        for svc in client.services:
            print(f"SERVICE {svc.uuid}")
            for ch in svc.characteristics:
                print(f"  CHAR {ch.uuid}  props={','.join(ch.properties)}  "
                      f"handle=0x{ch.handle:04X}")
                for d in ch.descriptors:
                    print(f"    DESC {d.uuid}  handle=0x{d.handle:04X}")


asyncio.run(main())
