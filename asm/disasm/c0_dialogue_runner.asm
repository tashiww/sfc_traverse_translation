; ==============================================================================
; Traverse: Starlight & Prairie - Disassembly Reference
; Bank $C0: Dialogue Runner, Typewriter Dispatcher, Line Evaluator
; ROM Range: PC 0x00F395 - 0x00F595 (SNES $C0:F395 - $C0:F595)
; ==============================================================================

; ------------------------------------------------------------------------------
; $C0:F395: Character Typewriter Dispatcher & Macro Script Stepper
; Called after each character rendered in dialogue to synchronize VBlank,
; update typewriter delay, and advance scene macro script [$D1].
; ------------------------------------------------------------------------------
Dialogue_TypewriterTick:
    CMP #$8B                ; Check for punctuation (comma)
    BEQ .pause_long
    CMP #$86                ; Check for punctuation (period)
    BEQ .pause_long
    CMP #$88                ; Check for punctuation (ellipsis)
    BNE .check_short
.pause_long:
    JSR $FE6D               ; Extended pause for heavy punctuation
    BRA .step_macro

.check_short:
    CMP #$87
    BEQ .pause_short
    CMP #$89
    BNE .step_macro
    DEY
    LDA [$A3],Y             ; Check preceding character
    CMP #$FB
    BEQ .step_macro
.pause_short:
    JSR $FE5E               ; Standard pause for lighter punctuation

.step_macro:
    PHX
    LDY $0C7B               ; Load macro script offset in [$D1]
    STZ $B8                 ; Clear NMI request flag
    LDA #$01
    STA $B9                 ; Set VBlank sync flag
    STZ $B6                 ; Idle DMA mode
    JSR $CB33               ; Wait for VBlank (LDA $4210 : BPL ...)

    ; Advance macro script command 1:
    TDC
    LDA [$D1],Y
    INY
    ASL
    TAX
    JSR ($F32D,X)           ; Execute command from table $C0:F32D

    LDA $0C8F               ; Animation active flag
    BNE .step_2
    JSR $FA7E               ; Process character animation frame
    LDA #$03
    STA $B6                 ; NMI DMA mode 3 (sprite DMA)
    STZ $B8
    JSR $CB33               ; Wait for VBlank

.step_2:
    TDC
    LDA [$D1],Y
    INY
    ASL
    TAX
    TDC
    JSR ($F32D,X)           ; Execute command 2 from table

    LDA #$01
    STA $B9
    STA $B6
    STZ $B8
    JSR $CB33               ; Wait for VBlank

    TDC
    LDA [$D1],Y
    INY
    ASL
    TAX
    JSR ($F32D,X)           ; Execute command 3 from table

    LDA $0C8F
    BNE .step_4
    JSR $FA7E
    STZ $B6
    LDA #$03
    STA $B6
    STZ $B8
    JSR $CB33

.step_4:
    TDC
    LDA [$D1],Y
    INY
    ASL
    TAX
    JSR ($F32D,X)           ; Execute command 4 from table

    LDA $0C88               ; Skip flag
    BEQ .step_5
    JSR $F452
    BRA .finish_tick

.step_5:
    LDA #$01
    STA $B9
    STA $B6
    STZ $B8
    JSR $CB33
    TDC
    LDA [$D1],Y
    INY
    ASL
    TAX
    TDC
    JSR ($F32D,X)           ; Execute command 5 from table

    LDA $0C8F
    BNE .save_offset
    JSR $FA7E
    STZ $B6
    LDA #$03
    STA $B6
    STZ $B8
    JSR $CB33

.save_offset:
    STY $0C7B               ; Save advanced macro script offset
    PLX
    RTL


; ------------------------------------------------------------------------------
; $C0:F501: Dialogue Line Processing & Hook Location
; Invoked by macro command 0x06.
; ------------------------------------------------------------------------------
Dialogue_RenderLine:
    STY $0C7B               ; Save macro script offset
    PEA $0202               ; Push initial row parameter (Row = 2)
    TDC
    PHA                     ; Push initial col parameter (Col = 0)
    INC A                   ; A = 1
    STA $0C7E               ; Line active flag = 1

.render_loop:
    LDA #$2B                ; Attribute: BG3, Palette 2, Priority 1, Tile Base $0300
    STA $A8

    ; --- HOOK TARGET FOR VWF ENGINE ---
    JSL $DCCA99             ; In clean ROM: JSL $DC:CA99 (replaced with JSL VWF_LineHook)

    TXA
    LSR
    AND #$3F
    STA $0C7F               ; Save consumed tile columns
    REP #$21
    TYA                     ; Y = bytes consumed from string [$A3]
    ADC $A3
    STA $A3                 ; Advance string pointer past line
    TXA
    ASL
    ASL
    SEP #$20
    XBA
    STA $0C80               ; Save consumed pixel width

    ; Check control byte following the line:
    LDA [$A3]
    CMP #$FF                ; $FF = Newline within message box
    BNE .check_control_01

    ; Handle Newline ($FF):
    LDA #$02
    STA $03,S               ; Set row parameter
    REP #$20
    INC $A3                 ; Skip $FF
    SEP #$20
    JSR $FE5E               ; Wait for button press
    JSR $FE5E
    JSR $FE6D
    JSR $EFEC               ; Clear line buffers ($7E:CE80 and $7E:C780)
    TDC
    STA $01,S               ; Reset column offset to 0
    BRA .render_loop        ; Loop to render next line in box

.check_control_01:
    CMP #$01
    BNE .check_control_fe
    STZ $EC
    LDA #$2F
    JSR $FDC9
    JSR $FD08
    JMP $F57C

.check_control_fe:
    CMP #$FE                ; $FE = End of dialogue box / message complete
    BEQ .message_complete

    ; If neither $FF nor $FE (e.g. $00 indentation byte):
    LDA $03,S
    CLC
    ADC #$02
    STA $03,S               ; Advance row by 2
    LDA #$02
    STA $02,S
    STZ $B8
    JSR $CB33               ; Wait for VBlank
    JSR $FA7E
    STZ $B8
    JSR $CB33
    BRA .render_loop        ; Loop to render next line

.message_complete:
    JSR $FE5E               ; Wait for player button press to dismiss box
    REP #$20
    INC $A3                 ; Skip $FE
    SEP #$20
    STZ $0C7E               ; Line active = 0
    PLA
    STA $0C81
    PLX
    LDY $0C7B               ; Restore macro script offset
    RTS                     ; Return to macro dispatcher
