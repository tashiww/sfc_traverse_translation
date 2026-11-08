#!/usr/bin/env python3
"""
Master Additive Build Pipeline for Traverse: Starlight & Prairie (SNES)
Reconstructs the English translation ROM from the clean Japanese ROM in stages.
"""

import argparse
import datetime
import os
import shutil
import subprocess
import sys
from pathlib import Path

from tools.rom_utils import (
    CLEAN_ROM_CRC32,
    CLEAN_ROM_SHA1,
    fix_snes_checksum,
    verify_clean_rom,
)

ROOT_DIR = Path(__file__).resolve().parent
CLEAN_ROM_NAME = "Traverse - Starlight & Prairie (Japan).sfc"
CLEAN_ROM_PATH = ROOT_DIR / "rom" / CLEAN_ROM_NAME
BUILD_DIR = ROOT_DIR / "build"
TARGET_ROM_PATH = BUILD_DIR / "traverse_en.sfc"
ASAR_PATH = ROOT_DIR / "bin" / "asar"
FLIPS_PATH = ROOT_DIR / "bin" / "flips"
PATCHES_DIR = ROOT_DIR / "patches"


def step_verify_clean_rom() -> bytes:
    print("[1/5] Verifying clean ROM...")
    if not CLEAN_ROM_PATH.exists():
        sys.exit(f"Error: Clean ROM not found at {CLEAN_ROM_PATH}")
    data = CLEAN_ROM_PATH.read_bytes()
    if not verify_clean_rom(data):
        print(f"Warning: Clean ROM does not match expected CRC32 {CLEAN_ROM_CRC32:08X} / SHA1 {CLEAN_ROM_SHA1}.")
    else:
        print("      Clean ROM verified successfully.")
    return data


def step_copy_rom():
    print(f"[2/5] Creating fresh working copy at {TARGET_ROM_PATH.relative_to(ROOT_DIR)}...")
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CLEAN_ROM_PATH, TARGET_ROM_PATH)


def step_apply_asm():
    print("[3/5] Assembling 65816 assembly patches with Asar...")
    main_asm = ROOT_DIR / "asm" / "main.asm"
    if not main_asm.exists():
        print("      No asm/main.asm found, skipping assembly stage.")
        return

    cmd = [str(ASAR_PATH), str(main_asm), str(TARGET_ROM_PATH)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr, file=sys.stderr)
        sys.exit(f"Error: Asar assembly failed with code {res.returncode}")
    if res.stdout.strip():
        print("      " + res.stdout.strip().replace("\n", "\n      "))
    print("      Assembly patches applied successfully.")


def step_insert_scripts():
    print("[4/5] Inserting script translations and tables...")
    from tools.inserter import ScriptInserter, DEFAULT_TABLE
    inserter = ScriptInserter(TARGET_ROM_PATH, ROOT_DIR / "translations", DEFAULT_TABLE)
    stats = inserter.run(dry_run=False, verbose=False)
    print(f"      Processed {stats['total_strings']} strings across {stats['total_files']} files ({stats['total_translated']} translated).")
    if stats['total_translated'] > 0:
        print(f"      Bank $C1 pool: {stats['pool_c1_used']} bytes written.")
        print(f"      Bank $CA pool: {stats['pool_ca_used']} bytes written.")
        if stats.get('pool_db_used', 0) > 0:
            print(f"      Bank $DB pool: {stats['pool_db_used']} bytes written.")


def step_finalize_rom():
    print("[5/5] Recalculating SNES HiROM checksum...")
    data = bytearray(TARGET_ROM_PATH.read_bytes())
    csum, comp = fix_snes_checksum(data)
    TARGET_ROM_PATH.write_bytes(data)
    print(f"      Updated Checksum: 0x{csum:04X}, Complement: 0x{comp:04X}")


def step_create_patches():
    print("[+] Generating release patches...")
    PATCHES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bps_path = PATCHES_DIR / f"traverse_en_{timestamp}.bps"
    ips_path = PATCHES_DIR / f"traverse_en_{timestamp}.ips"

    # Flips BPS
    cmd_bps = [str(FLIPS_PATH), "--create", "--bps", str(CLEAN_ROM_PATH), str(TARGET_ROM_PATH), str(bps_path)]
    res_bps = subprocess.run(cmd_bps, capture_output=True, text=True)
    if res_bps.returncode == 0:
        print(f"      BPS patch created: {bps_path.relative_to(ROOT_DIR)}")

    # Flips IPS
    cmd_ips = [str(FLIPS_PATH), "--create", "--ips", str(CLEAN_ROM_PATH), str(TARGET_ROM_PATH), str(ips_path)]
    res_ips = subprocess.run(cmd_ips, capture_output=True, text=True)
    if res_ips.returncode == 0:
        print(f"      IPS patch created: {ips_path.relative_to(ROOT_DIR)}")


def main():
    parser = argparse.ArgumentParser(description="Traverse: Starlight & Prairie ROM Build Pipeline")
    parser.add_argument("--patch", action="store_true", help="Generate BPS/IPS patches in patches/")
    args = parser.parse_args()

    print("=" * 65)
    print(" Traverse: Starlight & Prairie - Automated Translation Build")
    print("=" * 65)

    step_verify_clean_rom()
    step_copy_rom()
    step_apply_asm()
    step_insert_scripts()
    step_finalize_rom()

    if args.patch:
        step_create_patches()

    print("=" * 65)
    print(f" Build complete! Output ROM: {TARGET_ROM_PATH.relative_to(ROOT_DIR)}")
    print("=" * 65)


if __name__ == "__main__":
    main()
