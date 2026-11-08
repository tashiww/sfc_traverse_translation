#!/usr/bin/env python3
"""
Traverse Character Table Generator
Generates ja_tbl.tbl with verified single-byte and multi-byte mappings.
"""

from pathlib import Path

# Digits 1-9, 0 at 0x01 - 0x0A
DIGITS = [
    ("01", "1"), ("02", "2"), ("03", "3"), ("04", "4"), ("05", "5"),
    ("06", "6"), ("07", "7"), ("08", "8"), ("09", "9"), ("0a", "0"),
]

# Uppercase Latin A-Z at 0x0B - 0x24
LETTERS = [
    (f"{0x0b + i:02x}", chr(ord("A") + i)) for i in range(26)
]

# Map / Exploration Kanji at 0x25 - 0x2F
MAP_KANJI = [
    ("25", "大"),
    ("26", "国"),
    ("27", "都"),
    ("28", "州"),
    ("29", "町"),
    ("2a", "村"),
    ("2b", "城"),
    ("2c", "東"),
    ("2d", "西"),
    ("2e", "南"),
    ("2f", "北"),
]

# Base Hiragana starting at 0x30
GOJUON_HIRA = [
    ("30", "あ"), ("31", "い"), ("32", "う"), ("33", "え"), ("34", "お"),
    ("35", "か"), ("36", "き"), ("37", "く"), ("38", "け"), ("39", "こ"),
    ("3a", "さ"), ("3b", "し"), ("3c", "す"), ("3d", "せ"), ("3e", "そ"),
    ("3f", "た"), ("40", "ち"), ("41", "つ"), ("42", "て"), ("43", "と"),
    ("44", "な"), ("45", "に"), ("46", "ぬ"), ("47", "ね"), ("48", "の"),
    ("49", "は"), ("4a", "ひ"), ("4b", "ふ"), ("4c", "へ"), ("4d", "ほ"),
    ("4e", "ま"), ("4f", "み"), ("50", "む"), ("51", "め"), ("52", "も"),
    ("53", "や"), ("54", "ゆ"), ("55", "よ"),
    ("56", "ら"), ("57", "り"), ("58", "る"), ("59", "れ"), ("5a", "ろ"),
    ("5b", "わ"), ("5c", "を"), ("5d", "ん"),
]

# Dakuten / Handakuten
DAKUTEN_HIRA = [
    ("5e", "か゛"),
    ("5f", "が"), ("60", "ぎ"), ("61", "ぐ"), ("62", "げ"), ("63", "ご"),
    ("64", "ざ"), ("65", "じ"), ("66", "ず"), ("67", "ぜ"), ("68", "ぞ"),
    ("69", "だ"), ("6a", "ぢ"), ("6b", "づ"), ("6c", "で"), ("6d", "ど"),
    ("6e", "ば"), ("6f", "び"), ("70", "ぶ"), ("71", "べ"), ("72", "ぼ"),
    ("73", "ぱ"), ("74", "ぴ"), ("75", "ぷ"), ("76", "ぺ"), ("77", "ぽ"),
]

# Small kana
SMALL_KANA = [
    ("78", "ぁ"), ("79", "ぃ"), ("7a", "ぅ"), ("7b", "ぇ"), ("7c", "ぉ"),
    ("7d", "っ"),
    ("7e", "ゃ"), ("7f", "ゅ"), ("80", "ょ"),
]

# Katakana 0xA1 - 0xDF
KATAKANA = [
    ("a1", "｡"), ("a2", "｢"), ("a3", "｣"), ("a4", "､"), ("a5", "･"),
    ("a6", "ヲ"), ("a7", "ァ"), ("a8", "ィ"), ("a9", "ゥ"), ("aa", "ェ"), ("ab", "ォ"),
    ("ac", "ャ"), ("ad", "ュ"), ("ae", "ョ"), ("af", "ッ"), ("b0", "ー"),
    ("b1", "ア"), ("b2", "イ"), ("b3", "ウ"), ("b4", "エ"), ("b5", "オ"),
    ("b6", "カ"), ("b7", "キ"), ("b8", "ク"), ("b9", "ケ"), ("ba", "コ"),
    ("bb", "サ"), ("bc", "シ"), ("bd", "ス"), ("be", "セ"), ("bf", "ソ"),
    ("c0", "タ"), ("c1", "チ"), ("c2", "ツ"), ("c3", "テ"), ("c4", "ト"),
    ("c5", "ナ"), ("c6", "ニ"), ("c7", "ヌ"), ("c8", "ネ"), ("c9", "ノ"),
    ("ca", "ハ"), ("cb", "ヒ"), ("cc", "フ"), ("cd", "ヘ"), ("ce", "ホ"),
    ("cf", "マ"), ("d0", "ミ"), ("d1", "ム"), ("d2", "メ"), ("d3", "モ"),
    ("d4", "ヤ"), ("d5", "ユ"), ("d6", "ヨ"),
    ("d7", "ラ"), ("d8", "リ"), ("d9", "ル"), ("da", "レ"), ("db", "ロ"),
    ("dc", "ワ"), ("dd", "ン"), ("de", "ﾞ"), ("df", "ﾟ"),
]

# Verified Multi-byte Kanji (index = ((b1 - 0xFA) << 8) | b2)
KANJI = [
    ("fb00", "生"),
    ("fb01", "人"),
    ("fb03", "女"),
    ("fb04", "母"),
    ("fb05", "木"),
    ("fb06", "林"),
    ("fb07", "森"),
    ("fb08", "本"),
    ("fb09", "休"),
    ("fb0a", "日"),
    ("fb0b", "月"),
    ("fb0c", "火"),
    ("fb0d", "水"),
    ("fb0e", "金"),
    ("fb0f", "土"),
    ("fb10", "天"),
    ("fb11", "気"),
    ("fb12", "父"),
    ("fb13", "先"),
    ("fb14", "学"),
    ("fb15", "校"),
    ("fb16", "男"),
    ("fb17", "子"),
    ("fb18", "白"),
    ("fb19", "赤"),
    ("fb1a", "青"),
    ("fb1b", "色"),
    ("fb1c", "春"),
    ("fb1d", "夏"),
    ("fb1e", "秋"),
    ("fb1f", "冬"),
    ("fbcf", "素"),
    ("fc53", "受"),
    ("fcad", "地"),
    ("fcae", "恵"),
    ("fcaf", "晴"),
]

def generate_tbl():
    tbl_path = Path("tables/ja_tbl.tbl")
    lines = [
        "# ============================================================================",
        "# Traverse: Starlight & Prairie - Japanese Character Table",
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

    lines.append("\n# Multi-Byte Kanji")
    for code, ch in KANJI:
        lines.append(f"{code}={ch}")

    lines.append("\n# Equipment Tags & Control Codes")
    lines.append("48e1=[Sword]")
    lines.append("48e2=[Axe]")
    lines.append("48e6=[Shield]")
    lines.append("48f8=[Armor]")
    lines.append("fb6a=<wait_btn>")
    lines.append("fd71=<end_dlg>")
    lines.append("fd6f=<page>")
    lines.append("fd6e=<br>")
    lines.append("fd70=<choice>")
    lines.append("fe00=<wait_auto>")

    tbl_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Written updated table to {tbl_path}")

if __name__ == "__main__":
    generate_tbl()
