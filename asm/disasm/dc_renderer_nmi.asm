; ==============================================================================
; Traverse: Starlight & Prairie - Disassembly Reference
; Bank $DC: Native 16x16 Character Renderer & NMI DMA Subsystem
; ROM Range: PC 0x1CCA99 - 0x1CCCC0 & PC 0x1CC000 - 0x1CC180
; ==============================================================================

; ------------------------------------------------------------------------------
; $DC:CA99: Native Japanese Character Line Renderer
; Inputs:
;   [$A3] = 24-bit pointer to dialogue string
;   $A8   = Tile attribute byte ($2B)
;   Stack:
;     $01,S: Col offset (0)
;     $03,S: Row parameter (2, 4, 6...)
; ------------------------------------------------------------------------------
Native_RenderDialogueLine:
    PHP
    PHB
    SEP #$20
    LDA #$DB
    STA $A5                 ; Font Bank $DB
    LDA #$D3
    PHA
    PLB                     ; DB = Data Bank $D3
    TDC
    TAY                     ; Y = 0 (string read offset)

    ; Calculate Tilemap Byte Offset from Row and Col:
    LDA $08,S               ; Row parameter (2 or 4)
    XBA
    REP #$30
    LDX #$CB15
    STX $EA
    LSR : LSR               ; (Row * 256) / 4 = Row * 64 bytes
    SEP #$20
    ADC $07,S
    ADC $07,S               ; + (Col * 2) bytes
    TAX                     ; X = Exact byte offset into $7E:C780!

.char_loop:
    LDA [$A3],Y             ; Read character from string
    INY
    CMP #$FF                ; End of string marker
    BEQ .return

    CMP #$F0                ; Variable substitution ([protag], [pet])
    BEQ .handle_var
    CMP #$FB                ; Extended Kanji block 1 ($FBxx)
    BCC .ascii_or_special

    ; Decode 2-byte Kanji ($FBxx / $FCxx):
    SBC #$FA
    LSR
    XBA
    LDA [$A3],Y             ; Read second byte
    INY
    XBA
    REP #$20
    ROR : ROR
    AND #$FFC0              ; Glyph index * 64 bytes per 16x16 tile
    BRA .blit_glyph

.handle_var:
    ; (Recursively renders name from buffer $7E:EEC9)
    ...
    BRA .char_loop

.ascii_or_special:
    XBA
    LDA #$00
    REP #$20
    LSR : LSR               ; char * 64 bytes
.blit_glyph:
    PHX
    PHY
    TAY                     ; Y = Font ROM offset

    ; Character index in buffer $7E:CE80:
    LDA $0A,S
    AND #$00FF
    ASL : ASL : ASL : ASL   ; char_count * 16
    TAX
    JMP ($00EA)             ; Jump to unrolled 64-byte copy loop ($DC:CB15)

; Unrolled copy writes 64 bytes to $7E:CE80:
; Tile 0 (top-left)     -> $7ECE80,X
; Tile 1 (top-right)    -> $7ECE90,X
; Tile 2 (bottom-left)  -> $7ECEA0,X
; Tile 3 (bottom-right) -> $7ECEB0,X

.tilemap_write:
    SEP #$20
    PLY
    PLX
    LDA $06,S               ; Base Tile ID
    STA $7EC780,X           ; Top-Left tile
    INC A
    STA $7EC782,X           ; Top-Right tile
    INC A
    STA $7EC7C0,X           ; Bottom-Left tile ($7EC7C0 = $7EC780 + 0x40)
    INC A
    STA $7EC7C2,X           ; Bottom-Right tile
    INC A
    STA $06,S               ; Base Tile ID += 4 for next character

    ; Set Tile Attribute Byte:
    LDA $A8                 ; Attribute byte ($2B)
    STA $7EC781,X           ; Top-Left attribute
    STA $7EC783,X           ; Top-Right attribute
    STA $7EC7C1,X           ; Bottom-Left attribute
    STA $7EC7C3,X           ; Bottom-Right attribute

    INX : INX : INX : INX   ; Advance tilemap offset by 4 bytes (2 tile cols)

    ; Trigger Typewriter Tick & VBlank DMA:
    LDA $A6                 ; Dialogue active flag
    BEQ .char_loop
    PHB
    TDC : PHA : PLB         ; Set DB = 0
    PHY
    DEY
    LDA [$A3],Y             ; A = Character just rendered
    JSL $C0:F395            ; Call typewriter tick & VBlank synchronization
    PLY
    PLB
    JMP .char_loop

.return:
    PLB
    PLP
    RTL                     ; Return to $C0:F515 (X = final tilemap offset, Y = bytes read)


; ------------------------------------------------------------------------------
; $DC:C0C2 - $DC:C170: NMI VBlank Dialogue DMAs
; Executes every frame during vertical blanking when $B6 / $B8 flags are set.
; ------------------------------------------------------------------------------
NMI_VBlankHandler:
    LDA $B8
    BNE .check_b8_modes

    ; Idle mode ($B8 == 0):
    LDA $B6
    BEQ .dma_dialogue_glyph_buffer   ; If $B6 == 0: Transfer $7E:CE80 to VRAM $5800!
    DEC A
    BNE .sprite_dma

    ; $B6 == 1: DMA entire BG3 Tilemap ($7E:C780) to VRAM $0C00
    LDX #$0C00
    STX $2116               ; VRAM Address = $0C00 (word)
    LDX #$1801
    STX $4300               ; DMA Mode: 2 registers write once ($2118, $2119)
    LDX #$C780
    STX $4302               ; Source = $7E:C780
    LDA #$7E
    STA $4304               ; Bank = $7E
    LDX #$0700
    STX $4305               ; Size = 0x700 bytes (1,792 bytes = 32x28 words)
    LDA #$01
    STA $420B               ; Fire DMA Channel 0!
    STZ $B6
    ...

.dma_dialogue_glyph_buffer:
    ; Normal running frame: Transfer dialogue glyphs from $7E:CE80 to VRAM $5800
    LDX #$5800
    STX $2116               ; VRAM Address = $5800 (word)
    LDX #$CE80
    STX $4302               ; Source = $7E:CE80
    LDA #$7E
    STA $4304               ; Bank = $7E
    LDX #$0D40
    LDA $A6
    BEQ +
    LDX #$0E00              ; Full size = 0x0E00 bytes
+   STX $4305
    LDA #$01
    STA $420B               ; Fire DMA Channel 0!
    RTI
