#!/usr/bin/env python3
"""
Traverse: Starlight & Prairie - VWF Font Builder
Generates 1bpp glyph bitmaps and proportional width tables for the VWF engine.
"""

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
FONTS_DIR = ROOT_DIR / "fonts"
ASM_VWF_DIR = ROOT_DIR / "asm" / "vwf"
BDF_PATH = FONTS_DIR / "Tamzen7x13r.bdf"


def parse_bdf_glyphs(path: Path) -> dict[int, list[int]]:
    glyphs = {}
    with open(path, "r", encoding="latin-1") as f:
        lines = f.readlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("STARTCHAR"):
            encoding = -1
            bitmap_lines = []
            while i < len(lines):
                l = lines[i].strip()
                if l.startswith("ENCODING"):
                    encoding = int(l.split()[1])
                elif l == "BITMAP":
                    i += 1
                    while i < len(lines) and lines[i].strip() != "ENDCHAR":
                        bitmap_lines.append(int(lines[i].strip(), 16))
                        i += 1
                    break
                i += 1
            if 32 <= encoding <= 126:
                glyphs[encoding] = bitmap_lines
        i += 1
    return glyphs


def build_vwf_font():
    ASM_VWF_DIR.mkdir(parents=True, exist_ok=True)
    glyphs = parse_bdf_glyphs(BDF_PATH)

    font_bin = bytearray()
    widths_bin = bytearray()

    for code in range(32, 127):
        if code == 32: # Space
            # 16 blank rows, width = 4
            font_bin.extend(bytes(16))
            widths_bin.append(4)
            continue

        raw_bm = glyphs.get(code, [0] * 13)
        # Center in 16-row box (1 row top padding, up to 13 glyph rows, remaining bottom padding)
        bm16 = [0] + raw_bm[:14] + [0] * max(0, 15 - len(raw_bm))
        bm16 = bm16[:16]

        # Calculate tight horizontal bounding box
        min_x, max_x = 8, -1
        for row in bm16:
            for b in range(8):
                if (row >> (7 - b)) & 1:
                    min_x = min(min_x, b)
                    max_x = max(max_x, b)

        if max_x >= min_x:
            char_w = (max_x - min_x + 1)
            prop_w = char_w + 1 # 1px kerning spacing
            # Left-align glyph bits so bit 7 is the first pixel of the character
            aligned_bm = [((r << min_x) & 0xFF) for r in bm16]
        else:
            prop_w = 4
            aligned_bm = [0] * 16

        for r in aligned_bm:
            font_bin.append(r)
        widths_bin.append(prop_w)

    out_font = ASM_VWF_DIR / "vwf_font.bin"
    out_widths = ASM_VWF_DIR / "vwf_widths.bin"

    out_font.write_bytes(font_bin)
    out_widths.write_bytes(widths_bin)

    print(f"Generated VWF font files:")
    print(f"  {out_font.relative_to(ROOT_DIR)} ({len(font_bin)} bytes, 95 glyphs x 16 rows)")
    print(f"  {out_widths.relative_to(ROOT_DIR)} ({len(widths_bin)} bytes width table)")


if __name__ == "__main__":
    build_vwf_font()
