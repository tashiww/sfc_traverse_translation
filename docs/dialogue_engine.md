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

### Root Cause: Why Debug Words Appeared
The routine `$C0:F395` is not merely a typewriter pause; it is the **Cutscene Macro Dispatcher**. Every invocation steps through commands from the macro script pointer `[$D1]`.
Because an English dialogue string has ~35 characters (compared to ~15 in Japanese), calling `JSL $C0:F395` for every English character executed 175 macro commands, running completely past the end of the 28-command prologue script into unmapped ROM!
This caused the macro dispatcher to execute random ROM bytes as commands, eventually jumping to `$C0:B31F` (the Country Selection screen handler), which overwrote BG3 with country descriptions ("Country", "Auto", "Remove", "Specialist").

### Solution: Direct VBlank Synchronization
In `VWF_RenderEnglishLine`:
- We do **not** call `JSL $C0:F395`.
- Instead, typewriter delay and VRAM synchronization are performed directly via `STZ $B6 : LDA.l $004210 : BPL -` (1-frame VBlank wait).
- This triggers NMI to DMA `$7E:CE80` to VRAM `$5800` smoothly without touching `[$D1]` or advancing macro script execution.
- Tile corruption on character boundaries was resolved by removing `$05,S` reloads that clobbered the low byte in A during horizontal glyph splits.

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

---

## 5. Dual Dialogue Engine Architecture: Engine 1 vs Engine 2

The game does not use a single monolithic dialogue engine. It contains two distinct, specialized dialogue subsystems:

| Feature | Engine 1: Prologue / Static Windows | Engine 2: Overworld / Cutscene Events |
|---|---|---|
| **Primary Call Sites** | Macro command `0x06` (`$C0:F501` -> `$DC:CA99` -> `$DC:CAA1`) | Scenario event loop (`$C0:1B54` -> `$C0:31FB`) |
| **Hook Point** | `org $DCCAA1 : JML RenderEnglishVWF` | `org $C01B63 : JSL Engine2_Redirect` & `org $C034A4 : JSL Engine2_VWF_Blit` |
| **String Redirection** | Dynamic lookup in `StringRedirectTable` at `$CA:7000` | Setup hook at `$C0:1B63` repoints `[$040A:$040B]` to Bank `$CA` |
| **Tile Allocation** | Dynamic BG3 tile allocation (2 tiles/col, up to 28 cols) | Static 32-tile linear line mapping |
| **WRAM Framebuffer** | `$7E:CE80` (896 bytes, 56 tiles) | `$7E:8000` (1,024 bytes direct line buffer) |
| **VRAM Transfer** | NMI mode `$B6` / `$B8` DMAs `$7E:CE80` to VRAM `$5800` | Frame VBlank handler at `$C0:35C0` DMAs `$7E:8000` to VRAM page `($03FD + slot*2 + 2)` |
| **Tilemap Management** | Writes dynamically to BG3 tilemap at `$7E:C780` | Tilemap at `$7F:F480` indexes fixed tile sequence `0..31` and `32..63` |
| **Original Font Format** | 16x16 Full-width Kanji/Kana from Bank `$D3` | 12x12/16 Half/Shifted Kanji/Kana from Bank `$D3` (12px pitch) |

---

## 6. Engine 2 Reverse Engineering & Disassembly

### 6.1 Cutscene Dialogue Setup & Frame Stepping (`$C0:1B54` – `$C0:1B86`)

This routine is called by the main scenario loop on every frame to drive dialogue advancement:

```assembly
; ============================================================================
; $C0:1B54: Scenario Dialogue Frame Dispatcher
; Drives cutscene dialogue boxes during overworld events.
; Checks sub-state $0407; if idle, initializes string pointer from script [$3B].
; While dialogue is active ($0407 != 0), halts script pointer advancement.
; ============================================================================
$C0:1B54: AD 07 04      LDA $0407           ; Check dialogue sub-state
$C0:1B57: D0 1C         BNE .step_dialogue  ; If already active ($0407 != 0), run frame step

; --- Initialize New Dialogue Box ---
$C0:1B59: C2 20         REP #$20            ; 16-bit Accumulator
$C0:1B5B: B7 3B         LDA [$3B],Y         ; Read 16-bit relative string offset from script [$3B]
$C0:1B5D: 18            CLC
$C0:1B5E: 69 02 00      ADC #$0002          ; Account for 2-byte opcode size
$C0:1B61: 65 3B         ADC $3B             ; Compute absolute 16-bit string address in ROM bank
$C0:1B63: 8D 0B 04      STA $040B           ; Store low 16-bit address into $040B (HOOK POINT!)
$C0:1B66: E2 20         SEP #$20            ; 8-bit Accumulator
$C0:1B68: A5 3D         LDA $3D             ; Read script bank byte
$C0:1B6A: 8D 0A 04      STA $040A           ; Store string bank into $040A
$C0:1B6D: A9 01         LDA #$01
$C0:1B6F: 8D 07 04      STA $0407           ; Set $0407 = 1 (State 1: Initialize dialogue window)
$C0:1B72: 9C 0D 04      STZ $040D           ; Reset line index counter to 0

.step_dialogue:
$C0:1B75: 20 FB 31      JSR $31FB           ; *** EXECUTE DIALOGUE CONTROLLER STEP ***
$C0:1B78: A4 3B         LDY $3B             ; Load script offset Y
$C0:1B7A: AD 07 04      LDA $0407           ; Check if dialogue is still active
$C0:1B7D: D0 04         BNE .halt_script    ; If $0407 != 0, keep script pointer on current opcode
$C0:1B7F: C8            INY : INY           ; Dialogue complete: advance script pointer past opcode
$C0:1B81: 80 01         BRA .save_script
.halt_script:
$C0:1B83: 88            DEY                 ; Decrement Y so caller re-executes same script opcode next frame
.save_script:
$C0:1B84: 84 3B         STY $3B             ; Save updated script offset
$C0:1B86: 60            RTS
```

---

### 6.2 The Engine 2 Dialogue State Machine (`$C0:31FB` – `$C0:3281`)

Variable `$0407` controls the state of the active dialogue box:
- **State 0**: Inactive / idle.
- **State 1**: Clear line buffers, configure initial ring buffer slot, transition to State 2.
- **State 2**: Active character typewriter loop. Reads text byte stream and renders glyphs.
- **State 3**: Advance line. Increments ring buffer slot `$040E`, resets cursor `$0412`, updates tilemap.
- **State 4**: Window prompt / wait for button press to scroll or dismiss.

```assembly
; ============================================================================
; $C0:31FB: Engine 2 State Dispatcher
; ============================================================================
$C0:31FB: AD 07 04      LDA $0407           ; Load state
$C0:31FE: F0 0F         BEQ .state0         ; State 0: Idle -> Exit
$C0:3200: 3A            DEC A
$C0:3201: F0 12         BEQ .state1         ; State 1: Initialize dialogue box
$C0:3203: 3A            DEC A
$C0:3204: F0 0C         BEQ .state2         ; State 2: Render characters
$C0:3206: 3A            DEC A
$C0:3207: D0 03         BNE .check_state4
$C0:3209: 82 47 00      BRL .state3         ; State 3: Advance line
.check_state4:
$C0:320C: 3A            DEC A
$C0:320D: F0 73         BEQ .state4         ; State 4: Prompt / wait for button press
.state0:
$C0:320F: 82 E7 01      BRL $33F9           ; Exit RTS
.state2:
$C0:3212: 82 08 01      BRL $331D           ; Branch to character rendering loop

; --- State 1: Initialize Dialogue Box Window ---
.state1:
$C0:3215: AD 16 04      LDA $0416           ; Check if string already finished
$C0:3218: D0 30         BNE .abort_box
$C0:321A: AD 0D 04      LDA $040D           ; Check line counter
$C0:321D: D0 34         BNE .state3
$C0:321F: A5 07         LDA $07             ; Typewriter speed setting
$C0:3221: C9 02         CMP #$02
$C0:3223: 90 02         BCC +
$C0:3225: A9 07         LDA #$07
+       8D 09 04      STA $0409           ; Save typewriter delay mask
$C0:322A: 20 FA 33      JSR $33FA           ; Clear tilemaps at $7F:F480
$C0:322D: 20 46 35      JSR $3546           ; Initialize palette and attributes
$C0:3230: A2 00 00      LDX #$0000          ; 16-bit X
$C0:3233: 8E 12 04      STX $0412           ; Reset horizontal cursor $0412 to 0
$C0:3236: 9C 0E 04      STZ $040E           ; Reset ring buffer line slot to 0
$C0:3239: A2 80 00      LDX #$0080
$C0:323C: 8E 0F 04      STX $040F           ; Initial Base Tile ID = $0080
$C0:323F: A9 02         LDA #$02
$C0:3241: 8D 08 04      STA $0408           ; Set DMA mode 2 (bitmap + tilemap)
$C0:3244: 8D 07 04      STA $0407           ; Set State 2 (Active rendering)
$C0:3247: 82 AF 01      BRL $33F9           ; Exit RTS

; --- State 3: Advance Line ---
.state3:
$C0:3253: AD 0E 04      LDA $040E           ; Load ring buffer line slot (0..3)
$C0:3256: 1A            INC A
$C0:3257: 29 03         AND #$03            ; Wrap slot around modulo 4
$C0:3259: 8D 0E 04      STA $040E           ; Update ring buffer line slot
$C0:325C: A2 00 00      LDX #$0000          ; 16-bit X
$C0:325F: 8E 12 04      STX $0412           ; Reset horizontal cursor $0412 to 0
$C0:3262: AD 0D 04      LDA $040D           ; Load visible line counter
$C0:3265: 1A            INC A
$C0:3266: 29 03         AND #$03
$C0:3268: 8D 0D 04      STA $040D           ; Update line counter
$C0:326B: D0 0D         BNE .no_scroll
$C0:326D: A9 02         LDA #$02
$C0:326F: 8D 0D 04      STA $040D           ; Clamp visible lines
$C0:3272: 20 15 34      JSR $3415           ; Scroll tilemap up by 1 line
$C0:3275: A9 02         LDA #$02
$C0:3277: 8D 08 04      STA $0408           ; Request tilemap DMA
.no_scroll:
$C0:327A: A9 02         LDA #$02
$C0:327C: 8D 07 04      STA $0407           ; Return to State 2 (Rendering)
$C0:327F: 82 77 01      BRL $33F9           ; Exit RTS
```

---

### 6.3 State 2 Character Dispatcher (`$C0:331D` – `$C0:33CC`)

On each frame in State 2, this routine executes:
1. If horizontal cursor `$0412 == 0` (first frame of a new line):
   - Wipes the 1024-byte direct line buffer at `$7E:8000` via `JSL $C0348D`.
   - Computes tilemap entries for the line via `JSR $344F`.
   - Initializes `$0412` to `$0010` (16 bytes = 1 tile column = 8 pixels margin).
   - Resets native toggle flag `$0411 = 0`.
2. Checks typewriter frame delay (`$03B9 & $0409`).
3. Reads the next character code from `[$040A:$040B]`:
   - Code `$FF`: End of string (`INC $0416`, advance to State 4 prompt).
   - Code `$FE`: Line break (advance to State 3).
   - Code `$F0`–`$F2`: Dynamic protagonist/party character names.
   - Code `$FB`–`$FD`: Japanese 2-byte Kanji/Kana.
   - Normal codes (`< $F0`): English glyph code directly dispatched to `JSL $C034A4`!

```assembly
; ============================================================================
; $C0:331D: State 2 Character Dispatcher
; ============================================================================
$C0:331D: AE 12 04      LDX $0412           ; Check horizontal cursor
$C0:3320: D0 18         BNE .read_char      ; If not 0, line buffer is ready -> read character

; --- First Tick of Line: Wipe Line Buffer & Setup Tilemap ---
$C0:3322: 22 8D 34 C0   JSL $C0348D         ; Zero out 1024 bytes ($7E:8000 to $7E:83FF)
$C0:3326: 20 4F 34      JSR $344F           ; Assign base tiles $040F to tilemap $7F:F480
$C0:3329: A2 10 00      LDX #$0010          ; 16-bit X
$C0:332C: 8E 12 04      STX $0412           ; Set $0412 = $0010 (8-pixel left margin!)
$C0:332F: 9C 11 04      STZ $0411           ; Reset 12px toggle flag to 0
$C0:3332: A9 02         LDA #$02
$C0:3334: 8D 08 04      STA $0408           ; Request tilemap + bitmap DMA
$C0:3337: 82 BF 00      BRL $33F9           ; Return to sync frame with PPU

; --- Read Next Character ---
.read_char:
$C0:333A: AD 09 04      LDA $0409           ; Typewriter delay mask
$C0:333D: F0 08         BEQ +
$C0:333F: AD B9 03      LDA $03B9           ; Frame tick counter
$C0:3342: 2D 09 04      AND $0409
$C0:3345: D0 F0         BNE $3337           ; Delay active: wait until next frame
+       AC 0B 04      LDY $040B           ; Text stream read offset
$C0:334A: 8B            PHB                 ; Save DB
$C0:334B: AD 0A 04      LDA $040A           ; Text stream bank byte
$C0:334E: 48            PHA
$C0:334F: AB            PLB                 ; Set DB = text bank ($CA)
$C0:3350: C2 20         REP #$20            ; 16-bit A
$C0:3352: B9 00 00      LDA $0000,Y         ; Read 16-bit word from text stream
$C0:3355: E2 20         SEP #$20            ; 8-bit A
$C0:3357: AB            PLB                 ; Restore DB
$C0:3358: C8            INY                 ; Advance string offset
$C0:3359: 8C 0B 04      STY $040B

; --- Control Code Evaluation ---
$C0:335C: C9 FF         CMP #$FF            ; Code $FF: End of string?
$C0:335E: D0 06         BNE +
$C0:3360: EE 16 04      INC $0416           ; Mark string finished
$C0:3363: 82 7E 00      BRL .trigger_prompt
+       C9 FA         CMP #$FA            ; Code $FA: Prompt break?
$C0:3368: D0 02         BNE +
$C0:336A: 80 F7         BRA $3363
+       C9 FE         CMP #$FE            ; Code $FE: Line break?
$C0:336E: F0 68         BEQ .do_line_break  ; Handle line break!
$C0:3370: C9 FB         CMP #$FB            ; Code >= $FB: 2-byte Japanese character?
$C0:3372: B0 50         BCS .is_japanese_char
$C0:3374: C9 F0         CMP #$F0            ; Code $F0: Hero name variable?
$C0:3376: F0 0E         BEQ .is_name_var

; --- Single Byte Character (English) ---
$C0:3380: EB            XBA                 ; Put byte into high byte
$C0:3381: A9 00         LDA #$00            ; Zero out low byte
$C0:3383: EB            XBA                 ; Swap back: 16-bit A = (char_code & 0x00FF)
$C0:3384: 80 46         BRA .call_blitter   ; Jump to JSL $C034A4!

.call_blitter:
$C0:33CC: 22 A4 34 C0   JSL $C034A4         ; *** CHARACTER BLITTER ENTRY POINT ***
$C0:33D0: AE 12 04      LDX $0412           ; Check horizontal cursor
$C0:33D3: E0 F0 01      CPX #$01F0          ; Reached line capacity ($01F0 = 496 bytes)?
$C0:33D6: D0 1C         BNE .step_done
.do_line_break:
$C0:33D8: A9 03         LDA #$03
$C0:33DA: 8D 07 04      STA $0407           ; Set State 3 (Advance line)
...
```

---

## 7. Engine 2 Fixed-Width Font (FWF) Root Cause Analysis

### 7.1 The Disassembly of Native Character Blitter `$C0:34A4`

When characters are dispatched to `JSL $C034A4`, the clean ROM executes:

```assembly
; ============================================================================
; $C0:34A4: Native Character Blitter
; Inputs:
;   16-bit A = character code
;   $0412    = current horizontal byte offset
; ============================================================================
$C0:34A4: C2 20         REP #$20            ; 16-bit Accumulator
$C0:34A6: 0A : 0A : 0A  ASL : ASL : ASL
$C0:34A9: 0A : 0A : 0A  ASL : ASL : ASL     ; A = char_code * 64 (glyph size in Bank $D3)
$C0:34AC: AA            TAX                 ; X = source offset in Bank $D3 font ROM
$C0:34AD: AC 12 04      LDY $0412           ; Y = destination byte offset in $7E:8000
$C0:34B0: E2 20         SEP #$20            ; 8-bit Accumulator
$C0:34B2: AD 11 04      LDA $0411           ; Toggle flag (alternates 0 and 1)
$C0:34B5: 1A            INC A
$C0:34B6: 29 01         AND #$01
$C0:34B8: 8D 11 04      STA $0411           ; Update toggle flag
$C0:34BB: 20 D6 34      JSR $34D6           ; Execute glyph rasterizer

; --- Hardcoded Cursor Advance ---
$C0:34BE: A0 10 00      LDY #$0010          ; Default advance: 16 bytes (8 pixels = 1 tile column)
$C0:34C1: AD 11 04      LDA $0411           ; Check toggle flag
$C0:34C4: D0 03         BNE +               ; If $0411 == 1, advance by 16 bytes
$C0:34C6: A0 20 00      LDY #$0020          ; If $0411 == 0, advance by 32 bytes (16 pixels = 2 columns)
+       C2 20         REP #$20            ; 16-bit Accumulator
$C0:34CB: 98            TYA
$C0:34CC: 18            CLC
$C0:34CD: 6D 12 04      ADC $0412           ; $0412 += 16 or 32 bytes!
$C0:34D0: 8D 12 04      STA $0412           ; Store updated cursor offset
$C0:34D3: E2 20         SEP #$20
$C0:34D5: 6B            RTL
```

### 7.2 Why English Rendered as Fixed-Width (FWF)

The native blitter was designed for a **12-pixel fixed-pitch font**:
1. When printing the first character of a pair (`$0411 == 1`):
   - Blits unshifted into tile column `col` at `$7E:8000,Y` (top) and `$7E:8200,Y` (bottom).
   - Advances cursor `$0412` by **16 bytes (+8 pixels)**.
2. When printing the second character of a pair (`$0411 == 0`):
   - Blits with a **4-bit horizontal shift** (`ASL #4` at `$C0:351A`), splitting the glyph across column `col` and column `col + 1`.
   - Advances cursor `$0412` by **32 bytes (+16 pixels)**.
3. Over two characters, the total cursor advance is `16 + 32 = 48` bytes = **24 pixels (exactly 12 pixels per character)**.

Because English characters vary from 3 pixels (`'i'`, `'l'`) to 8 pixels (`'W'`, `'M'`), forcing every English letter onto this hardcoded alternating 12-pixel grid caused wide, unnatural gaps between narrow letters and spaces, rendering as rigid Fixed-Width Font.

---

## 8. Engine 2 Variable-Width Font (VWF) Architecture

To achieve true proportional VWF rendering in cutscenes, we hook `JSL $C034A4` with a custom proportional blitter:

```
[Text Stream] -> Char Code -> [WidthTableVWF] -> char_width (3..8 px)
                                     |
                                     v
                        cursor_x (0..248 px)
                        col_start = cursor_x >> 3
                        bit_shift = cursor_x & 7
                                     |
                                     v
                 [FontVWF 1bpp Glyph + Shadow Mask]
                                     |
           +-------------------------+-------------------------+
           |                                                   |
           v                                                   v
   Top Half (Rows 0..7)                               Bottom Half (Rows 8..15)
   Col col_start:   $7E:8000 + col*16                 Col col_start:   $7E:8200 + col*16
   Col col_start+1: $7E:8010 + col*16                 Col col_start+1: $7E:8210 + col*16
```

### 8.1 Memory Layout & Tile Offsets
- **Frame Buffer**: WRAM `$7E:8000`–`$7E:83FF` (1,024 bytes = 64 8×8 tiles in 2bpp format).
  - Row 0 (Top half): 32 tiles at `$7E:8000` to `$7E:81FF`.
  - Row 1 (Bottom half): 32 tiles at `$7E:8200` to `$7E:83FF`.
- For tile column `c` (`0 <= c < 32`):
  - Top tile: `$7E:8000 + (c << 4)`.
  - Bottom tile: `$7E:8200 + (c << 4)`.
  - Next column top tile: `$7E:8000 + (c << 4) + 16`.
  - Next column bottom tile: `$7E:8200 + (c << 4) + 16`.

### 8.2 Proportional Rasterization Algorithm
1. Read `char_code` from 16-bit A (passed by caller).
2. Look up proportional width from `WidthTableVWF,X`.
3. Compute `bit_shift = cursor_x & 7` and `col_start = cursor_x >> 3`.
4. Derive destination byte offset `X = col_start << 4`.
5. Rasterize 8 rows of Top Tile into `$7E:8000,X` (and spill to `$7E:8010,X` if `bit_shift > 0`).
6. Rasterize 8 rows of Bottom Tile into `$7E:8200,X` (and spill to `$7E:8210,X` if `bit_shift > 0`).
7. Clean exterior drop shadow: `Plane 1 &= ~Plane 0` across both tiles.
8. Update pixel cursor: `cursor_x += char_width`.
9. Synchronize `$0412 = (cursor_x >> 3) << 4` (or minimum `$0010`) to maintain perfect alignment with native engine state machines.

---

### 8.3 Complete Annotated Disassembly of Engine 2 VWF Blitter (`Engine2_CharBlit`)

The Engine 2 proportional blitter intercepts the native blitter at `$C0:34A4` (`JML Engine2_CharBlit` in Bank `$CA` at `$CA:8A26`):

```assembly
; ============================================================================
; Engine2_CharBlit: Proportional Variable-Width Font (VWF) Blitter
; Hooked at $C0:34A4. Called from $C0:33CC via JSL $C034A4.
; Inputs:
;   16-bit A: Character code (clean ROM entry had 8-bit A with high byte zeroed)
;   $7E:040A: Text bank byte ($CA for translated English)
;   $7E:0411: Line initialization flag (0 = new line, 1 = line in progress)
;   $7E:0414: Horizontal pixel cursor (cursor_x: 8..240 pixels)
; Outputs:
;   $7E:8000..$7E:83FF: Direct 2bpp line buffer updated with proportional glyph
;   $7E:0412: Synchronized horizontal byte offset for native engine state machine
; ============================================================================
Engine2_CharBlit:
    ; Clean ROM at $C0:34A4 executed REP #$20 first!
    ; Caller ($C0:33CC) is in 8-bit Accumulator mode (M=1). We MUST execute REP #$20
    ; first so that 16-bit char_code is preserved and stack operations are 16-bit!
    REP #$20            ; 16-bit Accumulator (M=0)
    PHA                 ; Push 16-bit char_code to stack (2 bytes)
    SEP #$20            ; 8-bit Accumulator (M=1)
    LDA.l $7E040A       ; Read string bank byte using 24-bit long addressing
    CMP #$CA            ; English translation string in Bank $CA?
    BEQ .check_char

; --- Fallback for Native Japanese Kana / Kanji ---
.native_jp:
    REP #$20            ; 16-bit A
    PLA                 ; Restore original 16-bit char_code
    ASL A               ; Execute the 2 ASLs replaced by hook at $C0:34A4
    ASL A
    JML $C034A8         ; Jump to remaining 4 ASLs and native blitter in Bank $C0

; --- Check English Character Set ---
.check_char:
    REP #$20            ; 16-bit A
    PLA                 ; Restore original 16-bit char_code
    CMP #$0100          ; Check if 2-byte Japanese character code (>= $0100)
    BCC .is_vwf         ; English 1-byte code (< $0100): proceed to VWF!
    ASL A
    ASL A
    JML $C034A8         ; Japanese character: fallback to native blitter

; --- Proportional VWF Blitter Core ---
.is_vwf:
    PHP                 ; Save caller's status flags (1 byte)
    REP #$30            ; 16-BIT ACCUMULATOR AND 16-BIT INDEX REGISTERS (M=0, X=0)!
    PHB                 ; Save caller's Data Bank (1 byte)
    PHX                 ; Save caller's 16-bit X (2 bytes)
    PHY                 ; Save caller's 16-bit Y (2 bytes)
    PHA                 ; Stack $01,S = 16-bit char_code (2 bytes)

    ; Set Data Bank = Current Bank ($CA) to read FontVWF and WidthTableVWF:
    PHK
    PLB

    ; --- Line Start Synchronization ---
    ; In clean ROM, $C0:332F executes STZ $0411 whenever a new line starts.
    ; If $7E:0411 == 0, reset cursor_x to 8 pixels left margin.
    SEP #$20            ; 8-bit A
    LDA.l $7E0411
    BNE +
    LDA #$01
    STA.l $7E0411       ; Mark line active ($7E:0411 = 1)
    REP #$20
    LDA #$0008          ; cursor_x = 8 pixels (Tile 1 start)
    STA.l $7E0414
    BRA ++
+   REP #$20
++

    ; --- Space Character ($0000) Handling ---
    LDA $01,S           ; Load 16-bit char_code from stack
    BNE .not_space

    ; If cursor_x == 8 (beginning of line), absorb delimiter space without advancing:
    LDA.l $7E0414
    CMP #$0008
    BEQ .update_cursor
    ; In-line space: advance cursor_x by 4 pixels:
    CLC
    ADC #$0004
    STA.l $7E0414
    BRA .update_cursor

.not_space:
    ; --- Look Up Proportional Width from WidthTableVWF ---
    TAX                 ; X = 16-bit char_code
    SEP #$20            ; 8-bit A
    LDA.l WidthTableVWF,X ; Read visual glyph width + 1px spacing
    REP #$20            ; 16-bit A
    AND #$00FF
    BNE +
    LDA #$0006          ; Default fallback width = 6 px
+   PHA                 ; Push 16-bit char_width: Stack $01,S = width, $03,S = code

    ; --- Compute Destination Memory Coordinates ---
    ; font_ptr = char_code * 32 bytes (16-bit Y)
    LDA $03,S
    ASL : ASL : ASL : ASL : ASL
    TAY                 ; Y = font_ptr in Bank $CA

    ; bit_shift = cursor_x & 7 (0..7 bit shift within destination tile)
    LDA.l $7E0414
    AND #$0007
    STA $EA             ; $EA = bit_shift (16-bit word, high byte $EB = 0)

    ; col_start = cursor_x >> 3, col_offset = col_start * 16 bytes
    LDA.l $7E0414
    LSR : LSR : LSR
    ASL : ASL : ASL : ASL
    TAX                 ; X = destination byte offset in $7E:8000 line buffer

    ; Safety bounds check: abort blit if past buffer capacity (col_offset >= 496)
    CPX #$01F0
    BCS .skip_blit

    ; Blit 8 rows of Top Tile (rows 0..7) into $7E:8000,X
    JSR Engine2_BlitTopRows

    ; Blit 8 rows of Bottom Tile (rows 8..15) into $7E:8200,X
    JSR Engine2_BlitBottomRows

    ; Clean Drop Shadow Mask: Plane 1 &= ~Plane 0 across both columns
    JSR Engine2_CleanShadowMask

.skip_blit:
    REP #$20            ; Ensure 16-bit Accumulator after blitting subroutines!
    PLA                 ; Pull 16-bit char_width from stack
    CLC
    ADC.l $7E0414
    STA.l $7E0414       ; Update pixel cursor: cursor_x += char_width

.update_cursor:
    REP #$20            ; Ensure 16-bit Accumulator
    ; --- Synchronize Native State Machine Cursor ($7E:0412) ---
    ; If cursor_x >= 240, trigger automatic newline ($0412 = $01F0):
    LDA.l $7E0414
    CMP #$00F0          ; 240 pixels (hex 0x00F0)
    BCC +
    LDA #$01F0
    STA.l $7E0412
    BRA .exit_blit
+   ; Else set $0412 = max($0010, (cursor_x >> 3) << 4):
    LSR : LSR : LSR
    ASL : ASL : ASL : ASL
    BNE +
    LDA #$0010
+   STA.l $7E0412

.exit_blit:
    REP #$30            ; Ensure 16-bit A, X, Y for clean, balanced pops
    PLA                 ; Drop 16-bit char_code from stack
    PLY                 ; Restore caller's 16-bit Y
    PLX                 ; Restore caller's 16-bit X
    PLB                 ; Restore caller's Data Bank
    PLP                 ; Restore caller's Status Register P (M and X restored!)
    SEP #$20            ; Guarantee 8-bit Accumulator for caller at $C0:33CC
    RTL
```

---

### 8.4 Critical 65816 Architectural Lessons & Invariants

During development and headless debugging, three subtle 65816 hardware pitfalls were identified and resolved:

1. **The 65816 Data Bank (`DB`) Addressing Trap**:
   - In 65816, instructions using 16-bit absolute addressing (e.g., `STA $0411`, `STA $0414`, `LDA $0412`) append the Data Bank register `DB` to form the 24-bit physical address `(DB << 16) | addr`.
   - When switching `DB = $CA` to read `FontVWF` and `WidthTableVWF` from ROM, executing `STA $0414` inadvertently writes to ROM `$CA:0414` (which SNES hardware silently ignores!), leaving WRAM `$7E:0414` unwritten.
   - **Resolution**: All WRAM state variables (`$7E:040A`, `$7E:0411`, `$7E:0412`, `$7E:0414`) MUST use 24-bit long addressing (`.l $7E04xx`), which bypasses `DB` and targets WRAM directly.

2. **Index Register (`X`/`Y`) Size Mismatch on Stack Pushes/Pops**:
   - The native caller at `$C0:33CC` executes in 8-bit index mode (`X=1`).
   - If `PHX` and `PHY` execute before `REP #$30`, they push only 1 byte each (2 bytes total). If `PLY` and `PLX` execute in 16-bit mode (`X=0`), they pull 2 bytes each (4 bytes total), shifting the stack by 2 bytes and corrupting the 3-byte `RTL` return address, causing a CPU freeze.
   - **Resolution**: `REP #$30` MUST be executed immediately upon entering `.is_vwf` before `PHX` and `PHY`, ensuring every push and pop is a strict 16-bit operation.

3. **Bank `$CA` Free Space Pool Segregation**:
   - Bank `$CA` (`0x0A0000`–`0x0AFFFF`, 64KB) is completely empty in clean ROM.
   - The translation places ASM routines, `FontVWF` (8,192 bytes), and `WidthTableVWF` (256 bytes) between `$CA:8000` and `$CA:B225`.
   - Setting the script inserter's translation string pool start at `0x0AC000` (`$CA:C000`) completely separates script strings (`$CA:C000`–`$CA:D350`) from font data (`$CA:8000`–`$CA:B225`), permanently preventing table corruption.
