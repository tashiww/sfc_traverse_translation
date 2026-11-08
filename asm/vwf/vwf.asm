; ============================================================================
; Traverse: Starlight & Prairie - Variable-Width Font (VWF) Engine
; Real-time proportional 1bpp/2bpp rasterizer with automatic drop shadow
; ============================================================================

hirom

; Hook into the master dialogue character line renderer in Bank $C0
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
;   $A8   = Tile attribute byte (0x2B)
; Outputs:
;   Y = Number of bytes consumed from [$A3]
;   X = Tilemap offset (0x0038)
; ----------------------------------------------------------------------------
VWF_RenderEnglishLine:
    PHP
    PHB
    PHK
    PLB                 ; DB = Current Bank ($CA)

    ; Clear line buffer in WRAM ($7E:CE80 - $7E:D1FF: 56 tiles * 16 bytes = 896 bytes)
    REP #$30            ; 16-bit A, X, Y
    LDX #$037E          ; 896 - 2
    LDA #$0000
.clear_loop:
    STA $7ECE80,x
    DEX
    DEX
    BPL .clear_loop

    ; Allocate 18 bytes (9 words) on stack for private local variables:
    ; $01,S: cursor_x    (16-bit horizontal pixel position, initially 0)
    ; $03,S: char_width  (16-bit)
    ; $05,S: tile_col    (16-bit)
    ; $07,S: bit_shift   (16-bit)
    ; $09,S: fg_word     (16-bit)
    ; $0B,S: sh_word     (16-bit)
    ; $0D,S: font_ptr    (16-bit)
    ; $0F,S: str_y       (16-bit string read offset Y)
    ; $11,S: tile_addr   (16-bit temp tile base offset)
    PEA $0000           ; $11,S
    PEA $0000           ; $0F,S
    PEA $0000           ; $0D,S
    PEA $0000           ; $0B,S
    PEA $0000           ; $09,S
    PEA $0000           ; $07,S
    PEA $0000           ; $05,S
    PEA $0000           ; $03,S
    PEA $0000           ; $01,S

.char_loop:
    REP #$20
    LDA $0F,S           ; String offset Y
    TAY
    SEP #$20            ; 8-bit A
    LDA [$A3],y
    INY
    REP #$20
    TYA
    STA $0F,S           ; Update string offset Y
    SEP #$20

    CMP #$FF            ; End of line
    BNE +
    JMP .line_done
+
    CMP #$20            ; Space character
    BNE .check_ascii

    ; Space: cursor_x += 4
    REP #$20            ; 16-bit A
    LDA $01,S           ; cursor_x
    CLC
    ADC #$0004
    STA $01,S
    JMP .char_loop

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
    LDA.l VWF_WidthTable,x
    REP #$20            ; 16-bit A
    AND #$00FF
    STA $03,S           ; char_width

    ; Glyph offset in VWF_FontTable: char_index * 16
    TXA
    ASL
    ASL
    ASL
    ASL
    STA $0D,S           ; font_ptr

    ; Compute tile_col and bit_shift from cursor_x ($01,S)
    LDA $01,S           ; cursor_x
    AND #$0007
    STA $07,S           ; bit_shift (0..7)

    LDA $01,S
    LSR
    LSR
    LSR
    STA $05,S           ; tile_col = cursor_x >> 3

    ; Blit 16 rows of glyph
    LDY #$0000          ; Row counter Y = 0..15

.row_loop:
    REP #$20
    LDA $0D,S           ; font_ptr
    TAX
    SEP #$20            ; 8-bit A
    LDA.l VWF_FontTable,x
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
    ; If Y < 8: top row offset = tile_col * 16 + (Y * 2)
    ; If Y >= 8: bottom row offset = (28 + tile_col) * 16 + ((Y - 8) * 2)
    CPY #$0008
    BCS .calc_bottom
    LDA $05,S           ; tile_col
    BRA .calc_addr
.calc_bottom:
    LDA $05,S           ; tile_col
    CLC
    ADC #$001C          ; + 28 tiles
.calc_addr:
    ASL
    ASL
    ASL
    ASL                 ; tile * 16
    STA $11,S           ; tile base offset
    TYA
    AND #$0007
    ASL                 ; (Y & 7) * 2
    CLC
    ADC $11,S
    TAX                 ; X = exact byte offset in $7E:CE80 for row Y

    ; Write Foreground:
    ; High byte to $7ECE80,X (tile_col, Bitplane 0)
    ; Low byte to $7ECE90,X (tile_col + 1, Bitplane 0)
    LDA $09,S           ; fg_word
    SEP #$20            ; 8-bit A
    XBA                 ; High byte (tile_col)
    ORA $7ECE80,x
    STA $7ECE80,x
    XBA                 ; Low byte (tile_col + 1)
    BEQ .fg_done
    ; Check if tile_col < 27
    REP #$20
    LDA $05,S           ; tile_col
    CMP #$001B
    SEP #$20
    BCS .fg_done
    ORA $7ECE90,x       ; tile_col + 1
    STA $7ECE90,x
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
    ORA $7ECE81,x
    STA $7ECE81,x
    XBA                 ; Low byte (tile_col + 1)
    BEQ .next_row
    REP #$20
    LDA $05,S           ; tile_col
    CMP #$001B
    SEP #$20
    BCS .next_row
    ORA $7ECE91,x
    STA $7ECE91,x

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

    JMP .char_loop

.line_done:
    ; Setup tilemap entries in $7E:C780 (top) and $7E:C7C0 (bottom)
    ; Attribute byte is in $A8 (0x2B)
    SEP #$20
    LDA $A8             ; A = 0x2B
    XBA                 ; High byte = 0x2B
    REP #$30            ; 16-bit A, X
    LDX #$0000
.tilemap_loop:
    ; Top tile: tile ID = X >> 1
    TXA
    LSR
    SEP #$20
    LDA $A8             ; High byte = $A8 attribute
    XBA
    REP #$20
    STA $7EC780,x

    ; Bottom tile: tile ID = (X >> 1) + 28
    CLC
    ADC #$001C
    STA $7EC7C0,x

    INX
    INX
    CPX #$0038          ; 28 tiles * 2 bytes = 56 bytes
    BNE .tilemap_loop

    ; Load return registers:
    LDA $0F,S           ; A = bytes consumed from [$A3]
    TAY                 ; Y = bytes consumed from [$A3]
    LDX #$0038          ; X = tilemap offset

    ; Release 9 stack words (18 bytes):
    TSC
    CLC
    ADC #$0012
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
