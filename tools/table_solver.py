#!/usr/bin/env python3
"""
Relative Search and Table Alignment Solver
Finds the exact TBL mapping for Traverse strings.
"""

from pathlib import Path

ROM_PATH = Path("rom/Traverse - Starlight & Prairie (Japan).sfc")

# Standard kana ordering: Gojuon (A, I, U, E, O, Ka, Ki, Ku, Ke, Ko, ...)
GOJUON_KATA = [
    "ア", "イ", "ウ", "エ", "オ",
    "カ", "キ", "ク", "ケ", "コ",
    "サ", "シ", "ス", "セ", "ソ",
    "タ", "チ", "ツ", "テ", "ト",
    "ナ", "ニ", "ヌ", "ネ", "ノ",
    "ハ", "ヒ", "フ", "ヘ", "ホ",
    "マ", "ミ", "ム", "メ", "モ",
    "ヤ", "ユ", "ヨ",
    "ラ", "リ", "ル", "レ", "ロ",
    "ワ", "ヲ", "ン"
]

GOJUON_HIRA = [
    "あ", "い", "う", "え", "お",
    "か", "き", "く", "け", "こ",
    "さ", "し", "す", "せ", "そ",
    "た", "ち", "つ", "て", "と",
    "な", "に", "ぬ", "ね", "の",
    "は", "ひ", "ふ", "へ", "ほ",
    "ま", "み", "む", "め", "も",
    "や", "ゆ", "よ",
    "ら", "り", "る", "れ", "ろ",
    "わ", "を", "ん"
]

def analyze_byte_distribution(data: bytes, start: int, end: int):
    slice_data = data[start:end]
    non_ff = [b for b in slice_data if b != 0xFF]
    unique_bytes = sorted(set(non_ff))
    print(f"Total bytes: {len(slice_data)}, Non-FF: {len(non_ff)}, Unique: {len(unique_bytes)}")
    print("Unique byte range: min=0x%02X, max=0x%02X" % (min(unique_bytes), max(unique_bytes)))
    print("Bytes: " + " ".join(f"{b:02X}" for b in unique_bytes))

def main():
    data = ROM_PATH.read_bytes()
    print("=== Analyzing Item Name Block at 0x014445 - 0x014660 ===")
    analyze_byte_distribution(data, 0x014445, 0x014660)

if __name__ == "__main__":
    main()
