#!/usr/bin/env python3
"""
Traverse: Starlight & Prairie - Bank $D3 (16x16 Font) Builder
Builds the complete 16KB 16x16 English font for Bank $D3 (0x130000 - 0x134000).

Directly driven by tables/en_tbl.tbl following least resistance with native ASM:
- Tile 0x00: Space (64 bytes of 0x00)
- Tiles 0x01..0x0A: Digits '0'..'9'
- Tiles 0x0B..0x24: Uppercase 'A'..'Z' (Slot 0x20 is 'V')
- Tiles 0x25..0x3E: Lowercase 'a'..'z'
- Tiles 0x3F..0x44: Extended symbols (;, %, &, $, ~, _)
- Tiles 0x81..0x8F: Native punctuation (+, /, *, ', ", !, ?, ,, ., -, …, ·, (, ), :)
- Tiles 0xEC..0xEF: Native game icons (★, ○, ☆, △) preserved from clean ROM
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
TABLE_PATH = ROOT_DIR / "tables" / "en_tbl.tbl"
OUT_BIN = ROOT_DIR / "asm" / "vwf" / "font_bank_d3.bin"


def parse_tbl(path: Path) -> dict:
    tbl = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip("\r\n")
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            code = int(k, 16)
            tbl[code] = v
    return tbl


def get_raw_bitmap(char: str, glyphs: dict) -> list:
    """Returns 16-row 1bpp bitmap for character, with fallbacks for special symbols."""
    if char == "…":
        # 3 dots aligned to Row 11:
        bm = [0] * 16
        bm[10] = 0b01010100
        bm[11] = 0b01010100
        return bm
    elif char == "·":
        # Centered dot at Row 8:
        bm = [0] * 16
        bm[7] = 0b00011000
        bm[8] = 0b00011000
        return bm

    code = ord(char)
    return glyphs.get(code, [0] * 16)


def make_16x16_tile_bytes(char: str, glyphs: dict) -> bytes:
    """Converts a character into a 64-byte 16x16 SNES 2bpp glyph with exterior shadow."""
    if char == " ":
        return bytes(64)

    raw = get_raw_bitmap(char, glyphs)
    bm = align_glyph_baseline(ord(char) if len(char) == 1 else 0, raw)
    sh = compute_exterior_shadow(bm, mode="exterior")

    # Native Traverse 16x16 bounding box standard: x_offset = 2
    x_offset = 2
    grid = [[0 for _ in range(16)] for _ in range(16)]
    for y in range(16):
        for x in range(8):
            fg = (bm[y] >> (7 - x)) & 1
            shadow = (sh[y] >> (7 - x)) & 1
            gx = x + x_offset
            if 0 <= gx < 16:
                if fg:
                    grid[y][gx] = 1
                elif shadow:
                    grid[y][gx] = 2

    # Pack 16x16 grid into 4 8x8 SNES 2bpp tiles (64 bytes):
    tiles_origin = [(0, 0), (8, 0), (0, 8), (8, 8)]
    res = bytearray(64)
    for t_idx, (tox, toy) in enumerate(tiles_origin):
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
    en_tbl = parse_tbl(TABLE_PATH)

    # Initialize with clean ROM's Bank $D3 16KB so native icons (0xEC..0xEF) are retained:
    if CLEAN_ROM_PATH.exists():
        clean_rom = CLEAN_ROM_PATH.read_bytes()
        font_buf = bytearray(clean_rom[0x130000 : 0x134000])
    else:
        font_buf = bytearray(16384)

    # Populate Bank $D3 directly by table code:
    for code, text in en_tbl.items():
        if code >= 0xEC:
            # Special icons or tags (leave clean ROM icons or handled elsewhere)
            continue
        if len(text) == 1:
            tile_bytes = make_16x16_tile_bytes(text, glyphs)
            font_buf[code * 64 : (code + 1) * 64] = tile_bytes

    # Ensure space slots are strictly blank (64 bytes of 0x00):
    font_buf[0x00 * 64 : 0x01 * 64] = bytes(64)  # Native Space
    font_buf[0x8B * 64 : 0x8C * 64] = bytes(64)  # Native Blank / Ellipsis filler

    OUT_BIN.parent.mkdir(parents=True, exist_ok=True)
    OUT_BIN.write_bytes(font_buf)
    print(f"Successfully generated {len(font_buf)} bytes in {OUT_BIN.relative_to(ROOT_DIR)} (256 16x16 glyphs).")


if __name__ == "__main__":
    build_font_bank_d3()
