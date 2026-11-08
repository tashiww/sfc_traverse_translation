#!/usr/bin/env python3
"""
Traverse: Starlight & Prairie - Font Tool
Dumps and encodes the 16x16 2bpp font from Bank $D3 (0x130000).
"""

from pathlib import Path
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parent.parent
ROM_PATH = ROOT_DIR / "rom" / "Traverse - Starlight & Prairie (Japan).sfc"
FONTS_DIR = ROOT_DIR / "fonts"

# Palette: 0=Transparent/Black, 1=White (Fill), 2=Dark Gray (Drop Shadow), 3=Accent
PALETTE = [
    (0, 0, 0, 0),        # 0: Transparent
    (255, 255, 255, 255), # 1: White
    (64, 64, 64, 255),   # 2: Drop Shadow (Dark Gray)
    (180, 180, 180, 255) # 3: Light Gray
]

def decode_tile_8x8_2bpp(chunk: bytes) -> list[list[int]]:
    """Decode one 8x8 2bpp SNES planar tile (16 bytes)."""
    grid = []
    for r in range(8):
        b1 = chunk[r * 2]
        b2 = chunk[r * 2 + 1]
        row = []
        for bit in range(7, -1, -1):
            val = ((b1 >> bit) & 1) | (((b2 >> bit) & 1) << 1)
            row.append(val)
        grid.append(row)
    return grid

def decode_glyph_16x16_2bpp(chunk: bytes) -> list[list[int]]:
    """Decode four 8x8 tiles into one 16x16 pixel grid (64 bytes)."""
    t0 = decode_tile_8x8_2bpp(chunk[0:16])
    t1 = decode_tile_8x8_2bpp(chunk[16:32])
    t2 = decode_tile_8x8_2bpp(chunk[32:48])
    t3 = decode_tile_8x8_2bpp(chunk[48:64])
    grid = []
    # Top 8 rows
    for r in range(8):
        grid.append(t0[r] + t1[r])
    # Bottom 8 rows
    for r in range(8):
        grid.append(t2[r] + t3[r])
    return grid

def dump_font_sheet(out_png: Path, cols: int = 32):
    data = ROM_PATH.read_bytes()
    font_base = 0x130000
    num_glyphs = 1024
    rows = (num_glyphs + cols - 1) // cols

    img = Image.new("RGBA", (cols * 16, rows * 16), (16, 16, 24, 255))
    pixels = img.load()

    for g in range(num_glyphs):
        chunk = data[font_base + g * 64 : font_base + (g + 1) * 64]
        grid = decode_glyph_16x16_2bpp(chunk)
        gx = (g % cols) * 16
        gy = (g // cols) * 16

        for y in range(16):
            for x in range(16):
                val = grid[y][x]
                if val != 0:
                    pixels[gx + x, gy + y] = PALETTE[val]

    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png)
    print(f"Dumped 1,024 font glyphs to {out_png.relative_to(ROOT_DIR)} ({cols*16}x{rows*16} px)")

if __name__ == "__main__":
    dump_font_sheet(FONTS_DIR / "font_bank_D3.png")
