; ============================================================================
; Traverse: Starlight & Prairie - Proportional Variable-Width Font (VWF) Engine
; Real-time 2bpp sub-pixel rasterizer with exterior drop shadow & typewriter
; ============================================================================

hirom

; Hook directly into the dialogue character line renderer in Bank $C0
; In clean ROM:
;   $C0:F511: JSL $DC:CA99 (22 99 CA DC)
org $C0F511
    JSL RenderEnglishVWF

; ----------------------------------------------------------------------------
; Engine Code & Font Data in Bank $CA Free Space ($CA8000+)
; ----------------------------------------------------------------------------
org $CA8000

; ----------------------------------------------------------------------------
; Direct Page Scratch Allocations (Local to VWF Line Renderer):
;   $DE: max_col     (16-bit: highest initialized tile column)
;   $E0: cursor_x    (16-bit: horizontal pixel position 0..223)
;   $E2: col_start   (16-bit: cursor_x >> 3)
;   $E4: font_ptr    (16-bit: offset in FontVWF)
;   $E6: base_tile   (16-bit: starting Base Tile ID for this line)
;   $E8: x_start     (16-bit: starting tilemap byte offset)
;   $EA: bit_shift   (16-bit: cursor_x & 7)
;   $EC: dest_off    (16-bit: destination byte offset in $7E:CE80)
;   $EE: char_width  (16-bit: character proportional width)
;   $F0: char_raw    (8-bit: current ASCII character code)
; ----------------------------------------------------------------------------

; ----------------------------------------------------------------------------
; Proportional VWF Line Renderer
; Inputs:
;   [$A3] = 24-bit pointer to dialogue string
;   $A8   = Tile attribute byte ($2B)
;   Stack layout at entry (relative to S after PHP:PHB):
;     $01,S: caller DB
;     $02,S: caller P
;     $03,S..$05,S: JSL return address ($C0:F515)
;     $06,S: caller Base Tile ID (starts at 0)
;     $07,S: caller Col parameter (starts at 2)
;     $08,S: caller Row parameter (starts at 2, 4, 6...)
;
; Outputs:
;   Y = Number of bytes consumed from [$A3] (including terminating $FF)
;   X = Current tilemap offset in $7E:C780
;   $06,S (caller Base Tile ID) incremented by consumed tiles (2 per column)
; ----------------------------------------------------------------------------
RenderEnglishVWF:
    PHP
    PHB

    ; Intelligent Language Detection:
    ; Check if string at [$A3] contains Japanese characters or control codes.
    ; Untranslated dialogue strings will fall back directly to the native Japanese
    ; renderer at $DC:CA99, completely preventing jumbled English letters!
    SEP #$20            ; 8-bit A
    REP #$10            ; 16-bit X, Y
    LDY #$0000
.detect_loop:
    LDA [$A3],Y
    CMP #$FF            ; End of line
    BEQ .detect_done
    CMP #$FE            ; End of box or wait
    BEQ .check_fe_wait
    ; Check Kanji prefix ($FB, $FC, $FD):
    CMP #$FB
    BCC +
    CMP #$FE
    BCC .passthrough_jp
+   ; Check Katakana / Japanese punctuation ($80..$EF):
    CMP #$80
    BCC +
    CMP #$F0
    BCC .passthrough_jp
+   INY
    CPY #$0018          ; Scan up to 24 bytes
    BNE .detect_loop
    BRA .detect_done

.check_fe_wait:
    ; Check if followed by $00 (<wait_auto> in Japanese dialogue):
    INY
    LDA [$A3],Y
    BEQ .passthrough_jp
    BRA .detect_done

.passthrough_jp:
    PLB
    PLP
    JML $DCCA99         ; Jump directly to native Japanese character renderer!

.detect_done:
    PHK
    PLB                 ; DB = Current Bank ($CA)

    ; Calculate starting tilemap byte offset from Row and Col:
    REP #$30            ; 16-bit A, X, Y
    LDA $08,S           ; Row parameter
    AND #$00FF
    XBA                 ; A = Row << 8
    LSR : LSR           ; A = Row * 64 bytes
    SEP #$20            ; 8-bit A
    CLC
    ADC $07,S
    ADC $07,S           ; + (Col * 2)
    REP #$20            ; 16-bit A
    AND #$07FE          ; Safety mask
    STA $E8             ; $E8 = x_start

    ; Read starting Base Tile ID from caller stack:
    SEP #$20            ; 8-bit A
    LDA $06,S           ; caller Base Tile ID
    REP #$20            ; 16-bit A
    AND #$00FF
    STA $E6             ; $E6 = base_tile

    ; Initialize line variables:
    STZ $DE             ; max_col = 0
    STZ $E0             ; cursor_x = 0

    ; Initialize tile column 0:
    LDA #$0000
    JSR InitTileColumn

    ; Y = string read offset
    LDY #$0000
    BRA .char_loop

.char_loop:
    SEP #$20            ; 8-bit A
    LDA [$A3],Y
    INY
    CMP #$FF            ; End of line / newline
    BNE +
    JMP .line_done
+   CMP #$FE            ; End of dialogue box
    BNE +
    JMP .hit_fe
+   CMP #$F0            ; Dynamic character name tags ($F0 = protag, $F1 = sub, $F2 = pet)
    BCC +
    CMP #$F3
    BCS +
    JMP .handle_var_name
+   CMP #$00            ; Traverse space
    BNE +
    JSR AdvanceSpace
    BRA .char_loop
+   CMP #$20            ; ASCII space
    BNE +
    JSR AdvanceSpace
    BRA .char_loop
+   CMP #$21
    BCC .char_loop      ; Skip unprintable
    CMP #$7F
    BCS .char_loop      ; Skip non-ASCII

    ; Printable ASCII character (0x21 - 0x7E)
    JSR DrawSingleChar
    BRA .char_loop

; ----------------------------------------------------------------------------
; Dynamic Variable Name Expansion ($F0=[protag], $F1=[sub], $F2=[pet])
; ----------------------------------------------------------------------------
.handle_var_name:
    ; A has $F0 ($7E:EEC9), $F1 ($7E:EED2), or $F2 ($7E:EEDB)
    CMP #$F0
    BNE +
    LDX #$EEC9
    BRA .got_var_buf
+   CMP #$F1
    BNE +
    LDX #$EED2
    BRA .got_var_buf
+   LDX #$EEDB
.got_var_buf:
    PHY                 ; Save caller string offset Y
.var_char_loop:
    SEP #$20            ; 8-bit A
    LDA.l $7E0000,X     ; Read character from WRAM buffer ($7E:EEC9, etc.)
    INX
    CMP #$FF            ; End of name marker
    BEQ .var_done
    CMP #$00            ; Null terminator
    BEQ .var_done
    CMP #$8B            ; Japanese blank filler
    BEQ .var_done

    ; Check Traverse native uppercase encoding ($0B..$24 -> 'A'..'Z'):
    CMP #$0B
    BCC +
    CMP #$25
    BCS +
    CLC
    ADC #$36            ; $0B + $36 = $41 ('A')
    JSR DrawSingleChar
    BRA .var_char_loop
+
    ; Check Traverse native digit encoding ($01..$0A -> '0'..'9'):
    CMP #$01
    BCC +
    CMP #$0B
    BCS +
    CLC
    ADC #$2F            ; $01 + $2F = $30 ('0')
    JSR DrawSingleChar
    BRA .var_char_loop
+
    ; Check native dash symbol ($8A -> '-'):
    CMP #$8A
    BNE +
    LDA #$2D            ; ASCII '-'
    JSR DrawSingleChar
    BRA .var_char_loop
+
    ; Check native dot symbol ($8C -> '.'):
    CMP #$8C
    BNE +
    LDA #$2E            ; ASCII '.'
    JSR DrawSingleChar
    BRA .var_char_loop
+
    ; Check native exclamation symbol ($86 -> '!'):
    CMP #$86
    BNE +
    LDA #$21            ; ASCII '!'
    JSR DrawSingleChar
    BRA .var_char_loop
+
    ; Check native question symbol ($87 -> '?'):
    CMP #$87
    BNE +
    LDA #$3F            ; ASCII '?'
    JSR DrawSingleChar
    BRA .var_char_loop
+
    CMP #$20            ; ASCII space
    BNE +
    JSR AdvanceSpace
    BRA .var_char_loop
+   CMP #$21
    BCC .var_char_loop  ; Skip unprintable
    CMP #$7F
    BCS .var_char_loop  ; Skip non-ASCII
    JSR DrawSingleChar
    BRA .var_char_loop
.var_done:
    PLY                 ; Restore caller string offset Y
    JMP .char_loop

.hit_fe:
    DEY                 ; Back up Y so caller peeks 0xFE
    BRA .line_done

.line_done:
    ; If typewriter was not active, trigger one frame DMA to commit VRAM:
    SEP #$20            ; 8-bit A
    LDA $A6
    BNE +
    STZ $B8
    STZ $B6             ; Mode 0: glyph buffer DMA
    LDA.l $004210
-   LDA.l $004210
    BPL -
+

    ; Calculate total consumed tile columns:
    ; total_cols = (cursor_x + 7) >> 3
    REP #$20            ; 16-bit A
    LDA $E0             ; cursor_x
    CLC
    ADC #$0007
    LSR : LSR : LSR     ; total_cols
    BNE +
    LDA #$0001          ; At least 1 column
+   STA $EE             ; Store total_cols in $EE

    ; Clean up any speculative columns (from total_cols to max_col):
    ; If max_col >= total_cols, clear those tilemap entries to $0000 so
    ; the next line's first tile never ghosts onto the end of this line!
-   LDA $DE             ; max_col
    CMP $EE             ; vs total_cols
    BCC .cols_cleaned   ; if max_col < total_cols, done!
    ASL                 ; max_col * 2
    CLC
    ADC $E8             ; + x_start ($E8)
    TAX
    LDA #$0000
    STA $7EC780,X       ; Clear Top tilemap entry
    STA $7EC7C0,X       ; Clear Bottom tilemap entry
    DEC $DE             ; max_col--
    BRA -

.cols_cleaned:
    ; Update caller Base Tile ID:
    ; Base Tile ID += total_cols * 2
    REP #$20            ; 16-bit A
    LDA $EE             ; Explicitly reload total_cols!
    ASL                 ; total_cols * 2
    SEP #$20            ; 8-bit A
    CLC
    ADC $06,S           ; caller Base Tile ID (offset $06,S)
    STA $06,S           ; Updated Base Tile ID!

    ; Compute final tilemap offset for caller:
    ; X = x_start + (total_cols * 2)
    REP #$20            ; 16-bit A
    LDA $EE             ; total_cols
    ASL                 ; total_cols * 2
    CLC
    ADC $E8             ; + x_start ($E8)
    TAX                 ; X = final tilemap byte offset!

    ; Restore caller DB and P:
    SEP #$20            ; 8-bit A
    REP #$10            ; 16-bit X, Y
    PLB
    PLP
    RTL

; ----------------------------------------------------------------------------
; AdvanceSpace:
; Advances cursor_x by 4 pixels and initializes newly crossed tile columns.
; ----------------------------------------------------------------------------
AdvanceSpace:
    REP #$20            ; 16-bit A
    LDA $E0             ; cursor_x
    CLC
    ADC #$0004          ; + 4 pixels
    STA $E0

    ; Check if new tile column crossed:
    LSR : LSR : LSR     ; col = cursor_x >> 3
    CMP $DE             ; vs max_col
    BCC +
    BEQ +
    JSR InitTileColumn
    STA $DE             ; max_col updated
+   SEP #$20            ; 8-bit A
    RTS

; ----------------------------------------------------------------------------
; DrawSingleChar:
; Real-time 2bpp sub-pixel VWF glyph rasterizer with exterior drop shadow
; Input:
;   A = ASCII character code (0x21 - 0x7E)
; Preserves:
;   Caller X, Y
; ----------------------------------------------------------------------------
DrawSingleChar:
    STA $F0             ; Save ASCII character in $F0
    PHY                 ; Save caller Y
    PHX                 ; Save caller X

    ; Look up character width:
    SEC
    SBC #$20
    REP #$20            ; 16-bit A
    AND #$00FF
    TAX                 ; X = char index (0..94)
    SEP #$20
    LDA.l WidthTableVWF,X
    REP #$20
    AND #$00FF
    STA $EE             ; $EE = char_width

    ; Calculate font data offset: char_index * 32 bytes
    TXA
    ASL : ASL : ASL : ASL : ASL
    STA $E4             ; $E4 = font_ptr

    ; Determine col_start and bit_shift from cursor_x:
    LDA $E0             ; cursor_x
    AND #$0007
    STA $EA             ; $EA = bit_shift (0..7)

    LDA $E0             ; cursor_x
    LSR : LSR : LSR     ; A = col_start (0..27)
    STA $E2             ; $E2 = col_start

    ; Ensure col_start and col_start + 1 are initialized:
    CMP $DE             ; col_start vs max_col
    BCC +
    BEQ +
    JSR InitTileColumn
    STA $DE
+
    LDA $E2             ; col_start
    INC A               ; col_start + 1
    CMP $DE             ; vs max_col
    BCC +
    BEQ +
    JSR InitTileColumn
    STA $DE
+

    ; Calculate destination byte offset in $7E:CE80:
    ; dest_offset = (base_tile + col_start * 2) * 16 bytes
    LDA $E2             ; col_start
    ASL                 ; col_start * 2
    CLC
    ADC $E6             ; + base_tile
    ASL : ASL : ASL : ASL ; * 16 bytes
    STA $EC             ; $EC = dest_offset
    TAX                 ; X = dest_offset

    ; Draw 8 rows of Top Tile (rows 0..7):
    LDY $E4             ; Y = font_ptr
    JSR BlitTopTileRows

    ; Draw 8 rows of Bottom Tile (rows 8..15):
    LDX $EC             ; Ensure X = dest_offset
    LDY $E4             ; Y = font_ptr
    JSR BlitBottomTileRows

    ; Clean mask: Plane 1 &= ~Plane 0:
    LDX $EC             ; Ensure X = dest_offset
    JSR CleanShadowMask

    ; Advance cursor_x += char_width:
    REP #$20            ; 16-bit A
    LDA $E0             ; cursor_x
    CLC
    ADC $EE             ; + char_width
    STA $E0             ; cursor_x updated!

    ; Typewriter synchronization & script stepping via native engine:
    SEP #$20            ; 8-bit A
    LDA $A6             ; Typewriter active?
    BEQ .skip_tw
    LDA $0C88           ; Fast-forward held?
    BNE .skip_tw

    ; Map punctuation to native Japanese pause codes:
    LDA $F0             ; Character just printed
    CMP #$21            ; '!'
    BNE +
    LDA #$86            ; Japanese '！' -> pause
    BRA .do_tick
+   CMP #$3F            ; '?'
    BNE +
    LDA #$87            ; Japanese '？' -> pause
    BRA .do_tick
+   CMP #$2C            ; ','
    BNE +
    LDA #$88            ; Japanese '、' -> pause
    BRA .do_tick
+   CMP #$2E            ; '.'
    BNE +
    LDA #$89            ; Japanese '。' -> pause
    BRA .do_tick
+   LDA #$01            ; Normal letter -> standard typewriter audio tick
.do_tick:
    PHA                 ; Save typewriter code on stack (1 byte)

    PHB                 ; Save DB ($CA)
    PEA $0000 : PLB : PLB ; DB = $00

    LDA $02,S           ; Reload typewriter code from stack
    JSL $C0F395         ; Step typewriter, audio bleep, DMA!

    PLB                 ; Restore DB ($CA)
    PLA                 ; Clean up pushed code

.skip_tw:
    PLX                 ; Restore caller X
    PLY                 ; Restore caller Y
    RTS

; ----------------------------------------------------------------------------
; Subroutine: InitTileColumn
; Inputs:
;   A = tile column index C (0..28)
; Initializes column C in $7E:CE80 (clears 32 bytes) and sets tilemap entries.
; Returns: A = C
; ----------------------------------------------------------------------------
InitTileColumn:
    PHA                 ; Save C on stack ($01,S)

    ; Calculate tilemap byte offset:
    ; Top tile: x_start + (C * 2)
    ; Bottom tile: x_start + 64 + (C * 2)
    ASL                 ; C * 2
    CLC
    ADC $E8             ; + x_start ($E8)
    TAX                 ; X = tilemap offset for top tile

    ; Tile IDs:
    ; Top tile ID = base_tile + (C * 2)
    ; Bottom tile ID = Top tile ID + 1
    LDA $01,S           ; C
    ASL                 ; C * 2
    CLC
    ADC $E6             ; + base_tile ($E6)
    SEP #$20            ; 8-bit A

    ; Set Top tile on tilemap:
    STA $7EC780,X       ; Top tile ID
    LDA $A8
    STA $7EC781,X       ; Top tile attribute

    ; Set Bottom tile on tilemap (row + 1 = +64 bytes):
    REP #$20
    LDA $01,S           ; C
    ASL
    CLC
    ADC $E6             ; + base_tile
    INC A               ; Top tile ID + 1
    SEP #$20
    STA $7EC7C0,X       ; Bottom tile ID
    LDA $A8
    STA $7EC7C1,X       ; Bottom tile attribute

    ; Clear 32 bytes in $7E:CE80 at (base_tile + C * 2) * 16:
    REP #$20
    LDA $01,S           ; C
    ASL
    CLC
    ADC $E6             ; + base_tile
    ASL : ASL : ASL : ASL ; * 16 bytes
    TAX                 ; X = destination offset in $7E:CE80

    LDA #$0000
    STA $7ECE80+0,X
    STA $7ECE80+2,X
    STA $7ECE80+4,X
    STA $7ECE80+6,X
    STA $7ECE80+8,X
    STA $7ECE80+10,X
    STA $7ECE80+12,X
    STA $7ECE80+14,X
    STA $7ECE80+16,X
    STA $7ECE80+18,X
    STA $7ECE80+20,X
    STA $7ECE80+22,X
    STA $7ECE80+24,X
    STA $7ECE80+26,X
    STA $7ECE80+28,X
    STA $7ECE80+30,X

    PLA                 ; Restore C
    RTS

; ----------------------------------------------------------------------------
; Subroutine: BlitTopTileRows
; Inputs:
;   Y = font_ptr (DB:FontVWF)
;   X = dest_offset ($7E:CE80)
; Blits rows 0..7 of FG and SH across col_start and col_start + 1.
; ----------------------------------------------------------------------------
BlitTopTileRows:
    SEP #$20
    LDA FontVWF+0,Y     : JSR BlitRow_FG_Top0
    LDA FontVWF+8,Y     : JSR BlitRow_SH_Top0
    LDA FontVWF+1,Y     : JSR BlitRow_FG_Top1
    LDA FontVWF+9,Y     : JSR BlitRow_SH_Top1
    LDA FontVWF+2,Y     : JSR BlitRow_FG_Top2
    LDA FontVWF+10,Y    : JSR BlitRow_SH_Top2
    LDA FontVWF+3,Y     : JSR BlitRow_FG_Top3
    LDA FontVWF+11,Y    : JSR BlitRow_SH_Top3
    LDA FontVWF+4,Y     : JSR BlitRow_FG_Top4
    LDA FontVWF+12,Y    : JSR BlitRow_SH_Top4
    LDA FontVWF+5,Y     : JSR BlitRow_FG_Top5
    LDA FontVWF+13,Y    : JSR BlitRow_SH_Top5
    LDA FontVWF+6,Y     : JSR BlitRow_FG_Top6
    LDA FontVWF+14,Y    : JSR BlitRow_SH_Top6
    LDA FontVWF+7,Y     : JSR BlitRow_FG_Top7
    LDA FontVWF+15,Y    : JSR BlitRow_SH_Top7
    RTS

; ----------------------------------------------------------------------------
; Subroutine: BlitBottomTileRows
; Inputs:
;   Y = font_ptr (DB:FontVWF)
;   X = dest_offset ($7E:CE80)
; Blits rows 8..15 of FG and SH across col_start and col_start + 1.
; ----------------------------------------------------------------------------
BlitBottomTileRows:
    SEP #$20
    LDA FontVWF+16,Y    : JSR BlitRow_FG_Btm0
    LDA FontVWF+24,Y    : JSR BlitRow_SH_Btm0
    LDA FontVWF+17,Y    : JSR BlitRow_FG_Btm1
    LDA FontVWF+25,Y    : JSR BlitRow_SH_Btm1
    LDA FontVWF+18,Y    : JSR BlitRow_FG_Btm2
    LDA FontVWF+26,Y    : JSR BlitRow_SH_Btm2
    LDA FontVWF+19,Y    : JSR BlitRow_FG_Btm3
    LDA FontVWF+27,Y    : JSR BlitRow_SH_Btm3
    LDA FontVWF+20,Y    : JSR BlitRow_FG_Btm4
    LDA FontVWF+28,Y    : JSR BlitRow_SH_Btm4
    LDA FontVWF+21,Y    : JSR BlitRow_FG_Btm5
    LDA FontVWF+29,Y    : JSR BlitRow_SH_Btm5
    LDA FontVWF+22,Y    : JSR BlitRow_FG_Btm6
    LDA FontVWF+30,Y    : JSR BlitRow_SH_Btm6
    LDA FontVWF+23,Y    : JSR BlitRow_FG_Btm7
    LDA FontVWF+31,Y    : JSR BlitRow_SH_Btm7
    RTS

; Row Blitting Helpers:
macro BlitFG(dest_offset)
    BEQ +
    XBA
    LDA #$00
    REP #$20
    JSR ShiftWord
    SEP #$20
    XBA
    ORA $7ECE80+<dest_offset>,X
    STA $7ECE80+<dest_offset>,X
    XBA
    BEQ +
    ORA $7ECE80+32+<dest_offset>,X
    STA $7ECE80+32+<dest_offset>,X
+   RTS
endmacro

macro BlitSH(dest_offset)
    BEQ +
    XBA
    LDA #$00
    REP #$20
    JSR ShiftWord
    SEP #$20
    XBA
    ORA $7ECE80+<dest_offset>,X
    STA $7ECE80+<dest_offset>,X
    XBA
    BEQ +
    ORA $7ECE80+32+<dest_offset>,X
    STA $7ECE80+32+<dest_offset>,X
+   RTS
endmacro

BlitRow_FG_Top0: %BlitFG(0)
BlitRow_SH_Top0: %BlitSH(1)
BlitRow_FG_Top1: %BlitFG(2)
BlitRow_SH_Top1: %BlitSH(3)
BlitRow_FG_Top2: %BlitFG(4)
BlitRow_SH_Top2: %BlitSH(5)
BlitRow_FG_Top3: %BlitFG(6)
BlitRow_SH_Top3: %BlitSH(7)
BlitRow_FG_Top4: %BlitFG(8)
BlitRow_SH_Top4: %BlitSH(9)
BlitRow_FG_Top5: %BlitFG(10)
BlitRow_SH_Top5: %BlitSH(11)
BlitRow_FG_Top6: %BlitFG(12)
BlitRow_SH_Top6: %BlitSH(13)
BlitRow_FG_Top7: %BlitFG(14)
BlitRow_SH_Top7: %BlitSH(15)

BlitRow_FG_Btm0: %BlitFG(16)
BlitRow_SH_Btm0: %BlitSH(17)
BlitRow_FG_Btm1: %BlitFG(18)
BlitRow_SH_Btm1: %BlitSH(19)
BlitRow_FG_Btm2: %BlitFG(20)
BlitRow_SH_Btm2: %BlitSH(21)
BlitRow_FG_Btm3: %BlitFG(22)
BlitRow_SH_Btm3: %BlitSH(23)
BlitRow_FG_Btm4: %BlitFG(24)
BlitRow_SH_Btm4: %BlitSH(25)
BlitRow_FG_Btm5: %BlitFG(26)
BlitRow_SH_Btm5: %BlitSH(27)
BlitRow_FG_Btm6: %BlitFG(28)
BlitRow_SH_Btm6: %BlitSH(29)
BlitRow_FG_Btm7: %BlitFG(30)
BlitRow_SH_Btm7: %BlitSH(31)

; ----------------------------------------------------------------------------
; Subroutine: ShiftWord
; Inputs:
;   A = 16-bit word (high byte = glyph byte, low byte = 0)
;   $EA = bit_shift (0..7)
; Outputs:
;   A = shifted 16-bit word
; Preserves: X, Y
; ----------------------------------------------------------------------------
ShiftWord:
    PHX                 ; Preserve X (dest_offset)
    LDX $EA             ; bit_shift (0..7)
    BEQ .s0
-   LSR A
    DEX
    BNE -
.s0:
    PLX                 ; Restore X
    RTS

; ----------------------------------------------------------------------------
; Subroutine: CleanShadowMask
; Inputs:
;   X = dest_offset ($7E:CE80)
; Masks Plane 1 &= ~Plane 0 for all 16 rows of col_start and col_start + 1.
; ----------------------------------------------------------------------------
CleanShadowMask:
    SEP #$20            ; 8-bit A
    macro MaskRow(p0_off, p1_off)
        LDA $7ECE80+<p0_off>,X
        EOR #$FF
        AND $7ECE80+<p1_off>,X
        STA $7ECE80+<p1_off>,X
    endmacro

    ; Col_start Top Tile:
    %MaskRow(0, 1)   : %MaskRow(2, 3)   : %MaskRow(4, 5)   : %MaskRow(6, 7)
    %MaskRow(8, 9)   : %MaskRow(10, 11) : %MaskRow(12, 13) : %MaskRow(14, 15)

    ; Col_start Bottom Tile:
    %MaskRow(16, 17) : %MaskRow(18, 19) : %MaskRow(20, 21) : %MaskRow(22, 23)
    %MaskRow(24, 25) : %MaskRow(26, 27) : %MaskRow(28, 29) : %MaskRow(30, 31)

    ; Col_start+1 Top Tile:
    %MaskRow(32, 33) : %MaskRow(34, 35) : %MaskRow(36, 37) : %MaskRow(38, 39)
    %MaskRow(40, 41) : %MaskRow(42, 43) : %MaskRow(44, 45) : %MaskRow(46, 47)

    ; Col_start+1 Bottom Tile:
    %MaskRow(48, 49) : %MaskRow(50, 51) : %MaskRow(52, 53) : %MaskRow(54, 55)
    %MaskRow(56, 57) : %MaskRow(58, 59) : %MaskRow(60, 61) : %MaskRow(62, 63)
    RTS

; ----------------------------------------------------------------------------
; Embedded VWF Font Data (3,040 bytes: 95 glyphs x 32 bytes)
; ----------------------------------------------------------------------------
FontVWF:
    incbin "vwf_font.bin"

; ----------------------------------------------------------------------------
; Embedded Proportional Width Table (95 bytes)
; ----------------------------------------------------------------------------
WidthTableVWF:
    incbin "vwf_widths.bin"
