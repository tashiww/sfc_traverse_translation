#!/usr/bin/env python3
"""
Traverse: Starlight & Prairie - Proportional VWF Font & Widths Builder
Generates:
1. asm/vwf/vwf_font.bin:
   256 glyphs indexed directly by table byte (0x00..0xFF), 32 bytes per glyph:
   - 8 bytes: Top Tile FG (rows 0..7)
   - 8 bytes: Top Tile Exterior Shadow (rows 0..7)
   - 8 bytes: Bottom Tile FG (rows 8..15)
   - 8 bytes: Bottom Tile Exterior Shadow (rows 8..15)
   Left-aligned so bit 7 is the first active pixel of the glyph.
   100% unified baseline at Row 11.
2. asm/vwf/vwf_widths.bin:
   256-byte proportional width table (exact visual pixel width + 1px spacing).

Directly driven by tables/en_tbl.tbl following least resistance with native ASM.
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

TABLE_PATH = ROOT_DIR / "tables" / "en_tbl.tbl"
OUT_FONT = ROOT_DIR / "asm" / "vwf" / "vwf_font.bin"
OUT_WIDTHS = ROOT_DIR / "asm" / "vwf" / "vwf_widths.bin"


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


def build_vwf_assets():
    glyphs = parse_bdf_glyphs(BDF_PATH)
    en_tbl = parse_tbl(TABLE_PATH)

    font_bytes = bytearray(256 * 32)
    widths_bytes = bytearray(256)

    # Slot 0x00: Native Space (width = 4)
    widths_bytes[0x00] = 4

    for code, text in en_tbl.items():
        if code == 0x00 or code >= 0xEC or len(text) != 1:
            continue

        raw = get_raw_bitmap(text, glyphs)
        bm16 = align_glyph_baseline(ord(text) if len(text) == 1 else 0, raw)

        min_x, max_x = 8, -1
        for r in bm16:
            for b in range(8):
                if (r >> (7 - b)) & 1:
                    min_x = min(min_x, b)
                    max_x = max(max_x, b)

        if max_x >= min_x:
            char_w = max_x - min_x + 1
            prop_w = char_w + 1  # 1px kerning spacing
            # Left-align glyph bits so bit 7 is the first pixel of the character:
            aligned_bm = [((r << min_x) & 0xFF) for r in bm16]
            aligned_sh = compute_exterior_shadow(aligned_bm, mode="exterior")
        else:
            prop_w = 4
            aligned_bm = [0] * 16
            aligned_sh = [0] * 16

        widths_bytes[code] = prop_w

        # Pack into 32 bytes at code * 32:
        # Top FG (8 bytes), Top SH (8 bytes), Bottom FG (8 bytes), Bottom SH (8 bytes)
        pos = code * 32
        for r in range(8):
            font_bytes[pos + r] = aligned_bm[r]
        for r in range(8):
            font_bytes[pos + 8 + r] = aligned_sh[r]
        for r in range(8, 16):
            font_bytes[pos + 16 + (r - 8)] = aligned_bm[r]
        for r in range(8, 16):
            font_bytes[pos + 24 + (r - 8)] = aligned_sh[r]

    OUT_FONT.parent.mkdir(parents=True, exist_ok=True)
    OUT_FONT.write_bytes(font_bytes)
    OUT_WIDTHS.write_bytes(widths_bytes)

    print(f"Generated VWF Assets:")
    print(f"  {OUT_FONT} ({len(font_bytes)} bytes, 256 glyphs x 32 bytes)")
    print(f"  {OUT_WIDTHS} ({len(widths_bytes)} bytes width table)")


if __name__ == "__main__":
    build_vwf_assets()
