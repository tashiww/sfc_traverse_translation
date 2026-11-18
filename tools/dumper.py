#!/usr/bin/env python3
"""
Traverse: Starlight & Prairie - Script & Text Dumper
Extracts dialogue scripts and tables using Thingy TBL into tashi_script_editor format.
Supports multi-line dialogue boxes with '# ' per line and 3 table types (normal, menu, prologue).
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

from tools.inserter import parse_script_file
from tools.rom_utils import load_tbl

ROM_PATH = ROOT_DIR / "rom" / "Traverse - Starlight & Prairie (Japan).sfc"
OUTPUT_DIR = ROOT_DIR / "translations"
TABLES_DIR = ROOT_DIR / "tables"

# Known Control Codes in Traverse Text Engine:
# 0xFE 0x00 is in-box line break in the scenario dialogue engine
CONTROL_CODES = {
    bytes([0xFE, 0x00]): "\n",
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

        # 5. Fallback single byte token
        res.append(f"<{b:02X}>")
        i += 1

    return "".join(res)


def is_genuine_dialogue(chunk: bytes, decoded: str) -> bool:
    """Filters out raw event script bytecode chunks from genuine scenario dialogue."""
    if len(chunk) > 450:
        return False

    clean = re.sub(r"<[^>]+>|\[[^\]]+\]", "", decoded).strip()
    jp_chars = len(re.findall(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\u3001\u3002\uFF01\uFF1F\u2026\u300C\u300D\u30FB\u30FC★☆○△]", clean))
    if jp_chars < 3 and not any(tag in decoded for tag in ("[protag]", "[sub]", "[pet]")):
        return False

    lines = [l.strip() for l in decoded.split("\n") if l.strip()]
    if not lines:
        return False

    has_genuine_line = False
    for l in lines:
        l_clean = re.sub(r"<[^>]+>|\[[^\]]+\]", "", l).strip()
        l_jp = len(re.findall(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\u3001\u3002\uFF01\uFF1F\u2026\u300C\u300D\u30FB\u30FC★☆○△]", l_clean))
        if l_jp >= 2 and (l_jp / max(1, len(l_clean))) >= 0.45:
            has_genuine_line = True
            break
        if any(kw in l for kw in ("手に入れた！", "仲間になった！", "戻した！", "ダスな。", "[protag]", "[sub]", "[pet]")):
            has_genuine_line = True
            break

    if not has_genuine_line:
        return False

    ascii_chars = len(re.findall(r"[A-Za-z0-9]", clean))
    if ascii_chars > 25 and (ascii_chars / max(1, len(clean))) > 0.45:
        return False

    return True


KNOWN_SPEAKERS_SET = {
    "ガラハド", "乱暴者", "女", "男", "男の子", "女の子", "お婆さん", "おじさん",
    "おじいさん", "おばさん", "ばあや", "じじょ", "じいさん", "村人", "町の人",
    "旅人", "商人", "兵士", "隊長", "受付", "悪魔", "侍女", "神官", "王",
    "王子", "王女", "女王", "しゃちょう", "店主", "マスター", "サム", "ナナ",
    "ボナルド", "バルモア", "ベベル", "リンクル", "フェリアラ", "ゴンビエール",
    "マルカリの花", "[protag]", "[sub]", "[pet]"
}


def trim_chunk_to_speaker(chunk: bytes, tbl: dict = None) -> tuple[bytes, int]:
    """Trims leading event script opcode bytes so chunk starts cleanly at speaker name."""
    fe = chunk.find(b"\xfe\x00")
    if fe == -1 or fe <= 6:
        return chunk, 0

    start_p = max(0, fe - 14)
    for p in range(start_p, fe):
        dec = decode_string(chunk[p:fe], tbl)
        if dec in KNOWN_SPEAKERS_SET:
            return chunk[p:], p

    return chunk, 0


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
            "table": "normal",
        })

    with open(out_file, "w", encoding="utf-8") as f:
        for s in strings:
            meta = {
                "str_num": s["str_num"],
                "bank": s["bank"],
                "ptr_pos": s["ptr_pos_hex"],
                "str_pos": s["str_pos_hex"],
                "length": s["length"],
                "table": s["table"],
            }
            f.write(json.dumps(meta) + "\n")
            for jp_line in s["text"].split("\n"):
                f.write(f"#{jp_line}\n")
            f.write("\n")

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
                    "table": "menu",
                }
                f.write(json.dumps(meta) + "\n")
                for jp_line in decoded.split("\n"):
                    f.write(f"#{jp_line}\n")
                f.write("\n")
                str_idx += 1
                total += 1

    print(f"Dumped {total} item/equipment strings to {out_file.relative_to(ROOT_DIR)}")


def dump_location_names(data: bytes, out_file: Path, tbl: dict = None):
    """
    Dumps the 60 world map location names from Bank $C1 (0x014300 / 0x01455A).
    Formatted for tashi_script_editor with JSON metadata, #JP comments, length & max_len.
    Translates Index 22 ('トムリアの街' -> 'Tomria') as verified in-game working location.
    """
    ptr_table_base = 0x014300
    num_entries = 60

    # Preserve existing translations if file exists
    existing_tl = {}
    if out_file.exists():
        entries = parse_script_file(out_file)
        for e in entries:
            if e["is_translated"]:
                str_num = e["meta"].get("str_num")
                if str_num is not None:
                    existing_tl[str_num] = e["en_text"]

    with open(out_file, "w", encoding="utf-8") as f:
        for i in range(num_entries):
            ptr_pos = ptr_table_base + i * 2
            b0 = data[ptr_pos]
            b1 = data[ptr_pos + 1]
            offset = (b0 << 8) | b1
            # Entry 22 bugfix: 0x4500 is a ROM typo, real string is at 0x4600
            if i == 22 and offset == 0x4500:
                offset = 0x4600

            str_pos = 0x010000 + offset
            end = data.find(b"\xFF", str_pos)
            raw = data[str_pos:end]

            # Decode characters
            jp_text = ""
            for b in raw:
                hk = f"{b:02x}"
                if tbl and hk in tbl:
                    jp_text += tbl[hk]
                else:
                    jp_text += f"[{hex(b)}]"

            max_len = 16

            meta = {
                "str_num": i,
                "prefix": "",
                "ptr_pos": ptr_pos,
                "str_pos": str_pos,
                "ptr_hex": f"0x{ptr_pos:06X}",
                "str_hex": f"0x{str_pos:06X}",
                "length": len(raw),
                "max_len": max_len,
                "table": "menu",
                "repoint": False,
                "ptr_type": "16bit_be",
            }

            f.write(json.dumps(meta) + "\n")
            f.write(f"#{jp_text} (length: {len(raw)}, max_len: {max_len})\n")

            tl = existing_tl.get(i, "Tomria" if i == 22 else "")
            if tl:
                f.write(f"{tl}\n")
            f.write("\n")

    print(f"Dumped {num_entries} location names to {out_file.relative_to(ROOT_DIR)} (Index 22 -> Tomria)")


def dump_prologue(data: bytes, out_file: Path, tbl: dict = None):
    """
    Dumps all 68 prologue dialogue boxes from Bank $DB (0x1BAA0F - 0x1BB7CA).
    Includes the birth drama Part 1, the 12 Goddess personality survey questions,
    interactive 3-choice options (<choice_menu>), Goddess blessings, and birth drama Part 2.
    Boxes are cleanly delimited by \\xFF\\xFE, \\xFF\\x01, and \\xFF\\xFF.
    Speaker name appears on Line 1, dialogue lines on Line 2+.
    Sets table to 'prologue'.
    """
    pos = 0x1BAA0F
    end_limit = 0x1BB7CA

    # Load existing translations if present
    existing_tl = {}
    if out_file.exists():
        old_entries = parse_script_file(out_file)
        for e in old_entries:
            if e["is_translated"]:
                str_pos = e["meta"].get("str_pos")
                if str_pos:
                    existing_tl[str_pos.lower()] = e["en_text"]

    boxes = []
    cur = pos
    box_idx = 0

    while cur < end_limit:
        cand = []
        for term_bytes, term_type in [(b"\xff\xfe", "<end_box>"), (b"\xff\x01", "<choice_menu>"), (b"\xff\xff", "<end_scene>")]:
            m = data.find(term_bytes, cur)
            if m != -1 and m < end_limit:
                cand.append((m, term_bytes, term_type))
        if not cand:
            break
        cand.sort(key=lambda x: x[0])
        box_end, term_bytes, term_type = cand[0]
        box_bytes = data[cur : box_end + 1]
        lines = [l for l in data[cur : box_end].split(b"\xff") if l]
        dec_lines = [decode_string(l, tbl).rstrip() for l in lines if l]

        pc_hex = f"0x{cur:06X}".lower()
        tl = existing_tl.get(pc_hex, "")

        boxes.append({
            "str_num": box_idx,
            "bank": "0xDB",
            "str_pos": f"0x{cur:06X}",
            "length": len(box_bytes),
            "term": term_type,
            "table": "prologue",
            "lines": dec_lines,
            "translation": tl,
        })
        box_idx += 1
        cur = box_end + 2

    # Standard English translations for all 68 prologue cutscene boxes:
    default_tl = [
        # 00 - 10: Birth Scene Part 1
        "Midwife\nAt this rate, Remy won't make it...",
        "Galahad\nCut the crap! You saying\nRemy is gonna die?!",
        "Midwife\nNothing is certain yet.\nBut to save the baby,\nRemy's body won't hold out...",
        "Galahad\nDon't be ridiculous! Save Remy!\nDo whatever it takes to save Remy!",
        "Midwife\n...So then, are you telling me\nto kill the unborn child?",
        "Galahad\nN-No, I'm not saying that!\nB-But... if Remy dies...\nI couldn't bear it...",
        "Midwife\nThe unborn child is blameless.\nGalahad, don't think foolish thoughts...",
        "Midwife\nZzz... Zzz... Snoore...",
        "Galahad\nHey! Old woman! Don't you dare\ndoze off at a time like this!\nHuh? What's going on? Even I'm feeling\nso sleepy...",
        "Galahad\nZzz... *snort*... *wheeze*...\nzzz...",
        "Gentle Voice\n[protag].\nChild of Remy, soon to be born.\nYour name is [protag].\nYou are the reincarnation of\nthe Archangel Borsark.",

        # 11 - 12: Gentle Voice introduces 12 Goddesses
        "Gentle Voice\nWe, the Twelve Goddesses of Fate,\nshall watch over and protect your life.\nCome, [protag].\nNow, answer our questions.",
        "Gentle Voice\nWe wish to know what kind of person\nyou will grow up to be.",

        # 13 - 15: Rosanne (Fire)
        "Rosanne\nI am Rosanne, Goddess of Fire.\nAnswer my question.\nYour home is engulfed in flames.\nYou can save only one person.",
        "Now, who will you save?\n  Family\n  Lover\n  Best Friend",
        "Rosanne\nHehe... I see.\nI understand. May your life be blessed\nwith great fortune, [protag].",

        # 16 - 19: Majorca (Water)
        "Majorca\nI am Majorca, Goddess of Water.\nAnswer my question.\nLost in the desert, your throat is\nparched with burning thirst.",
        "Majorca\nYet only a single drop of water\nremains in your canteen.",
        "Now, what will you do?\n  Drink it all now\n  Endure a little longer\n  Take just a single sip",
        "Majorca\nHehe... I see.\nI understand. May your life be blessed\nwith great fortune, [protag].",

        # 20 - 22: Chanii (Earth)
        "Chanii\nI am Chanii, Goddess of Earth.\nAnswer my question.",
        "Among all the blessings of the earth,\nwhich do you consider most wonderful?\n  Lush nature\n  Ores and mineral resources\n  Bountiful food of all kinds",
        "Chanii\nHehe... I see.\nI understand. May your life be blessed\nwith great fortune, [protag].",

        # 23 - 25: Gloria (Sky)
        "Gloria\nI am Gloria, Goddess of the Sky.\nAnswer my question.\nAs you are summoned to the heavens,\nyou look up at the sky.",
        "At that moment, what kind of sky\ndo you wish to behold?\n  A clear, cloudless blue sky\n  An overcast sky ready to rain\n  A raging thunderstorm",
        "Gloria\nHehe... I see.\nI understand. May your life be blessed\nwith great fortune, [protag].",

        # 26 - 28: Jeanne (Wind)
        "Jeanne\nI am Jeanne, Goddess of Wind.\nAnswer my question.\nThe wind has carried happiness to you.",
        "From which direction do you believe\nthat wind blew?\n  From the east\n  From the west\n  From the south",
        "Jeanne\nHehe... I see.\nI understand. May your life be blessed\nwith great fortune, [protag].",

        # 29 - 32: Isabella (Forest)
        "Isabella\nI am Isabella, Goddess of Forests.\nAnswer my question.\nYou are lost deep within the forest.",
        "Isabella\nBefore your eyes lie three paths.",
        "Which path will you take?\n  A bright, clear path\n  A steep, perilous shortcut\n  An untrodden beast trail",
        "Isabella\nHehe... I see.\nI understand. May your life be blessed\nwith great fortune, [protag].",

        # 33 - 35: Christina (Light)
        "Christina\nI am Christina, Goddess of Light.\nAnswer my question.\nLight and shadow--the world cannot\nexist without both.",
        "Which of the two draws your heart?\n  Light\n  Shadow\n  Neither",
        "Christina\nHehe... I see.\nI understand. May your life be blessed\nwith great fortune, [protag].",

        # 36 - 38: Natasia (Darkness)
        "Natasia\nI am Natasia, Goddess of Darkness.\nAnswer my question.\nAlone in the pitch-black darkness,\nwhat crosses your mind?",
        "What do you think of?\n  The fear of solitude\n  The solace of tranquility\n  Nothing at all",
        "Natasia\nHehe... I see.\nI understand. May your life be blessed\nwith great fortune, [protag].",

        # 39 - 41: Elena (Beauty)
        "Elena\nI am Elena, Goddess of Beauty.\nAnswer my question.",
        "What is the true essence of beauty\nto you?\n  Beauty is eternal\n  Beauty is fleeting\n  Beauty cannot be put into words",
        "Elena\nHehe... I see.\nI understand. May your life be blessed\nwith great fortune, [protag].",

        # 42 - 44: Elizabeth (Wisdom)
        "Elizabeth\nI am Elizabeth, Goddess of Wisdom.\nAnswer my question.",
        "Among these three, who do you believe\npossesses the greatest wisdom?\n  One who hides true intent\n  One who deceives without guilt\n  One who puts others before self",
        "Elizabeth\nHehe... I see.\nI understand. May your life be blessed\nwith great fortune, [protag].",

        # 45 - 48: Cynthia (Love)
        "Cynthia\nI am Cynthia, Goddess of Love.\nAnswer my question.\nYou have found someone you truly love.",
        "Cynthia\nTo spend more time together, your love\nasks you to sacrifice one thing in life.",
        "What would you sacrifice?\n  Time spent working\n  Time spent on hobbies\n  Time spent with friends",
        "Cynthia\nHehe... I see.\nI understand. May your life be blessed\nwith great fortune, [protag].",

        # 49 - 51: Jordy (Fate)
        "Jordy\nI am Jordy, Goddess of Fate.\nAnswer my question.",
        "Which of these words do you cherish\nmost of all?\n  Perseverance\n  Miracle\n  Hope",
        "Jordy\nHehe... I see.\nI understand. May your life be blessed\nwith great fortune, [protag].",

        # 52 - 53: Gentle Voice Sendoff
        "Gentle Voice\n[protag]. We look forward to\nwatching you grow into a splendid soul,\nand we shall always watch over you.",
        "Gentle Voice\nNow, receive your life in this world.\nAnd journey forth into your new life!",

        # 54 - 67: Birth Scene Part 2
        "Galahad\nUrrgh... Urrggghhh...",
        "Galahad\nWhoa! What in the world is this?!\nThe baby's already born!",
        "Galahad\nHey, old lady, wake up!",
        "Midwife\nGood gracious!",
        "Midwife\nGalahad, you did quite a job yourself.\nCare to take over my trade?",
        "Galahad\nQuit your nonsense! I didn't do anything!\nThat brat was born all on its own!",
        "Galahad\nThis baby... is it really human?",
        "Midwife\n...More importantly, look at Remy.",
        "Galahad\nWhat? H-Hey! Remy!!\nRemy, stay with me! Hold on!",
        "Midwife\n...It's too late. She has been taken\nto heaven. But look, you've been blessed\nwith such a precious new life.\nYou have to stay strong.",
        "Galahad\nWhat did you say?! This brat is precious?!\nThis monster that killed my Remy?!\n...This thing is a demon!\nA demon's child!",
        "Midwife\nHow could you say such a terrible thing?!\nBlaming such a sweet little baby...\nHave some decency!",
        "Galahad\nShut up! This... this thing...\nIt's hard to curse without a name.\n...Fine. [protag].\n[protag]!",
        "Galahad\nI just came up with the perfect name\nfor this demon child!\nI will never acknowledge this thing as\nmy child! It's the demon that killed Remy!",
    ]

    with open(out_file, "w", encoding="utf-8") as f:
        for idx, b in enumerate(boxes):
            meta = {
                "str_num": b["str_num"],
                "bank": b["bank"],
                "str_pos": b["str_pos"],
                "length": b["length"],
                "term": b["term"],
                "table": b["table"],
            }
            f.write(json.dumps(meta) + "\n")
            for jl in b["lines"]:
                f.write(f"#{jl}\n")
            tl = default_tl[idx] if idx < len(default_tl) else ""
            if b["translation"] and "\n" in b["translation"]:
                tl = b["translation"]
            if tl:
                for el in tl.split("\n"):
                    f.write(f"{el}\n")
            f.write("\n")

    print(f"Dumped {len(boxes)} dialogue boxes to {out_file.relative_to(ROOT_DIR)} with table 'prologue'.")
    return len(boxes)


def dump_dialogue_bank(data: bytes, bank_num: int, out_file: Path, tbl: dict = None):
    """
    Dumps dialogue strings from scenario Banks $F1-$F9.
    Filters bytecode chunks cleanly and formats multi-line dialogue boxes with '# ' per line.
    Preserves existing translations, converting any <wait_auto> to newline.
    """
    bank_off = bank_num * 0x10000
    bank_data = data[bank_off : bank_off + 65536]
    bank_snes = 0xC0 + bank_num

    # Load existing translations if present to preserve translator work:
    existing_translations = {}
    import subprocess
    import tempfile

    # First check git HEAD:
    try:
        git_rel = out_file.relative_to(ROOT_DIR)
        git_res = subprocess.run(["git", "show", f"HEAD:{git_rel}"], capture_output=True, text=True)
        if git_res.returncode == 0 and git_res.stdout:
            with tempfile.NamedTemporaryFile("w", delete=False) as tf:
                tf.write(git_res.stdout)
                tf_p = Path(tf.name)
            for e in parse_script_file(tf_p):
                if e["is_translated"]:
                    pos = e["meta"].get("str_pos")
                    if pos:
                        existing_translations[pos.lower()] = e["en_text"]
    except Exception:
        pass

    if out_file.exists():
        old_entries = parse_script_file(out_file)
        for e in old_entries:
            if e["is_translated"]:
                pos = e["meta"].get("str_pos")
                if pos:
                    existing_translations[pos.lower()] = e["en_text"]

    strings = []
    i = 0
    str_idx = 0
    while i < len(bank_data) - 5:
        end = bank_data.find(b"\xFF", i)
        if end == -1:
            break
        raw_chunk = bank_data[i:end]
        if len(raw_chunk) >= 5:
            chunk, trim_off = trim_chunk_to_speaker(raw_chunk, tbl)
            prefixes = sum(chunk.count(x) for x in (b"\xFB", b"\xFC", b"\xFD"))
            if prefixes >= 2 or b"\xFE\x00" in chunk:
                decoded = decode_string(chunk, tbl)
                if is_genuine_dialogue(chunk, decoded):
                    pc = bank_off + i + trim_off
                    pc_hex = f"0x{pc:06X}".lower()
                    en_tl = existing_translations.get(pc_hex, "")
                    if en_tl:
                        en_tl = en_tl.replace("<wait_auto>", "\n")
                    strings.append({
                        "str_num": str_idx,
                        "bank": f"0x{bank_snes:02X}",
                        "str_pos": f"0x{pc:06X}",
                        "length": len(chunk),
                        "table": "normal",
                        "text": decoded,
                        "translation": en_tl,
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
                "table": s["table"],
            }
            f.write(json.dumps(meta) + "\n")
            for jp_line in s["text"].split("\n"):
                f.write(f"#{jp_line}\n")
            if s["translation"]:
                for en_line in s["translation"].split("\n"):
                    f.write(f"{en_line}\n")
            f.write("\n")

    preserved_count = sum(1 for s in strings if s["translation"])
    print(f"Dumped {len(strings)} strings from Bank ${bank_snes:02X} to {out_file.relative_to(ROOT_DIR)} (preserved {preserved_count} translations)")
    return len(strings)


def main():
    parser = argparse.ArgumentParser(description="Traverse Script Dumper")
    parser.add_argument("--all", action="store_true", help="Dump all scenario dialogue banks ($F1-$F9) and prologue")
    parser.add_argument("--prologue", action="store_true", help="Dump Bank $DB prologue cutscene")
    parser.add_argument("--locations", action="store_true", help="Dump location names table")
    parser.add_argument("--items", action="store_true", help="Dump item tables")
    parser.add_argument("--c1", action="store_true", help="Dump Bank $C1 battle/system strings")
    args = parser.parse_args()

    if not ROM_PATH.exists():
        print(f"Error: ROM not found at {ROM_PATH}")
        return

    data = ROM_PATH.read_bytes()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    tbl_path = TABLES_DIR / "ja_tbl.tbl"
    tbl = load_tbl(tbl_path) if tbl_path.exists() else None

    # 1. Dump prologue cutscene
    if args.prologue or args.all:
        dump_prologue(data, OUTPUT_DIR / "dialogue_prologue.txt", tbl)

    # 2. Dump Bank $C1 battle/system strings
    if args.c1:
        dump_bank_c1_battle_strings(data, OUTPUT_DIR / "dialogue_bank_C1.txt", tbl)

    # 3. Dump item tables
    if args.items:
        dump_item_tables(data, OUTPUT_DIR / "items.txt", tbl)

    # 4. Dump location names table
    if args.locations:
        dump_location_names(data, OUTPUT_DIR / "location_names.txt", tbl)

    # 5. Dump scenario dialogue banks
    if args.all:
        total = 0
        for b in range(0x31, 0x3A):
            bank_snes = 0xC0 + b
            cnt = dump_dialogue_bank(data, b, OUTPUT_DIR / f"dialogue_bank_{bank_snes:02X}.txt", tbl)
            total += cnt
        print(f"Total scenario dialogue strings dumped: {total}")


if __name__ == "__main__":
    main()
