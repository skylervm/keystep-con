#include "tempo_layout.h"
.syntax unified
.thumb
.equ TEMPO_BYTE_PARSER, 0x0801a8a6
.equ TEMPO_SDRAM_INIT, 0x08017c68
.equ TEMPO_UP_CONT, 0x08012721
.equ TEMPO_DOWN_CONT, 0x08013bd7
.equ TEMPO_PROJECT_CONT, 0x08026561
.equ TEMPO_SCREEN_CONT, 0x08026691

.balign 4
.global tempo_receive
.type tempo_receive,%function
tempo_receive:
    push    {r0-r3, r12, lr}
    bl      tempo_receive_byte
    pop     {r0-r3, r12, lr}
    ldr     r12, =(TEMPO_BYTE_PARSER + 1)
    bx      r12                   @ untouched stock parser, original byte and return address
.size tempo_receive, .-tempo_receive

.balign 4
.global tempo_boot
.type tempo_boot,%function
tempo_boot:
    push    {r4, lr}
    call_abs TEMPO_SDRAM_INIT      @ controller setup and SDRAM commands finish first
    push    {r0-r3, r12, lr}
    ldr     r1, =TEMPO_ADDRESS
    movs    r0, #0
    movs    r2, #TEMPO_BYTES
1:  subs    r2, #4
    str     r0, [r1, r2]
    bne     1b
    ldr     r1, =TEMPO_BPM_ADDRESS
    str     r0, [r1]
    str     r0, [r1, #4]
    pop     {r0-r3, r12, lr}
    pop     {r4, pc}
.size tempo_boot, .-tempo_boot

.macro tempo_encoder name, direction, continuation
.balign 4
.global \name
.type \name,%function
\name:
    push    {r0-r3, r12, lr}
    mrs     r0, apsr
    push    {r0, r1}
    add     r0, sp, #32            @ original event-loop frame
    movs    r1, #\direction
    bl      tempo_turn
    mov     r6, r0
    pop     {r0, r1}
    msr     apsr_nzcvq, r0
    pop     {r0-r3, r12, lr}
    ldr     pc, =\continuation    @ no register or flag clobber on return
.size \name, .-\name
.endm
tempo_encoder tempo_up, 0, TEMPO_UP_CONT
tempo_encoder tempo_down, 1, TEMPO_DOWN_CONT

@ The normal project renderer and dedicated tempo renderer have different
@ registers/cache fields. Their already-consumed descriptor slots are reused.
.macro tempo_display name, source, current, saved, cache, workspace, continuation
.balign 4
.global \name
.type \name,%function
\name:
    push    {r0, \saved, r12, lr}
    mrs     r0, apsr
    push    {r0, \saved}
    sub     sp, #16
    movw    r0, #\cache
    str     r0, [sp]              @ fifth C argument
    mov     r0, r4
    mov     r1, \source
    add     r2, sp, #(40 + \workspace)
    add     r3, sp, #8
    bl      tempo_display_values
    mov     \source, r0
    ldr     r1, [sp, #8]
    ldr     \current, [sp, #12]
    add     sp, #16
    pop     {r0, \saved}
    msr     apsr_nzcvq, r0
    pop     {r0, \saved, r12, lr}
    ldr     pc, =\continuation
.size \name, .-\name
.endm
tempo_display tempo_project_values, r6, r2, r3, 0x112, 16, TEMPO_PROJECT_CONT
tempo_display tempo_screen_values, r8, r3, r2, 0x118, 8, TEMPO_SCREEN_CONT
.ltorg
