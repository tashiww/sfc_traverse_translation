#!/usr/bin/env python3
"""
Traverse: Starlight & Prairie - Kanji Importer & Pipeline Sync
Parses tables/manual_kanji.txt (16x16 blocks by prefix),
purges any unverified kanji assumptions, updates tables/ja_tbl.tbl,
and regenerates visual font sheets.
"""

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

TABLES_DIR = ROOT_DIR / "tables"
TBL_PATH = TABLES_DIR / "ja_tbl.tbl"
MANUAL_TXT = TABLES_DIR / "manual_kanji.txt"

from tools.gen_table import (
    DIGITS, LETTERS, MAP_KANJI, GOJUON_HIRA, DAKUTEN_HIRA, SMALL_KANA, KATAKANA
)


def parse_manual_kanji(manual_path: Path) -> dict[str, str]:
    if not manual_path.exists():
        print(f"Error: {manual_path} does not exist!")
        return {}

    lines = [l.strip() for l in manual_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    kanji_map = {}
    cur_prefix = None
    offset = 0

    for line in lines:
        if line.startswith("FB") or line.startswith("FC") or line.startswith("FD"):
            cur_prefix = line[:2].lower()
            offset = 0
        elif cur_prefix:
            for ch in line:
                hex_code = f"{cur_prefix}{offset:02x}"
                # Only keep confirmed characters; leave '？' out so it stays unknown
                if ch != "？":
                    kanji_map[hex_code] = ch
                offset += 1

    return kanji_map


def build_tbl(kanji_map: dict[str, str]):
    lines = [
        "# ============================================================================",
        "# Traverse: Starlight & Prairie - Japanese Character Table",
        f"# Confirmed Multi-Byte Kanji: {len(kanji_map)} (source: manual_kanji.txt)",
        "# ============================================================================",
        "",
        "# Numbers (1-9, 0)",
    ]
    for code, ch in DIGITS:
        lines.append(f"{code}={ch}")

    lines.append("\n# Latin Uppercase (A-Z)")
    for code, ch in LETTERS:
        lines.append(f"{code}={ch}")

    lines.append("\n# Single-Byte Map & Exploration Kanji")
    for code, ch in MAP_KANJI:
        lines.append(f"{code}={ch}")

    lines.append("\n# Hiragana (Gojuon)")
    for code, ch in GOJUON_HIRA:
        lines.append(f"{code}={ch}")

    lines.append("\n# Hiragana (Dakuten & Handakuten)")
    for code, ch in DAKUTEN_HIRA:
        lines.append(f"{code}={ch}")

    lines.append("\n# Small Hiragana")
    for code, ch in SMALL_KANA:
        lines.append(f"{code}={ch}")

    lines.append("\n# Katakana")
    for code, ch in KATAKANA:
        lines.append(f"{code}={ch}")

    lines.append("\n# Multi-Byte Kanji (from manual_kanji.txt)")
    for hex_code in sorted(kanji_map.keys()):
        lines.append(f"{hex_code}={kanji_map[hex_code]}")

    lines.append("\n# Equipment Tags & Control Codes")
    lines.append("48e1=[Sword]")
    lines.append("48e2=[Axe]")
    lines.append("48e6=[Shield]")
    lines.append("48f8=[Armor]")
    lines.append("fe00=<wait_auto>")

    TBL_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Updated {TBL_PATH.relative_to(ROOT_DIR)} with {len(kanji_map)} confirmed multi-byte kanji.")


def main():
    kanji_map = parse_manual_kanji(MANUAL_TXT)
    build_tbl(kanji_map)

    # Regenerate font sheets to reflect user mappings and highlight unmapped
    from tools.generate_font_sheets import main as regen_sheets
    print("Regenerating font sheets with updated manual table...")
    regen_sheets()

    # Re-dump Bank C1 and items with updated mappings
    from tools.dumper import dump_bank_c1_battle_strings, dump_item_tables
    from tools.rom_utils import load_tbl
    rom = (ROOT_DIR / "rom" / "Traverse - Starlight & Prairie (Japan).sfc").read_bytes()
    tbl = load_tbl(TBL_PATH)
    dump_bank_c1_battle_strings(rom, ROOT_DIR / "translations" / "dialogue_bank_C1.txt", tbl)
    dump_item_tables(rom, ROOT_DIR / "translations" / "items.txt", tbl)
    print("Re-dumped Bank C1 dialogue and items.")


if __name__ == "__main__":
    main()
