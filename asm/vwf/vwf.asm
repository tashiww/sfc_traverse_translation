; ============================================================================
; Traverse: Starlight & Prairie - Variable-Width Font (VWF) Engine
; Real-time proportional 1bpp/2bpp rasterizer with automatic drop shadow
; ============================================================================

hirom

; Hook into the master dialogue character line renderer in Bank $C0
; In clean ROM:
;   $C0:F511: JSL $DC:CA99 (22 99 CA DC)
org $C0F511
    JSL VWF_LineHook

; ----------------------------------------------------------------------------
; VWF Engine & Font Data (Bank $CA Free Space: $CA8000+)
; ----------------------------------------------------------------------------
org $CA8000

VWF_LineHook:
    PHP
    SEP #$20            ; 8-bit A
    ; Peek first character from string [$A3]
    LDA [$A3]
    CMP #$FF
    BEQ .use_native     ; Empty line -> native
    CMP #$20
    BCC .use_native     ; Control code / binary -> native
    CMP #$80
    BCS .use_native     ; High byte (Japanese kana/kanji) -> native

    ; ASCII English string detected -> Execute VWF
    PLP
    JML VWF_RenderEnglishLine

.use_native:
    PLP
    JML $DCCA99         ; Jump directly to original game routine


; ----------------------------------------------------------------------------
; VWF English Line Renderer
; Inputs:
;   [$A3] = 24-bit pointer to dialogue string
;   $A8   = Tile attribute byte ($2B)
;   Stack layout at entry (relative to S after PHP:PHB):
;     $01,S: caller DB
;     $02,S: caller P
;     $03,S..$05,S: JSL return address ($C0:F515)
;     $06,S: caller Base Tile ID (e.g. 0 or 8)
;     $07,S: caller Col parameter (starts at 2)
;     $08,S: caller Row parameter (starts at 4 for line 1, 6 for line 2)
;
; Outputs:
;   Y = Number of bytes consumed from [$A3] (including terminating $FF/$00)
;   X = Consumed tile columns * 2 ($0038)
;   $06,S (caller Base Tile ID) incremented by 56 tiles ($38)
; ----------------------------------------------------------------------------
VWF_RenderEnglishLine:
    PHP
    PHB
    PHK
    PLB                 ; DB = Current Bank ($CA)

    ; Allocate 22 bytes (11 words) on stack for private local variables:
    ; $01,S: cursor_x        (16-bit: pixel position 0..223)
    ; $03,S: char_width      (16-bit)
    ; $05,S: tile_col        (16-bit: cursor_x >> 3)
    ; $07,S: bit_shift       (16-bit: cursor_x & 7)
    ; $09,S: fg_word         (16-bit)
    ; $0B,S: sh_word         (16-bit)
    ; $0D,S: font_ptr        (16-bit)
    ; $0F,S: str_y           (16-bit: string read offset Y)
    ; $11,S: line_tile_base  (16-bit: starting tile ID for this line)
    ; $13,S: line_x_base     (16-bit: tilemap byte offset = Row * 64 + Col * 2)
    ; $15,S: temp_word       (16-bit scratch word)
    PEA $0000           ; $15,S
    PEA $0000           ; $13,S
    PEA $0000           ; $11,S
    PEA $0000           ; $0F,S
    PEA $0000           ; $0D,S
    PEA $0000           ; $0B,S
    PEA $0000           ; $09,S
    PEA $0000           ; $07,S
    PEA $0000           ; $05,S
    PEA $0000           ; $03,S
    PEA $0000           ; $01,S

    ; Caller parameters on stack (offset = 22 + original offset):
    ; $1C,S: Base Tile ID
    ; $1D,S: Col
    ; $1E,S: Row

    ; Compute line_x_base = (Row * 64) + (Col * 2) in pure 16-bit:
    REP #$30            ; 16-bit A, X, Y
    LDA $1E,S           ; Row parameter
    AND #$00FF
    ASL : ASL : ASL : ASL : ASL : ASL ; Row * 64
    STA $13,S

    LDA $1D,S           ; Col parameter
    AND #$00FF
    ASL                 ; Col * 2
    CLC
    ADC $13,S
    STA $13,S           ; line_x_base = Row * 64 + Col * 2

    ; Read line_tile_base:
    LDA $1C,S           ; Base Tile ID from caller
    AND #$00FF
    STA $11,S           ; line_tile_base

    ; Clear 56 tiles (896 bytes) in WRAM $7E:CE80 starting at line_tile_base * 16:
    LDA $11,S           ; line_tile_base
    ASL : ASL : ASL : ASL ; * 16
    TAX                 ; X = byte offset in $7E:CE80
    LDY #$01C0          ; 448 words = 896 bytes
    LDA #$0000
.clear_line:
    STA $7ECE80,X
    INX
    INX
    DEY
    BNE .clear_line

    ; Prepare attribute byte in high byte of temp_word ($15,S):
    SEP #$20
    LDA $A8             ; Tile attribute ($2B)
    XBA
    LDA #$00
    REP #$20
    STA $15,S           ; $15,S = Attribute << 8 (0x2B00)

    ; Initialize tilemap entries in $7E:C780 for this line (28 columns):
    ; Top row at line_x_base: tile IDs = line_tile_base + col
    ; Bottom row at line_x_base + 64: tile IDs = line_tile_base + 28 + col
    LDA $13,S
    TAX                 ; X = line_x_base
    LDY #$0000          ; Y = column byte offset (0..54)
.init_tilemap:
    TYA
    LSR                 ; tile column index 0..27
    CLC
    ADC $11,S           ; line_tile_base + col
    ORA $15,S           ; Combine with attribute high byte
    STA $7EC780,X       ; Top row entry

    CLC
    ADC #$001C          ; Tile ID += 28
    STA $7EC7C0,X       ; Bottom row entry ($7EC780,X + 64)

    INX
    INX
    INY
    INY
    CPY #$0038          ; 28 columns * 2 bytes = 56 bytes
    BNE .init_tilemap

    ; Trigger tilemap DMA ($B6 = 1) to update VRAM $0C00 with clean tilemap entries:
    SEP #$20
    STZ $B8
    LDA #$01
    STA $B6
    LDA.l $004210
-   LDA.l $004210
    BPL -

.char_loop:
    REP #$20
    LDA $0F,S           ; String offset Y
    TAY
    SEP #$20            ; 8-bit A
    LDA [$A3],Y
    INY
    REP #$20
    TYA
    STA $0F,S           ; Advance string offset Y
    SEP #$20

    CMP #$FF            ; End of line
    BEQ .line_done_jmp
    CMP #$00            ; End of line / space delimiter
    BEQ .line_done_jmp

    CMP #$20            ; Space character
    BNE .check_ascii

    ; Space: cursor_x += 4
    REP #$20            ; 16-bit A
    LDA $01,S           ; cursor_x
    CLC
    ADC #$0004
    STA $01,S
    JMP .char_loop

.line_done_jmp:
    JMP .line_done

.check_ascii:
    CMP #$21
    BCC .char_loop      ; Skip unprintable (< 0x21)
    CMP #$7F
    BCS .char_loop      ; Skip non-ASCII (>= 0x7F)

    ; Printable ASCII char in A (0x21 - 0x7E)
    SEC
    SBC #$20            ; Index 1 - 94
    REP #$30            ; 16-bit A, X
    AND #$00FF
    TAX                 ; X = char index

    ; Read character width from VWF_WidthTable
    SEP #$20            ; 8-bit A
    LDA.l VWF_WidthTable,X
    REP #$20            ; 16-bit A
    AND #$00FF
    STA $03,S           ; char_width

    ; Glyph offset in VWF_FontTable: char_index * 16
    TXA
    ASL : ASL : ASL : ASL
    STA $0D,S           ; font_ptr

    ; Compute tile_col and bit_shift from cursor_x ($01,S)
    LDA $01,S           ; cursor_x
    AND #$0007
    STA $07,S           ; bit_shift (0..7)

    LDA $01,S
    LSR : LSR : LSR
    STA $05,S           ; tile_col = cursor_x >> 3

    ; Box width boundary check: 28 tile columns max
    CMP #$001C
    BCS .char_loop

    ; Blit 16 rows of glyph
    LDY #$0000          ; Row counter Y = 0..15

.row_loop:
    REP #$20
    LDA $0D,S           ; font_ptr
    TAX
    SEP #$20            ; 8-bit A
    LDA.l VWF_FontTable,X
    INX
    REP #$20
    TXA
    STA $0D,S           ; Advance font_ptr
    SEP #$20
    BNE .blit_row
    JMP .next_row

.blit_row:
    ; A has glyph byte. Put into high byte of 16-bit word:
    XBA
    LDA #$00
    XBA
    REP #$20            ; 16-bit A

    ; Shift right by bit_shift ($07,S)
    LDA $07,S           ; bit_shift
    TAX
    BEQ .shift_fg_done
.shift_fg_loop:
    LSR
    DEX
    BNE .shift_fg_loop
.shift_fg_done:
    STA $09,S           ; fg_word = shifted foreground

    ; Calculate shadow word: shift once more (shift + 1)
    LSR
    STA $0B,S           ; sh_word = shifted shadow

    ; Calculate tile byte offset for row Y:
    ; Top row: (line_tile_base + tile_col) * 16 + (Y * 2)
    ; Bottom row: (line_tile_base + 28 + tile_col) * 16 + ((Y - 8) * 2)
    CPY #$0008
    BCS .calc_bottom
    LDA $05,S           ; tile_col
    CLC
    ADC $11,S           ; + line_tile_base
    BRA .calc_addr
.calc_bottom:
    LDA $05,S           ; tile_col
    CLC
    ADC #$001C          ; + 28 tiles
    ADC $11,S           ; + line_tile_base
.calc_addr:
    ASL : ASL : ASL : ASL ; tile * 16
    STA $15,S           ; tile base offset
    TYA
    AND #$0007
    ASL                 ; (Y & 7) * 2
    CLC
    ADC $15,S
    TAX                 ; X = exact byte offset in $7E:CE80 for row Y

    ; Write Foreground:
    ; High byte to $7ECE80,X (tile_col, Bitplane 0)
    ; Low byte to $7ECE90,X (tile_col + 1, Bitplane 0)
    LDA $09,S           ; fg_word
    SEP #$20            ; 8-bit A
    XBA                 ; High byte (tile_col)
    ORA $7ECE80,X
    STA $7ECE80,X
    XBA                 ; Low byte (tile_col + 1)
    BEQ .fg_done
    ; Check if tile_col < 27
    REP #$20
    LDA $05,S           ; tile_col
    CMP #$001B
    SEP #$20
    BCS .fg_done
    ORA $7ECE90,X       ; tile_col + 1
    STA $7ECE90,X
.fg_done:

    ; Write Drop Shadow (at row Y + 1):
    CPY #$000F          ; If Y == 15, row 16 is clipped
    BEQ .next_row

    ; Compute shadow row address in X:
    CPY #$0007
    BNE .sh_normal_row
    ; Crossing top tile row 7 to bottom tile row 8: +434 bytes
    TXA
    REP #$20
    CLC
    ADC #$01B2
    TAX
    SEP #$20
    BRA .sh_write
.sh_normal_row:
    INX
    INX
.sh_write:
    ; Shadow is in Bitplane 1 (odd byte: $7ECE81,X)
    REP #$20
    LDA $0B,S           ; sh_word (16-bit)
    SEP #$20
    XBA                 ; High byte (tile_col)
    ORA $7ECE81,X
    STA $7ECE81,X
    XBA                 ; Low byte (tile_col + 1)
    BEQ .next_row
    REP #$20
    LDA $05,S           ; tile_col
    CMP #$001B
    SEP #$20
    BCS .next_row
    ORA $7ECE91,X
    STA $7ECE91,X

.next_row:
    REP #$20
    INY
    CPY #$0010
    BEQ +
    JMP .row_loop
+

    ; Advance cursor_x by char_width
    LDA $01,S           ; cursor_x
    CLC
    ADC $03,S           ; + char_width
    STA $01,S

    ; Typewriter tick & VBlank synchronization
    SEP #$20
    LDA $A6             ; Typewriter enabled?
    BEQ .skip_tick

    PHB
    TDC
    PHA
    PLB                 ; DB = 0
    LDA #$00            ; No punctuation pause
    JSL $C0F395         ; Dialogue_TypewriterTick: DMAs $7E:CE80 to VRAM $5800 & steps animation
    PLB                 ; DB = Bank $CA

.skip_tick:
    JMP .char_loop

.line_done:
    ; Ensure glyph buffer is DMA'd to VRAM $5800 (for instant mode or final glyph sync):
    SEP #$20
    STZ $B8
    STZ $B6             ; Mode 0: DMA $7E:CE80 to VRAM $5800!
    LDA.l $004210
-   LDA.l $004210
    BPL -

    ; Update caller's Base Tile ID ($1C,S) by adding 56 tiles ($38):
    LDA $1C,S
    CLC
    ADC #$38
    STA $1C,S

    ; Load return registers:
    REP #$20
    LDA $0F,S           ; A = bytes consumed from [$A3]
    TAY                 ; Y = bytes consumed from [$A3]
    LDX #$0038          ; X = consumed tile columns * 2

    ; Release 11 stack words (22 bytes):
    TSC
    CLC
    ADC #$0016
    TCS

    SEP #$20            ; 8-bit A
    REP #$10            ; 16-bit X, Y
    PLB                 ; Restore DB
    PLP                 ; Restore P
    RTL

; ----------------------------------------------------------------------------
; Embedded VWF Font Data
; ----------------------------------------------------------------------------
VWF_FontTable:
    incbin "vwf_font.bin"

VWF_WidthTable:
    incbin "vwf_widths.bin"
