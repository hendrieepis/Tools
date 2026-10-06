"""Monitor live RDTech UM34C (varian BLE) via Bluetooth Low Energy.

Pemakaian:
    python um34c_monitor.py                 # polling terus-menerus (Ctrl+C untuk stop)
    python um34c_monitor.py 100             # 100x polling lalu berhenti
    python um34c_monitor.py 100 data.csv    # sekaligus catat ke CSV

Penjelasan protokol & pemakaian lengkap: lihat README.md di folder ini.
"""
import asyncio
import sys
import time

from bleak import BleakClient

ADDR = "00:15:A3:00:43:9A"
CHAR = "0000ffe1-0000-1000-8000-00805f9b34fb"
POLL_INTERVAL_S = 0.3
RESPONSE_TIMEOUT_S = 2.0

MODES = {
    0: "UNKNOWN", 1: "QC2", 2: "QC3", 3: "APP2.4A", 4: "APP2.1A",
    5: "APP1.0A", 6: "APP0.5A", 7: "DCP1.5A", 8: "SAMSUNG",
}

# Posisi byte untuk checksum UM34C (XOR dari byte ganjil) - sesuai wiki sigrok.
CHECKSUM_POS = [1, 3, 7, 9, 15, 17, 19, 23, 31, 39, 41, 45, 49, 53, 55, 57,
                59, 63, 67, 69, 73, 79, 83, 89, 97, 99, 109, 111, 113, 119,
                121, 127]


def checksum(pkt: bytes) -> int:
    csum = 0
    for pos in CHECKSUM_POS:
        csum ^= pkt[pos]
    return csum


def find_packet(buf: bytearray):
    """Cari paket 130 byte yang diawali model ID 0x0d4c (UM34C) di buffer."""
    for idx in range(max(0, len(buf) - 129)):
        if buf[idx:idx + 2] == b"\x0d\x4c" and len(buf) - idx >= 130:
            return idx
    return -1


def parse(pkt: bytes):
    big = lambda a, b: int.from_bytes(pkt[a:b], "big")
    return {
        "V": big(2, 4) / 100.0,
        "I": big(4, 6) / 1000.0,
        "W": big(6, 10) / 1000.0,
        "TC": big(10, 12),
        "TF": big(12, 14),
        "D+": big(96, 98) / 100.0,
        "D-": big(98, 100) / 100.0,
        "mode": MODES.get(big(100, 102), "?"),
        "mAh": big(102, 106),
        "mWh": big(106, 110),
        "ohm": big(122, 126) / 10.0,
        "chk_ok": pkt[129] == checksum(pkt),
    }


async def main():
    polls = int(sys.argv[1]) if len(sys.argv) > 1 else 0  # 0 = tanpa batas
    csv_path = sys.argv[2] if len(sys.argv) > 2 else None
    csv = open(csv_path, "w", encoding="utf-8") if csv_path else None
    if csv:
        csv.write("time,V,I,W,TC,TF,D+,D-,mode,mAh,mWh,ohm,chk_ok\n")

    async with BleakClient(ADDR, timeout=30) as client:
        buf = bytearray()

        def cb(_, data: bytearray):
            buf.extend(data)

        await client.start_notify(CHAR, cb)
        print(f"Terhubung ke UM34C ({ADDR}) - polling 0xF0, Ctrl+C untuk stop")
        count = 0
        try:
            while polls == 0 or count < polls:
                buf.clear()
                await client.write_gatt_char(CHAR, b"\xf0", response=False)
                t0 = time.monotonic()
                pkt = None
                while time.monotonic() - t0 < RESPONSE_TIMEOUT_S:
                    idx = find_packet(buf)
                    if idx >= 0:
                        pkt = bytes(buf[idx:idx + 130])
                        break
                    await asyncio.sleep(0.02)
                count += 1
                if pkt is None:
                    print(f"timeout, {len(buf)} byte diterima: {buf.hex()}")
                    continue
                d = parse(pkt)
                print(f"V={d['V']:7.2f}V  I={d['I']:7.3f}A  W={d['W']:8.3f}W  "
                      f"T={d['TC']}C  D+={d['D+']:.2f} D-={d['D-']:.2f}  "
                      f"mode={d['mode']:8s}  mAh={d['mAh']}  mWh={d['mWh']}"
                      f"{'' if d['chk_ok'] else '  [checksum MISMATCH]'}",
                      flush=True)
                if csv:
                    csv.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')},{d['V']},"
                              f"{d['I']},{d['W']},{d['TC']},{d['TF']},{d['D+']},"
                              f"{d['D-']},{d['mode']},{d['mAh']},{d['mWh']},"
                              f"{d['ohm']},{int(d['chk_ok'])}\n")
                    csv.flush()
                await asyncio.sleep(POLL_INTERVAL_S)
        finally:
            try:
                await client.stop_notify(CHAR)
            except Exception:
                pass
    if csv:
        csv.close()


try:
    asyncio.run(main())
except KeyboardInterrupt:
    pass
