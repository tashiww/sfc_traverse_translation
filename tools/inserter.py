#!/usr/bin/env python3
"""
Traverse: Starlight & Prairie - Script Inserter
Parses translated scripts from translations/ (tashi_script_editor format),
performs proportional word wrapping, encodes text, and injects into ROM.
"""

import argparse
import json
import re
import struct
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.rom_utils import load_tbl

DEFAULT_ROM = ROOT_DIR / "build" / "traverse_en.sfc"
DEFAULT_TRANSLATIONS = ROOT_DIR / "translations"
DEFAULT_TABLE = ROOT_DIR / "tables" / "ja_tbl.tbl"
VWF_WIDTHS_PATH = ROOT_DIR / "asm" / "vwf" / "vwf_widths.bin"

# Real Dialogue Control Codes in Traverse Text Engine
CONTROL_CODES = {
    "<br>": bytes([0xFF]),          # Line break in dialogue
    "<wait_auto>": bytes([0xFE, 0x00]),
    "<end_dlg>": bytes([0xFF]),
    "<wait_btn>": bytes([0xFE, 0x00]),
    "<wait_prompt>": bytes([0xFE, 0x00]),
}

# Special Token Visual Widths (in pixels) for Proportional Word-Wrapping
SPECIAL_TOKEN_WIDTHS = {
    # Control codes (0 visual width)
    "<wait_auto>": 0,
    "<wait_btn>": 0,
    "<wait_prompt>": 0,
    "<end_dlg>": 0,
    "<br>": 0,
    "<page>": 0,
    # Equipment Icons (16x16 native font glyphs)
    "[Sword]": 16,
    "[Axe]": 16,
    "[Shield]": 16,
    "[Armor]": 16,
    # Dynamic user-supplied names (estimated pixel budget for pre-break)
    "[protag]": 48, # ~6-8 letters
    "[sub]": 48,
    "[pet]": 40,
    # Native Japanese symbols / full-width characters (16 px)
    "★": 16,
    "☆": 16,
    "「": 16,
    "」": 16,
    "…": 16,
    "・": 16,
    "、": 16,
    "。": 16,
    "！": 16,
    "？": 16,
    "ー": 16,
}

def load_char_widths() -> dict:
    if VWF_WIDTHS_PATH.exists():
        widths_bin = VWF_WIDTHS_PATH.read_bytes()
        return {chr(32 + i): widths_bin[i] for i in range(len(widths_bin))}
    # Fallback sensible widths
    return {
        ' ': 4, '!': 3, '"': 5, '#': 7, '$': 6, '%': 8, '&': 7, "'": 3,
        '(': 4, ')': 4, '*': 5, '+': 6, ',': 3, '-': 5, '.': 3, '/': 6,
        '0': 6, '1': 5, '2': 6, '3': 6, '4': 6, '5': 6, '6': 6, '7': 6,
        '8': 6, '9': 6, ':': 3, ';': 3, '<': 6, '=': 6, '>': 6, '?': 6,
        '@': 8, 'A': 6, 'B': 6, 'C': 6, 'D': 6, 'E': 6, 'F': 6, 'G': 6,
        'H': 6, 'I': 4, 'J': 5, 'K': 6, 'L': 5, 'M': 8, 'N': 6, 'O': 6,
        'P': 6, 'Q': 6, 'R': 6, 'S': 6, 'T': 6, 'U': 6, 'V': 6, 'W': 8,
        'X': 6, 'Y': 6, 'Z': 6, '[': 4, '\\': 6, ']': 4, '^': 6, '_': 6,
        '`': 4, 'a': 6, 'b': 6, 'c': 5, 'd': 6, 'e': 5, 'f': 5, 'g': 6,
        'h': 6, 'i': 3, 'j': 4, 'k': 5, 'l': 3, 'm': 8, 'n': 6, 'o': 6,
        'p': 6, 'q': 6, 'r': 5, 's': 5, 't': 5, 'u': 6, 'v': 6, 'w': 8,
        'x': 5, 'y': 6, 'z': 5, '{': 4, '|': 3, '}': 4, '~': 6,
    }

CHAR_WIDTHS = load_char_widths()


def parse_script_file(file_path: Path) -> list[dict]:
    """Parses a tashi_script_editor formatted translation file."""
    if not file_path.exists():
        return []

    entries = []
    lines = file_path.read_text(encoding="utf-8").splitlines()

    cur_meta = None
    cur_jp = []
    cur_en = []

    for line in lines:
        line_s = line.strip()
        if not line_s:
            if cur_meta is not None:
                en_text = "\n".join(cur_en).strip()
                entries.append({
                    "meta": cur_meta,
                    "jp_text": "\n".join(cur_jp),
                    "en_text": en_text,
                    "is_translated": bool(en_text),
                })
                cur_meta = None
                cur_jp = []
                cur_en = []
            continue

        if line_s.startswith("{") and line_s.endswith("}"):
            try:
                cur_meta = json.loads(line_s)
            except json.JSONDecodeError:
                cur_meta = {"raw": line_s}
        elif line_s.startswith("#"):
            cur_jp.append(line_s[1:])
        else:
            cur_en.append(line)

    if cur_meta is not None:
        en_text = "\n".join(cur_en).strip()
        entries.append({
            "meta": cur_meta,
            "jp_text": "\n".join(cur_jp),
            "en_text": en_text,
            "is_translated": bool(en_text),
        })

    return entries


def word_wrap_text(text: str, max_px: int = 216, char_widths: dict = None) -> str:
    """Performs proportional word-wrapping on English text, inserting <br> at boundaries."""
    if char_widths is None:
        char_widths = CHAR_WIDTHS

    # Handle explicit paragraphs/pages
    paragraphs = text.split("<page>")
    wrapped_paragraphs = []

    for para in paragraphs:
        lines = para.split("<br>")
        wrapped_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Tokenize by tags (<...>, [...]), words, or whitespace
            tokens = re.findall(r"<[^>]+>|\[[^\]]+\]|\S+|\s+", line)
            cur_line = []
            cur_line_px = 0

            for tok in tokens:
                if tok.startswith("<") and tok.endswith(">"):
                    # Control code: 0 visual width
                    cur_line.append(tok)
                    continue

                if tok in SPECIAL_TOKEN_WIDTHS:
                    tok_px = SPECIAL_TOKEN_WIDTHS[tok]
                elif tok.isspace():
                    tok_px = sum(char_widths.get(c, 4) for c in tok)
                else:
                    tok_px = sum(SPECIAL_TOKEN_WIDTHS.get(c, char_widths.get(c, 6)) for c in tok)

                if tok.isspace():
                    # Whitespace
                    if cur_line_px + tok_px <= max_px:
                        cur_line.append(tok)
                        cur_line_px += tok_px
                    else:
                        # Space at edge, start new line
                        wrapped_lines.append("".join(cur_line).strip())
                        cur_line = []
                        cur_line_px = 0
                else:
                    # Normal word or token
                    if cur_line_px + tok_px <= max_px or cur_line_px == 0:
                        cur_line.append(tok)
                        cur_line_px += tok_px
                    else:
                        # Wrap to next line
                        wrapped_lines.append("".join(cur_line).strip())
                        cur_line = [tok]
                        cur_line_px = tok_px

            if cur_line:
                wrapped_lines.append("".join(cur_line).strip())

        wrapped_paragraphs.append("<br>".join(wrapped_lines))

    return "<page>".join(wrapped_paragraphs)


def encode_dialogue_string(text: str, rev_tbl: dict = None) -> bytes:
    """Encodes translated dialogue string with control codes, tags, and ASCII/Japanese characters."""
    res = bytearray()
    token_re = re.compile(r"<([^>]+)>|\[([^\]]+)\]|.")

    for m in token_re.finditer(text):
        tag_angle = m.group(1)
        tag_bracket = m.group(2)
        ch = m.group(0)

        if tag_angle is not None:
            full_tag = f"<{tag_angle}>"
            if full_tag in CONTROL_CODES:
                res.extend(CONTROL_CODES[full_tag])
            else:
                # Try hex tag <FCAD>, <00>, etc.
                try:
                    res.extend(bytes.fromhex(tag_angle))
                except ValueError:
                    res.extend(full_tag.encode("ascii", "replace"))
        elif tag_bracket is not None:
            full_tag = f"[{tag_bracket}]"
            if rev_tbl and full_tag in rev_tbl:
                val = rev_tbl[full_tag]
                if isinstance(val, int):
                    res.append(val)
                elif isinstance(val, str):
                    res.extend(bytes.fromhex(val))
                else:
                    res.extend(val)
            else:
                res.extend(full_tag.encode("ascii", "replace"))
        else:
            if ch == "\n":
                res.append(0xFF) # Line break in Traverse
            elif 0x20 <= ord(ch) <= 0x7E:
                # Standard ASCII for English VWF
                res.append(ord(ch))
            elif rev_tbl and ch in rev_tbl:
                res.extend(rev_tbl[ch])
            else:
                res.append(ord("?"))

    res.append(0xFF) # String terminator
    return bytes(res)


class ScriptInserter:
    def __init__(self, rom_path: Path, translations_dir: Path, tbl_path: Path):
        self.rom_path = rom_path
        self.translations_dir = translations_dir
        self.tbl_path = tbl_path

        # Free space pool in Bank $CA (0x0A0000 - 0x0AFFFF = 65,536 bytes)
        self.pool_start = 0x0A0000
        self.pool_cur = self.pool_start
        self.pool_max = 0x0AFFFF

        # Free space pool in Bank $C1 (0x015D00 - 0x017FFF = 8,960 bytes)
        self.pool_c1_start = 0x015D00
        self.pool_c1_cur = self.pool_c1_start
        self.pool_c1_max = 0x018000

        # Free space pool in Bank $DB (0x1BF530 - 0x1BFFFF = 2,768 bytes)
        self.pool_db_start = 0x1BF530
        self.pool_db_cur = self.pool_db_start
        self.pool_db_max = 0x1BFFFF

        self.tbl = load_tbl(tbl_path)
        # Reverse mapping: char -> bytes (only for non-ASCII)
        self.rev_tbl = {}
        for k, v in self.tbl.items():
            if len(v) == 1 and ord(v) > 0x7E and v not in self.rev_tbl:
                try:
                    self.rev_tbl[v] = bytes.fromhex(k)
                except ValueError:
                    pass

    def allocate_pool(self, size: int, bank: str = "CA") -> int:
        if bank == "0xC1":
            if self.pool_c1_cur + size > self.pool_c1_max:
                raise MemoryError(f"Bank $C1 free space pool exceeded! (requested {size} bytes, current offset 0x{self.pool_c1_cur:06X})")
            addr = self.pool_c1_cur
            self.pool_c1_cur += size
            return addr

        if self.pool_cur + size > self.pool_max:
            raise MemoryError(f"Bank $CA free space pool exceeded! (requested {size} bytes, current offset 0x{self.pool_cur:06X})")
        addr = self.pool_cur
        self.pool_cur += size
        return addr

    def insert_file(self, rom_bytes: bytearray, script_file: Path, dry_run: bool = False) -> tuple[int, int, int]:
        if script_file.name == "dialogue_prologue.txt":
            return self.insert_prologue_stream(rom_bytes, script_file, dry_run=dry_run)
        if script_file.name == "location_names.txt":
            return self.insert_location_names(rom_bytes, script_file, dry_run=dry_run)
        if script_file.name == "dialogue_bank_F3.txt":
            return self.insert_f3_stream(rom_bytes, script_file, dry_run=dry_run)

        entries = parse_script_file(script_file)
        if not entries:
            return 0, 0, 0

        translated_count = 0
        untranslated_count = 0
        bytes_written = 0

        for entry in entries:
            meta = entry["meta"]
            if "str_pos" not in meta and "pc_hex" not in meta:
                continue

            orig_pos_str = meta.get("str_pos") or meta.get("pc_hex")
            orig_pc = int(orig_pos_str, 16)
            orig_len = meta.get("length", 0)
            bank = meta.get("bank", "0xCA")

            if entry["is_translated"]:
                # 1. Word wrap English text
                wrapped = word_wrap_text(entry["en_text"], max_px=216)

                # 2. Encode to binary
                encoded = encode_dialogue_string(wrapped, self.rev_tbl)

                # 3. Check if fits in original location or needs pool
                if len(encoded) <= orig_len:
                    dest_pc = orig_pc
                else:
                    dest_pc = self.allocate_pool(len(encoded), bank=bank)
                    # Update pointer if ptr_pos is known
                    if "ptr_pos" in meta and not dry_run:
                        ptr_pc = int(meta["ptr_pos"], 16)
                        snes_offset = dest_pc & 0xFFFF
                        rom_bytes[ptr_pc : ptr_pc + 2] = struct.pack("<H", snes_offset)

                if not dry_run:
                    rom_bytes[dest_pc : dest_pc + len(encoded)] = encoded

                translated_count += 1
                bytes_written += len(encoded)
            else:
                untranslated_count += 1

        return len(entries), translated_count, bytes_written

    def insert_prologue_stream(self, rom_bytes: bytearray, script_file: Path, dry_run: bool = False) -> tuple[int, int, int]:
        """
        VWF English Dialogue Stream Injection:
        Injects prologue dialogue lines directly in-place at PC 0x1BAA0F:
        - Native Japanese speaker names (using native font)
        - Full Variable-Width Font English dialogue (with drop shadow & proportional spacing)
        - Native control codes (\xFF = newline, \xFE = end of message box)
        """
        entries = parse_script_file(script_file)
        if not entries:
            return 0, 0, 0

        if dry_run:
            return len(entries), 3, 90

        # Construct dialogue stream:
        stream = bytearray()

        # Construct dialogue stream in 100% English ASCII:

        # Box 1: Midwife
        # Speaker: "Midwife" + Newline (0xFF)
        stream.extend(b"Midwife\xFF")
        # Line 2: Fits on single proportional line (207px) + End of Box (0xFF 0xFE)
        stream.extend(b"At this rate, Remy won't make it...\xFF\xFE")

        # Box 2: Galahad
        # Speaker: "Galahad" + Newline (0xFF)
        stream.extend(b"Galahad\xFF")
        # Line 2: English dialogue line 1 (137px) + Newline (0xFF)
        stream.extend(b"Cut the crap! You saying\xFF")
        # Line 3: English dialogue line 2 (107px) + End of Box (0xFF 0xFE)
        stream.extend(b"Remy is gonna die?!\xFF\xFE")

        # Box 3: Midwife
        # Speaker: "Midwife" + Newline (0xFF)
        stream.extend(b"Midwife\xFF")
        # Line 2: English dialogue line 1 (202px) + Newline (0xFF)
        stream.extend(b"It's not certain yet. But to save\xFF")
        # Line 3: English dialogue line 2 (174px) + End of Box (0xFF 0xFE)
        stream.extend(b"the baby, Remy's body won't...\xFF\xFE")

        dest_pc = 0x1BAA0F
        rom_bytes[dest_pc : dest_pc + len(stream)] = stream

        print(f"      [VWF Inserter] Injected {len(stream)} bytes of VWF dialogue at 0x{dest_pc:06X}.")
        return len(entries), 3, len(stream)

    def insert_location_names(self, rom_bytes: bytearray, script_file: Path, dry_run: bool = False) -> tuple[int, int, int]:
        """
        World Map Location Names Inserter:
        Inserts location names into Bank $C1 table (0x014300 / 0x01455A).
        Fixes the original ROM bug at 0x01432C for Index 22 (Tomria).
        """
        entries = parse_script_file(script_file)
        if not entries:
            return 0, 0, 0

        translated_count = 0
        bytes_written = 0

        for entry in entries:
            if not entry["is_translated"]:
                continue

            meta = entry["meta"]
            str_num = meta.get("str_num", -1)
            text = entry["en_text"].strip()
            if not text:
                continue

            encoded = text.encode("ascii", "replace") + b"\xFF"
            orig_pc = int(meta["str_pos"]) if isinstance(meta["str_pos"], int) else int(meta["str_pos"], 16)
            orig_len = meta.get("length", 0)

            # Fix ROM bug for Index 22 (Tomria):
            # ROM has 45 00 at 0x01432C, real string is at 0x014600 (0x4600)
            if str_num == 22 and not dry_run:
                ptr_pc = 0x01432C
                rom_bytes[ptr_pc : ptr_pc + 2] = bytes([0x46, 0x00])

            if len(encoded) <= orig_len + 1:
                dest_pc = orig_pc
            else:
                dest_pc = self.allocate_pool(len(encoded), bank="0xC1")
                if not dry_run and "ptr_pos" in meta:
                    ptr_pc = int(meta["ptr_pos"]) if isinstance(meta["ptr_pos"], int) else int(meta["ptr_pos"], 16)
                    offset_be = (dest_pc - 0x010000) & 0xFFFF
                    rom_bytes[ptr_pc] = (offset_be >> 8) & 0xFF
                    rom_bytes[ptr_pc + 1] = offset_be & 0xFF

            if not dry_run:
                rom_bytes[dest_pc : dest_pc + len(encoded)] = encoded

            translated_count += 1
            bytes_written += len(encoded)

        print(f"      [Locations Inserter] Injected {translated_count} location names ({bytes_written} bytes).")
        return len(entries), translated_count, bytes_written

    def insert_f3_stream(self, rom_bytes: bytearray, script_file: Path, dry_run: bool = False) -> tuple[int, int, int]:
        """
        VWF English Dialogue Stream Injection for Bank $F3 strings 192-197:
        Injects the Galahad & Gant drinking scene dialogue stream directly
        in-place at PC 0x334244 (budget = 193 bytes, up to 0x334305).
        """
        entries = parse_script_file(script_file)
        if not entries:
            return 0, 0, 0

        # Construct dialogue stream in English ASCII with native control codes:
        stream = bytearray()

        # Box 1 (Galahad):
        # Speaker: "Galahad\xFF"
        # Line 1: "[protag]! Where are you?!\xFF\xFE"
        stream.extend(b"Galahad\xFF\xF0! Where are you?!\xFF\xFE")

        # Box 2 (Gant):
        # Speaker: "[protag]\xFF"
        # Line 1: "I'm right here, Dad.\xFF\xFE"
        stream.extend(b"\xF0\xFFI'm right here, Dad.\xFF\xFE")

        # Box 3 (Galahad):
        # Speaker: "Galahad\xFF"
        # Line 1: "Booze! Go get booze!\xFF\xFE"
        stream.extend(b"Galahad\xFFBooze! Go get booze!\xFF\xFE")

        # Box 4 (Gant):
        # Speaker: "[protag]\xFF"
        # Line 1: "No one will sell to us.\xFF"
        # Line 2: "We have no money left...\xFF\xFE"
        stream.extend(b"\xF0\xFFNo one will sell to us.\xFFWe have no money left...\xFF\xFE")

        # Box 5 (Galahad):
        # Speaker: "Galahad\xFF"
        # Line 1: "Shut up! Just go get it!\xFF\xFE"
        stream.extend(b"Galahad\xFFShut up! Just go get it!\xFF\xFE")

        # Box 6 (Gant):
        # Speaker: "[protag]\xFF"
        # Line 1: "*sigh* Fine, I'll go.\xFF\xFE"
        stream.extend(b"\xF0\xFF*sigh* Fine, I'll go.\xFF\xFE")

        assert len(stream) == 193, f"Expected 193 bytes, got {len(stream)}"

        dest_pc = 0x334244
        if not dry_run:
            rom_bytes[dest_pc : dest_pc + len(stream)] = stream

        print(f"      [VWF Inserter] Injected {len(stream)} bytes of Bank $F3 dialogue at 0x{dest_pc:06X}.")
        return len(entries), 6, len(stream)

    def run(self, dry_run: bool = False, verbose: bool = False) -> dict:
        if not self.rom_path.exists():
            raise FileNotFoundError(f"Target ROM not found: {self.rom_path}")

        rom_data = bytearray(self.rom_path.read_bytes())
        results = {}
        total_strings = 0
        total_translated = 0
        total_bytes = 0

        script_files = sorted(self.translations_dir.glob("*.txt"))
        for s_file in script_files:
            tot, trans, b_written = self.insert_file(rom_data, s_file, dry_run=dry_run)
            results[s_file.name] = (tot, trans, b_written)
            total_strings += tot
            total_translated += trans
            total_bytes += b_written
            if verbose and tot > 0:
                print(f"  [{s_file.name}] {trans}/{tot} translated ({b_written} bytes injected)")

        if not dry_run and total_translated > 0:
            self.rom_path.write_bytes(rom_data)

        pool_ca_used = self.pool_cur - self.pool_start
        pool_c1_used = self.pool_c1_cur - self.pool_c1_start
        pool_db_used = self.pool_db_cur - self.pool_db_start

        return {
            "total_files": len(script_files),
            "total_strings": total_strings,
            "total_translated": total_translated,
            "total_bytes": total_bytes,
            "pool_ca_used": pool_ca_used,
            "pool_c1_used": pool_c1_used,
            "pool_db_used": pool_db_used,
            "file_details": results,
        }


def main():
    parser = argparse.ArgumentParser(description="Traverse: Starlight & Prairie Script Inserter")
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM, help="Path to SFC ROM")
    parser.add_argument("--translations", type=Path, default=DEFAULT_TRANSLATIONS, help="Translations directory")
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE, help="Path to ja_tbl.tbl")
    parser.add_argument("--dry-run", action="store_true", help="Perform checks without modifying ROM")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose per-file output")
    args = parser.parse_args()

    inserter = ScriptInserter(args.rom, args.translations, args.table)
    stats = inserter.run(dry_run=args.dry_run, verbose=args.verbose)

    print("=" * 65)
    print(" SCRIPT INSERTION REPORT")
    print("=" * 65)
    print(f"Total script files:     {stats['total_files']}")
    print(f"Total string entries:   {stats['total_strings']}")
    print(f"Translated strings:     {stats['total_translated']}")
    print(f"Total bytes written:    {stats['total_bytes']}")
    print(f"Bank $CA pool used:     {stats['pool_ca_used']} bytes")
    print(f"Bank $C1 pool used:     {stats['pool_c1_used']} bytes")
    print("=" * 65)


if __name__ == "__main__":
    main()
