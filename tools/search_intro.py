#!/usr/bin/env python3
"""
Exhaustive relative search across multiple kana orderings and encodings
for '大地から受ける恵であなたがもっとも素晴らしい'
"""

from pathlib import Path

ROM_PATH = Path("rom/Traverse - Starlight & Prairie (Japan).sfc")

# Try various kana sets:
# 1. Standard AIUEO
# 2. Akasatana
# 3. Iroha
# 4. Standard Shift-JIS / EUC / JIS

AIUEO_HIRA = "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"
AIUEO_KATA = "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン"

AKASATANA_HIRA = "あかさたなはまやらわいきしちにひみりうくすつぬふむゆるえけせてねへめれおこそとのほもよろをん"

IROHA_HIRA = "いろはにほへとちりぬるをわかよたれそつねならむうゐのおくやまけふこえてあさきゆめみしゑひもせす"

def test_pattern(data: bytes, phrase: str, alphabet: str, name: str):
    idxs = []
    for ch in phrase:
        if ch in alphabet:
            idxs.append(alphabet.index(ch))
        else:
            return
    deltas = [idxs[i+1] - idxs[i] for i in range(len(idxs)-1)]
    # Search for deltas in data
    # Allow 1-byte stride, 2-byte stride (if 16-bit)
    for stride in [1, 2]:
        for i in range(len(data) - len(deltas) * stride):
            match = True
            for d_idx, d_val in enumerate(deltas):
                p1 = i + d_idx * stride
                p2 = p1 + stride
                if (data[p2] - data[p1]) != d_val:
                    match = False
                    break
            if match:
                print(f"MATCH [{name}, stride={stride}] at PC 0x{i:06X}: base byte = 0x{data[i]:02X}")

def main():
    data = ROM_PATH.read_bytes()
    targets = [
        "あなた",
        "なた",
        "から",
        "もっとも",
        "とも",
        "すばらしい",
        "らしい",
        "うける",
        "ける"
    ]
    alphabets = [
        ("AIUEO_HIRA", AIUEO_HIRA),
        ("AIUEO_KATA", AIUEO_KATA),
        ("AKASATANA_HIRA", AKASATANA_HIRA),
        ("IROHA_HIRA", IROHA_HIRA)
    ]
    for t in targets:
        for a_name, a_str in alphabets:
            test_pattern(data, t, a_str, f"{t}_{a_name}")

if __name__ == "__main__":
    main()
