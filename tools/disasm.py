#!/usr/bin/env python3
"""
Comprehensive 65816 Disassembler for SNES HiROM / LoROM
"""

import sys

# Addressing modes:
# 'imp': implied/accumulator (0 bytes operand)
# 'imm_m': immediate 8-bit or 16-bit depending on M flag
# 'imm_x': immediate 8-bit or 16-bit depending on X flag
# 'imm_8': immediate 8-bit always (e.g. REP, SEP)
# 'dp': direct page $dd (1 byte)
# 'dp_x': direct page indexed $dd,X (1 byte)
# 'dp_y': direct page indexed $dd,Y (1 byte)
# 'dp_ind': direct page indirect ($dd) (1 byte)
# 'dp_ind_long': direct page indirect long [$dd] (1 byte)
# 'dp_ind_x': direct page indexed indirect ($dd,X) (1 byte)
# 'dp_ind_y': direct page indirect indexed ($dd),Y (1 byte)
# 'dp_ind_long_y': direct page indirect long indexed [$dd],Y (1 byte)
# 'sr': stack relative $dd,S (1 byte)
# 'sr_ind_y': stack relative indirect indexed ($dd,S),Y (1 byte)
# 'abs': absolute $aaaa (2 bytes)
# 'abs_x': absolute indexed $aaaa,X (2 bytes)
# 'abs_y': absolute indexed $aaaa,Y (2 bytes)
# 'abs_ind': absolute indirect ($aaaa) (2 bytes)
# 'abs_ind_x': absolute indexed indirect ($aaaa,X) (2 bytes)
# 'abs_long': absolute long $bbbaaaa (3 bytes)
# 'abs_long_x': absolute long indexed $bbbaaaa,X (3 bytes)
# 'abs_long_ind': absolute indirect long [$aaaa] (2 bytes)
# 'rel_8': relative 8-bit (1 byte)
# 'rel_16': relative 16-bit (2 bytes)
# 'block': block move $src, $dst (2 bytes)

TABLE = {
    0x00: ("BRK", "imm_8"),
    0x01: ("ORA", "dp_ind_x"),
    0x02: ("COP", "imm_8"),
    0x03: ("ORA", "sr"),
    0x04: ("TSB", "dp"),
    0x05: ("ORA", "dp"),
    0x06: ("ASL", "dp"),
    0x07: ("ORA", "dp_ind_long"),
    0x08: ("PHP", "imp"),
    0x09: ("ORA", "imm_m"),
    0x0A: ("ASL", "imp"),
    0x0B: ("PHD", "imp"),
    0x0C: ("TSB", "abs"),
    0x0D: ("ORA", "abs"),
    0x0E: ("ASL", "abs"),
    0x0F: ("ORA", "abs_long"),
    0x10: ("BPL", "rel_8"),
    0x11: ("ORA", "dp_ind_y"),
    0x12: ("ORA", "dp_ind"),
    0x13: ("ORA", "sr_ind_y"),
    0x14: ("TRB", "dp"),
    0x15: ("ORA", "dp_x"),
    0x16: ("ASL", "dp_x"),
    0x17: ("ORA", "dp_ind_long_y"),
    0x18: ("CLC", "imp"),
    0x19: ("ORA", "abs_y"),
    0x1A: ("INC", "imp"),
    0x1B: ("TCS", "imp"),
    0x1C: ("TRB", "abs"),
    0x1D: ("ORA", "abs_x"),
    0x1E: ("ASL", "abs_x"),
    0x1F: ("ORA", "abs_long_x"),
    0x20: ("JSR", "abs"),
    0x21: ("AND", "dp_ind_x"),
    0x22: ("JSL", "abs_long"),
    0x23: ("AND", "sr"),
    0x24: ("BIT", "dp"),
    0x25: ("AND", "dp"),
    0x26: ("ROL", "dp"),
    0x27: ("AND", "dp_ind_long"),
    0x28: ("PLP", "imp"),
    0x29: ("AND", "imm_m"),
    0x2A: ("ROL", "imp"),
    0x2B: ("PLD", "imp"),
    0x2C: ("BIT", "abs"),
    0x2D: ("AND", "abs"),
    0x2E: ("ROL", "abs"),
    0x2F: ("AND", "abs_long"),
    0x30: ("BMI", "rel_8"),
    0x31: ("AND", "dp_ind_y"),
    0x32: ("AND", "dp_ind"),
    0x33: ("AND", "sr_ind_y"),
    0x34: ("BIT", "dp_x"),
    0x35: ("AND", "dp_x"),
    0x36: ("ROL", "dp_x"),
    0x37: ("AND", "dp_ind_long_y"),
    0x38: ("SEC", "imp"),
    0x39: ("AND", "abs_y"),
    0x3A: ("DEC", "imp"),
    0x3B: ("TSC", "imp"),
    0x3C: ("BIT", "abs_x"),
    0x3D: ("AND", "abs_x"),
    0x3E: ("ROL", "abs_x"),
    0x3F: ("AND", "abs_long_x"),
    0x40: ("RTI", "imp"),
    0x41: ("EOR", "dp_ind_x"),
    0x42: ("WDM", "imm_8"),
    0x43: ("EOR", "sr"),
    0x44: ("MVP", "block"),
    0x45: ("EOR", "dp"),
    0x46: ("LSR", "dp"),
    0x47: ("EOR", "dp_ind_long"),
    0x48: ("PHA", "imp"),
    0x49: ("EOR", "imm_m"),
    0x4A: ("LSR", "imp"),
    0x4B: ("PHK", "imp"),
    0x4C: ("JMP", "abs"),
    0x4D: ("EOR", "abs"),
    0x4E: ("LSR", "abs"),
    0x4F: ("EOR", "abs_long"),
    0x50: ("BVC", "rel_8"),
    0x51: ("EOR", "dp_ind_y"),
    0x52: ("EOR", "dp_ind"),
    0x53: ("EOR", "sr_ind_y"),
    0x54: ("MVN", "block"),
    0x55: ("EOR", "dp_x"),
    0x56: ("LSR", "dp_x"),
    0x57: ("EOR", "dp_ind_long_y"),
    0x58: ("CLI", "imp"),
    0x59: ("EOR", "abs_y"),
    0x5A: ("PHY", "imp"),
    0x5B: ("TCD", "imp"),
    0x5C: ("JML", "abs_long"),
    0x5D: ("EOR", "abs_x"),
    0x5E: ("LSR", "abs_x"),
    0x5F: ("EOR", "abs_long_x"),
    0x60: ("RTS", "imp"),
    0x61: ("ADC", "dp_ind_x"),
    0x62: ("PER", "rel_16"),
    0x63: ("ADC", "sr"),
    0x64: ("STZ", "dp"),
    0x65: ("ADC", "dp"),
    0x66: ("ROR", "dp"),
    0x67: ("ADC", "dp_ind_long"),
    0x68: ("PLA", "imp"),
    0x69: ("ADC", "imm_m"),
    0x6A: ("ROR", "imp"),
    0x6B: ("RTL", "imp"),
    0x6C: ("JMP", "abs_ind"),
    0x6D: ("ADC", "abs"),
    0x6E: ("ROR", "abs"),
    0x6F: ("ADC", "abs_long"),
    0x70: ("BVS", "rel_8"),
    0x71: ("ADC", "dp_ind_y"),
    0x72: ("ADC", "dp_ind"),
    0x73: ("ADC", "sr_ind_y"),
    0x74: ("STZ", "dp_x"),
    0x75: ("ADC", "dp_x"),
    0x76: ("ROR", "dp_x"),
    0x77: ("ADC", "dp_ind_long_y"),
    0x78: ("SEI", "imp"),
    0x79: ("ADC", "abs_y"),
    0x7A: ("PLY", "imp"),
    0x7B: ("TDC", "imp"),
    0x7C: ("JMP", "abs_ind_x"),
    0x7D: ("ADC", "abs_x"),
    0x7E: ("ROR", "abs_x"),
    0x7F: ("ADC", "abs_long_x"),
    0x80: ("BRA", "rel_8"),
    0x81: ("STA", "dp_ind_x"),
    0x82: ("BRL", "rel_16"),
    0x83: ("STA", "sr"),
    0x84: ("STY", "dp"),
    0x85: ("STA", "dp"),
    0x86: ("STX", "dp"),
    0x87: ("STA", "dp_ind_long"),
    0x88: ("DEY", "imp"),
    0x89: ("BIT", "imm_m"),
    0x8A: ("TXA", "imp"),
    0x8B: ("PHB", "imp"),
    0x8C: ("STY", "abs"),
    0x8D: ("STA", "abs"),
    0x8E: ("STX", "abs"),
    0x8F: ("STA", "abs_long"),
    0x90: ("BCC", "rel_8"),
    0x91: ("STA", "dp_ind_y"),
    0x92: ("STA", "dp_ind"),
    0x93: ("STA", "sr_ind_y"),
    0x94: ("STY", "dp_x"),
    0x95: ("STA", "dp_x"),
    0x96: ("STX", "dp_y"),
    0x97: ("STA", "dp_ind_long_y"),
    0x98: ("TYA", "imp"),
    0x99: ("STA", "abs_y"),
    0x9A: ("TXS", "imp"),
    0x9B: ("TXY", "imp"),
    0x9C: ("STZ", "abs"),
    0x9D: ("STA", "abs_x"),
    0x9E: ("STZ", "abs_x"),
    0x9F: ("STA", "abs_long_x"),
    0xA0: ("LDY", "imm_x"),
    0xA1: ("LDA", "dp_ind_x"),
    0xA2: ("LDX", "imm_x"),
    0xA3: ("LDA", "sr"),
    0xA4: ("LDY", "dp"),
    0xA5: ("LDA", "dp"),
    0xA6: ("LDX", "dp"),
    0xA7: ("LDA", "dp_ind_long"),
    0xA8: ("TAY", "imp"),
    0xA9: ("LDA", "imm_m"),
    0xAA: ("TAX", "imp"),
    0xAB: ("PLB", "imp"),
    0xAC: ("LDY", "abs"),
    0xAD: ("LDA", "abs"),
    0xAE: ("LDX", "abs"),
    0xAF: ("LDA", "abs_long"),
    0xB0: ("BCS", "rel_8"),
    0xB1: ("LDA", "dp_ind_y"),
    0xB2: ("LDA", "dp_ind"),
    0xB3: ("LDA", "sr_ind_y"),
    0xB4: ("LDY", "dp_x"),
    0xB5: ("LDA", "dp_x"),
    0xB6: ("LDX", "dp_y"),
    0xB7: ("LDA", "dp_ind_long_y"),
    0xB8: ("CLV", "imp"),
    0xB9: ("LDA", "abs_y"),
    0xBA: ("TSX", "imp"),
    0xBB: ("TYX", "imp"),
    0xBC: ("LDY", "abs_x"),
    0xBD: ("LDA", "abs_x"),
    0xBE: ("LDX", "abs_y"),
    0xBF: ("LDA", "abs_long_x"),
    0xC0: ("CPY", "imm_x"),
    0xC1: ("CMP", "dp_ind_x"),
    0xC2: ("REP", "imm_8"),
    0xC3: ("CMP", "sr"),
    0xC4: ("CPY", "dp"),
    0xC5: ("CMP", "dp"),
    0xC6: ("DEC", "dp"),
    0xC7: ("CMP", "dp_ind_long"),
    0xC8: ("INY", "imp"),
    0xC9: ("CMP", "imm_m"),
    0xCA: ("DEX", "imp"),
    0xCB: ("WAI", "imp"),
    0xCC: ("CPY", "abs"),
    0xCD: ("CMP", "abs"),
    0xCE: ("DEC", "abs"),
    0xCF: ("CMP", "abs_long"),
    0xD0: ("BNE", "rel_8"),
    0xD1: ("CMP", "dp_ind_y"),
    0xD2: ("CMP", "dp_ind"),
    0xD3: ("CMP", "sr_ind_y"),
    0xD4: ("PEI", "dp"),
    0xD5: ("CMP", "dp_x"),
    0xD6: ("DEC", "dp_x"),
    0xD7: ("CMP", "dp_ind_long_y"),
    0xD8: ("CLD", "imp"),
    0xD9: ("CMP", "abs_y"),
    0xDA: ("PHX", "imp"),
    0xDB: ("STP", "imp"),
    0xDC: ("JML", "abs_long_ind"),
    0xDD: ("CMP", "abs_x"),
    0xDE: ("DEC", "abs_x"),
    0xDF: ("CMP", "abs_long_x"),
    0xE0: ("CPX", "imm_x"),
    0xE1: ("SBC", "dp_ind_x"),
    0xE2: ("SEP", "imm_8"),
    0xE3: ("SBC", "sr"),
    0xE4: ("CPX", "dp"),
    0xE5: ("SBC", "dp"),
    0xE6: ("INC", "dp"),
    0xE7: ("SBC", "dp_ind_long"),
    0xE8: ("INX", "imp"),
    0xE9: ("SBC", "imm_m"),
    0xEA: ("NOP", "imp"),
    0xEB: ("XBA", "imp"),
    0xEC: ("CPX", "abs"),
    0xED: ("SBC", "abs"),
    0xEE: ("INC", "abs"),
    0xEF: ("SBC", "abs_long"),
    0xF0: ("BEQ", "rel_8"),
    0xF1: ("SBC", "dp_ind_y"),
    0xF2: ("SBC", "dp_ind"),
    0xF3: ("SBC", "sr_ind_y"),
    0xF4: ("PEA", "abs"),
    0xF5: ("SBC", "dp_x"),
    0xF6: ("INC", "dp_x"),
    0xF7: ("SBC", "dp_ind_long_y"),
    0xF8: ("SED", "imp"),
    0xF9: ("SBC", "abs_y"),
    0xFA: ("PLX", "imp"),
    0xFB: ("XCE", "imp"),
    0xFC: ("JSR", "abs_ind_x"),
    0xFD: ("SBC", "abs_x"),
    0xFE: ("INC", "abs_x"),
    0xFF: ("SBC", "abs_long_x")
}

def format_instruction(rom_bytes, cur_pc, m_flag, x_flag):
    b = rom_bytes[cur_pc]
    mnemonic, mode = TABLE[b]
    
    # Determine length and formatting
    if mode == "imp":
        length = 1
        operand_str = ""
    elif mode == "imm_m":
        if m_flag:
            length = 2
            val = rom_bytes[cur_pc + 1]
            operand_str = f"#${val:02X}"
        else:
            length = 3
            val = rom_bytes[cur_pc + 1] | (rom_bytes[cur_pc + 2] << 8)
            operand_str = f"#${val:04X}"
    elif mode == "imm_x":
        if x_flag:
            length = 2
            val = rom_bytes[cur_pc + 1]
            operand_str = f"#${val:02X}"
        else:
            length = 3
            val = rom_bytes[cur_pc + 1] | (rom_bytes[cur_pc + 2] << 8)
            operand_str = f"#${val:04X}"
    elif mode == "imm_8":
        length = 2
        val = rom_bytes[cur_pc + 1]
        operand_str = f"#${val:02X}"
    elif mode == "dp":
        length = 2
        val = rom_bytes[cur_pc + 1]
        operand_str = f"${val:02X}"
    elif mode == "dp_x":
        length = 2
        val = rom_bytes[cur_pc + 1]
        operand_str = f"${val:02X},X"
    elif mode == "dp_y":
        length = 2
        val = rom_bytes[cur_pc + 1]
        operand_str = f"${val:02X},Y"
    elif mode == "dp_ind":
        length = 2
        val = rom_bytes[cur_pc + 1]
        operand_str = f"(${val:02X})"
    elif mode == "dp_ind_long":
        length = 2
        val = rom_bytes[cur_pc + 1]
        operand_str = f"[${val:02X}]"
    elif mode == "dp_ind_x":
        length = 2
        val = rom_bytes[cur_pc + 1]
        operand_str = f"(${val:02X},X)"
    elif mode == "dp_ind_y":
        length = 2
        val = rom_bytes[cur_pc + 1]
        operand_str = f"(${val:02X}),Y"
    elif mode == "dp_ind_long_y":
        length = 2
        val = rom_bytes[cur_pc + 1]
        operand_str = f"[${val:02X}],Y"
    elif mode == "sr":
        length = 2
        val = rom_bytes[cur_pc + 1]
        operand_str = f"${val:02X},S"
    elif mode == "sr_ind_y":
        length = 2
        val = rom_bytes[cur_pc + 1]
        operand_str = f"(${val:02X},S),Y"
    elif mode == "abs":
        length = 3
        val = rom_bytes[cur_pc + 1] | (rom_bytes[cur_pc + 2] << 8)
        operand_str = f"${val:04X}"
    elif mode == "abs_x":
        length = 3
        val = rom_bytes[cur_pc + 1] | (rom_bytes[cur_pc + 2] << 8)
        operand_str = f"${val:04X},X"
    elif mode == "abs_y":
        length = 3
        val = rom_bytes[cur_pc + 1] | (rom_bytes[cur_pc + 2] << 8)
        operand_str = f"${val:04X},Y"
    elif mode == "abs_ind":
        length = 3
        val = rom_bytes[cur_pc + 1] | (rom_bytes[cur_pc + 2] << 8)
        operand_str = f"(${val:04X})"
    elif mode == "abs_ind_x":
        length = 3
        val = rom_bytes[cur_pc + 1] | (rom_bytes[cur_pc + 2] << 8)
        operand_str = f"(${val:04X},X)"
    elif mode == "abs_long":
        length = 4
        val = rom_bytes[cur_pc + 1] | (rom_bytes[cur_pc + 2] << 8) | (rom_bytes[cur_pc + 3] << 16)
        operand_str = f"${val:06X}"
    elif mode == "abs_long_x":
        length = 4
        val = rom_bytes[cur_pc + 1] | (rom_bytes[cur_pc + 2] << 8) | (rom_bytes[cur_pc + 3] << 16)
        operand_str = f"${val:06X},X"
    elif mode == "abs_long_ind":
        length = 3
        val = rom_bytes[cur_pc + 1] | (rom_bytes[cur_pc + 2] << 8)
        operand_str = f"[${val:04X}]"
    elif mode == "rel_8":
        length = 2
        offset = rom_bytes[cur_pc + 1]
        if offset >= 0x80:
            offset -= 0x100
        target = (cur_pc + 2 + offset)
        target_snes = (0xC0 + (target >> 16)) << 16 | (target & 0xFFFF)
        operand_str = f"${target_snes:06X} ({offset:+d})"
    elif mode == "rel_16":
        length = 3
        offset = rom_bytes[cur_pc + 1] | (rom_bytes[cur_pc + 2] << 8)
        if offset >= 0x8000:
            offset -= 0x10000
        target = (cur_pc + 3 + offset)
        target_snes = (0xC0 + (target >> 16)) << 16 | (target & 0xFFFF)
        operand_str = f"${target_snes:06X} ({offset:+d})"
    elif mode == "block":
        length = 3
        src = rom_bytes[cur_pc + 1]
        dst = rom_bytes[cur_pc + 2]
        operand_str = f"${src:02X},${dst:02X}"
    else:
        length = 1
        operand_str = "???"

    new_m = m_flag
    new_x = x_flag
    if mnemonic == "SEP":
        flag_byte = rom_bytes[cur_pc + 1]
        if flag_byte & 0x20: new_m = 1
        if flag_byte & 0x10: new_x = 1
    elif mnemonic == "REP":
        flag_byte = rom_bytes[cur_pc + 1]
        if flag_byte & 0x20: new_m = 0
        if flag_byte & 0x10: new_x = 0

    raw_bytes = rom_bytes[cur_pc:cur_pc + length]
    raw_str = " ".join(f"{x:02X}" for x in raw_bytes)
    return length, mnemonic, operand_str, raw_str, new_m, new_x

def disasm_block(rom_bytes, pc_start, num_instructions=30, m_flag=1, x_flag=1):
    cur = pc_start
    for _ in range(num_instructions):
        if cur >= len(rom_bytes):
            break
        snes_bank = 0xC0 + (cur >> 16)
        snes_addr = cur & 0xFFFF
        length, mnemonic, operand_str, raw_str, m_flag, x_flag = format_instruction(rom_bytes, cur, m_flag, x_flag)
        print(f"${snes_bank:02X}:{snes_addr:04X} (PC 0x{cur:06X}) [M={m_flag} X={x_flag}]: {raw_str:12s}  {mnemonic:4s} {operand_str}")
        cur += length

if __name__ == "__main__":
    with open("rom/Traverse - Starlight & Prairie (Japan).sfc", "rb") as f:
        data = f.read()
    
    addr = 0x1CCA99
    if len(sys.argv) > 1:
        addr = int(sys.argv[1], 16)
    count = 40
    if len(sys.argv) > 2:
        count = int(sys.argv[2])
    m_init = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    x_init = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    disasm_block(data, addr, count, m_init, x_init)
