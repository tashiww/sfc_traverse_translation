#!/usr/bin/env python3
"""
Traverse: Starlight & Prairie - Font Sheet Generator
Generates labeled visual font charts and missing-kanji sheets.
"""

from collections import Counter
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT_DIR = Path(__file__).resolve().parent.parent
ROM_PATH = ROOT_DIR / "rom" / "Traverse - Starlight & Prairie (Japan).sfc"
FONTS_DIR = ROOT_DIR / "fonts"
TABLES_DIR = ROOT_DIR / "tables"
TBL_PATH = TABLES_DIR / "ja_tbl.tbl"

FONT_PATH = "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf"
LABEL_FONT = ImageFont.truetype(FONT_PATH, 10)
KANJI_FONT = ImageFont.truetype(FONT_PATH, 13)

# 2bpp Palette:
# 0: Background, 1: Glyph Fill (White), 2: Drop Shadow (Dark Gray), 3: Accent (Mid Gray)
COLOR_BG_KNOWN = (24, 26, 32)
COLOR_BG_MISSING = (36, 28, 24)
COLOR_BORDER_KNOWN = (45, 50, 60)
COLOR_BORDER_MISSING = (180, 100, 30)
COLOR_TEXT_KNOWN = (100, 220, 120)
COLOR_TEXT_MISSING = (240, 160, 40)
COLOR_LABEL = (170, 180, 195)

GLYPH_PALETTE = {
    0: (0, 0, 0, 0),         # transparent
    1: (255, 255, 255, 255), # White
    2: (60, 60, 60, 255),    # Drop Shadow
    3: (180, 180, 180, 255), # Mid
}


def load_tbl(tbl_path: Path) -> dict[str, str]:
    mapping = {}
    if not tbl_path.exists():
        return mapping
    for line in tbl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            mapping[k.lower()] = v
    return mapping


def count_script_frequencies(rom: bytes) -> Counter:
    banks = [
        (0x010000, 0x018000), # Bank C1
        (0x1B0000, 0x1C0000), # Bank DB
        (0x310000, 0x390000), # Banks F1..F9
    ]
    counts = Counter()
    for b_start, b_end in banks:
        data = rom[b_start:b_end]
        i = 0
        while i < len(data) - 1:
            b1, b2 = data[i], data[i+1]
            if b1 in (0xFB, 0xFC, 0xFD):
                counts[f"{b1:02x}{b2:02x}"] += 1
                i += 2
            else:
                counts[f"{b1:02x}"] += 1
                i += 1
    return counts


def decode_glyph_16x16(chunk: bytes) -> Image.Image:
    """Decodes four 8x8 2bpp tiles into a 16x16 RGBA Image."""
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    pixels = im.load()

    # 4 tiles: (0,0), (8,0), (0,8), (8,8)
    tile_offsets = [(0, 0), (8, 0), (0, 8), (8, 8)]
    for t_idx, (tox, toy) in enumerate(tile_offsets):
        tile_bytes = chunk[t_idx * 16 : (t_idx + 1) * 16]
        for r in range(8):
            b1 = tile_bytes[r * 2]
            b2 = tile_bytes[r * 2 + 1]
            for bit in range(7, -1, -1):
                color_idx = ((b1 >> bit) & 1) | (((b2 >> bit) & 1) << 1)
                if color_idx != 0:
                    pixels[tox + (7 - bit), toy + r] = GLYPH_PALETTE[color_idx]
    return im


def render_cell(hex_code: str, glyph_img: Image.Image, mapped_char: str, count: int,
                cell_w: int = 52, cell_h: int = 66) -> Image.Image:
    """Renders one labeled cell with 2x magnified glyph."""
    is_known = bool(mapped_char) and not mapped_char.startswith("<")
    bg_color = COLOR_BG_KNOWN if is_known else COLOR_BG_MISSING
    border_color = COLOR_BORDER_KNOWN if is_known else COLOR_BORDER_MISSING

    cell = Image.new("RGB", (cell_w, cell_h), bg_color)
    draw = ImageDraw.Draw(cell)
    draw.rectangle([0, 0, cell_w - 1, cell_h - 1], outline=border_color, width=1)

    # Label (hex code) at top
    label_text = hex_code.upper()
    bbox = draw.textbbox((0, 0), label_text, font=LABEL_FONT)
    lw = bbox[2] - bbox[0]
    draw.text(((cell_w - lw) // 2, 2), label_text, font=LABEL_FONT, fill=COLOR_LABEL)

    # Magnify glyph 2x -> 32x32
    scaled_glyph = glyph_img.resize((32, 32), Image.NEAREST)
    glyph_x = (cell_w - 32) // 2
    glyph_y = 15
    cell.paste(scaled_glyph, (glyph_x, glyph_y), scaled_glyph)

    # Footer (character or ?)
    if is_known:
        footer_text = mapped_char
        footer_color = COLOR_TEXT_KNOWN
    else:
        footer_text = f"? ({count})" if count > 0 else "?"
        footer_color = COLOR_TEXT_MISSING

    bbox_f = draw.textbbox((0, 0), footer_text, font=KANJI_FONT)
    fw = bbox_f[2] - bbox_f[0]
    draw.text(((cell_w - fw) // 2, cell_h - 16), footer_text, font=KANJI_FONT, fill=footer_color)

    return cell


def create_16x16_sheet(title: str, prefix: str, glyph_start_idx: int,
                       rom_font_data: bytes, tbl: dict[str, str], counts: Counter,
                       out_path: Path):
    """Creates a 16 columns x 16 rows chart for a 256-glyph range."""
    cell_w, cell_h = 52, 66
    cols, rows = 16, 16
    header_h = 36
    margin = 8

    img_w = margin * 2 + cols * cell_w
    img_h = margin * 2 + header_h + rows * cell_h

    sheet = Image.new("RGB", (img_w, img_h), (14, 15, 18))
    draw = ImageDraw.Draw(sheet)

    # Title header
    draw.text((margin, 8), title, font=KANJI_FONT, fill=(220, 225, 235))
    legend = "Green = Known/Mapped   |   Orange = Missing Interpretation (needs user input)"
    draw.text((margin + 260, 10), legend, font=LABEL_FONT, fill=(180, 185, 195))

    for r in range(rows):
        for c in range(cols):
            idx = r * 16 + c
            g_idx = glyph_start_idx + idx
            chunk = rom_font_data[g_idx * 64 : (g_idx + 1) * 64]
            glyph_img = decode_glyph_16x16(chunk)

            if prefix:
                hex_code = f"{prefix}{idx:02x}"
            else:
                hex_code = f"{idx:02x}"

            mapped_char = tbl.get(hex_code, "")
            cnt = counts.get(hex_code, 0)

            cell = render_cell(hex_code, glyph_img, mapped_char, cnt, cell_w, cell_h)
            x = margin + c * cell_w
            y = margin + header_h + r * cell_h
            sheet.paste(cell, (x, y))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    print(f"Generated {out_path.name} ({img_w}x{img_h} px)")


def create_missing_kanji_sheet(rom_font_data: bytes, tbl: dict[str, str],
                               counts: Counter, out_path: Path):
    """Creates a compact contact sheet containing ONLY missing kanji, ordered by code."""
    missing_items = []

    # Check FB, FC, FD
    for prefix, start_g in [("fb", 256), ("fc", 512), ("fd", 768)]:
        for idx in range(256):
            hex_code = f"{prefix}{idx:02x}"
            char = tbl.get(hex_code, "")
            # If not in tbl, or value is a control code / hex placeholder
            if not char or char.startswith("<"):
                g_idx = start_g + idx
                chunk = rom_font_data[g_idx * 64 : (g_idx + 1) * 64]
                if any(chunk): # only non-empty
                    cnt = counts.get(hex_code, 0)
                    missing_items.append((hex_code, g_idx, chunk, cnt))

    cell_w, cell_h = 52, 66
    cols = 20
    rows = (len(missing_items) + cols - 1) // cols
    header_h = 36
    margin = 8

    img_w = margin * 2 + cols * cell_w
    img_h = margin * 2 + header_h + rows * cell_h

    sheet = Image.new("RGB", (img_w, img_h), (14, 15, 18))
    draw = ImageDraw.Draw(sheet)

    title = f"Traverse - Missing Kanji Review Sheet ({len(missing_items)} characters to interpret)"
    draw.text((margin, 8), title, font=KANJI_FONT, fill=(240, 180, 50))
    info = "Number in parentheses = Frequency in game script"
    draw.text((margin + 520, 10), info, font=LABEL_FONT, fill=(180, 185, 195))

    for i, (hex_code, g_idx, chunk, cnt) in enumerate(missing_items):
        r = i // cols
        c = i % cols
        glyph_img = decode_glyph_16x16(chunk)
        cell = render_cell(hex_code, glyph_img, "", cnt, cell_w, cell_h)
        x = margin + c * cell_w
        y = margin + header_h + r * cell_h
        sheet.paste(cell, (x, y))

    sheet.save(out_path)
    print(f"Generated {out_path.name} with {len(missing_items)} missing glyphs ({img_w}x{img_h} px)")

    # Also generate tables/missing_kanji.txt
    txt_path = TABLES_DIR / "missing_kanji.txt"
    lines = [
        "# ============================================================================",
        "# Traverse: Starlight & Prairie - Missing Kanji Definitions",
        f"# Total missing kanji: {len(missing_items)}",
        "# Instructions: Type the Japanese character after the '=' sign for each hex code.",
        "# Run: python3 tools/import_kanji.py to update ja_tbl.tbl automatically.",
        "# ============================================================================",
        "",
    ]
    cur_prefix = None
    for hex_code, g_idx, _, cnt in missing_items:
        prefix = hex_code[:2].upper()
        if prefix != cur_prefix:
            cur_prefix = prefix
            lines.append(f"\n# --- {cur_prefix} Series ---")
        lines.append(f"{hex_code}=  # used {cnt}x")

    txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Generated text template at {txt_path.relative_to(ROOT_DIR)}")


def main():
    data = ROM_PATH.read_bytes()
    font_data = data[0x130000 : 0x140000]
    tbl = load_tbl(TBL_PATH)
    counts = count_script_frequencies(data)

    print("Generating font sheets...")
    create_16x16_sheet("Traverse Font Sheet - Single Byte Range ($00 - $FF)",
                       "", 0, font_data, tbl, counts, FONTS_DIR / "sheet_single_byte.png")
    create_16x16_sheet("Traverse Font Sheet - FB Kanji Series ($FB00 - $FBFF)",
                       "fb", 256, font_data, tbl, counts, FONTS_DIR / "sheet_kanji_FB.png")
    create_16x16_sheet("Traverse Font Sheet - FC Kanji Series ($FC00 - $FCFF)",
                       "fc", 512, font_data, tbl, counts, FONTS_DIR / "sheet_kanji_FC.png")
    create_16x16_sheet("Traverse Font Sheet - FD Kanji Series ($FD00 - $FDFF)",
                       "fd", 768, font_data, tbl, counts, FONTS_DIR / "sheet_kanji_FD.png")

    create_missing_kanji_sheet(font_data, tbl, counts, FONTS_DIR / "sheet_missing_kanji.png")


if __name__ == "__main__":
    main()
