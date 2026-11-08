#!/usr/bin/env python3
"""
Test 1bpp 16x16 and 8x8 font rendering from ROM offsets to ASCII
"""

from pathlib import Path

ROM_PATH = Path("rom/Traverse - Starlight & Prairie (Japan).sfc")


def print_1bpp_16x16(glyph_bytes: bytes, label: str = ""):
    if len(glyph_bytes) < 32:
        return
    print(f"--- Glyph: {label} (32 bytes) ---")
    # A 16x16 glyph in linear 1bpp is 16 rows of 2 bytes (16 bits)
    for r in range(16):
        b1 = glyph_bytes[r * 2]
        b2 = glyph_bytes[r * 2 + 1]
        line = ""
        for bit in range(7, -1, -1):
            line += "##" if (b1 & (1 << bit)) else "  "
        for bit in range(7, -1, -1):
            line += "##" if (b2 & (1 << bit)) else "  "
        print(line)


def scan_for_kanji(data: bytes, start_pc: int, end_pc: int):
    # Scan for recognizable kanji glyphs (like horizontal lines, crosses)
    # in linear 16x16 1bpp (32 bytes/glyph)
    for pc in range(start_pc, end_pc, 32):
        chunk = data[pc : pc + 32]
        # Check density: not all zero and not all FF
        ones = sum(bin(b).count("1") for b in chunk)
        if 15 <= ones <= 80:
            # Check if it looks like a character
            top_empty = chunk[0] == 0 and chunk[1] == 0
            bottom_empty = chunk[30] == 0 and chunk[31] == 0
            if top_empty and bottom_empty:
                # check if next glyph also matches
                next_chunk = data[pc + 32 : pc + 64]
                next_ones = sum(bin(b).count("1") for b in next_chunk)
                if 15 <= next_ones <= 80:
                    print(f"Potential 16x16 font starting around PC 0x{pc:06X}")
                    for g in range(5):
                        print_1bpp_16x16(
                            data[pc + g * 32 : pc + (g + 1) * 32],
                            f"Offset 0x{pc + g * 32:06X}",
                        )
                    return pc
    return None


def main():
    data = ROM_PATH.read_bytes()
    # Check candidates
    for bank in [0x0C, 0x0F, 0x12, 0x13, 0x1C, 0x1D, 0x20, 0x2D, 0x2E, 0x30, 0x3E]:
        pc = bank * 0x10000
        print(f"\nChecking Bank at PC 0x{pc:06X}...")
        found = scan_for_kanji(data, pc, pc + 0x10000)
        if found:
            break


if __name__ == "__main__":
    main()
