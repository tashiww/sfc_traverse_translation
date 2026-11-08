#!/usr/bin/env python3
"""
Relative Search Tool for Traverse
Searches for '大地から受ける恵であなたがもっとも素晴らしい' and substrings like 'あなた', 'から', 'もっとも'
"""

import sys
from pathlib import Path

ROM_PATH = Path("rom/Traverse - Starlight & Prairie (Japan).sfc")

GOJUON = [
    "あ", "い", "う", "え", "お",
    "か", "き", "く", "け", "こ",
    "さ", "し", "す", "せ", "そ",
    "た", "ち", "ツ", "て", "と",
    "な", "に", "ぬ", "ね", "の",
    "は", "ひ", "ふ", "へ", "ほ",
    "ま", "み", "む", "め", "も",
    "や", "ゆ", "よ",
    "ら", "り", "る", "れ", "ろ",
    "わ", "を", "ん"
]

def search_pattern_mottomo(data: bytes):
    """Search for 'もっとも' pattern: byte[i] == byte[i+3], where byte[i] is candidate 'も'"""
    print("\n--- Searching for 'も..も' (mottomo) patterns ---")
    matches = []
    # If 'も' is X, and small tsu/to are Y, Z: X Y Z X
    for i in range(len(data) - 4):
        b0 = data[i]
        b1 = data[i+1]
        b2 = data[i+2]
        b3 = data[i+3]
        if b0 == b3 and b0 != b1 and b0 != b2 and b1 != b2:
            # Check context: within dialogue banks $C1, $DB, $F1-$F9
            bank = data[i]
            pc = i
            # Check if this could be within a dialogue string (terminated with FF within 100 bytes)
            end = data.find(b"\xFF", pc)
            if end != -1 and 5 < (end - pc) < 150:
                # check if preceded by 'anata' or similar
                # let's look at 16 bytes before and 16 bytes after
                before = data[max(0, pc-16):pc]
                after = data[pc:min(len(data), end+1)]
                # check if dialogue bank ($010000..$01FFFF, $1B0000..$1BFFFF, $310000..$39FFFF)
                bank_byte = pc >> 16
                if bank_byte in [0x01, 0x1B] or (0x31 <= bank_byte <= 0x39):
                    matches.append((pc, b0, before, after))
    print(f"Found {len(matches)} candidate 'も..も' occurrences in dialogue banks.")
    for pc, b0, before, after in matches[:25]:
        print(f"  PC 0x{pc:06X} (SNES ${0xC0+(pc>>16):02X}:{pc&0xFFFF:04X}):")
        print(f"    Before: {before.hex(' ')}")
        print(f"    After:  {after.hex(' ')}")

def search_relative(data: bytes, text: str, alphabet: list):
    """Standard relative search across a known alphabet ordering"""
    indices = []
    for ch in text:
        if ch in alphabet:
            indices.append(alphabet.index(ch))
        else:
            return
    deltas = [indices[i+1] - indices[i] for i in range(len(indices)-1)]
    print(f"\n--- Relative search for '{text}' (deltas={deltas}) ---")
    for i in range(len(data) - len(deltas)):
        match = True
        for d_idx, d_val in enumerate(deltas):
            if (data[i + d_idx + 1] - data[i + d_idx]) != d_val:
                match = False
                break
        if match:
            print(f"  MATCH at PC 0x{i:06X}: base byte = 0x{data[i]:02X}")

def main():
    data = ROM_PATH.read_bytes()
    search_pattern_mottomo(data)
    search_relative(data, "あなた", GOJUON)
    search_relative(data, "から", GOJUON)

if __name__ == "__main__":
    main()
