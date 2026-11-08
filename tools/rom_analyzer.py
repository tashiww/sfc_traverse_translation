#!/usr/bin/env python3
"""
Traverse: Starlight & Prairie - ROM Heuristic Analyzer
Performs entropy analysis, pointer table discovery, and string pattern hunting.
"""

import math
import struct
from pathlib import Path

ROM_PATH = Path("rom/Traverse - Starlight & Prairie (Japan).sfc")


def calc_entropy(chunk: bytes) -> float:
    if not chunk:
        return 0.0
    counts = [0] * 256
    for b in chunk:
        counts[b] += 1
    ent = 0.0
    l = len(chunk)
    for c in counts:
        if c > 0:
            p = c / l
            ent -= p * math.log2(p)
    return ent


def analyze_banks(data: bytes):
    print("=" * 75)
    print(" BANK ENTROPY & STRUCTURE SUMMARY (64 Banks of 64KB)")
    print("=" * 75)
    num_banks = len(data) // 65536
    for bank_idx in range(num_banks):
        bank_snes = 0xC0 + bank_idx
        chunk = data[bank_idx * 65536 : (bank_idx + 1) * 65536]
        ent = calc_entropy(chunk)
        zeroes = chunk.count(0)
        ffs = chunk.count(0xFF)

        if ent < 4.0:
            desc = "Sparse / Empty / Large Zero Blocks"
        elif ent < 6.4:
            desc = "Code / Tables / Pointers"
        elif ent < 7.2:
            desc = "Uncompressed Graphics / Mixed"
        else:
            desc = "High Entropy (Compressed Data / Sound Samples)"

        print(
            f"Bank ${bank_snes:02X} (PC 0x{bank_idx * 0x10000:06X}): "
            f"Entropy {ent:4.2f} | 00: {zeroes:5d} | FF: {ffs:5d} -> {desc}"
        )


def find_pointer_tables(data: bytes, min_len: int = 8):
    """
    Search for arrays of 16-bit little-endian pointers where:
    - Pointers point to addresses in the same 64KB bank ($0000-$FFFF, usually >= $0000).
    - Pointers are monotonically increasing (or non-decreasing).
    """
    print("\n" + "=" * 75)
    print(" MONOTONIC 16-BIT POINTER TABLE SEARCH")
    print("=" * 75)
    num_banks = len(data) // 65536
    found_tables = []

    for bank_idx in range(num_banks):
        bank_snes = 0xC0 + bank_idx
        bank_data = data[bank_idx * 65536 : (bank_idx + 1) * 65536]

        # Scan for sequences of 16-bit values that form a table of pointers
        i = 0
        while i < len(bank_data) - 4:
            ptrs = []
            cur = i
            while cur + 2 <= len(bank_data):
                val = struct.unpack_from("<H", bank_data, cur)[0]
                if not ptrs:
                    # First pointer: usually points into the second half of bank or at least ahead
                    if val > cur:
                        ptrs.append(val)
                        cur += 2
                    else:
                        break
                else:
                    last = ptrs[-1]
                    # Monotonically increasing with reasonable distance (< 2048 bytes between entries)
                    if last <= val < last + 2048 and val < len(bank_data):
                        ptrs.append(val)
                        cur += 2
                    else:
                        break

            if len(ptrs) >= min_len:
                first_target = ptrs[0]
                # Table cannot overlap its targets
                if (cur - 1) < first_target:
                    pc_start = bank_idx * 65536 + i
                    found_tables.append((bank_snes, pc_start, i, len(ptrs), ptrs[0], ptrs[-1]))
                    i = cur
                    continue
            i += 2

    print(f"Discovered {len(found_tables)} candidate 16-bit pointer tables (min length: {min_len})")
    for b, pc, bank_off, count, first, last in found_tables:
        if count >= 16:
            print(
                f"  Bank ${b:02X} at PC 0x{pc:06X} (${b:02X}:{bank_off:04X}): "
                f"{count} entries -> Points to ${b:02X}:{first:04X} .. ${b:02X}:{last:04X}"
            )


def main():
    if not ROM_PATH.exists():
        print(f"Error: {ROM_PATH} not found.")
        return
    data = ROM_PATH.read_bytes()
    analyze_banks(data)
    find_pointer_tables(data, min_len=16)


if __name__ == "__main__":
    main()
