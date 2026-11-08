#!/usr/bin/env python3
"""
Traverse Kana Alignment Cracker
Uses known item names from Soul & Sword to solve the exact character encoding.
"""

from pathlib import Path
import struct

ROM_PATH = Path("rom/Traverse - Starlight & Prairie (Japan).sfc")

def main():
    data = ROM_PATH.read_bytes()

    # Table 0: Pointers at 0x0142B6 (34 entries)
    # Table 1: Pointers at 0x0142FA (48 entries)
    # Table 2: Pointers at 0x014386 (33 entries)
    # Table 3: Pointers at 0x0143E8 (21 entries)
    # Table 4: Pointers at 0x014418 (22 entries)

    tables = [
        ("Table 0 (Consumables/Items?)", 0x0142B6, 34),
        ("Table 1 (Swords/Weapons?)", 0x0142FA, 48),
        ("Table 2 (Axes/Blunt?)", 0x014386, 33),
        ("Table 3 (Armor/Shields?)", 0x0143E8, 21),
        ("Table 4 (Accessories/Helms?)", 0x014418, 22),
    ]

    for name, tbl_off, count in tables:
        print(f"\n=======================================================")
        print(f" {name} at 0x{tbl_off:06X} ({count} items)")
        print(f"=======================================================")
        ptrs = [struct.unpack_from(">H", data, tbl_off + i*2)[0] for i in range(count)]
        for i, ptr in enumerate(ptrs):
            pc = 0x010000 + ptr
            end = data.find(b"\xFF", pc)
            raw = data[pc:end]
            hex_str = " ".join(f"{b:02X}" for b in raw)
            print(f"  {i:2d} (0x{pc:06X}): {hex_str}")

if __name__ == "__main__":
    main()
