; ============================================================================
; Traverse: Starlight & Prairie - English Translation Patch
; Asar 65816 Assembly Patch Entry Point
; ============================================================================

hirom

; Master assembly hooks:
incsrc "vwf/vwf.asm"

; ----------------------------------------------------------------------------
; Upgrade 8x8 Menu Font at $C0:A39A (PC 0x00A39A, 1104 bytes, 69 tiles):
; ----------------------------------------------------------------------------
org $C0A39A
    incbin "vwf/font8x8.bin"

; ----------------------------------------------------------------------------
; Default Character Names in ROM (Bank $DB at $B7CA, PC 0x1BB7CA):
; ----------------------------------------------------------------------------
org $DBB7CA
    ; Protagonist 1 (default "Gant") - 9 bytes:
    db "Gant", $FF, $FF, $FF, $FF, $FF
    ; Protagonist 2 Sub (default "Sonia") - 9 bytes:
    db "Sonia", $FF, $FF, $FF, $FF
    ; Pet (default "Boancho") - 9 bytes:
    db "Boancho", $FF, $FF
