#!/usr/bin/env python3
"""
Traverse: Starlight & Prairie - Bank $D2:E000 (8x16 Font) Builder
Builds the complete 8KB 8x16 English font for Bank $D2:E000 (0x12E000 - 0x130000).
Replaces the clean Japanese 8x16 font (which had Hiragana at 0x30..0x7F) with
commercial typography English glyphs matching en_tbl.tbl and locations.tbl.

Each character is 32 bytes (two vertically stacked 8x8 2bpp tiles):
- Tile char*2: Top 8x8 half
- Tile char*2 + 1: Bottom 8x8 half
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
from tools.rom_utils import load_tbl

CLEAN_ROM_PATH = ROOT_DIR / "rom" / "Traverse - Starlight & Prairie (Japan).sfc"
TABLE_PATH = ROOT_DIR / "tables" / "en_tbl.tbl"
OUT_BIN = ROOT_DIR / "asm" / "vwf" / "font_bank_d2.bin"


def make_8x16_tile_bytes(char: str, glyphs: dict) -> bytes:
    """Converts a character into a 32-byte 8x16 SNES 2bpp glyph (two 8x8 tiles) with exterior shadow."""
    if char == " ":
        return bytes(32)

    code = ord(char)
    raw = glyphs.get(code, [0] * 16)
    bm = align_glyph_baseline(code, raw)

    # Modern Sans-Serif Typographic Refinement for narrow characters:
    # Eliminates wide monospaced typewriter serifs on 'i', 'l', 'j'
    if char == "i":
        bm = [0] * 16
        bm[2] = 0b00010000
        for r in range(5, 12):
            bm[r] = 0b00010000
    elif char == "l":
        bm = [0] * 16
        for r in range(2, 12):
            bm[r] = 0b00010000
    elif char == "j":
        bm = [0] * 16
        bm[2] = 0b00010000
        for r in range(5, 12):
            bm[r] = 0b00010000
        bm[12] = 0b00010000
        bm[13] = 0b00110000
        bm[14] = 0b00100000

    sh = compute_exterior_shadow(bm, mode="exterior")

    top_tile = bytearray(16)
    for r in range(8):
        top_tile[r * 2] = bm[r]
        top_tile[r * 2 + 1] = sh[r]

    btm_tile = bytearray(16)
    for r in range(8):
        btm_tile[r * 2] = bm[8 + r]
        btm_tile[r * 2 + 1] = sh[8 + r]

    return bytes(top_tile + btm_tile)


def build_font_bank_d2():
    glyphs = parse_bdf_glyphs(BDF_PATH)
    tbl = load_tbl(TABLE_PATH)

    # Initialize with clean ROM's Bank $D2:E000 8KB:
    if CLEAN_ROM_PATH.exists():
        clean_rom = CLEAN_ROM_PATH.read_bytes()
        font_buf = bytearray(clean_rom[0x12E000 : 0x130000])
    else:
        font_buf = bytearray(8192)

    # Populate 8x16 font buffer directly by character table code:
    for code_str, text in tbl.items():
        try:
            code = int(code_str, 16)
        except ValueError:
            continue
        if code > 0xFF:
            continue
        if len(text) == 1:
            tile_bytes = make_8x16_tile_bytes(text, glyphs)
            offset = code * 32
            if offset + 32 <= len(font_buf):
                font_buf[offset : offset + 32] = tile_bytes

    # Ensure space slot 0x00 is strictly blank (32 bytes of 0x00):
    font_buf[0 : 32] = bytes(32)

    OUT_BIN.parent.mkdir(parents=True, exist_ok=True)
    OUT_BIN.write_bytes(font_buf)
    print(f"Successfully generated {len(font_buf)} bytes in {OUT_BIN.relative_to(ROOT_DIR)} (256 8x16 glyphs).")


if __name__ == "__main__":
    build_font_bank_d2()
