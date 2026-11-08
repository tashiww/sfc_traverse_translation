#!/usr/bin/env python3
"""
Traverse: Starlight & Prairie - Clean 8x16 Font Builder
Generates 2bpp SNES font tiles with:
- 100% Unified Baseline (aligned to Row 11 for all uppercase and lowercase letters)
- Typographic Cap-Height alignment for quotes/apostrophes
- Exterior-Only Drop Shadow (strictly outside glyph contours, eliminating interior self-shadowing)
"""

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
BDF_PATH = ROOT_DIR / "fonts" / "Tamzen8x16r.bdf"
OUT_BIN = ROOT_DIR / "asm" / "vwf" / "font8x16.bin"


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


def align_glyph_baseline(code: int, raw_bm: list[int]) -> list[int]:
    """
    Normalizes glyph baseline to Row 11 across all characters:
    - In raw Tamzen: a,b,d,h,j,l,m,n,r,u,w,y,g,p,q,O,Q are on baseline 12.
      Shifting them up by 1 pixel aligns them with c,e,f,i,k,o,s,t,v,x,z and A-Z at Row 11.
    - Quotes/apostrophes start at Row 1 (above cap-height).
      Shifting them down by 2 pixels aligns them with cap-height (Row 3).
    """
    bm = raw_bm[:16] + [0] * max(0, 16 - len(raw_bm))
    ch = chr(code)

    # Shift up by 1 pixel to unify baseline to Row 11:
    shift_up = set("abdhjlmnruwygpqOQ")
    if ch in shift_up:
        return bm[1:16] + [0]

    # Shift down by 2 pixels to align with cap-height (Row 3):
    if ch in ("'", '"', '`'):
        return [0, 0] + bm[:14]

    return bm


def compute_exterior_shadow(bm: list[int], mode: str = "exterior") -> list[int]:
    """
    Computes drop shadow mask for an 8x16 1bpp glyph.
    Mode 'exterior': (+1X, +1Y) drop shadow strictly outside the glyph,
    filtered to never fall inside enclosed or semi-enclosed glyph counters.
    """
    if mode == "none":
        return [0] * 16

    if mode == "right":
        return [(b >> 1) & (~b) & 0xFF for b in bm]

    raw_sh = [0] + [(b >> 1) for b in bm[:15]]
    cand = [raw_sh[r] & (~bm[r]) & 0xFF for r in range(16)]

    grid = [[0] * 8 for _ in range(16)]
    for r in range(16):
        for c in range(8):
            if (bm[r] >> (7 - c)) & 1:
                grid[r][c] = 1
            elif (cand[r] >> (7 - c)) & 1:
                grid[r][c] = 2

    out_sh = [0] * 16
    for r in range(16):
        row_val = 0
        for c in range(8):
            if grid[r][c] == 2:
                # Do NOT cast shadow if there is foreground above it in the same column,
                # unless it is strictly below the lowest foreground pixel in that column.
                has_fg_above = any(grid[ar][c] == 1 for ar in range(r))
                if not has_fg_above:
                    row_val |= (1 << (7 - c))
                else:
                    lowest_fg = max([ar for ar in range(16) if grid[ar][c] == 1])
                    if r > lowest_fg:
                        row_val |= (1 << (7 - c))
        out_sh[r] = row_val
    return out_sh


def make_snes_2bpp(bm: list[int], sh: list[int]) -> bytearray:
    """Converts 16 rows of 8px bitmap and shadow into two SNES 8x8 2bpp tiles."""
    top_tile = bytearray()
    for r in range(8):
        top_tile.append(bm[r])
        top_tile.append(sh[r])

    btm_tile = bytearray()
    for r in range(8, 16):
        btm_tile.append(bm[r])
        btm_tile.append(sh[r])

    return top_tile + btm_tile


def build_font(mode: str = "exterior"):
    glyphs = parse_bdf_glyphs(BDF_PATH)
    font_data = bytearray()

    for code in range(32, 127):
        raw = glyphs.get(code, [0] * 16)
        bm16 = align_glyph_baseline(code, raw)
        sh16 = compute_exterior_shadow(bm16, mode=mode)
        tile_2bpp = make_snes_2bpp(bm16, sh16)
        font_data.extend(tile_2bpp)

    OUT_BIN.write_bytes(font_data)
    print(f"Generated {len(font_data)} bytes in {OUT_BIN} ({len(font_data)//32} glyphs, unified baseline, mode='{mode}')")


if __name__ == "__main__":
    build_font("exterior")
