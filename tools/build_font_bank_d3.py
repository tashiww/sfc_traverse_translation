#!/usr/bin/env python3
"""
Traverse: Starlight & Prairie - Bank $D3 (16x16 Font) Builder
Builds the complete 16KB 16x16 English font for Bank $D3 (0x130000 - 0x134000).

Formats each glyph into 4 SNES 2bpp 8x8 tiles (64 bytes):
- Tile 0: Top-Left (0..7, 0..7)
- Tile 1: Top-Right (8..15, 0..7)
- Tile 2: Bottom-Left (0..7, 8..15)
- Tile 3: Bottom-Right (8..15, 8..15)

Covers:
- ASCII characters 0x20..0x7E (full standard printable ASCII)
- Native uppercase letters 0x0B..0x24 ('A'..'Z')
- Native digits 0x01..0x0A ('0'..'9')
- Native symbols 0x86 ('!'), 0x87 ('?'), 0x8A ('-'), 0x8C ('.')
- Preserves native icons (★, ○, ☆, △) at 0xEC..0xEF from clean ROM
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.build_font8x16 import (
    BDF_PATH,
    align_glyph_baseline,
    compute_exterior_shadow,
    parse_bdf_glyphs,
)

CLEAN_ROM_PATH = ROOT_DIR / "rom" / "Traverse - Starlight & Prairie (Japan).sfc"
OUT_BIN = ROOT_DIR / "asm" / "vwf" / "font_bank_d3.bin"


def make_16x16_tile_bytes(code: int, glyphs: dict) -> bytes:
    """Converts an ASCII glyph into a 64-byte 16x16 SNES 2bpp glyph with exterior shadow."""
    if code == 32:  # Space
        return bytes(64)

    raw = glyphs.get(code, [0] * 16)
    bm = align_glyph_baseline(code, raw)
    sh = compute_exterior_shadow(bm, mode="exterior")

    # Native Traverse 16x16 bounding box standard: x_offset = 2
    x_off = 2
    grid = [[0] * 16 for _ in range(16)]
    for r in range(16):
        b = bm[r]
        s = sh[r]
        for c in range(8):
            if (b >> (7 - c)) & 1:
                grid[r][x_off + c] = 1  # Foreground
            elif (s >> (7 - c)) & 1:
                grid[r][x_off + c] = 2  # Drop shadow

    # Encode into 4 SNES 2bpp tiles:
    # Tile 0: Top-Left, Tile 1: Top-Right, Tile 2: Bottom-Left, Tile 3: Bottom-Right
    res = bytearray(64)
    tile_offsets = [(0, 0), (8, 0), (0, 8), (8, 8)]
    for t_idx, (tox, toy) in enumerate(tile_offsets):
        for r in range(8):
            p0 = 0
            p1 = 0
            for c in range(8):
                val = grid[toy + r][tox + c]
                if val & 1:
                    p0 |= 1 << (7 - c)
                if (val >> 1) & 1:
                    p1 |= 1 << (7 - c)
            res[t_idx * 16 + r * 2] = p0
            res[t_idx * 16 + r * 2 + 1] = p1
    return bytes(res)


def build_font_bank_d3():
    glyphs = parse_bdf_glyphs(BDF_PATH)

    # Initialize with clean ROM's Bank $D3 16KB so native icons (0xEC..0xEF) are retained:
    if CLEAN_ROM_PATH.exists():
        clean_rom = CLEAN_ROM_PATH.read_bytes()
        font_buf = bytearray(clean_rom[0x130000 : 0x134000])
    else:
        font_buf = bytearray(16384)

    # 1. Inject full ASCII range 0x20..0x7E:
    for code in range(32, 127):
        font_buf[code * 64 : (code + 1) * 64] = make_16x16_tile_bytes(code, glyphs)

    # 2. Map Native digits 0x01..0x0A (from ASCII '0'..'9'):
    for d in range(10):
        ascii_code = 0x30 + d
        native_code = 0x01 + d
        font_buf[native_code * 64 : (native_code + 1) * 64] = font_buf[ascii_code * 64 : (ascii_code + 1) * 64]

    # 3. Map Native uppercase 0x0B..0x24 (from ASCII 'A'..'Z'):
    for l in range(26):
        ascii_code = 0x41 + l
        native_code = 0x0B + l
        font_buf[native_code * 64 : (native_code + 1) * 64] = font_buf[ascii_code * 64 : (ascii_code + 1) * 64]

    # 4. Map Native punctuation:
    font_buf[0x00 * 64 : 0x01 * 64] = bytes(64)  # Native Space
    font_buf[0x86 * 64 : 0x87 * 64] = font_buf[0x21 * 64 : 0x22 * 64]  # Native '!'
    font_buf[0x87 * 64 : 0x88 * 64] = font_buf[0x3F * 64 : 0x40 * 64]  # Native '?'
    font_buf[0x8A * 64 : 0x8B * 64] = font_buf[0x2D * 64 : 0x2E * 64]  # Native '-'
    font_buf[0x8C * 64 : 0x8D * 64] = font_buf[0x2E * 64 : 0x2F * 64]  # Native '.'

    OUT_BIN.parent.mkdir(parents=True, exist_ok=True)
    OUT_BIN.write_bytes(font_buf)
    print(f"Successfully generated {len(font_buf)} bytes in {OUT_BIN.relative_to(ROOT_DIR)} (256 16x16 glyphs).")


if __name__ == "__main__":
    build_font_bank_d3()
