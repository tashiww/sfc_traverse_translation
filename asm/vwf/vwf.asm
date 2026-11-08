; ============================================================================
; Traverse: Starlight & Prairie - Proportional Variable-Width Font (VWF) Engine
; Real-time 2bpp sub-pixel rasterizer with exterior drop shadow & typewriter
; ============================================================================

hirom

; Universal Hook into Dialogue Character Line Renderer at $DC:CAA1
; In clean ROM:
;   $DC:CA8F: PHP : PHB : SEP #$20 : STZ $A6 : STA $A5 : BRA $DCCAA1
;   $DC:CA99: PHP : PHB : SEP #$20 : LDA #$DB : STA $A5 : BRA $DCCAA1 (falls through)
;   $DC:CAA1: LDA #$D3 : PHA : PLB (4 bytes: A9 D3 48 AB)
; Every dialogue renderer in the entire game (cutscene macro 0x06, regular NPC
; interactions, map events, dialogue boxes) calls $DC:CA99 or $DC:CA8F and
; converges at $DC:CAA1.
; By placing a JML here, ALL dialogue automatically routes to RenderEnglishVWF!
org $DCCAA1
    JML RenderEnglishVWF

; ----------------------------------------------------------------------------
; Dynamic String Redirection Table in Bank $CA
; Allows any dialogue string in any bank to be transparently repointed to
; unmapped free space in Bank $CA without modifying original bytecode.
; Format per entry (8 bytes):
;   +0: orig_addr (16-bit LE)
;   +2: orig_bank (8-bit)
;   +3: new_addr  (16-bit LE)
;   +5: new_bank  (8-bit)
;   +6: orig_len  (16-bit LE)
; Table ends with $0000 (16-bit orig_addr == 0).
; ----------------------------------------------------------------------------
org $CA7000
StringRedirectTable:
    fillbyte $00 : fill 4096

; ----------------------------------------------------------------------------
; Engine Code & Font Data in Bank $CA Free Space ($CA8000+)
; ----------------------------------------------------------------------------
org $CA8000

; ----------------------------------------------------------------------------
; Direct Page Scratch Allocations (Local to VWF Line Renderer):
;   $D4: current_col (16-bit: current col parameter)
;   $D6: current_row (16-bit: current row parameter)
;   $D8: orig_addr   (16-bit: saved caller $A3)
;   $DA: orig_bank   (8-bit: saved caller $A5)
;   $DB: is_redirect (8-bit: 0=normal, 1=redirected)
;   $DC: orig_len    (16-bit: original string byte budget)
;   $DE: max_col     (16-bit: highest initialized tile column)
;   $E0: cursor_x    (16-bit: horizontal pixel position 0..223)
;   $E2: col_start   (16-bit: cursor_x >> 3)
;   $E4: font_ptr    (16-bit: offset in FontVWF)
;   $E6: base_tile   (16-bit: starting Base Tile ID for this line)
;   $E8: x_start     (16-bit: starting tilemap byte offset)
;   $EA: bit_shift   (16-bit: cursor_x & 7)
;   $EC: dest_off    (16-bit: destination byte offset in $7E:CE80)
;   $EE: char_width  (16-bit: character proportional width / total_cols)
;   $F0: char_raw    (8-bit: current table character code)
; ----------------------------------------------------------------------------

; ----------------------------------------------------------------------------
; Proportional VWF Line Renderer
; Inputs:
;   [$A3] = 24-bit pointer to dialogue string
;   $A8   = Tile attribute byte ($2B)
;   Stack layout at entry (relative to S from caller $DC:CA8F / $DC:CA99):
;     $01,S: caller DB (pushed by PHB)
;     $02,S: caller P  (pushed by PHP)
;     $03,S..$05,S: JSL return address
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
    ; Note: Caller ($DC:CA8F or $DC:CA99) already executed PHP : PHB : SEP #$20.
    ; Do NOT push PHP : PHB again!

    ; ------------------------------------------------------------------------
    ; Dynamic String Redirection Check:
    ; Checks if [$A3] matches an entry in StringRedirectTable.
    ; If matched, repoints [$A3] to the allocated free space pool in Bank $CA.
    ; ------------------------------------------------------------------------
    REP #$30            ; 16-bit A, X, Y
    PHX
    STZ $D8             ; Clear saved orig_addr
    STZ $DA             ; Clear orig_bank / is_redirect
    STZ $DC             ; Clear orig_len
    LDX #$0000
.redirect_loop:
    LDA.l StringRedirectTable,X     ; 16-bit orig_addr
    BEQ .redirect_done              ; $0000 marks end of table
    CMP $A3                         ; Compare 16-bit address
    BNE +
    SEP #$20                        ; 8-bit A
    LDA.l StringRedirectTable+2,X   ; 8-bit orig_bank
    CMP $A5                         ; Compare bank byte
    REP #$20                        ; 16-bit A
    BNE +
    ; Match found! Save original caller state:
    LDA $A3
    STA $D8                         ; $D8 = saved orig_addr
    SEP #$20
    LDA $A5
    STA $DA                         ; $DA = saved orig_bank
    LDA #$01
    STA $DB                         ; $DB = is_redirect flag = 1
    REP #$20
    LDA.l StringRedirectTable+6,X   ; 16-bit orig_len
    STA $DC                         ; $DC = saved orig_len
    ; Repoint read pointer [$A3] to new 24-bit pointer in Bank $CA pool:
    LDA.l StringRedirectTable+3,X   ; 16-bit new_addr
    STA $A3
    SEP #$20                        ; 8-bit A
    LDA.l StringRedirectTable+5,X   ; 8-bit new_bank
    STA $A5
    REP #$20                        ; 16-bit A
    BRA .redirect_done
+   TXA
    CLC
    ADC #$0008                      ; Next entry (8 bytes)
    TAX
    BRA .redirect_loop

.redirect_done:
    PLX

    ; Check if string was redirected in StringRedirectTable:
    SEP #$20            ; 8-bit A
    REP #$10            ; 16-bit X, Y
    LDA $DB             ; is_redirect flag
    BNE .is_english     ; Redirected -> execute English VWF engine!

    ; Untranslated string: resume pristine native Japanese renderer at $DC:CAA5:
    LDA #$D3
    PHA
    PLB                 ; DB = $D3
    JML $DCCAA5

.is_english:
    PHK
    PLB                 ; DB = Current Bank ($CA)

    ; Read starting Base Tile ID from caller stack:
    SEP #$20            ; 8-bit A
    LDA $06,S           ; caller Base Tile ID
    REP #$20            ; 16-bit A
    AND #$00FF
    STA $E6             ; $E6 = base_tile

    ; Read starting Col from caller stack:
    SEP #$20            ; 8-bit A
    LDA $07,S           ; Col parameter
    REP #$20            ; 16-bit A
    AND #$00FF
    STA $D4             ; $D4 = current_col

    ; Read starting Row from caller stack:
    SEP #$20            ; 8-bit A
    LDA $08,S           ; Row parameter
    REP #$20            ; 16-bit A
    AND #$00FF
    STA $D6             ; $D6 = current_row

    ; Calculate starting tilemap byte offset:
    JSR .calc_row_offset

    ; Initialize line variables:
    STZ $DE             ; max_col = 0
    STZ $E0             ; cursor_x = 0

    ; Initialize tile column 0:
    LDA #$0000
    JSR InitTileColumn

    ; Y = string read offset
    LDY #$0000
    BRA .char_loop

.calc_row_offset:
    REP #$30            ; 16-bit A, X, Y
    LDA $D6             ; current_row
    AND #$00FF
    XBA                 ; A = Row << 8
    LSR : LSR           ; A = Row * 64 bytes
    CLC
    ADC $D4
    ADC $D4             ; + (Col * 2)
    AND #$07FE          ; Safety mask
    STA $E8             ; $E8 = x_start
    RTS

.char_loop:
    SEP #$20            ; 8-bit A
    LDA [$A3],Y
    INY
    CMP #$FF            ; End of message / dialogue box ($FF)
    BNE +
    JMP .line_done
+   CMP #$80            ; In-box newline ($80) -> next line in same dialogue box!
    BNE +
    JMP .do_newline
+   CMP #$FE            ; If $FE $00 delimiter:
    BNE +
    LDA [$A3],Y         ; Peek next byte
    CMP #$00
    BNE .char_loop
    INY                 ; Skip $00
    BRA .char_loop
+   CMP #$F0            ; Dynamic character name tags ($F0 = protag, $F1 = sub, $F2 = pet)
    BCC +
    CMP #$F3
    BCS +
    JMP .handle_var_name
+   CMP #$00            ; Native Space ($00)
    BNE +
    JSR AdvanceSpace
    BRA .char_loop
+   ; Character in en_tbl: direct table index (zero ASCII math!)
    JSR DrawSingleChar
    JMP .char_loop

.do_newline:
    ; Clean up speculative columns on this line:
    REP #$20            ; 16-bit A
    LDA $E0             ; cursor_x
    CLC
    ADC #$0007
    LSR : LSR : LSR     ; total_cols
    BNE +
    LDA #$0001
+   STA $EE
-   LDA $DE             ; max_col
    CMP $EE
    BCC .nl_cleaned
    ASL
    CLC
    ADC $E8             ; + x_start
    TAX
    LDA #$0000
    STA $7EC780,X       ; Clear top
    STA $7EC7C0,X       ; Clear bottom
    DEC $DE
    BRA -

.nl_cleaned:
    ; Advance base_tile by total_cols * 2:
    LDA $EE             ; total_cols
    ASL
    CLC
    ADC $E6             ; base_tile
    STA $E6

    ; Advance current_row by 2:
    LDA $D6             ; current_row
    CLC
    ADC #$0002
    STA $D6

    ; Reset line variables:
    STZ $DE             ; max_col = 0
    STZ $E0             ; cursor_x = 0

    ; Recalculate x_start and initialize tile column 0 for new line:
    JSR .calc_row_offset
    LDA #$0000
    JSR InitTileColumn

    JMP .char_loop

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
    CMP #$00            ; Null terminator / blank
    BEQ .var_done
    CMP #$8B            ; Japanese blank filler
    BEQ .var_done

    ; Name bytes in WRAM already match en_tbl.tbl directly (zero conversion needed!):
    JSR DrawSingleChar
    BRA .var_char_loop
.var_done:
    PLY                 ; Restore caller string offset Y
    JMP .char_loop

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

    ; Calculate total consumed tile columns for the final line:
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
    ADC $E6             ; Add to current base_tile ($E6)
    STA $06,S           ; Updated Base Tile ID!

    ; Compute final tilemap offset for caller:
    ; X = x_start + (total_cols * 2)
    REP #$20            ; 16-bit A
    LDA $EE             ; total_cols
    ASL                 ; total_cols * 2
    CLC
    ADC $E8             ; + x_start ($E8)
    TAX                 ; X = final tilemap byte offset!

    ; ------------------------------------------------------------------------
    ; State Restoration for String Redirection:
    ; ------------------------------------------------------------------------
    SEP #$20            ; 8-bit A
    LDA $DB             ; is_redirect
    BEQ .restore_normal

    ; Redirected string:
    ; 1. Restore caller $A3 to original Bank $F3 address:
    REP #$20            ; 16-bit A
    LDA $D8             ; saved orig_addr
    STA $A3
    ; 2. Restore caller $A5 to original Bank $F3:
    SEP #$20            ; 8-bit A
    LDA $DA             ; saved orig_bank
    STA $A5
    ; 3. Return Y = orig_len so caller advances past original Bank $F3 string:
    REP #$10            ; 16-bit X, Y
    LDY $DC             ; Y = orig_len!
    BRA .exit_renderer

.restore_normal:
    ; Normal non-redirected string:
    ; Y already has consumed bytes count!

.exit_renderer:
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
;   A = Character code in en_tbl (0x01 - 0xEF)
; Preserves:
;   Caller X, Y
; ----------------------------------------------------------------------------
DrawSingleChar:
    STA $F0             ; Save character code in $F0
    PHY                 ; Save caller Y
    PHX                 ; Save caller X

    ; Look up character width directly by table code (zero ASCII math!):
    REP #$20            ; 16-bit A
    AND #$00FF
    TAX                 ; X = char code (0..255)
    SEP #$20
    LDA.l WidthTableVWF,X
    REP #$20
    AND #$00FF
    STA $EE             ; $EE = char_width

    ; Calculate font data offset: char_code * 32 bytes
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
    ; Typewriter synchronization via direct VBlank DMA:
    ; Transfers $7E:CE80 glyph buffer to VRAM $5800 at 60fps without touching
    ; or overrunning the cutscene macro script [$D1]!
    SEP #$20            ; 8-bit A
    STZ $B8
    STZ $B6             ; Mode 0: glyph buffer DMA
    LDA.l $004210
-   LDA.l $004210
    BPL -

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
