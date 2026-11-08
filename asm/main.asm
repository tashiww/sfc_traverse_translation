; ============================================================================
; Traverse: Starlight & Prairie - English Translation Patch
; Asar 65816 Assembly Patch Entry Point
; ============================================================================

hirom

; Example free space in Bank $09 ($C9:B0D5 - $CA:0000) ~85KB
; free_space_start = $C9B0D5

; Master assembly hooks:
incsrc "vwf/vwf.asm"
