; ============================================================================
; Traverse: Starlight & Prairie - English Translation Patch
; Asar 65816 Assembly Patch Entry Point
; ============================================================================

hirom

; Master assembly hooks:
incsrc "vwf/vwf.asm"

; ----------------------------------------------------------------------------
; Universal 8x16 English Font in Bank $D2 (PC 0x12E000, 8,192 bytes, 256 glyphs):
; Replaces raw Japanese Kana in location and status banner font with English ASCII.
; ----------------------------------------------------------------------------
org $D2E000
    incbin "vwf/font_bank_d2.bin"

; ----------------------------------------------------------------------------
; Universal 16x16 English Font in Bank $D3 (PC 0x130000, 16,384 bytes, 256 glyphs):
; Replaces raw Japanese Kana with full English ASCII and native glyph sets.
; ----------------------------------------------------------------------------
org $D30000
    incbin "vwf/font_bank_d3.bin"

; ----------------------------------------------------------------------------
; Upgrade 8x8 Menu Font at $C0:A39A (PC 0x00A39A, 1104 bytes, 69 tiles):
; ----------------------------------------------------------------------------
org $C0A39A
    incbin "vwf/font8x8.bin"

; ----------------------------------------------------------------------------
; Character Naming Screen Grid Table in Bank $DB (PC 0x1BA782):
; Replaces raw Japanese Kana with unified 8-row English grid:
; Uppercase (Rows 0-2), Lowercase (Rows 3-5), Digits (Row 6), Symbols (Row 7).
; Total 80 cells (8 rows x 10 cols) - eliminates all 5-row blank spaces!
; ----------------------------------------------------------------------------
org $DBA782
    ; Row 0: A B C D E F G H I J
    db $0B, $0C, $0D, $0E, $0F, $10, $11, $12, $13, $14
    ; Row 1: K L M N O P Q R S T
    db $15, $16, $17, $18, $19, $1A, $1B, $1C, $1D, $1E
    ; Row 2: U V W X Y Z . , ! ?
    db $1F, $20, $21, $22, $23, $24, $89, $88, $86, $87
    ; Row 3: a b c d e f g h i j
    db $25, $26, $27, $28, $29, $2A, $2B, $2C, $2D, $2E
    ; Row 4: k l m n o p q r s t
    db $2F, $30, $31, $32, $33, $34, $35, $36, $37, $38
    ; Row 5: u v w x y z - ' & /
    db $39, $3A, $3B, $3C, $3D, $3E, $8A, $84, $41, $82
    ; Row 6: 0 1 2 3 4 5 6 7 8 9
    db $01, $02, $03, $04, $05, $06, $07, $08, $09, $0A
    ; Row 7: ( ) " : * + … · ★  
    db $8D, $8E, $85, $8F, $83, $81, $8B, $8C, $EC, $00
    ; Row 8: Padding
    db $00, $00, $00, $00, $00, $00, $00, $00, $00, $00

org $DBA7DC
    ; Mirror Page 1 cleanly:
    db $0B, $0C, $0D, $0E, $0F, $10, $11, $12, $13, $14
    db $15, $16, $17, $18, $19, $1A, $1B, $1C, $1D, $1E
    db $1F, $20, $21, $22, $23, $24, $89, $88, $86, $87
    db $25, $26, $27, $28, $29, $2A, $2B, $2C, $2D, $2E
    db $2F, $30, $31, $32, $33, $34, $35, $36, $37, $38
    db $39, $3A, $3B, $3C, $3D, $3E, $8A, $84, $41, $82
    db $01, $02, $03, $04, $05, $06, $07, $08, $09, $0A
    db $8D, $8E, $85, $8F, $83, $81, $8B, $8C, $EC, $00
    db $00, $00, $00, $00, $00, $00, $00, $00, $00, $00

; ----------------------------------------------------------------------------
; Naming Grid Bounds Configuration (Bank $DB):
; Clamp total cell count ($C5) to 80 ($50) so cursor stops at Row 7:
; ----------------------------------------------------------------------------
org $DBDE0E
    db $50              ; Protagonist & Sonia name grid limit (80 cells = 8 rows)

org $DBDF59
    db $50              ; Pet name grid limit (80 cells = 8 rows)

; Hide down-arrow sprite on character naming screen (all 8 rows fit on screen):
org $C0EF56
    ldx #$F0AE          ; Y=240 (off-screen) instead of Y=192
    stx $0100

; ----------------------------------------------------------------------------
; Initial Name Cursor Positions (Bank $C0):
; ----------------------------------------------------------------------------
org $C0D7F3
    lda #$05            ; Protagonist initial cursor position (after "Gyant", 5 letters)
    sta $9B

org $C0D9DF
    lda #$05            ; Sonia initial cursor position (after "Sonia", 5 letters)
    sta $9B

org $C0DF9F
    lda #$07            ; Pet initial cursor position (after "Boancho", 7 letters)
    sta $9B

; ----------------------------------------------------------------------------
; Default Character Names in ROM (Bank $DB at $B7CA, PC 0x1BB7CA):
; Uses Traverse native character encoding ($0B..$24 -> A..Z, $25..$3E -> a..z):
; ----------------------------------------------------------------------------
org $DBB7CA
    ; Protagonist 1 (default "Gyant") - 9 bytes:
    db $11, $3D, $25, $32, $38, $8B, $8B, $8B, $FF

org $DBB7D3
    ; Protagonist 2 Sub (default "Sonia") - 9 bytes:
    db $1D, $33, $32, $2D, $25, $8B, $8B, $8B, $FF

org $DBB8F3
    ; Pet (default "Boancho") - 9 bytes (at actual default pet index $DB:B8F3!):
    db $0C, $33, $25, $32, $27, $2C, $33, $8B, $FF
