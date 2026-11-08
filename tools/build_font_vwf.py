#!/usr/bin/env python3
"""
Traverse: Starlight & Prairie - Proportional VWF Font & Widths Builder
Generates:
1. asm/vwf/vwf_font.bin:
   95 ASCII glyphs (0x20..0x7E), 32 bytes per glyph:
   - 8 bytes: Top Tile FG (rows 0..7)
   - 8 bytes: Top Tile Exterior Shadow (rows 0..7)
   - 8 bytes: Bottom Tile FG (rows 8..15)
   - 8 bytes: Bottom Tile Exterior Shadow (rows 8..15)
   Left-aligned so bit 7 is the first active pixel of the glyph.
   100% unified baseline at Row 11.
2. asm/vwf/vwf_widths.bin:
   95-byte proportional width table (exact visual pixel width + 1px spacing).
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.build_font8x16 import parse_bdf_glyphs, BDF_PATH, align_glyph_baseline, compute_exterior_shadow
OUT_FONT = ROOT_DIR / "asm" / "vwf" / "vwf_font.bin"
OUT_WIDTHS = ROOT_DIR / "asm" / "vwf" / "vwf_widths.bin"


def build_vwf_assets():
    glyphs = parse_bdf_glyphs(BDF_PATH)
    font_bytes = bytearray()
    widths_bytes = bytearray()

    for code in range(32, 127):
        if code == 32: # Space
            widths_bytes.append(4)
            # 32 bytes of zeros
            font_bytes.extend(bytes(32))
            continue

        raw = glyphs.get(code, [0] * 16)
        bm16 = align_glyph_baseline(code, raw)

        min_x, max_x = 8, -1
        for r in bm16:
            for b in range(8):
                if (r >> (7 - b)) & 1:
                    min_x = min(min_x, b)
                    max_x = max(max_x, b)

        if max_x >= min_x:
            char_w = (max_x - min_x + 1)
            prop_w = char_w + 1 # 1px kerning spacing
            # Left-align glyph bits so bit 7 is the first pixel of the character:
            aligned_bm = [((r << min_x) & 0xFF) for r in bm16]
            aligned_sh = compute_exterior_shadow(aligned_bm, mode="exterior")
        else:
            prop_w = 4
            aligned_bm = [0] * 16
            aligned_sh = [0] * 16

        widths_bytes.append(prop_w)

        # Pack into 32 bytes:
        # Top FG (8 bytes), Top SH (8 bytes), Bottom FG (8 bytes), Bottom SH (8 bytes)
        for r in range(8):
            font_bytes.append(aligned_bm[r])
        for r in range(8):
            font_bytes.append(aligned_sh[r])
        for r in range(8, 16):
            font_bytes.append(aligned_bm[r])
        for r in range(8, 16):
            font_bytes.append(aligned_sh[r])

    OUT_FONT.write_bytes(font_bytes)
    OUT_WIDTHS.write_bytes(widths_bytes)

    print(f"Generated VWF Assets:")
    print(f"  {OUT_FONT} ({len(font_bytes)} bytes, 95 glyphs x 32 bytes)")
    print(f"  {OUT_WIDTHS} ({len(widths_bytes)} bytes width table)")


if __name__ == "__main__":
    build_vwf_assets()
