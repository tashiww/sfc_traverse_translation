; ============================================================================
; Traverse: Starlight & Prairie - English Translation Patch
; Asar 65816 Assembly Patch Entry Point
; ============================================================================

hirom

; Master assembly hooks:
incsrc "vwf/vwf.asm"

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
; Rewire Page 0 (Hiragana -> Uppercase English) and Page 1 (Katakana -> Lowercase English):
; ----------------------------------------------------------------------------
org $DBA782
    ; Page 0 (Uppercase English):
    ; Row 0: A B C D E F G H I J
    db $0B, $0C, $0D, $0E, $0F, $10, $11, $12, $13, $14
    ; Row 1: K L M N O P Q R S T
    db $15, $16, $17, $18, $19, $1A, $1B, $1C, $1D, $1E
    ; Row 2: U V W X Y Z - . ! ?
    db $1F, $20, $21, $22, $23, $24, $8A, $8C, $86, $87
    ; Row 3: 0 1 2 3 4 5 6 7 8 9
    db $01, $02, $03, $04, $05, $06, $07, $08, $09, $0A
    ; Rows 4..8: Blank cells (50 bytes)
    db $00, $00, $00, $00, $00, $00, $00, $00, $00, $00
    db $00, $00, $00, $00, $00, $00, $00, $00, $00, $00
    db $00, $00, $00, $00, $00, $00, $00, $00, $00, $00
    db $00, $00, $00, $00, $00, $00, $00, $00, $00, $00
    db $00, $00, $00, $00, $00, $00, $00, $00, $00, $00

org $DBA7DC
    ; Page 1 (Lowercase English):
    ; Row 0: a b c d e f g h i j
    db $61, $62, $63, $64, $65, $66, $67, $68, $69, $6A
    ; Row 1: k l m n o p q r s t
    db $6B, $6C, $6D, $6E, $6F, $70, $71, $72, $73, $74
    ; Row 2: u v w x y z - . ! ?
    db $75, $76, $77, $78, $79, $7A, $8A, $8C, $86, $87
    ; Row 3: 0 1 2 3 4 5 6 7 8 9
    db $30, $31, $32, $33, $34, $35, $36, $37, $38, $39
    ; Rows 4..8: Blank cells (50 bytes)
    db $00, $00, $00, $00, $00, $00, $00, $00, $00, $00
    db $00, $00, $00, $00, $00, $00, $00, $00, $00, $00
    db $00, $00, $00, $00, $00, $00, $00, $00, $00, $00
    db $00, $00, $00, $00, $00, $00, $00, $00, $00, $00
    db $00, $00, $00, $00, $00, $00, $00, $00, $00, $00

; ----------------------------------------------------------------------------
; Default Character Names in ROM (Bank $DB at $B7CA, PC 0x1BB7CA):
; Uses Traverse native character encoding ($0B..$24 -> A..Z):
; ----------------------------------------------------------------------------
org $DBB7CA
    ; Protagonist 1 (default "GANT") - 9 bytes:
    db $11, $0B, $18, $1E, $8B, $8B, $8B, $8B, $FF
    ; Protagonist 2 Sub (default "SONIA") - 9 bytes:
    db $1D, $19, $18, $13, $0B, $8B, $8B, $8B, $FF
    ; Pet (default "BOANCHO") - 9 bytes:
    db $0C, $19, $0B, $18, $0D, $12, $19, $8B, $FF
