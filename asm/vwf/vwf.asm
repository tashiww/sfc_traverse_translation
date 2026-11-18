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

; Universal Hook into Overworld / Continent Cutscene Dialogue Setup at $C0:1B63
; In clean ROM:
;   $C0:1B63: STA $040B : SEP #$20 : LDA $3D : STA $040A (10 bytes: 8D 0B 04 E2 20 A5 3D 8D 0A 04)
; Replaces with JSL Engine2_Redirect to transparently repoint cutscene dialogue to Bank $CA!
org $C01B63
    JSL Engine2_Redirect
    NOP : NOP : NOP : NOP : NOP : NOP

; Universal Hook into Engine 2 Character Blitter at $C0:34A4
; In clean ROM:
;   $C0:34A4: REP #$20 : ASL : ASL (4 bytes: C2 20 0A 0A)
; Replaces with JML Engine2_CharBlit to provide proportional Variable-Width Font blitting!
org $C034A4
    JML Engine2_CharBlit

; Universal Hook into Status Bar Location Setup at $C0:36E1
org $C036E1
    SEP #$20
    JSL LocationVWF_Setup
    SEP #$20
    PLB
    RTS
    padbyte $EA : pad $C03703

; Universal Hook into Status Bar VRAM Transfer at $C0:0FE5
org $C00FE5
    JSL LocationVWF_TransferHook

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
    CMP #$86            ; '!'
    BNE +
    LDA #$86            ; Japanese '！' -> pause
    BRA .do_tick
+   CMP #$87            ; '?'
    BNE +
    LDA #$87            ; Japanese '？' -> pause
    BRA .do_tick
+   CMP #$88            ; ','
    BNE +
    LDA #$88            ; Japanese '、' -> pause
    BRA .do_tick
+   CMP #$89            ; '.'
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
; Engine2_Redirect:
; Intercepts Overworld / Continent Cutscene Dialogue setup at $C0:1B64.
; If (orig_addr, orig_bank) matches an entry in StringRedirectTable,
; redirects $040B and $040A to the relocated string in Bank $CA.
; Inputs:
;   16-bit A = orig_addr (from ADC $3B)
;   Direct Page $3D = orig_bank
; Outputs:
;   $040B = new_addr (or orig_addr if not redirected)
;   $040A = new_bank (or orig_bank if not redirected)
;   SEP #$20 (8-bit A) upon return
; ----------------------------------------------------------------------------
Engine2_Redirect:
    PHP
    PHB
    PHX
    PHY

    REP #$30            ; 16-bit A, X, Y
    PHA                 ; Save 16-bit orig_addr on stack ($01,S)

    ; Store default (orig_addr and orig_bank) into $040B and $040A:
    STA $040B
    SEP #$20            ; 8-bit A
    LDA $3D             ; orig_bank
    STA $040A
    REP #$20            ; 16-bit A

    ; Search StringRedirectTable in Bank $CA:
    LDX #$0000
.loop:
    LDA.l StringRedirectTable,X     ; 16-bit orig_addr
    BEQ .done                       ; End of table ($0000)
    CMP $01,S                       ; Compare orig_addr
    BNE +
    SEP #$20                        ; 8-bit A
    LDA.l StringRedirectTable+2,X   ; 8-bit orig_bank
    CMP $3D
    REP #$20                        ; 16-bit A
    BNE +
    ; Match found in StringRedirectTable!
    LDA.l StringRedirectTable+3,X   ; 16-bit new_addr
    STA $040B
    SEP #$20                        ; 8-bit A
    LDA.l StringRedirectTable+5,X   ; 8-bit new_bank
    STA $040A
    REP #$20                        ; 16-bit A
    BRA .done

+   TXA
    CLC
    ADC #$0008                      ; Next entry (8 bytes)
    TAX
    BRA .loop

.done:
    PLA                 ; Drop orig_addr from stack
    PLY
    PLX
    PLB
    PLP
    SEP #$20            ; Ensure 8-bit A for caller
    RTL

; ----------------------------------------------------------------------------
; Engine2_CharBlit:
; Proportional Variable-Width Font (VWF) Character Blitter for Engine 2.
; Intercepts character blitter calls at $C0:34A4.
; Inputs:
;   16-bit A = char_code (caller set A in 8-bit mode, B cleared to 0)
;   $040A    = string bank byte ($CA for English)
;   $0411    = native line start toggle (0 = new line start, reset by $C0:332F)
;   $0412    = horizontal cursor offset in $7E:8000
;   $0414    = horizontal pixel cursor cursor_x (8..240)
; Outputs:
;   RTL with SEP #$20 (8-bit A)
; ----------------------------------------------------------------------------
Engine2_CharBlit:
    ; Clean ROM at $C0:34A4 executed REP #$20 first!
    ; Caller ($C0:33CC) is in 8-bit mode (M=1). We MUST execute REP #$20 first
    ; so that 16-bit char_code is restored and stack operations are 16-bit!
    REP #$20            ; 16-bit Accumulator
    PHA                 ; Save 16-bit char_code on stack (2 bytes)
    SEP #$20            ; 8-bit Accumulator
    LDA.l $7E040A       ; Read string bank byte from WRAM $7E:040A
    CMP #$CA
    BEQ .check_char

.native_jp:
    REP #$20            ; 16-bit A
    PLA                 ; Restore original 16-bit char_code
    ASL A               ; Execute the 2 ASLs replaced by hook at $C0:34A4
    ASL A
    JML $C034A8         ; Jump to remaining 4 ASLs and native blitter in Bank $C0

.check_char:
    REP #$20            ; 16-bit A
    PLA                 ; Restore original 16-bit char_code
    CMP #$0100          ; Check if 2-byte Japanese character code (>= $0100)
    BCC .is_vwf
    ASL A
    ASL A
    JML $C034A8

.is_vwf:
    PHP                 ; Save caller status flags (1 byte)
    REP #$30            ; 16-BIT ACCUMULATOR AND 16-BIT INDEX (X, Y) FOR ENTIRE VWF BLITTER!
    PHB                 ; Save caller Data Bank (1 byte)
    PHX                 ; Save caller 16-bit X (2 bytes)
    PHY                 ; Save caller 16-bit Y (2 bytes)
    PHA                 ; Stack $01,S = 16-bit char_code (2 bytes)

    ; Set DB = Current Bank ($CA) to read FontVWF and WidthTableVWF:
    PHK
    PLB

    ; Check if new line was initialized ($7E:0411 == 0):
    SEP #$20            ; 8-bit A
    LDA.l $7E0411
    BNE +
    ; New line started! Initialize cursor_x to 8 pixels margin:
    LDA #$01
    STA.l $7E0411       ; Mark line initialized
    REP #$20
    LDA #$0008          ; cursor_x = 8 pixels
    STA.l $7E0414
    BRA ++
+   REP #$20
++

    ; Check if char_code is Space ($0000):
    LDA $01,S
    BNE .not_space

    ; Space character:
    ; If cursor_x == 8 (very start of line), absorb leading delimiter space without advancing:
    LDA.l $7E0414
    CMP #$0008
    BEQ .update_cursor
    ; Normal in-line space: advance cursor_x by 4 pixels:
    CLC
    ADC #$0004
    STA.l $7E0414
    BRA .update_cursor

.not_space:
    ; Character in en_tbl.tbl: look up proportional width:
    TAX                 ; X = 16-bit char_code
    SEP #$20            ; 8-bit A
    LDA.l WidthTableVWF,X
    REP #$20            ; 16-bit A
    AND #$00FF
    BNE +
    LDA #$0006          ; Default width = 6 px
+   PHA                 ; Stack $01,S = 16-bit char_width, $03,S = 16-bit char_code

    ; Compute font_ptr = char_code * 32:
    LDA $03,S
    ASL : ASL : ASL : ASL : ASL
    TAY                 ; Y = font_ptr in Bank $CA

    ; Compute bit_shift = cursor_x & 7:
    LDA.l $7E0414
    AND #$0007
    STA $EA             ; $EA = bit_shift (0..7, high byte $EB is 0)

    ; Compute col_start = cursor_x >> 3, col_offset = col_start * 16:
    LDA.l $7E0414
    LSR : LSR : LSR
    ASL : ASL : ASL : ASL
    TAX                 ; X = col_offset in $7E:8000

    ; Safety bounds check: don't write past line buffer (col_offset < 496):
    CPX #$01F0
    BCS .skip_blit

    ; Blit 8 rows of Top Tile (rows 0..7) into $7E:8000:
    JSR Engine2_BlitTopRows

    ; Blit 8 rows of Bottom Tile (rows 8..15) into $7E:8200:
    JSR Engine2_BlitBottomRows

    ; Clean Drop Shadow Mask (Plane 1 &= ~Plane 0):
    JSR Engine2_CleanShadowMask

.skip_blit:
    REP #$20            ; CRUCIAL: Restore 16-bit A after blitting subroutines!
    ; Advance cursor_x += char_width:
    PLA                 ; Pull 16-bit char_width from stack
    CLC
    ADC.l $7E0414
    STA.l $7E0414

.update_cursor:
    REP #$20            ; Ensure 16-bit A
    ; Synchronize $0412 with native state machine:
    ; If cursor_x >= 240, trigger automatic newline ($0412 = $01F0):
    LDA.l $7E0414
    CMP #$00F0
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
    REP #$30            ; Ensure 16-bit A, X, Y for clean pops
    PLA                 ; Drop 16-bit char_code from stack
    PLY                 ; Restore caller 16-bit Y
    PLX                 ; Restore caller 16-bit X
    PLB                 ; Restore caller DB
    PLP                 ; Restore caller P (original M and X restored!)
    SEP #$20            ; Guarantee 8-bit Accumulator for caller at $C0:33CC
    RTL

; ----------------------------------------------------------------------------
; Engine2 Blitting Subroutines
; ----------------------------------------------------------------------------
macro E2_BlitRow(fg_offset, sh_offset, base_addr, p0_off, p1_off)
    LDA.w FontVWF+<fg_offset>,Y
    BEQ ?no_fg
    XBA
    LDA #$00
    REP #$20
    JSR ShiftWord
    SEP #$20
    XBA
    ORA.l <base_addr>+<p0_off>,X
    STA.l <base_addr>+<p0_off>,X
    XBA
    BEQ ?no_fg
    ORA.l <base_addr>+16+<p0_off>,X
    STA.l <base_addr>+16+<p0_off>,X
?no_fg:
    LDA.w FontVWF+<sh_offset>,Y
    BEQ ?no_sh
    XBA
    LDA #$00
    REP #$20
    JSR ShiftWord
    SEP #$20
    XBA
    ORA.l <base_addr>+<p1_off>,X
    STA.l <base_addr>+<p1_off>,X
    XBA
    BEQ ?no_sh
    ORA.l <base_addr>+16+<p1_off>,X
    STA.l <base_addr>+16+<p1_off>,X
?no_sh:
endmacro

Engine2_BlitTopRows:
    SEP #$20
    %E2_BlitRow(0, 8,  $7E8000, 0,  1)
    %E2_BlitRow(1, 9,  $7E8000, 2,  3)
    %E2_BlitRow(2, 10, $7E8000, 4,  5)
    %E2_BlitRow(3, 11, $7E8000, 6,  7)
    %E2_BlitRow(4, 12, $7E8000, 8,  9)
    %E2_BlitRow(5, 13, $7E8000, 10, 11)
    %E2_BlitRow(6, 14, $7E8000, 12, 13)
    %E2_BlitRow(7, 15, $7E8000, 14, 15)
    RTS

Engine2_BlitBottomRows:
    SEP #$20
    %E2_BlitRow(16, 24, $7E8200, 0,  1)
    %E2_BlitRow(17, 25, $7E8200, 2,  3)
    %E2_BlitRow(18, 26, $7E8200, 4,  5)
    %E2_BlitRow(19, 27, $7E8200, 6,  7)
    %E2_BlitRow(20, 28, $7E8200, 8,  9)
    %E2_BlitRow(21, 29, $7E8200, 10, 11)
    %E2_BlitRow(22, 30, $7E8200, 12, 13)
    %E2_BlitRow(23, 31, $7E8200, 14, 15)
    RTS

macro E2_MaskRow(addr)
    LDA.l <addr>,X
    EOR #$FF
    AND.l <addr>+1,X
    STA.l <addr>+1,X
endmacro

Engine2_CleanShadowMask:
    SEP #$20
    ; Top tile col_start
    %E2_MaskRow($7E8000+0)  : %E2_MaskRow($7E8000+2)
    %E2_MaskRow($7E8000+4)  : %E2_MaskRow($7E8000+6)
    %E2_MaskRow($7E8000+8)  : %E2_MaskRow($7E8000+10)
    %E2_MaskRow($7E8000+12) : %E2_MaskRow($7E8000+14)

    ; Top tile col_start + 1
    %E2_MaskRow($7E8010+0)  : %E2_MaskRow($7E8010+2)
    %E2_MaskRow($7E8010+4)  : %E2_MaskRow($7E8010+6)
    %E2_MaskRow($7E8010+8)  : %E2_MaskRow($7E8010+10)
    %E2_MaskRow($7E8010+12) : %E2_MaskRow($7E8010+14)

    ; Bottom tile col_start
    %E2_MaskRow($7E8200+0)  : %E2_MaskRow($7E8200+2)
    %E2_MaskRow($7E8200+4)  : %E2_MaskRow($7E8200+6)
    %E2_MaskRow($7E8200+8)  : %E2_MaskRow($7E8200+10)
    %E2_MaskRow($7E8200+12) : %E2_MaskRow($7E8200+14)

    ; Bottom tile col_start + 1
    %E2_MaskRow($7E8210+0)  : %E2_MaskRow($7E8210+2)
    %E2_MaskRow($7E8210+4)  : %E2_MaskRow($7E8210+6)
    %E2_MaskRow($7E8210+8)  : %E2_MaskRow($7E8210+10)
    %E2_MaskRow($7E8210+12) : %E2_MaskRow($7E8210+14)
    RTS


; ----------------------------------------------------------------------------

; ----------------------------------------------------------------------------
; LocationVWF_TransferHook:
; Replaces JSL $C0102E at $C0:0FE5.
; Runs original $C0102E, then DMAs 384 bytes from $7F:F700 to VRAM word $2300 (0x4600).
; ----------------------------------------------------------------------------
LocationVWF_TransferHook:
    JSL $C0102E         ; Execute original calendar setup at $C0:102E!

    PHP
    PHB
    PEA $0000 : PLB : PLB   ; DB = $00 for hardware registers

    SEP #$20
    LDA #$01 : STA $4300    ; DMA mode 1
    LDA #$18 : STA $4301    ; Dest $2118 (VMDATAL)
    LDA #$00 : STA $4302    ; Source low = $00
    LDA #$F7 : STA $4303    ; Source high = $F7 ($7F:F700)
    LDA #$7F : STA $4304    ; Source bank = $7F ($7F:F700)
    LDA #$80 : STA $4305    ; Size low = $80
    LDA #$01 : STA $4306    ; Size high = $01 (384 bytes)

    STZ $2116               ; VRAM word low = $00
    LDA #$23 : STA $2117    ; VRAM word high = $23 (word address $2300 = byte 0x4600)

    LDA #$01 : STA $420B    ; Fire DMA channel 0!

    PLB
    PLP
    RTL

; ----------------------------------------------------------------------------
; LocationVWF_Setup:
; Intercepts location setup at $C0:36E1.
; Writes tilemap entries $2060..$2077 (Left-aligned in center box: cols 10..21).
; Renders string from [$C1:X] into $7F:F700 with proportional widths.
; ----------------------------------------------------------------------------
LocationVWF_Setup:
    PHP
    PHB
    PHX                 ; Save string pointer X on stack ($01,S)
    PHY

    REP #$30            ; 16-bit A, X, Y

    ; 1. Populate status bar BG3 tilemap in Bank $7F (Center box cols 10..21):
    ; Top row ($7F:F054..$7F:F06A): tiles $60, $62, $64 ... with attr $20
    ; Bottom row ($7F:F094..$7F:F0AA): tiles $61, $63, $65 ... with attr $20
    LDA #$2060 : STA.l $7FF054
    LDA #$2062 : STA.l $7FF056
    LDA #$2064 : STA.l $7FF058
    LDA #$2066 : STA.l $7FF05A
    LDA #$2068 : STA.l $7FF05C
    LDA #$206A : STA.l $7FF05E
    LDA #$206C : STA.l $7FF060
    LDA #$206E : STA.l $7FF062
    LDA #$2070 : STA.l $7FF064
    LDA #$2072 : STA.l $7FF066
    LDA #$2074 : STA.l $7FF068
    LDA #$2076 : STA.l $7FF06A

    LDA #$2061 : STA.l $7FF094
    LDA #$2063 : STA.l $7FF096
    LDA #$2065 : STA.l $7FF098
    LDA #$2067 : STA.l $7FF09A
    LDA #$2069 : STA.l $7FF09C
    LDA #$206B : STA.l $7FF09E
    LDA #$206D : STA.l $7FF0A0
    LDA #$206F : STA.l $7FF0A2
    LDA #$2071 : STA.l $7FF0A4
    LDA #$2073 : STA.l $7FF0A6
    LDA #$2075 : STA.l $7FF0A8
    LDA #$2077 : STA.l $7FF0AA

    ; 2. Clear 384-byte RAM tile buffer at $7F:F700..$7F:F87F to 0:
    LDX #$0000
    TXA
-   STA.l $7FF700,X
    INX : INX
    CPX #$0180
    BCC -

    ; 3. Render location string into $7F:F700:
    LDA $03,S           ; Restore string pointer X
    TAX
    JSR LocationVWF_Render

    PLY
    PLX
    PLB
    PLP
    RTL

; ----------------------------------------------------------------------------
; LocationVWF_Render:
; Pure proportional VWF rasterizer for location banner.
; ----------------------------------------------------------------------------
LocationVWF_Render:
    PHP
    PHB
    PHK : PLB           ; DB = Bank $CA (to read FontVWF and WidthTableVWF)
    REP #$30            ; 16-bit A, X, Y

    ; Preserve DP scratch variables:
    LDA $D4 : PHA
    LDA $D6 : PHA
    LDA $D8 : PHA
    LDA $DA : PHA
    LDA $EA : PHA
    LDA $EC : PHA

    STX $D8             ; $D8 = string read pointer
    STZ $D6             ; $D6 = cursor_x = 0 (Left-aligned in box!)

.blit_loop:
    LDX $D8
    SEP #$20            ; 8-bit A
    LDA.l $C10000,X     ; Read char byte from Bank $C1
    CMP #$FF            ; String terminator?
    BEQ .blit_done
    INX
    STX $D8             ; Advance string pointer

    REP #$20            ; 16-bit A
    AND #$00FF
    PHA                 ; Push char_code on stack ($01,S)

    BEQ .is_space

    ; Non-space char: look up proportional width:
    TAX
    SEP #$20
    LDA.w WidthTableVWF,X
    REP #$20
    AND #$00FF
    PHA                 ; Push char_width on stack ($01,S), char_code is ($03,S)
    BRA .do_blit

.is_space:
    LDA #$0004
    PHA                 ; Space width = 4 pixels ($01,S)
    BRA .skip_char

.do_blit:
    ; Check if cursor_x >= 96 (fits in 12 columns):
    LDA $D6             ; cursor_x
    CMP #$0060          ; 96 pixels = 0x0060
    BCS .skip_char

    ; $EA = bit_shift = cursor_x & 7:
    AND #$0007
    STA $EA

    ; col = cursor_x >> 3:
    LDA $D6
    LSR : LSR : LSR     ; A = col (0..11)
    CMP #$000C          ; col >= 12?
    BCS .skip_char

    ; tile_offset = col * 32:
    ASL : ASL : ASL : ASL : ASL
    STA $EC             ; $EC = tile_offset

    ; font_ptr = char_code * 32:
    LDA $03,S           ; 16-bit char_code
    ASL : ASL : ASL : ASL : ASL
    TAY                 ; Y = font_ptr in FontVWF

    ; Blit glyph:
    JSR LocationVWF_BlitGlyph

.skip_char:
    REP #$20
    PLA                 ; Pull char_width
    CLC
    ADC $D6
    STA $D6             ; cursor_x += char_width
    PLA                 ; Pull char_code
    BRA .blit_loop

.blit_done:
    JSR LocationVWF_CleanShadow

    ; Restore DP scratch variables:
    PLA : STA $EC
    PLA : STA $EA
    PLA : STA $DA
    PLA : STA $D8
    PLA : STA $D6
    PLA : STA $D4

    PLB
    PLP
    RTS

; ----------------------------------------------------------------------------
; LocationVWF_BlitGlyph:
; Blits top tile (FontVWF+0..15) and bottom tile (FontVWF+16..31) into $7F:F700.
; ----------------------------------------------------------------------------
macro Loc_BlitRow(fg_off, sh_off, base_addr, p0_off, p1_off)
    LDA.w FontVWF+<fg_off>,Y
    BEQ ?no_fg
    XBA
    LDA #$00
    REP #$20
    JSR Loc_ShiftWord
    SEP #$20
    XBA
    ORA.l <base_addr>+<p0_off>,X
    STA.l <base_addr>+<p0_off>,X
    XBA
    BEQ ?no_fg
    CPX #$0160
    BCS ?no_fg
    ORA.l <base_addr>+32+<p0_off>,X
    STA.l <base_addr>+32+<p0_off>,X
?no_fg:
    LDA.w FontVWF+<sh_off>,Y
    BEQ ?no_sh
    XBA
    LDA #$00
    REP #$20
    JSR Loc_ShiftWord
    SEP #$20
    XBA
    ORA.l <base_addr>+<p1_off>,X
    STA.l <base_addr>+<p1_off>,X
    XBA
    BEQ ?no_sh
    CPX #$0160
    BCS ?no_sh
    ORA.l <base_addr>+32+<p1_off>,X
    STA.l <base_addr>+32+<p1_off>,X
?no_sh:
endmacro

LocationVWF_BlitGlyph:
    LDX $EC             ; X = tile_offset
    SEP #$20

    ; Top tile rows 0..7:
    %Loc_BlitRow(0, 8,   $7FF700, 0,  1)
    %Loc_BlitRow(1, 9,   $7FF700, 2,  3)
    %Loc_BlitRow(2, 10,  $7FF700, 4,  5)
    %Loc_BlitRow(3, 11,  $7FF700, 6,  7)
    %Loc_BlitRow(4, 12,  $7FF700, 8,  9)
    %Loc_BlitRow(5, 13,  $7FF700, 10, 11)
    %Loc_BlitRow(6, 14,  $7FF700, 12, 13)
    %Loc_BlitRow(7, 15,  $7FF700, 14, 15)

    ; Bottom tile rows 8..15:
    %Loc_BlitRow(16, 24, $7FF710, 0,  1)
    %Loc_BlitRow(17, 25, $7FF710, 2,  3)
    %Loc_BlitRow(18, 26, $7FF710, 4,  5)
    %Loc_BlitRow(19, 27, $7FF710, 6,  7)
    %Loc_BlitRow(20, 28, $7FF710, 8,  9)
    %Loc_BlitRow(21, 29, $7FF710, 10, 11)
    %Loc_BlitRow(22, 30, $7FF710, 12, 13)
    %Loc_BlitRow(23, 31, $7FF710, 14, 15)

    REP #$20
    RTS

; ----------------------------------------------------------------------------
; Loc_ShiftWord:
; Shifts 16-bit A right by $EA (0..7). Preserves X.
; ----------------------------------------------------------------------------
Loc_ShiftWord:
    PHX
    LDX $EA
    BEQ .done
-   LSR A
    DEX
    BNE -
.done:
    PLX
    RTS

; ----------------------------------------------------------------------------
; LocationVWF_CleanShadow:
; Masks Plane 1 &= ~Plane 0 for all 12 columns of 8x16 tiles in $7F:F700.
; ----------------------------------------------------------------------------
LocationVWF_CleanShadow:
    LDX #$0000
.loop:
    SEP #$20
    macro LocMaskRow(off)
        LDA.l $7FF700+<off>,X
        EOR #$FF
        AND.l $7FF700+<off>+1,X
        STA.l $7FF700+<off>+1,X
    endmacro
    %LocMaskRow(0)  : %LocMaskRow(2)  : %LocMaskRow(4)  : %LocMaskRow(6)
    %LocMaskRow(8)  : %LocMaskRow(10) : %LocMaskRow(12) : %LocMaskRow(14)
    %LocMaskRow(16) : %LocMaskRow(18) : %LocMaskRow(20) : %LocMaskRow(22)
    %LocMaskRow(24) : %LocMaskRow(26) : %LocMaskRow(28) : %LocMaskRow(30)

    REP #$20
    TXA
    CLC : ADC #$0020
    TAX
    CPX #$0180
    BCS .done
    JMP .loop
.done:
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
