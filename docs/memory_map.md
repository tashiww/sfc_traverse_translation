# Traverse: Starlight & Prairie - Memory & Hardware Architecture Map

This document establishes the verified hardware, VRAM, WRAM, and ROM mapping for *Traverse: Starlight & Prairie* (SNES HiROM FastROM 4MB).

---

## 1. SNES PPU & VRAM Layout

| VRAM Address (Word) | VRAM Address (Byte) | Associated BG / Layer | Purpose / Content |
|---|---|---|---|
| `$0800` | `$1000` | BG2 | BG2 Tilemap base register (`$2108 = $08`) |
| `$0C00` | `$1800` | BG3 | BG3 Tilemap base register (`$2109 = $0C`) - Dialogue Window & UI Layer |
| `$1000` | `$2000` | BG1 | BG1 Tilemap base register (`$2107 = $10`) |
| `$2000` | `$4000` | BG1 | BG1 Character tile data base register (`$210B` low nibble = `2`) |
| `$4000` | `$8000` | BG2 & BG3 | Character tile data base register (`$210B` high nibble = `4`, `$210C` low nibble = `4`) |
| `$5000` | `$A000` | BG3 (Tile 512+) | 8x8 UI / Menu font tiles (DMA'd from `$7E:0D80`). Contains menu words: "Country", "Remove", "Auto", etc. |
| `$5800` | `$B000` | BG3 (Tile 768 / `$0300`+) | 16x16 Dialogue character tiles (DMA'd from `$7E:CE80`). 56 tiles = 28 columns × 2 tile rows. |

### Tilemap Attribute Encoding for Dialogue (BG3, 2bpp)
In Mode 1, BG3 is 2bpp (16 bytes per 8×8 tile, 8 words).
A tilemap entry is a 16-bit word (`vhopppcc cccccccc`):
- Bits 0–7 (Low byte): Tile index low 8 bits (`0x00`–`0xFF`).
- Bits 8–9 (High byte bits 0–1): Tile index high 2 bits (`cc`).
- Bits 10–12 (High byte bits 2–4): Palette selection (`010` = Palette 2).
- Bit 13 (High byte bit 5): Priority flag (`1` = high priority, renders above BG1/BG2).
- Bits 14–15 (High byte bits 6–7): Flip flags (`0` = no flip).

**Attribute Byte (`$A8` = `0x2B` = `%00101011`)**:
- Bits 0–1 = `11` -> Tile index bits 8 & 9 are both 1 (`0x0300` = Tile 768).
- Palette = 2 (`%010`), Priority = 1 (`%1`).
- Therefore, Tile ID `0` with attribute `0x2B` resolves to **VRAM Tile 768 (`$0300`)**, which starts exactly at VRAM word address `$4000 + (768 * 8) = $5800`!

---

## 2. WRAM (`$7E:0000` - `$7E:FFFF`) Memory Map

### Direct Page (`$00` - `$FF`) Variables Used by Dialogue Engine
| DP Address | Size | Name | Purpose |
|---|---|---|---|
| `$86`, `$88`, `$8B` | 1B | Text Punctuation | Codes checked for typewriter pause intervals |
| `$A3` - `$A5` | 3B | `str_ptr` | 24-bit long pointer to current dialogue string (`[$A3]`) |
| `$A6` | 1B | `dialogue_active` | Main loop flag (`$C0:EF8B: LDA $A6 : BNE ...`). `0` = dialogue closed, `1` = active |
| `$A8` | 1B | `tile_attr` | Tilemap attribute byte (typically `$2B` for dialogue) |
| `$B6` | 1B | `nmi_dma_mode` | NMI DMA selector: `0` = idle/normal, `1` = tilemap DMA, `2` = dialogue buffer DMA, `3` = sprite DMA |
| `$B8` | 1B | `nmi_vblank_req` | NMI trigger flag: `0` = idle, `1` = process NMI, `2` = transfer `$7E:CE80` to `$5800` |
| `$B9` | 1B | `vblank_sync` | Set to 1 when synchronizing frame ticks |
| `$D1` - `$D3` | 3B | `macro_script_ptr` | 24-bit long pointer to scenario macro bytecode stream (`[$D1]`, Bank `$DB`) |
| `$EC` | 1B | `dialogue_row` | Current rendering row / line offset counter |
| `$ED` | 1B | `dialogue_cols` | Columns counter |

### WRAM Data Buffers
| Address Range | Size | Name | Description |
|---|---|---|---|
| `$7E:0D80` - `$7E:1A7F` | 3,328 B | `ui_font_buffer` | 8x8 bitmap font buffer. DMA'd to VRAM `$5000` by `$DC:C0C3` |
| `$7E:C780` - `$7E:CE7F` | 1,792 B | `bg3_tilemap` | BG3 Tilemap buffer (32×28 words). DMA'd to VRAM `$0C00` by `$DC:C0E0` |
| `$7E:C780` + X | 64 B | `tilemap_top_row` | Top tile row for current line: `X = (Row * 64) + (Col * 2)` |
| `$7E:C7C0` + X | 64 B | `tilemap_btm_row` | Bottom tile row for current line: `X + 0x40` |
| `$7E:CE80` - `$7E:D1FF` | 896 B | `dialogue_glyph_buffer` | 16x16 Dialogue line character buffer (56 8×8 tiles × 16 bytes). DMA'd to VRAM `$5800` by `$DC:C14A` |

### Engine Global Variables in Bank `$00` / Direct Page Storage
| Address | Size | Description |
|---|---|---|
| `$0C7B` | 2B | Macro script offset Y in `[$D1]` |
| `$0C7E` | 1B | Dialogue active line state flag |
| `$0C7F` | 1B | Consumed tilemap width `(X >> 1) & 0x3F` |
| `$0C80` | 1B | Consumed pixel width `(X << 2)` |
| `$0C81` | 1B | Saved accumulator register upon box exit |
| `$0C88` | 1B | Script branch / skip condition flag |
| `$0C8F` | 1B | Window animation in-progress flag |

---

## 3. ROM Free Space & Relocation Pools

| Bank | PC Range | SNES Range | Size | Status in Clean ROM | Usage in Translation |
|---|---|---|---|---|---|
| `$CA` | `0x0A0000`–`0x0AFFFF` | `$CA:8000`–`$CA:FFFF` | 65,536 B | Native unmapped free space (`0x00` filled) | VWF Engine code (`$CA:8000`), proportional fonts (`vwf_font.bin`, `vwf_widths.bin`), scenario string pools |
| `$DB` | `0x1BF530`–`0x1BFFFF` | `$DB:F530`–`$DB:FFFF` | 2,768 B | Unused space at end of dialogue bank | Relocated opening prologue stream (`$DB:F530`), repointed at `$C0:EF83` |
| `$C1` | `0x015D00`–`0x017FFF` | `$C1:DD00`–`$C1:FFFF` | 8,960 B | Unused trailing space in Bank `$C1` | Dynamic script overflow pool for scenario text |
