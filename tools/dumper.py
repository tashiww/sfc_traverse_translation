#!/usr/bin/env python3
"""
Traverse: Starlight & Prairie - Script & Text Dumper
Extracts dialogue scripts and tables using Thingy TBL into tashi_script_editor format.
"""

import argparse
import json
import struct
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.rom_utils import load_tbl

ROM_PATH = ROOT_DIR / "rom" / "Traverse - Starlight & Prairie (Japan).sfc"
OUTPUT_DIR = ROOT_DIR / "translations"
TABLES_DIR = ROOT_DIR / "tables"

# Known Control Codes in Traverse Text Engine
CONTROL_CODES = {
    bytes([0xFE, 0x00]): "<wait_auto>",
}


def decode_string(raw_bytes: bytes, tbl: dict = None) -> str:
    """Decodes raw script bytes into readable Japanese text and control codes."""
    i = 0
    res = []
    while i < len(raw_bytes):
        # 1. Check known multi-byte control codes
        pair = raw_bytes[i : i + 2]
        if pair in CONTROL_CODES:
            res.append(CONTROL_CODES[pair])
            i += 2
            continue

        # 2. Check 2-byte hex keys in TBL (e.g. 48e1, fcad, fbcf)
        if tbl and i + 1 < len(raw_bytes):
            two_hex = f"{raw_bytes[i]:02x}{raw_bytes[i+1]:02x}"
            if two_hex in tbl:
                res.append(tbl[two_hex])
                i += 2
                continue

        b = raw_bytes[i]

        # 3. Check 1-byte hex key in TBL (hiragana, katakana, digits, symbols)
        hex_key = f"{b:02x}"
        if tbl and hex_key in tbl:
            res.append(tbl[hex_key])
            i += 1
            continue

        # 4. Fallback 2-byte kanji token (FB xx, FC xx, FD xx)
        if b in (0xFB, 0xFC, 0xFD) and i + 1 < len(raw_bytes):
            res.append(f"<{raw_bytes[i:i+2].hex().upper()}>")
            i += 2
            continue

        # 6. Fallback single byte token
        res.append(f"<{b:02X}>")
        i += 1

    return "".join(res)


def dump_bank_c1_battle_strings(data: bytes, out_file: Path, tbl: dict = None):
    """Dumps the 257 verified battle/status/dialogue strings from Bank $C1 pointer table at 0x012F4A."""
    tbl_off = 0x012F4A
    ptrs = []
    for i in range(1000):
        p = struct.unpack_from("<H", data, tbl_off + i * 2)[0]
        if 0x3100 <= p <= 0x4800:
            ptrs.append(p)
        else:
            break

    strings = []
    for idx, p in enumerate(ptrs):
        pc = 0x010000 + p
        end = data.find(b"\xFF", pc)
        raw = data[pc:end]
        decoded = decode_string(raw, tbl)
        strings.append({
            "str_num": idx,
            "bank": "0xC1",
            "ptr_pos_hex": f"0x{tbl_off + idx * 2:06X}",
            "str_pos_hex": f"0x{pc:06X}",
            "length": len(raw),
            "text": decoded,
        })

    with open(out_file, "w", encoding="utf-8") as f:
        for s in strings:
            meta = {
                "str_num": s["str_num"],
                "bank": s["bank"],
                "ptr_pos": s["ptr_pos_hex"],
                "str_pos": s["str_pos_hex"],
                "length": s["length"],
            }
            f.write(json.dumps(meta) + "\n")
            f.write(f"#{s['text']}\n")
            f.write("\n\n")

    print(f"Dumped {len(strings)} strings from Bank $C1 table to {out_file.relative_to(ROOT_DIR)}")


def dump_item_tables(data: bytes, out_file: Path, tbl: dict = None):
    """Dumps the 5 item & equipment tables from Bank $C1."""
    tables = [
        ("consumables", 0x0142B6, 34),
        ("swords", 0x0142FA, 48),
        ("heavy_weapons", 0x014386, 33),
        ("shields_armors", 0x0143E8, 21),
        ("accessories", 0x014418, 22),
    ]

    total = 0
    with open(out_file, "w", encoding="utf-8") as f:
        str_idx = 0
        for category, tbl_off, count in tables:
            ptrs = [struct.unpack_from(">H", data, tbl_off + i * 2)[0] for i in range(count)]
            for i, p in enumerate(ptrs):
                pc = 0x010000 + p
                end = data.find(b"\xFF", pc)
                raw = data[pc:end]
                decoded = decode_string(raw, tbl)
                meta = {
                    "str_num": str_idx,
                    "category": category,
                    "cat_idx": i,
                    "pc_hex": f"0x{pc:06X}",
                    "length": len(raw),
                }
                f.write(json.dumps(meta) + "\n")
                f.write(f"#{decoded}\n")
                f.write("\n\n")
                str_idx += 1
                total += 1

    print(f"Dumped {total} item/equipment strings to {out_file.relative_to(ROOT_DIR)}")


def dump_dialogue_bank(data: bytes, bank_num: int, out_file: Path, tbl: dict = None):
    """Dumps dialogue strings from scenario Banks $F1-$F9."""
    bank_off = bank_num * 0x10000
    bank_data = data[bank_off : bank_off + 65536]
    strings = []

    i = 0
    str_idx = 0
    while i < len(bank_data) - 5:
        end = bank_data.find(b"\xFF", i)
        if end == -1:
            break
        chunk = bank_data[i:end]
        if len(chunk) >= 5:
            prefixes = sum(chunk.count(x) for x in (b"\xFB", b"\xFC", b"\xFD"))
            if prefixes >= 2 or any(c in chunk for c in CONTROL_CODES):
                pc = bank_off + i
                decoded = decode_string(chunk, tbl)
                strings.append({
                    "str_num": str_idx,
                    "bank": f"0x{0xC0 + bank_num:02X}",
                    "str_pos": f"0x{pc:06X}",
                    "length": len(chunk),
                    "text": decoded,
                })
                str_idx += 1
                i = end + 1
                continue
        i += 1

    with open(out_file, "w", encoding="utf-8") as f:
        for s in strings:
            meta = {
                "str_num": s["str_num"],
                "bank": s["bank"],
                "str_pos": s["str_pos"],
                "length": s["length"],
            }
            f.write(json.dumps(meta) + "\n")
            f.write(f"#{s['text']}\n")
            f.write("\n\n")

    print(f"Dumped {len(strings)} strings from Bank ${0xC0 + bank_num:02X} to {out_file.relative_to(ROOT_DIR)}")
    return len(strings)


def main():
    parser = argparse.ArgumentParser(description="Traverse Script Dumper")
    parser.add_argument("--all", action="store_true", help="Dump all scenario dialogue banks ($F1-$F9)")
    args = parser.parse_args()

    if not ROM_PATH.exists():
        print(f"Error: ROM not found at {ROM_PATH}")
        return

    data = ROM_PATH.read_bytes()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    tbl_path = TABLES_DIR / "ja_tbl.tbl"
    tbl = load_tbl(tbl_path) if tbl_path.exists() else None

    # 1. Dump Bank $C1 battle/system strings
    dump_bank_c1_battle_strings(data, OUTPUT_DIR / "dialogue_bank_C1.txt", tbl)

    # 2. Dump item tables
    dump_item_tables(data, OUTPUT_DIR / "items.txt", tbl)

    # 3. Dump scenario dialogue banks
    if args.all:
        total = 0
        for b in range(0x31, 0x3A):
            bank_snes = 0xC0 + b
            cnt = dump_dialogue_bank(data, b, OUTPUT_DIR / f"dialogue_bank_{bank_snes:02X}.txt", tbl)
            total += cnt
        print(f"Total scenario dialogue strings dumped: {total}")


if __name__ == "__main__":
    main()
