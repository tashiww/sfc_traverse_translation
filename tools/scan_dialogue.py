#!/usr/bin/env python3
"""
Scan the entire 4MB ROM for Dialogue Tables and Script Blocks
matching the Traverse text engine pattern (FB xx, FC xx, FD xx prefixes and FB 6A terminators).
"""

import struct
from pathlib import Path

ROM_PATH = Path("rom/Traverse - Starlight & Prairie (Japan).sfc")


def scan_all_banks():
    data = ROM_PATH.read_bytes()
    num_banks = len(data) // 65536

    print("=" * 75)
    print(" SCANNING ALL 64 BANKS FOR SCRIPT BLOCKS AND POINTER TABLES")
    print("=" * 75)

    script_blocks = []

    for bank_idx in range(num_banks):
        bank_snes = 0xC0 + bank_idx
        bank_data = data[bank_idx * 65536 : (bank_idx + 1) * 65536]

        # Count occurrences of candidate terminators FB 6A and lead bytes FC / FD / FB
        fb_6a_count = bank_data.count(b"\xFB\x6A")
        fd_71_count = bank_data.count(b"\xFD\x71")
        total_dialogue_markers = fb_6a_count + fd_71_count

        if total_dialogue_markers > 10:
            print(
                f"Bank ${bank_snes:02X} (PC 0x{bank_idx * 0x10000:06X}): "
                f"FB 6A count={fb_6a_count:3d}, FD 71 count={fd_71_count:3d} -> DIALOGUE / SCRIPT DETECTED!"
            )
            script_blocks.append((bank_snes, bank_idx, fb_6a_count, fd_71_count))

    print(f"\nTotal banks containing dialogue scripts: {len(script_blocks)}")
    return script_blocks


if __name__ == "__main__":
    scan_all_banks()
