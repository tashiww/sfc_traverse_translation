"""
SNES HiROM utilities for Traverse: Starlight & Prairie
"""

import hashlib
import struct
from pathlib import Path

CLEAN_ROM_CRC32 = 0xB5113CCB
CLEAN_ROM_SHA1 = "47d94a325a87fd476a3b1e0850222f359b081998"
HEADER_OFFSET_HIROM = 0xFFC0
CHECKSUM_COMP_OFFSET = 0xFFDC
CHECKSUM_OFFSET = 0xFFDE


def verify_clean_rom(rom_bytes: bytes) -> bool:
    """Verifies that the ROM matches the known clean dump."""
    import zlib
    crc = zlib.crc32(rom_bytes) & 0xFFFFFFFF
    sha1 = hashlib.sha1(rom_bytes).hexdigest()
    return crc == CLEAN_ROM_CRC32 and sha1 == CLEAN_ROM_SHA1


def snes_to_pc(snes_addr: int) -> int:
    """Convert SNES HiROM address ($C00000-$FFFFFF) to PC file offset."""
    bank = (snes_addr >> 16) & 0xFF
    addr = snes_addr & 0xFFFF
    if 0xC0 <= bank <= 0xFF:
        return ((bank - 0xC0) << 16) | addr
    if 0x40 <= bank <= 0x7D:
        return ((bank - 0x40) << 16) | addr
    if 0x00 <= bank <= 0x3F and addr >= 0x8000:
        return (bank << 16) | addr
    raise ValueError(f"Invalid HiROM address: ${snes_addr:06X}")


def pc_to_snes(pc_offset: int, bank_base: int = 0xC0) -> int:
    """Convert PC file offset to SNES HiROM address (defaults to FastROM $C0+)."""
    bank = bank_base + (pc_offset >> 16)
    addr = pc_offset & 0xFFFF
    return (bank << 16) | addr


def fix_snes_checksum(rom_data: bytearray) -> tuple[int, int]:
    """
    Recalculates and updates the SNES HiROM checksum and complement checksum.
    Returns (checksum, complement).
    """
    # Clear checksum fields before calculation
    rom_data[CHECKSUM_COMP_OFFSET:CHECKSUM_COMP_OFFSET + 2] = b"\xFF\xFF"
    rom_data[CHECKSUM_OFFSET:CHECKSUM_OFFSET + 2] = b"\x00\x00"

    # In HiROM, calculate sum over all bytes
    rom_sum = sum(rom_data) & 0xFFFF
    rom_comp = rom_sum ^ 0xFFFF

    struct.pack_into("<HH", rom_data, CHECKSUM_COMP_OFFSET, rom_comp, rom_sum)
    return rom_sum, rom_comp


def load_tbl(tbl_path: Path, reverse: bool = False) -> dict:
    """
    Loads a standard Thingy TBL file.
    If reverse=False: returns {hex_code_str: char}
    If reverse=True: returns {char: hex_code_bytes}
    """
    mapping = {}
    with open(tbl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                if reverse:
                    mapping[v] = bytes.fromhex(k)
                else:
                    mapping[k.lower()] = v
    return mapping
