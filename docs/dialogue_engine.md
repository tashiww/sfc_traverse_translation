# Traverse: Starlight & Prairie - Dialogue Engine & VWF Architecture

This document details the reverse-engineered execution flow of the dialogue system, typewriter effect, control code processing, and VWF integration.

---

## 1. Dialogue Engine Execution Flow

The dialogue subsystem operates through two interleaved layers:
1. **The Scenario Macro Dispatcher (`$C0:F395` / `[$D1]`)**: Drives the cutscene, camera, typewriter sound, and box animations.
2. **The Line Character Renderer (`$C0:F501` -> `$DC:CA99`)**: Draws glyphs into WRAM buffer `$7E:CE80` and assigns tile indices to BG3 tilemap `$7E:C780`.

```
Scene Trigger:
$C0:EF82: LDX #$AA0F -> STX $A3 (pointer to text stream)
$C0:EF87: JSL $C0:F395 (launch dialogue controller)
    |
    v
Main Loop ($C0:EF8B):
    LDA $A6 : BNE $C0:EF8B  (wait until $A6 == 0 when dialogue box closes)
```

---

## 2. The Dialogue Runner (`$C0:F501` – `$C0:F590`)

When a line is to be printed, macro command `0x06` invokes `$C0:F501`:

```assembly
C0:F501: STY $0C7B          ; Preserve macro script offset in [$D1]
C0:F504: PEA $0202          ; Stack: Push line row parameters (Row = 2, 4...)
C0:F507: TDC                ; A = 0
C0:F508: PHA                ; Stack: Push column parameter (Col = 0)
C0:F509: INC A              ; A = 1
C0:F50A: STA $0C7E          ; Mark line active
C0:F50D: LDA #$2B           ; Tile attribute (BG3, Pal 2, Priority 1, Tile Base $0300)
C0:F50F: STA $A8            ; Store attribute byte
C0:F511: JSL $DC:CA99       ; *** CHARACTER LINE RENDERER HOOK POINT ***
C0:F515: TXA
C0:F516: LSR : AND #$3F
C0:F519: STA $0C7F          ; Save consumed tile columns
C0:F51C: REP #$21
C0:F51E: TYA                ; Y = bytes consumed from text stream [$A3]
C0:F51F: ADC $A3
C0:F521: STA $A3            ; Advance $A3 past the consumed string
C0:F523: TXA : ASL : ASL : SEP #$20 : XBA
C0:F529: STA $0C80          ; Save consumed pixel width
```

### Control Byte Evaluation (`$C0:F52C` – `$C0:F590`)
After the character renderer finishes reading up to `$FF`:
```assembly
C0:F52C: LDA [$A3]          ; Peek control byte immediately following string
C0:F52E: CMP #$FF           ; Code $FF: Newline within same message
C0:F530: BNE .check_01
C0:F532: LDA #$02 : STA $03,S
C0:F536: REP #$20 : INC $A3 : SEP #$20
C0:F53C: JSR $FE5E          ; Wait for button press
C0:F545: JSR $EFEC          ; Clear line buffers ($7E:CE80 and $7E:C780)
C0:F548: TDC : STA $01,S    ; Reset column offset to 0
C0:F54B: BRA $C0:F50D       ; Loop to render next line

.check_01:
C0:F54D: CMP #$01
C0:F54F: BNE .check_fe
C0:F551: STZ $EC
...

.check_fe:
C0:F55E: CMP #$FE           ; Code $FE: End of dialogue block / close window
C0:F560: BEQ .box_done
; If byte is neither $FF nor $FE (e.g., $00 indentation space):
C0:F562: LDA $03,S : CLC : ADC #$02 : STA $03,S  ; Advance row by 2
C0:F569: LDA #$02 : STA $02,S
C0:F56D: STZ $B8 : JSR $CB33 : JSR $FA7E : STZ $B8 : JSR $CB33
C0:F57A: BRA $C0:F50D       ; Loop to render next line

.box_done:
C0:F57C: JSR $FE5E          ; Wait for user button press
C0:F57F: REP #$20 : INC $A3 : SEP #$20  ; Skip $FE
C0:F585: STZ $0C7E
C0:F588: PLA : STA $0C81 : PLX
C0:F58D: LDY $0C7B
C0:F590: RTS                ; Return to macro dispatcher
```

---

## 3. The Native Japanese Character Renderer (`$DC:CA99`)

### Stack Parameter Layout
When called from `$C0:F511`:
- Before `JSL`: `$01,S` = Col (`$00`), `$03,S` = Row (`$02` for speaker name, `$04` for dialogue line 2).
- Inside `$DC:CA99` (after `PHP : PHB`):
  - `$06,S`: Col offset (0)
  - `$07,S`: Col high byte
  - `$08,S`: Row number (`0x02` or `0x04`)
  - `$09,S`: Row high byte

### Tilemap Coordinate Calculation (`$DC:CAA7` – `$DC:CAB9`):
```assembly
DC:CAA7: LDA $08,S          ; Load Row (2 or 4)
DC:CAA9: XBA
DC:CAAA: REP #$30
DC:CAAC: LDX #$CB15 : STX $EA
DC:CAB1: LSR : LSR          ; (Row * 256) / 4 = Row * 64 bytes
DC:CAB3: SEP #$20
DC:CAB5: ADC $07,S
DC:CAB7: ADC $07,S          ; Add (Col * 2)
DC:CAB9: TAX                ; X = Byte offset into $7E:C780!
```
- Row 2 (Speaker Name): `X = 2 * 64 = 0x0080` (Row 2 in tilemap).
- Row 4 (Dialogue Line 1): `X = 4 * 64 = 0x0100` (Row 4 in tilemap).
- Row 6 (Dialogue Line 2): `X = 6 * 64 = 0x0180` (Row 6 in tilemap).

### Character Tile Copy & Typewriter Delay:
For each Japanese 16x16 character:
1. Copies 64 bytes from font ROM to `$7E:CE80,X` (4 8×8 tiles: Top-Left, Top-Right, Bottom-Left, Bottom-Right).
2. Writes 4 tilemap entries:
   - `$7E:C780,X` = Tile ID
   - `$7E:C782,X` = Tile ID + 1
   - `$7E:C7C0,X` = Tile ID + 2 (`$7E:C7C0` = `$7E:C780 + 0x40`, the next 32-tile row)
   - `$7E:C7C2,X` = Tile ID + 3
   - High byte for all 4 tiles = `$A8` (`0x2B`).
3. Calls `$C0:F395` (`JSL $C0:F395` at `$DC:CC38`):
   - Performs typewriter delay.
   - Waits for VBlank (`JSR $C0:CB33`).
   - NMI fires and DMAs `$7E:CE80` to VRAM `$5800` and `$7E:C780` to VRAM `$0C00`.
   - Character appears immediately on screen.

---

## 4. Root Cause Analysis: The "Country / Remove / Auto" Glitch

In the user's Mesen test of commit `9853615`, the screen showed:
1. Menu words ("Country", "Remove", "Auto", "Specialist") and dots scattered across the screen.
2. The English dialogue never appeared.

### Why Did This Happen?
1. **Hardcoded Offset `X = 0` in `.line_done`**:
   `asm/vwf/vwf.asm` wrote tilemap entries with `LDX #$0000`:
   ```assembly
   STA $7EC780,x   ; Row 0 of BG3!
   STA $7EC7C0,x   ; Row 1 of BG3!
   ```
   Instead of using the row offset from the stack (`Row * 64 = 0x0100` for Row 4), it wrote to Row 0 and Row 1 of BG3, which is the very top of the screen outside the dialogue window!
2. **Missing DMA Synchronization (`JSL $C0:F395` / VBlank Trigger)**:
   The native engine calls `JSL $C0:F395` character-by-character, allowing the NMI handler to DMA `$7E:CE80` to VRAM `$5800`.
   Our VWF routine rendered the line in RAM and returned immediately without triggering an NMI VBlank wait.
   Consequently, **VRAM `$5800` was never updated with our English glyphs!**
   VRAM `$5800` still contained the dormant 8x8 menu font tiles loaded during boot ("Country", "Remove", "Auto", "Specialist").
3. **The Tile Base Attribute `$2B`**:
   `$A8` (`0x2B`) selects Tile Base `0x0300` (Tile 768), which corresponds to VRAM `$5800`.
   Because `$7E:CE80` was not transferred, the PPU faithfully rendered the old tiles at VRAM `$5800`!

---

## 5. VWF Implementation & Stack Layout Resolution

### Stack Parameter Layout (Entering VWF from `$C0:F511`)
When `$C0:F511` calls `JSL VWF_LineHook`:
- `S+1`: PCL, `S+2`: PCH, `S+3`: PB (return address to `$C0:F515`)
- `S+4`: caller Base Tile ID (`$00` or `$08` after speaker name)
- `S+5`: caller Col parameter (`$02`)
- `S+6`: caller Row parameter (`$04` for Line 1, `$06` for Line 2)

Inside `VWF_RenderEnglishLine`, after `PHP : PHB` and pushing 11 local variable words (22 bytes):
- Caller Base Tile ID is at `$1C,S`
- Caller Col parameter is at `$1D,S`
- Caller Row parameter is at `$1E,S`

### Dynamic Coordinate and Buffer Calculation:
- `line_x_base = (Row * 64) + (Col * 2)`:
  - Row 4 (Line 1): `(4 * 64) + (2 * 2) = 0x0104` (writes to BG3 tilemap Row 4 / Row 5)
  - Row 6 (Line 2): `(6 * 64) + (2 * 2) = 0x0184` (writes to BG3 tilemap Row 6 / Row 7)
- `line_tile_base`: Read from `$1C,S` (e.g. Tile 8 for Line 1, Tile 64 for Line 2).
- WRAM Buffer Protection: Clears only the 56 tiles allocated for this line starting at `line_tile_base * 16`. Tiles 0..7 (speaker name) and preceding line tiles are 100% preserved.
- Tilemap Initialization:
  - Top row: `$7EC780 + line_x_base + col * 2` gets `line_tile_base + col` with attribute `$2B`.
  - Bottom row: `$7EC7C0 + line_x_base + col * 2` gets `line_tile_base + 28 + col` with attribute `$2B`.
- VRAM DMA & Typewriter Synchronization:
  - Updates tilemap in VRAM `$0C00` at line start via `$B6 = 1` + VBlank wait.
  - Ticks typewriter per character via `JSL $C0:F395` (with `DB = 0`), which DMAs `$7E:CE80` to VRAM `$5800` each frame and steps character bust animation.
  - Final sync at line end via `$B6 = 0` + VBlank wait.
- Stack & Register Return:
  - Updates caller's Base Tile ID at `$1C,S` by adding 56 tiles (`$38`).
  - Sets return registers: `Y = bytes_read`, `X = 0x0038`.
  - Restores DB, P, and returns via `RTL` to `$C0:F515`.
