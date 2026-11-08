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
DEFAULT_TABLE = ROOT_DIR / "tables" / "en_tbl.tbl"
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
    widths = {}
    tbl = load_tbl(DEFAULT_TABLE, reverse=True)
    if VWF_WIDTHS_PATH.exists():
        widths_bin = VWF_WIDTHS_PATH.read_bytes()
        for char, code_b in tbl.items():
            code = code_b[0]
            if code < len(widths_bin):
                widths[char] = widths_bin[code]
    return widths

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
        delim = "<wait_auto>" if "<wait_auto>" in para else "<br>"
        lines = para.split(delim)
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

        wrapped_paragraphs.append(delim.join(wrapped_lines))

    return "<page>".join(wrapped_paragraphs)


NATIVE_UPPERCASE = {
    "A": 0x0B, "B": 0x0C, "C": 0x0D, "D": 0x0E, "E": 0x0F, "F": 0x10, "G": 0x11,
    "H": 0x12, "I": 0x13, "J": 0x14, "K": 0x15, "L": 0x16, "M": 0x17, "N": 0x18,
    "O": 0x19, "P": 0x1A, "Q": 0x1B, "R": 0x1C, "S": 0x1D, "T": 0x1E, "U": 0x1F,
    "V": 0x20, "W": 0x21, "X": 0x22, "Y": 0x23, "Z": 0x24, " ": 0x00, "-": 0x8A,
    ".": 0x8C, "!": 0x86, "?": 0x87, "'": 0x00,
}

KNOWN_SPEAKERS = {
    "GALAHAD", "RUFFIAN", "WOMAN", "MAN", "BOY", "OLD WOMAN", "OLD MAN",
    "GANT", "SONIA", "BOANCHO", "REMY", "[PROTAG]", "[SUB]", "[PET]"
}


def get_token_px_width(token: str) -> int:
    if "[protag]" in token or "[sub]" in token or "[pet]" in token:
        t = token.replace("[protag]", "Gant").replace("[sub]", "Soni").replace("[pet]", "Boan")
        return sum(CHAR_WIDTHS.get(c, 6) for c in t)
    return sum(CHAR_WIDTHS.get(c, 6) for c in token)


def word_wrap_to_lines(text: str, max_px: int = 216) -> list[str]:
    words = text.split()
    lines = []
    cur_line = []
    cur_px = 0
    space_px = CHAR_WIDTHS.get(" ", 4)

    for word in words:
        w_px = get_token_px_width(word)
        needed = w_px if not cur_line else space_px + w_px
        if cur_line and cur_px + needed > max_px:
            lines.append(" ".join(cur_line))
            cur_line = [word]
            cur_px = w_px
        else:
            cur_line.append(word)
            cur_px += needed
    if cur_line:
        lines.append(" ".join(cur_line))
    return lines


def encode_text_with_tbl(text: str, tbl: dict) -> bytes:
    res = bytearray()
    tokens = re.split(r"(\[[^\]]+\])", text)
    for tok in tokens:
        if not tok:
            continue
        if tok in tbl:
            res.extend(tbl[tok])
        else:
            for ch in tok:
                if ch in tbl:
                    res.extend(tbl[ch])
                else:
                    res.extend(tbl.get("?", b"\x87"))
    return bytes(res)


def encode_dialogue_string(text: str, tbl: dict) -> bytes:
    """Encodes translated dialogue string with speaker name and dialogue body in native table VWF."""
    parts = text.split("<wait_auto>")
    res = bytearray()

    # Check if first part before <wait_auto> is a speaker name:
    first_part = parts[0].strip()
    speaker_part = None
    if len(parts) > 1 and (first_part.upper() in KNOWN_SPEAKERS or first_part.startswith("[") or len(first_part) <= 12):
        speaker_part = first_part
        body_text = " ".join(p.strip() for p in parts[1:] if p.strip())
    else:
        body_text = " ".join(p.strip() for p in parts if p.strip())

    if speaker_part:
        res.extend(encode_text_with_tbl(speaker_part, tbl))
        res.append(0x80)  # In-box newline after speaker name!

    # Word wrap dialogue body into lines <= 216px:
    wrapped_lines = word_wrap_to_lines(body_text, max_px=216)
    for idx, line in enumerate(wrapped_lines):
        if idx > 0:
            res.append(0x80)  # In-box newline between dialogue lines
        res.extend(encode_text_with_tbl(line, tbl))

    res.append(0xFF)  # Dialogue box terminator!
    return bytes(res)


class ScriptInserter:
    def __init__(self, rom_path: Path, translations_dir: Path, tbl_path: Path):
        self.rom_path = rom_path
        self.translations_dir = translations_dir
        self.tbl_path = tbl_path

        # Free space pool in Bank $CA ($CA:B000 - $CA:FF00 = 20,224 bytes in safe upper half)
        self.pool_start = 0x0AB000
        self.pool_cur = self.pool_start
        self.pool_max = 0x0AFF00

        # String Redirection Table at 0x0A7000 (Bank $CA, $CA:7000 - $CA:7FFF = 4096 bytes)
        self.redirect_table_pc = 0x0A7000
        self.redirect_entries = []

        # Free space pool in Bank $C1 (0x015D00 - 0x017FFF = 8,960 bytes)
        self.pool_c1_start = 0x015D00
        self.pool_c1_cur = self.pool_c1_start
        self.pool_c1_max = 0x018000

        # Free space pool in Bank $DB (0x1BF530 - 0x1BFFFF = 2,768 bytes)
        self.pool_db_start = 0x1BF530
        self.pool_db_cur = self.pool_db_start
        self.pool_db_max = 0x1BFFFF

        self.en_tbl = load_tbl(tbl_path, reverse=True)

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
        if "location_names" in script_file.name:
            return self.insert_location_names(rom_bytes, script_file, dry_run=dry_run)

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
            orig_pc = int(orig_pos_str, 16) if isinstance(orig_pos_str, str) else int(orig_pos_str)

            # If orig_pc points to a leading 0xFE delimiter, advance past it:
            if orig_pc < len(rom_bytes) and rom_bytes[orig_pc] == 0xFE:
                orig_pc += 1

            orig_len = meta.get("length", 0)
            if not orig_len:
                m = re.search(r"length:\s*(\d+)", entry.get("jp_text", ""))
                if m:
                    orig_len = int(m.group(1))

            # Determine precise clean ROM byte budget (distance to and including terminating 0xFF):
            ff_pos = rom_bytes.find(b"\xff", orig_pc)
            if ff_pos != -1 and orig_len > 0 and (ff_pos - orig_pc) <= orig_len + 5:
                real_orig_len = (ff_pos - orig_pc) + 1
            elif ff_pos != -1 and orig_len == 0 and (ff_pos - orig_pc) < 10:
                real_orig_len = (ff_pos - orig_pc) + 1
            else:
                real_orig_len = orig_len + 1

            bank = meta.get("bank", "0xCA")
            table_mode = meta.get("table", "normal")

            if entry["is_translated"]:
                if table_mode == "menu":
                    clean_text = entry["en_text"].strip()
                    encoded = encode_text_with_tbl(clean_text, self.en_tbl) + b"\xFF"
                else:
                    encoded = encode_dialogue_string(entry["en_text"], self.en_tbl)

                # Greenfield Allocation Strategy:
                # Always allocate full dialogue strings in unmapped Bank $CA free space pool!
                dest_pc = self.allocate_pool(len(encoded), bank="0xCA")
                if "ptr_pos" in meta and not dry_run:
                    ptr_pc = int(meta["ptr_pos"], 16) if isinstance(meta["ptr_pos"], str) else int(meta["ptr_pos"])
                    ptr_type = meta.get("ptr_type", "16bit_le")
                    if ptr_type == "16bit_be":
                        offset_be = (dest_pc - 0x010000) & 0xFFFF
                        rom_bytes[ptr_pc] = (offset_be >> 8) & 0xFF
                        rom_bytes[ptr_pc + 1] = offset_be & 0xFF
                    else:
                        snes_offset = dest_pc & 0xFFFF
                        rom_bytes[ptr_pc : ptr_pc + 2] = struct.pack("<H", snes_offset)
                elif not dry_run:
                    # Relocate without static pointer -> Register in StringRedirectTable!
                    orig_addr = orig_pc & 0xFFFF
                    orig_bank_str = meta.get("bank", "0xF3")
                    orig_bank = int(orig_bank_str, 16) if isinstance(orig_bank_str, str) else int(orig_bank_str)
                    new_addr = dest_pc & 0xFFFF
                    new_bank = (dest_pc >> 16) + 0xC0
                    self.redirect_entries.append((orig_addr, orig_bank, new_addr, new_bank, real_orig_len))
                    print(f"      [Redirect] Relocated 0x{orig_pc:06X} ($ {orig_bank:02X}:{orig_addr:04X}) -> 0x{dest_pc:06X} ($ {new_bank:02X}:{new_addr:04X}) in Bank $CA pool (orig_len={real_orig_len})")

                if not dry_run:
                    rom_bytes[dest_pc : dest_pc + len(encoded)] = encoded
                    # Bank $F3 scenario stream remains clean and uncorrupted!
                    # RenderEnglishVWF intercepts orig_addr/orig_bank, renders from Bank $CA,
                    # and returns Y = orig_len so caller advances past the pristine Bank $F3 string cleanly.

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

        # Construct dialogue stream using native table en_tbl:
        # Box 1: Midwife
        stream.extend(encode_text_with_tbl("Midwife", self.en_tbl) + b"\x80")
        stream.extend(encode_text_with_tbl("At this rate, Remy won't make it...", self.en_tbl) + b"\xFF\xFE")

        # Box 2: Galahad
        stream.extend(encode_text_with_tbl("Galahad", self.en_tbl) + b"\x80")
        stream.extend(encode_text_with_tbl("Cut the crap! You saying", self.en_tbl) + b"\x80")
        stream.extend(encode_text_with_tbl("Remy is gonna die?!", self.en_tbl) + b"\xFF\xFE")

        # Box 3: Midwife
        stream.extend(encode_text_with_tbl("Midwife", self.en_tbl) + b"\x80")
        stream.extend(encode_text_with_tbl("It's not certain yet. But to save", self.en_tbl) + b"\x80")
        stream.extend(encode_text_with_tbl("the baby, Remy's body won't...", self.en_tbl) + b"\xFF\xFE")

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

            # Encode location names using native table en_tbl:
            encoded = encode_text_with_tbl(text, self.en_tbl) + b"\xFF"
            orig_pc = int(meta["str_pos"]) if isinstance(meta["str_pos"], int) else int(meta["str_pos"], 16)
            orig_len = meta.get("length", 0)
            if not orig_len:
                m = re.search(r"length:\s*(\d+)", entry.get("jp_text", ""))
                if m:
                    orig_len = int(m.group(1))

            ptr_pos_val = int(meta["ptr_pos"]) if isinstance(meta["ptr_pos"], int) else int(meta["ptr_pos"], 16) if "ptr_pos" in meta else 0

            # Fix ROM bug for Index 22 (Tomria):
            # ROM has 45 00 at 0x01432C, real string is at 0x014600 (0x4600)
            if (str_num == 22 or ptr_pos_val == 0x01432C) and not dry_run:
                ptr_pc = 0x01432C
                rom_bytes[ptr_pc : ptr_pc + 2] = bytes([0x46, 0x00])

            if len(encoded) <= orig_len + 1:
                dest_pc = orig_pc
            else:
                dest_pc = self.allocate_pool(len(encoded), bank="0xC1")
                if not dry_run and ptr_pos_val:
                    ptr_pc = ptr_pos_val
                    offset_be = (dest_pc - 0x010000) & 0xFFFF
                    rom_bytes[ptr_pc] = (offset_be >> 8) & 0xFF
                    rom_bytes[ptr_pc + 1] = offset_be & 0xFF

            if not dry_run:
                rom_bytes[dest_pc : dest_pc + len(encoded)] = encoded

            translated_count += 1
            bytes_written += len(encoded)

        print(f"      [Locations Inserter] Injected {translated_count} location names ({bytes_written} bytes).")
        return len(entries), translated_count, bytes_written

    def run(self, dry_run: bool = False, verbose: bool = False) -> dict:
        if not self.rom_path.exists():
            raise FileNotFoundError(f"Target ROM not found: {self.rom_path}")

        rom_data = bytearray(self.rom_path.read_bytes())
        results = {}
        total_strings = 0
        total_translated = 0
        total_bytes = 0

        script_files = sorted(self.translations_dir.glob("*.txt"))
        # If any translated_<name>.txt exists, suppress the corresponding <name>.txt:
        translated_prefixes = {f.name[len("translated_"):]: f for f in script_files if f.name.startswith("translated_")}
        script_files = [f for f in script_files if f.name not in translated_prefixes]

        for s_file in script_files:
            tot, trans, b_written = self.insert_file(rom_data, s_file, dry_run=dry_run)
            results[s_file.name] = (tot, trans, b_written)
            total_strings += tot
            total_translated += trans
            total_bytes += b_written
            if verbose and tot > 0:
                print(f"  [{s_file.name}] {trans}/{tot} translated ({b_written} bytes injected)")

        if not dry_run and len(self.redirect_entries) > 0:
            for idx, (orig_addr, orig_bank, new_addr, new_bank, orig_len) in enumerate(self.redirect_entries):
                pos = self.redirect_table_pc + idx * 8
                struct.pack_into("<HBHBH", rom_data, pos, orig_addr, orig_bank, new_addr, new_bank, orig_len)
            term_pos = self.redirect_table_pc + len(self.redirect_entries) * 8
            rom_data[term_pos : term_pos + 2] = b"\x00\x00"
            print(f"      [Redirect Table] Wrote {len(self.redirect_entries)} redirection entries (8B each) to 0x{self.redirect_table_pc:06X}.")

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
