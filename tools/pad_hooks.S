@ Step buttons as live pads (KeyStep Pro 2.5.20): drum pads or chord pads, one mode at a time.
@
@ Hold Drum, press Seq (track 1 row): drum pads on/off. Step N plays drum lane N (note from
@ the Drum Map, global 81-106) on the drum output channel (global 79) while held.
@ Hold Seq, press Arp on track 2, 3 or 4: chord pads for that track on/off.
@   - hold a chord on the keys (that track selected) and tap a step: the step keeps those notes
@   - tap a step with no keys held: its chord sounds while the step is held, on the track's
@     MIDI output channel (75+track)
@   - Erase + step: the step forgets its chord
@   - Shift + Exit (stock undo) undoes the last capture or erase, again to redo; otherwise stock
@   - a step with no chord plays the scale chord of the track's current root and scale:
@     steps 1-8 triads on degrees 1-8, steps 9-16 7th chords on degrees 1-8, rooted in the
@     keyboard's lowest octave (Chromatic counts as major; User 1/2 from the project)
@   - a kept chord moves with the octave buttons (kept as played at octave 0)
@   - Save Project stores the chords with the project (5 notes per step, 3 tracks x 16 steps)
@ Hold Seq, press Mute on any track: root chords for that track. Keys on that track are silent
@ and only pick the root (the lowest one held when a step is pressed; it stays after the key is
@ let go); steps play chords on that root,
@ built from the track's scale (Chromatic counts as major), named by the step number:
@   1 root+octave, 2 sus2, 3 triad, 4 sus4, 5 power, 6 sixth, 7 seventh, 8 triad octave up,
@   9 ninth, 10 add9, 11 eleventh, 12 1st inversion, 13 thirteenth, 14 2nd inversion, 15 7sus4,
@   16 triad octave down. Before a key is pressed the root is the track's root in the keyboard's
@   lowest octave. A chord that runs past the keys shown moves by whole octaves to fit them.
@ The screen names what keys and chord pads play: a note (E3) or a chord (C#m, A/C#), about a
@ second each time (note_show.c); root-chord keys show the root.
@ While the pad's track is selected (track 1 for drum pads), the keys light for the notes a
@ step plays, in the track colour, as the KeyStep lights notes it plays itself.
@ With the sequencer recording (Rec), what the steps play is recorded on the selected track
@ like keys (drum hits as lanes while track 1 shows drums); root-chord keys are not recorded.
@ Turning one mode on turns the others off. The pattern and the selected track are not touched.
@ Stock, the first button of each combo already switches the track's mode (Drum: track 1 to
@ drum mode, Seq: to sequencer mode); the second press, which would switch it back, is taken.
@ Seq alone, Arp alone, Shift + Control (Control mode) and Shift + Drum (unmute all drums)
@ stay stock.
@ Make bass: hold Seq on the bass track, press the Track button of the track with the chords:
@ the bass track's current pattern becomes a bass line from the chord track's current pattern
@ (bass_gen.c, same rules as the KeyStep Con page). Still holding Seq, steps 1-5 switch the
@ style and write it again: 1 Root, 2 Root + 5th, 3 Octaves, 4 Pulse, 5 Follow rhythm. The
@ style is kept for the next time; the screen names it.
@
@ Hooks: the event loop 08012338 calls the button press handler 080500d8 at 08012708
@ (r0 buttons, r1 id, r2 1) and the release handler 0804e700 at 080126ea (r0 buttons, r1 id);
@ Save Project 08047c84 programs the project's second sector at 08047d36 (r0 flash, r1 sector).
@ The BLs are redirected here; anything not handled goes to the stock function unchanged.
@ Button record: buttons + 0x6c + id*3, byte +2 is 0 while held. Track rows are 6 ids apart
@ from 0x12: pattern down, up, Seq, Drum/Arp, Mute, Track select. Shift 1, Exit 0xc, Erase 0x10,
@ steps 0x2e-0x3d.
@ Held keys: 37 x {note, channel, track} at 0x20004ddc, note 0xff when the key is up.

.equ STOCK_PRESS,   0x080500d8
.equ STOCK_RELEASE, 0x0804e700
.equ CHORD_FLAG,    0x0802d160      @ (seq, track, project) -> chord mode on
.equ LANE_NOTE,     0x080347c8      @ (any, lane) -> sxtb note, Drum Map aware
.equ MSG_NOTE_ON,   0x08017e70      @ (ch, note, vel) -> packed 0x9n message
.equ MSG_NOTE_OFF,  0x08017e28      @ (ch, note, 0) -> 0x8n or 0x9n vel 0 per setting
.equ MIDI_SEND,     0x0801a6e0      @ (port, msg, 3) -> USB and DIN
.equ KEY_SLOT_SP,   0x6a            @ in the event loop's frame: index of the key being sent
.equ KEY_LED,       0x08034ab4      @ (seq, note, track) -> key LED id (0x46-0x6a; 0x45/0x6b octave arrows; 0x78 none)
.equ LED_SET,       0x08053eb8      @ (leds, id, on, colour, [sp] 0, [sp+4] 0)
.equ LEDS_PTR,      0x20001490
.equ LED_FLUSH,     0x08054c2c      @ (leds): sends the changed LEDs (+0x184 + id flags)
.equ TRACK_COLOURS,  0x20000058
.equ SEL_TRACK,     0x200001a4      @ selected track; 4 = track 1 as drums
.equ REC_NOTE,      0x0802a244      @ (track, note or drum lane, vel, x) -> note slot (0xc0+ = not recorded)
.equ REC_END,       0x08029e78      @ (track, slot): the recorded note's length, at release
.equ REC_X,         0x20003d9d      @ 4th REC_NOTE argument for sequencer notes (as chord mode passes)
.equ RECORDING,     0x20003d91      @ live recording (the drum keys' test)
.equ REC_ARMED,     0x20002d5b      @ ... or armed while the sequencer plays (seq + 0xc)
.equ STOCK_KEY_REC, 0x080108a4      @ live key record, called by the event loop at 08015ee0
.equ MIDI_PORT_PTR, 0x20001800
.equ GLOBALS,       0x20000874      @ global id N at +4+N
.equ SEQ_PTR,       0x20001498      @ -> sequencer state, 0xfec per project
.equ CUR_PROJECT,   0x20004dad      @ current project 0-15
.equ CUR_PAT,       0x20004da8      @ current pattern per track
.equ SCALE_MASKS,   0x20000004      @ u16 per scale index, bit n = semitone n above the root
.equ HELD_KEYS,     0x20004ddc
.equ KEY_MAP,       0x20000674      @ per track 128 bytes: key note -> note played (scale map)
.equ PAD_VELOCITY,  100
.equ ID_ERASE,      0x10
.equ ID_SHIFT,      1
.equ ID_EXIT,       0x0c
@ FLASH_READ, STAGE_WRITE, SECTOR_WRITE, FLASH_CTX, STAGE_BASE and call_abs come from
@ name_hooks.S, assembled first
.equ CHORD_FLASH,   0x6001fef0      @ + project << 17: 256 bytes between the project block
                                    @ (ends 0x1feec) and the name (0x1fff0)
.equ CHORD_SECTOR_OFF, 0xfef0
.equ CHORD_MAGIC,   0x31444843      @ "CHD1"
.equ CHORD_NOTES,   5

@ state in external RAM, in a stretch no stock code references (below the
@ save staging buffer at 0xC01F0000); not cleared at boot, so it carries a magic
.equ PAD_STATE,     0xC01EF800
.equ PAD_MAGIC,     0x5241445a      @ "ZDAR" (v10 layout, tempo lease at 484..511)
.equ ST_MODE,       4               @ 0 off, 1 drum pads, 2-4 chord pads for track 2-4,
                                    @ 5-8 root chords for track 1-4
.equ CT_MODE,       5
.equ ST_SW,         5               @ id of a press that was taken: take its release too
.equ ST_TAG,        6               @ project the chord table belongs to, 0xff none
.equ ST_NOTE,       16              @ 16 x 5: notes sounding per pad; [0] 0xff none, 0xfe taken silently
.equ ST_CHAN,       96              @ 16: channel per pad
.equ ST_UNDO,       112             @ 8: valid, track 1-3, pad, the pad's 5 notes before the last change
.equ ST_ROOT,       120             @ root note in root-chord mode, 0xff none yet
.equ ST_PTRK,       384             @ 16: track per pad (key lights), after the chord table
.equ ST_SLOT,       400             @ 16 x 5: recorded note slot per sounding note, 0xff none
.equ ST_BT,         480             @ make bass: bass track 0-3 while its Seq is held, 0xff none
.equ ST_BS,         481             @ make bass: chord track 0-3
.equ ST_BSTYLE,     482             @ make bass: style 0-4 (bass_gen.c)
.equ ST_TABLE,      128             @ 256: copy of the project's chord block (flash layout):
                                    @ magic, 4 spare, then track 2-4 x 16 pads x 5 notes, 0xff unused
.equ PAD_NONE,      0xff
.equ PAD_SILENT,    0xfe
.equ OCT_ZERO,      3               @ track octave byte shown as octave 0 (range -3..+2 = 0..5)

.section .text
.balign 4

@ r7 <- state, initialised on first use after power-up
.type pad_state,%function
pad_state:
    ldr     r7, =PAD_STATE
    ldr     r0, [r7]
    ldr     r1, =PAD_MAGIC
    cmp     r0, r1
    beq     1f
    movs    r0, #0
    str     r0, [r7, #ST_MODE]
    strb    r0, [r7, #ST_UNDO]
    strb    r0, [r7, #ST_BSTYLE]
    movs    r0, #0xff
    strb    r0, [r7, #ST_TAG]
    strb    r0, [r7, #ST_BT]
    movs    r2, #0
2:  adds    r3, r7, r2
    strb    r0, [r3, #ST_NOTE]
    adds    r2, #1
    cmp     r2, #80
    blo     2b
    str     r1, [r7]
1:  bx      lr
.size pad_state, .-pad_state

@ r0 = buttons, r1 = id -> r0 = 1 while held
.type is_held,%function
is_held:
    add     r1, r1, r1, lsl #1
    add     r0, r0, r1
    ldrb    r0, [r0, #0x6e]
    eor     r0, r0, #1
    bx      lr
.size is_held, .-is_held

@ r7 = state: make the chord table the current project's (read from flash when needed)
.type chords_load,%function
chords_load:
    push    {r4, lr}
    ldr     r0, =CUR_PROJECT
    ldrb    r4, [r0]
    ldrb    r0, [r7, #ST_TAG]
    cmp     r0, r4
    beq     2f
    movs    r0, #0
    strb    r0, [r7, #ST_UNDO]      @ another project: nothing to undo
    ldr     r0, =FLASH_CTX
    ldr     r1, =CHORD_FLASH
    add     r1, r1, r4, lsl #17
    add     r2, r7, #ST_TABLE
    movs    r3, #128                @ halfwords
    call_abs FLASH_READ
    ldr     r0, [r7, #ST_TABLE]
    ldr     r1, =CHORD_MAGIC
    cmp     r0, r1
    beq     1f
    str     r1, [r7, #ST_TABLE]     @ nothing stored (erased flash or other data): empty table
    movs    r0, #0xff
    movs    r2, #4
3:  adds    r3, r7, r2
    strb    r0, [r3, #ST_TABLE]
    adds    r2, #1
    cmp     r2, #256
    blo     3b
1:  strb    r4, [r7, #ST_TAG]
2:  pop     {r4, pc}
.size chords_load, .-chords_load

@ r0 = track 1-3, r1 = pad -> r0 = address of the pad's 5 stored notes (r7 = state)
.type chord_slot,%function
chord_slot:
    subs    r0, #1
    lsls    r2, r0, #4
    add     r2, r2, r1              @ track*16 + pad
    add     r2, r2, r2, lsl #2      @ x5
    add     r0, r7, r2
    adds    r0, #ST_TABLE + 8
    bx      lr
.size chord_slot, .-chord_slot

@ r0 = slot, r8 = track, r9 = pad, r7 = state: remember the slot before it changes
.type undo_keep,%function
undo_keep:
    movs    r1, #1
    strb    r1, [r7, #ST_UNDO]
    strb    r8, [r7, #ST_UNDO + 1]
    strb    r9, [r7, #ST_UNDO + 2]
    movs    r2, #0
1:  ldrb    r1, [r0, r2]
    add     r3, r7, r2
    strb    r1, [r3, #ST_UNDO + 3]
    adds    r2, #1
    cmp     r2, #CHORD_NOTES
    blo     1b
    bx      lr
.size undo_keep, .-undo_keep

@ r0 = track 0-3 -> r0 = (keyboard octave - octave 0) * 12: stored pad chords are kept as played
@ at octave 0 (the default) and move with the octave buttons. Uses r0-r3 only.
.type oct_shift,%function
oct_shift:
    ldr     r1, =SEQ_PTR
    ldr     r1, [r1]
    ldr     r2, =CUR_PROJECT
    ldrb    r2, [r2]
    movw    r3, #0xfec
    mla     r1, r2, r3, r1
    movs    r2, #0x16
    mla     r1, r0, r2, r1
    movw    r2, #0x1752
    ldrb    r0, [r1, r2]
    and     r0, r0, #7
    subs    r0, #OCT_ZERO
    movs    r1, #12
    mul     r0, r0, r1
    bx      lr
.size oct_shift, .-oct_shift

@ scale chord for pad r1 (0-15) of track r0 (1-3) into r2[0..3]; returns the count in r0
.type chord_notes,%function
chord_notes:
    push    {r4-r11, lr}
    sub     sp, #20                 @ degree buffer (16) + pad; 56 bytes total keeps alignment
    mov     r9, r2
    mov     r10, r1
    mov     r4, r0
    ldr     r0, =SEQ_PTR
    ldr     r5, [r0]
    ldr     r0, =CUR_PROJECT
    ldrb    r6, [r0]
    movw    r0, #0xfec
    mla     r5, r6, r0, r5          @ r5 = seq + project*0xfec
    ldr     r0, =CUR_PAT
    ldrb    r1, [r0, r4]
    movs    r0, #0x14
    mul     r1, r1, r0
    mov.w   r0, #0x140
    mla     r1, r4, r0, r1
    add     r1, r1, r5
    addw    r1, r1, #0x93a
    ldrb    r7, [r1]
    lsrs    r7, r7, #4              @ r7 = root 0-11
    ldrb    r8, [r1, #1]
    and     r8, r8, #15             @ r8 = scale index
    movs    r0, #0x16
    mla     r0, r4, r0, r5
    add     r0, r0, #0x1700
    adds    r0, #0x52
    ldrb    r6, [r0]
    and     r6, r6, #7              @ r6 = keyboard octave (lowest key shown = r6*12 + 24)
    cmp     r8, #8
    beq     chord_user1
    cmp     r8, #9
    beq     chord_user2
    cmp     r8, #0
    it      eq
    moveq   r8, #1                  @ Chromatic: use major
    cmp     r8, #9
    bhi     chord_major
    ldr     r0, =SCALE_MASKS
    ldrh    r0, [r0, r8, lsl #1]
    b       chord_rotate
chord_user1:
    movw    r1, #0x17c6
    ldrh    r0, [r5, r1]
    b       chord_mask
chord_user2:
    movw    r1, #0x17c8
    ldrh    r0, [r5, r1]
    b       chord_mask
chord_major:
    movw    r0, #0xab5
chord_rotate:
    ubfx    r0, r0, #0, #12
    lsl     r0, r0, r7
    lsr     r1, r0, #12
    orr     r0, r0, r1
chord_mask:
    ubfx    r0, r0, #0, #12
    cbnz    r0, 1f
    movw    r0, #0xab5              @ an empty user scale or the unused slot 7: major
    lsl     r0, r0, r7
    lsr     r1, r0, #12
    orr     r0, r0, r1
    ubfx    r0, r0, #0, #12
1:  @ walk up from the root collecting 14 scale notes (degrees 1-14)
    movs    r1, #12
    mul     r2, r6, r1
    adds    r2, #24
    add     r2, r2, r7              @ r2 = the root in the lowest octave shown
    mov     r3, r7                  @ r3 = pitch class of r2
    movs    r11, #0                 @ count
2:  lsr     r1, r0, r3
    tst     r1, #1
    beq     3f
    strb    r2, [sp, r11]
    add     r11, r11, #1
    cmp     r11, #14
    beq     4f
3:  adds    r2, #1
    adds    r3, #1
    cmp     r3, #12
    it      eq
    moveq   r3, #0
    cmp     r2, #127
    bls     2b
4:  @ pad -> degree k and size: 0-7 triads on k, 8-15 sevenths on k-8
    mov     r1, r10
    movs    r12, #3
    cmp     r1, #8
    blo     5f
    subs    r1, #8
    movs    r12, #4
5:  movs    r0, #0                  @ notes written
    movs    r3, #0                  @ chord tone index
6:  add     r2, r1, r3, lsl #1      @ degree k + 2i
    cmp     r2, r11
    bhs     7f                      @ ran past 127: fewer notes
    ldrb    r2, [sp, r2]
    strb    r2, [r9, r0]
    adds    r0, #1
7:  adds    r3, #1
    cmp     r3, r12
    blo     6b
    add     sp, #20
    pop     {r4-r11, pc}
.size chord_notes, .-chord_notes

@ send the message built by \builder (r0 ch, r1 note, r2 vel) to the MIDI port
.macro send_note builder
    call_abs \builder
    mov     r1, r0
    ldr     r0, =MIDI_PORT_PTR
    ldr     r0, [r0]
    movs    r2, #3
    call_abs MIDI_SEND
.endm

@ key light for note r0 of track r1 (drum pads: track 0): r2 = 1 on, 0 off; only while that
@ track is selected
.type pad_led,%function
pad_led:
    push    {r4-r6, lr}
    sub     sp, #8
    mov     r4, r1
    mov     r6, r2
    ldr     r3, =SEL_TRACK
    ldrb    r3, [r3]
    cmp     r3, r4
    beq     1f
    cmp     r4, #0                  @ track 1 is selected as 4 when it shows drums
    bne     3f
    cmp     r3, #4
    bne     3f
1:  mov     r1, r0
    mov     r2, r4
    ldr     r0, =SEQ_PTR
    ldr     r0, [r0]
    call_abs KEY_LED
    cmp     r0, #0x78
    beq     3f
    mov     r1, r0
    movs    r3, #8
    cbz     r6, 2f
    ldr     r3, =TRACK_COLOURS
    ldrb    r3, [r3, r4]
2:  movs    r2, #0
    str     r2, [sp]
    str     r2, [sp, #4]
    mov     r2, r6
    ldr     r0, =LEDS_PTR
    ldr     r0, [r0]
    call_abs LED_SET
3:  add     sp, #8
    pop     {r4-r6, pc}
.size pad_led, .-pad_led

@ r0 = track (drum pads: 0), r1 = mode -> r0 = 1 when what the pad plays should be recorded
.type rec_on,%function
rec_on:
    ldr     r2, =SEL_TRACK
    ldrb    r2, [r2]
    cmp     r1, #1
    bne     1f
    cmp     r2, #4                  @ drum hits: only while track 1 shows drums
    bne     3f
    b       2f
1:  cmp     r2, r0
    bne     3f
2:  ldr     r2, =RECORDING
    ldrb    r2, [r2]
    cbnz    r2, 4f
    ldr     r2, =REC_ARMED
    ldrb    r2, [r2]
    cbz     r2, 3f
    ldr     r2, =SEQ_PTR
    ldr     r2, [r2]
    ldrb    r2, [r2, #0xc]
    cbnz    r2, 4f
3:  movs    r0, #0
    bx      lr
4:  movs    r0, #1
    bx      lr
.size rec_on, .-rec_on

.global pad_press
.type pad_press,%function
pad_press:
    push    {r3-r11, lr}            @ 40 bytes: sp stays 8-byte aligned
    mov     r4, r0
    mov     r5, r1
    mov     r6, r2
    bl      pad_state
    @ make bass: Track (0x17/0x1d/0x23/0x29) with another row's Seq (0x14 + 6 * row) held
    subs    r0, r5, #0x17
    cmp     r0, #18
    bhi     5f
    movs    r1, #6
    udiv    r9, r0, r1
    mls     r3, r9, r1, r0
    cmp     r3, #0
    bne     5f
    movs    r10, #0
6:  cmp     r10, r9
    beq     7f
    mov     r0, r4
    add     r1, r10, r10, lsl #1
    lsls    r1, r1, #1
    adds    r1, #0x14
    bl      is_held
    cmp     r0, #0
    bne     bass_take
7:  adds    r10, #1
    cmp     r10, #4
    blo     6b
    b       8f
bass_take:
    strb    r10, [r7, #ST_BT]
    strb    r9, [r7, #ST_BS]
    b       bass_run
5:  subs    r9, r5, #0x2e           @ steps 1-5 while the bass track's Seq is still held: style
    cmp     r9, #4
    bhi     8f
    ldrb    r1, [r7, #ST_BT]
    cmp     r1, #3
    bhi     8f
    mov     r0, r4
    add     r1, r1, r1, lsl #1
    lsls    r1, r1, #1
    adds    r1, #0x14
    bl      is_held
    cmp     r0, #0
    beq     8f
    strb    r9, [r7, #ST_BSTYLE]
bass_run:
    strb    r5, [r7, #ST_SW]        @ its release is taken too
    ldrb    r0, [r7, #ST_BT]
    ldrb    r1, [r7, #ST_BS]
    ldrb    r2, [r7, #ST_BSTYLE]
    bl      bass_go
    pop     {r3-r11, pc}
8:
    @ toggles: Seq (0x14) with Drum held -> mode 1; Arp (0x1b/0x21/0x27) with its Seq held -> mode 2-4
    cmp     r5, #0x14
    bne     1f
    mov     r0, r4
    movs    r1, #0x15
    bl      is_held
    cbz     r0, press_step
    movs    r8, #1
    b       press_toggle
1:  subs    r0, r5, #0x16           @ Mute (0x16/0x1c/0x22/0x28) with its Seq held -> mode 5-8
    cmp     r0, #18
    bhi     3f
    movs    r1, #6
    udiv    r2, r0, r1
    mls     r3, r2, r1, r0
    cmp     r3, #0
    bne     3f
    add     r8, r2, #CT_MODE
    mov     r0, r4
    subs    r1, r5, #2              @ that row's Seq
    bl      is_held
    cmp     r0, #0
    beq     press_stock
    movs    r0, #0xff
    strb    r0, [r7, #ST_ROOT]      @ no root picked yet
    b       press_toggle
3:  subs    r0, r5, #0x15
    cmp     r0, #18
    bhi     press_step
    movs    r1, #6
    udiv    r2, r0, r1
    mls     r3, r2, r1, r0
    cmp     r3, #0
    bne     press_step
    cmp     r2, #0
    beq     press_step              @ 0x15 is Drum, not a combo key
    add     r8, r2, #1              @ track row 1-3 -> mode 2-4
    mov     r0, r4
    subs    r1, r5, #1              @ that row's Seq
    bl      is_held
    cmp     r0, #0
    beq     press_stock
press_toggle:
    strb    r5, [r7, #ST_SW]
    ldrb    r0, [r7, #ST_MODE]
    cmp     r0, r8
    it      eq
    moveq   r8, #0
    strb    r8, [r7, #ST_MODE]
    bl      chords_load             @ the step lights show the kept chords from the start
    pop     {r3-r11, pc}
press_step:
    cmp     r5, #ID_EXIT
    bne     press_pad
    ldrb    r0, [r7, #ST_MODE]      @ Shift + Exit in chord pad mode with a chord change to undo
    cmp     r0, #2
    blo     press_stock
    cmp     r0, #CT_MODE
    bhs     press_stock
    mov     r0, r4
    movs    r1, #ID_SHIFT
    bl      is_held
    cmp     r0, #0
    beq     press_stock
    bl      chords_load
    ldrb    r0, [r7, #ST_UNDO]
    cmp     r0, #0
    beq     press_stock
    ldrb    r0, [r7, #ST_UNDO + 1]
    ldrb    r1, [r7, #ST_UNDO + 2]
    bl      chord_slot
    movs    r2, #0                  @ swap: a second undo puts the change back
1:  ldrb    r1, [r0, r2]
    add     r3, r7, r2
    ldrb    r12, [r3, #ST_UNDO + 3]
    strb    r1, [r3, #ST_UNDO + 3]
    strb    r12, [r0, r2]
    adds    r2, #1
    cmp     r2, #CHORD_NOTES
    blo     1b
    strb    r5, [r7, #ST_SW]
    pop     {r3-r11, pc}
press_pad:
    subs    r0, r5, #0x2e
    cmp     r0, #15
    bhi     press_stock
    ldrb    r8, [r7, #ST_MODE]
    cmp     r8, #0
    beq     press_stock
    mov     r9, r0                  @ r9 = pad 0-15
    add     r10, r9, r9, lsl #2
    add     r10, r10, r7            @ r10 = &notes[pad][0] - ST_NOTE
    ldrb    r0, [r10, #ST_NOTE]
    cmp     r0, #PAD_NONE
    bne     press_done              @ already down
    movs    r0, #PAD_SILENT
    strb    r0, [r10, #ST_NOTE]
    movs    r0, #PAD_NONE
    strb    r0, [r10, #ST_NOTE + 1]
    strb    r0, [r10, #ST_NOTE + 2]
    strb    r0, [r10, #ST_NOTE + 3]
    strb    r0, [r10, #ST_NOTE + 4]
    cmp     r8, #CT_MODE
    bhs     press_root
    cmp     r8, #1
    bne     press_chord
    ldr     r0, =GLOBALS
    ldrb    r11, [r0, #4 + 79]      @ drum output channel; 16+ = off
    cmp     r11, #15
    bhi     press_done
    movs    r0, #0
    mov     r1, r9
    call_abs LANE_NOTE
    cmp     r0, #127
    bhi     press_done              @ -1 or out of range: no note
    strb    r0, [r10, #ST_NOTE]
    movs    r8, #0                  @ key lights: track 1
    b       press_send
press_chord:
    sub     r8, r8, #1              @ r8 = track 1-3
    bl      chords_load
    @ Erase held: forget this pad's chord
    mov     r0, r4
    movs    r1, #ID_ERASE
    bl      is_held
    cbz     r0, 2f
    mov     r0, r8
    mov     r1, r9
    bl      chord_slot
    mov     r6, r0
    bl      undo_keep
    mov     r0, r6
    movs    r1, #0xff
    movs    r2, #0
1:  strb    r1, [r0, r2]
    adds    r2, #1
    cmp     r2, #CHORD_NOTES
    blo     1b
    b       press_done
2:  @ keys held on this track: the pad keeps them (lowest first, up to 5)
    mov     r0, r8
    mov     r1, r9
    bl      chord_slot
    mov     r6, r0                  @ r6 = slot (the stock press args are no longer needed)
    sub     sp, #8
    movs    r3, #0                  @ count
    movs    r2, #0                  @ key
3:  add     r1, r2, r2, lsl #1
    ldr     r0, =HELD_KEYS
    add     r1, r1, r0
    ldrb    r0, [r1]
    cmp     r0, #127
    bhi     5f
    ldrb    r1, [r1, #2]
    cmp     r1, r8
    bne     5f
    movs    r1, #0                  @ insert sorted, skip duplicates
4:  cmp     r1, r3
    beq     44f
    ldrb    r12, [sp, r1]
    cmp     r12, r0
    beq     5f
    bhi     45f
    adds    r1, #1
    b       4b
45: cmp     r3, #CHORD_NOTES
    bhs     5f
    mov     r12, r3
46: cmp     r12, r1
    beq     47f
    sub     r11, r12, #1
    ldrb    r11, [sp, r11]
    strb    r11, [sp, r12]
    sub     r12, r12, #1
    b       46b
47: strb    r0, [sp, r1]
    adds    r3, #1
    b       5f
44: cmp     r3, #CHORD_NOTES
    bhs     5f
    strb    r0, [sp, r3]
    adds    r3, #1
5:  adds    r2, #1
    cmp     r2, #37
    blo     3b
    cbz     r3, 7f
    mov     r11, r3
    mov     r0, r6
    bl      undo_keep
    mov     r0, r8
    bl      oct_shift
    mov     r12, r0                 @ kept as played at octave 0
    mov     r3, r11
    movs    r2, #0                  @ store the capture; it sounds already on the keys
6:  cmp     r2, r3
    bhs     61f
    ldrb    r0, [sp, r2]
    sub     r0, r0, r12
    b       62f
61: movs    r0, #0xff
62: strb    r0, [r6, r2]
    adds    r2, #1
    cmp     r2, #CHORD_NOTES
    blo     6b
    add     sp, #8
    b       press_done
7:  add     sp, #8
    @ play: the stored chord, else the scale chord
    ldr     r0, =GLOBALS
    add     r0, r0, r8
    ldrb    r11, [r0, #4 + 75]      @ track output channel; 16+ = off
    cmp     r11, #15
    bhi     press_done
    ldrb    r0, [r6]
    cmp     r0, #127
    bhi     8f
    mov     r0, r8                  @ stored chord -> sounding list, moved with the octave
    bl      oct_shift
    mov     r12, r0
    movs    r2, #0                  @ read
    movs    r3, #0                  @ written
71: ldrb    r0, [r6, r2]
    cmp     r0, #127
    bhi     72f
    add     r0, r0, r12
    cmp     r0, #127
    bhi     72f                     @ out of range (also negative): skipped
    add     r1, r10, r3
    strb    r0, [r1, #ST_NOTE]
    adds    r3, #1
72: adds    r2, #1
    cmp     r2, #CHORD_NOTES
    blo     71b
    cmp     r3, #0                  @ nothing in range: stays taken silently
    beq     press_done
    b       press_send
8:  mov     r0, r8
    mov     r1, r9
    add     r2, r10, #ST_NOTE
    bl      chord_notes
    cmp     r0, #0                  @ nothing in range: stays taken silently
    beq     press_done
    b       press_send
press_root:
    sub     r8, r8, #CT_MODE        @ track 0-3
    ldr     r0, =GLOBALS
    add     r0, r0, r8
    ldrb    r11, [r0, #4 + 75]
    cmp     r11, #15
    bhi     press_done
    mov     r0, r8
    mov     r1, r9
    add     r2, r10, #ST_NOTE
    bl      root_chord
    cmp     r0, #0
    beq     press_done
press_send:
    add     r0, r7, r9
    strb    r11, [r0, #ST_CHAN]
    add     r0, r0, #ST_PTRK
    strb    r8, [r0]
    mov     r5, r8                  @ r5 = track (the button id is no longer needed)
    mov     r0, r8
    ldrb    r1, [r7, #ST_MODE]
    bl      rec_on
    mov     r4, r0                  @ r4 = record (the buttons pointer is no longer needed)
    movs    r8, #0
9:  add     r0, r10, r8
    ldrb    r1, [r0, #ST_NOTE]
    cmp     r1, #127
    bhi     92f
    mov     r6, r1
    mov     r0, r11
    movs    r2, #PAD_VELOCITY
    send_note MSG_NOTE_ON
    add     r1, r7, r9
    add     r1, r1, #ST_PTRK
    ldrb    r1, [r1]
    mov     r0, r6
    movs    r2, #1
    bl      pad_led
    movs    r0, #0xff               @ record it
    cmp     r4, #0
    beq     91f
    mov     r1, r6
    ldr     r3, =REC_X
    ldrb    r3, [r3]
    ldrb    r0, [r7, #ST_MODE]
    cmp     r0, #1
    itt     eq
    moveq   r1, r9                  @ drum hits record as the lane
    moveq   r3, r9
    mov     r0, r5
    movs    r2, #PAD_VELOCITY
    call_abs REC_NOTE
    cmp     r0, #0xc0
    it      hs
    movhs   r0, #0xff
91: add     r1, r9, r9, lsl #2
    add     r1, r1, r8
    add     r1, r1, r7
    add     r1, r1, #ST_SLOT
    strb    r0, [r1]
    adds    r8, #1
    cmp     r8, #CHORD_NOTES
    blo     9b
92: ldrb    r0, [r7, #ST_MODE]      @ the screen names the chord, or the drum lane and its note
    cmp     r0, #1
    bne     93f
    mov     r0, r9
    ldrb    r1, [r10, #ST_NOTE]
    bl      ns_drum
    b       press_done
93: add     r0, r10, #ST_NOTE
    bl      ns_pad
press_done:
    pop     {r3-r11, pc}
press_stock:
    mov     r0, r4
    mov     r1, r5
    mov     r2, r6
    pop     {r3-r11, lr}
    ldr     r12, =(STOCK_PRESS + 1)
    bx      r12
.size pad_press, .-pad_press

.global pad_release
.type pad_release,%function
pad_release:
    push    {r3-r11, lr}
    mov     r4, r0
    mov     r5, r1
    bl      pad_state
    ldrb    r0, [r7, #ST_BT]        @ the bass track's Seq let go: steps are steps again
    cmp     r0, #3
    bhi     1f
    add     r0, r0, r0, lsl #1
    lsls    r0, r0, #1
    adds    r0, #0x14
    cmp     r0, r5
    bne     1f
    movs    r0, #0xff
    strb    r0, [r7, #ST_BT]
1:  ldrb    r0, [r7, #ST_SW]
    cmp     r0, r5
    bne     release_step
    movs    r0, #0
    strb    r0, [r7, #ST_SW]
    pop     {r3-r11, pc}
release_step:
    subs    r0, r5, #0x2e
    cmp     r0, #15
    bhi     release_stock
    mov     r9, r0
    add     r10, r9, r9, lsl #2     @ pads keep their note offs even if the mode changed
    add     r10, r10, r7
    ldrb    r1, [r10, #ST_NOTE]
    cmp     r1, #PAD_NONE
    beq     release_stock
    add     r0, r7, r9
    ldrb    r11, [r0, #ST_CHAN]
    movs    r8, #0
9:  add     r0, r10, r8
    ldrb    r1, [r0, #ST_NOTE]
    movs    r2, #PAD_NONE
    strb    r2, [r0, #ST_NOTE]
    cmp     r1, #127
    bhi     10f
    mov     r6, r1
    mov     r0, r11
    movs    r2, #0
    send_note MSG_NOTE_OFF
    add     r1, r7, r9
    add     r1, r1, #ST_PTRK
    ldrb    r1, [r1]
    mov     r0, r6
    movs    r2, #0
    bl      pad_led
    add     r1, r9, r9, lsl #2      @ a recorded note gets its length
    add     r1, r1, r8
    add     r1, r1, r7
    add     r1, r1, #ST_SLOT
    ldrb    r2, [r1]
    movs    r0, #0xff
    strb    r0, [r1]
    cmp     r2, #0xc0
    bhs     10f
    mov     r1, r2
    add     r0, r7, r9
    add     r0, r0, #ST_PTRK
    ldrb    r0, [r0]
    call_abs REC_END
10: adds    r8, #1
    cmp     r8, #CHORD_NOTES
    blo     9b
    pop     {r3-r11, pc}
release_stock:
    mov     r0, r4
    mov     r1, r5
    pop     {r3-r11, lr}
    ldr     r12, =(STOCK_RELEASE + 1)
    bx      r12
.size pad_release, .-pad_release

@ Save Project, second sector: put the chord table into the staged sector, then program it
.global chord_save
.type chord_save,%function
chord_save:
    push    {r4-r7, lr}
    sub     sp, #12
    mov     r4, r0
    mov     r5, r1
    bl      pad_state
    bl      chords_load
    ldr     r0, =STAGE_BASE
    str     r0, [sp]
    mov     r0, r4
    movw    r1, #CHORD_SECTOR_OFF
    add     r2, r7, #ST_TABLE
    movs    r3, #128                @ halfwords
    call_abs STAGE_WRITE
    mov     r0, r4
    mov     r1, r5
    add     sp, #12
    pop     {r4-r7, lr}
    ldr     r12, =(SECTOR_WRITE + 1)
    bx      r12
.size chord_save, .-chord_save


@ the event loop sends a key's note on at 080156f6 (bl 0801a6e0: r0 port, r1 message, r2 3);
@ [sp + 0x6a] is the key and the held-key table already holds its note and track. A key on the
@ root-chord track only sets the root; everything else is sent as stock, then the screen names the
@ notes held on that key's track (note_show.c).
.global key_send
.type key_send,%function
key_send:
    push    {r4, lr}
    push    {r0-r3}
    ldrb    r4, [sp, #24 + KEY_SLOT_SP]     @ r4 = the key's slot
    add     r3, r4, r4, lsl #1
    ldr     r2, =HELD_KEYS
    add     r3, r3, r2              @ r3 = the key's {note, channel, track}
    ldr     r0, =PAD_STATE
    ldr     r1, [r0]
    ldr     r2, =PAD_MAGIC
    cmp     r1, r2
    bne     1f
    ldrb    r1, [r0, #ST_MODE]
    subs    r1, #CT_MODE
    ldrb    r2, [r3, #2]
    cmp     r1, r2
    bne     1f
    ldrb    r1, [r3]
    cmp     r1, #127
    bhi     1f
    strb    r1, [r0, #ST_ROOT]
    add     sp, #16
    mov     r0, r1
    bl      ns_root
    pop     {r4, pc}
1:  pop     {r0-r3}
    call_abs MIDI_SEND
    mov     r0, r4
    bl      ns_key
    pop     {r4, pc}
.size key_send, .-key_send

@ the event loop hands a pressed key to the stock key handler at 08015ee0 (bl 080108a4; r1 -> the
@ key's note, r3 -> its track); a 0 return drops the key (no sound, no record, no held-key entry).
@ A key on the root-chord track only picks the root: its note, mapped through the track's scale
@ table as the event loop maps held keys, becomes the root, and the key is dropped.
.global key_rec
.type key_rec,%function
key_rec:
    push    {r0-r3}
    ldr     r0, =PAD_STATE
    ldr     r1, [r0]
    ldr     r2, =PAD_MAGIC
    cmp     r1, r2
    bne     1f
    ldrb    r1, [r0, #ST_MODE]
    subs    r1, #CT_MODE
    ldr     r2, [sp, #12]
    ldrb    r2, [r2]
    cmp     r1, r2
    bne     1f
    ldr     r3, [sp, #4]
    ldrb    r3, [r3]                @ the key's note
    cmp     r3, #127
    bhi     2f
    ldr     r1, =KEY_MAP
    add     r1, r1, r2, lsl #7
    ldrb    r1, [r1, r3]            @ scale-mapped, as the held-key table stores it
    cmp     r1, #127
    bhi     2f
    strb    r1, [r0, #ST_ROOT]
    push    {r4, lr}
    mov     r0, r1
    bl      ns_root                 @ the screen names the new root
    pop     {r4, lr}
2:  pop     {r0-r3}
    movs    r0, #0
    bx      lr
1:  pop     {r0-r3}
    ldr     r12, =(STOCK_KEY_REC + 1)
    bx      r12
.size key_rec, .-key_rec

@ every LED send (bl 08054c2c, 7 callers; r0 = the LED object): the step lights show the pads first
@ while a pad mode is on (note_show.c ns_leds, given chord_notes for the scale chords)
.global led_flush
.type led_flush,%function
led_flush:
    push    {r4, lr}
    mov     r4, r0
    adr     r1, chord_notes + 1
    bl      ns_leds
    mov     r0, r4
    pop     {r4, lr}
    ldr     r12, =(LED_FLUSH + 1)
    bx      r12
.size led_flush, .-led_flush

@ chord for step r1 (0-15) on the root-chord root of track r0 (0-3) into r2[0..4]; count in r0
.type root_chord,%function
root_chord:
    push    {r4-r11, lr}
    sub     sp, #20                 @ degree buffer (16) + pad
    mov     r9, r2
    mov     r10, r1
    mov     r4, r0
    ldr     r0, =SEQ_PTR
    ldr     r5, [r0]
    ldr     r0, =CUR_PROJECT
    ldrb    r6, [r0]
    movw    r0, #0xfec
    mla     r5, r6, r0, r5
    ldr     r0, =CUR_PAT
    ldrb    r1, [r0, r4]
    movs    r0, #0x14
    mul     r1, r1, r0
    mov.w   r0, #0x140
    mla     r1, r4, r0, r1
    add     r1, r1, r5
    addw    r1, r1, #0x93a
    ldrb    r7, [r1]
    lsrs    r7, r7, #4              @ r7 = scale root 0-11
    ldrb    r8, [r1, #1]
    and     r8, r8, #15
    movs    r0, #0x16
    mla     r0, r4, r0, r5
    add     r0, r0, #0x1700
    adds    r0, #0x52
    ldrb    r6, [r0]
    and     r6, r6, #7              @ r6 = keyboard octave
    cmp     r8, #8
    beq     1f
    cmp     r8, #9
    beq     2f
    cmp     r8, #0
    it      eq
    moveq   r8, #1
    cmp     r8, #9
    bhi     3f
    ldr     r0, =SCALE_MASKS
    ldrh    r0, [r0, r8, lsl #1]
    b       4f
1:  movw    r1, #0x17c6
    ldrh    r0, [r5, r1]
    b       5f
2:  movw    r1, #0x17c8
    ldrh    r0, [r5, r1]
    b       5f
3:  movw    r0, #0xab5
4:  ubfx    r0, r0, #0, #12
    lsl     r0, r0, r7
    lsr     r1, r0, #12
    orr     r0, r0, r1
5:  ubfx    r0, r0, #0, #12
    cbnz    r0, 6f
    movw    r0, #0xab5
    lsl     r0, r0, r7
    lsr     r1, r0, #12
    orr     r0, r0, r1
    ubfx    r0, r0, #0, #12
6:  @ root: the lowest key held on this track (kept as the root), else the last one picked,
    @ else the scale root in the lowest octave shown. Read from the held keys because the key's
    @ own note-on (key_send) is not sent this way in every state, e.g. while playing.
    movs    r1, #12
    mul     r8, r6, r1
    add     r8, r8, #24             @ r8 = lowest key shown
    ldr     r3, =HELD_KEYS
    movs    r2, #0xff
    movs    r1, #37
14: ldrb    r12, [r3, #2]
    cmp     r12, r4
    bne     15f
    ldrb    r12, [r3]
    cmp     r12, r2
    it      lo
    movlo   r2, r12
15: adds    r3, #3
    subs    r1, #1
    bne     14b
    ldr     r1, =PAD_STATE
    cmp     r2, #127
    it      ls
    strbls  r2, [r1, #ST_ROOT]
    ldrb    r2, [r1, #ST_ROOT]
    cmp     r2, #127
    bls     7f
    add     r2, r8, r7
7:  strb    r2, [sp]                @ degree 0 = the root itself, in the scale or not
    movs    r11, #1
    movs    r1, #12
    udiv    r3, r2, r1
    mls     r3, r3, r1, r2          @ r3 = pitch class of r2
8:  adds    r2, #1
    adds    r3, #1
    cmp     r3, #12
    it      eq
    moveq   r3, #0
    cmp     r2, #127
    bhi     10f
    lsr     r1, r0, r3
    tst     r1, #1
    beq     8b
    strb    r2, [sp, r11]
    add     r11, r11, #1
    cmp     r11, #13
    blo     8b
10: adr     r6, rc_table            @ step -> 5 degree codes
    add     r10, r10, r10, lsl #2
    add     r6, r6, r10
    movs    r0, #0                  @ notes written
    movs    r3, #0
11: ldrb    r1, [r6, r3]
    cmp     r1, #0xff
    beq     13f
    and     r2, r1, #0x1f
    cmp     r2, r11
    bhs     12f                     @ above 127: skipped
    ldrb    r2, [sp, r2]
    tst     r1, #0x40
    it      ne
    addne   r2, r2, #12
    tst     r1, #0x20
    it      ne
    subne   r2, r2, #12
    cmp     r2, #127
    bhi     12f                     @ out of range (also negative): skipped
    strb    r2, [r9, r0]
    adds    r0, #1
12: adds    r3, #1
    cmp     r3, #CHORD_NOTES
    blo     11b
13: mov     r4, r0
    mov     r0, r9
    mov     r1, r4
    mov     r2, r8
    bl      fit_keys
    mov     r0, r4
    add     sp, #20
    pop     {r4-r11, pc}
.size root_chord, .-root_chord

@ move the r1 notes at r0 by whole octaves onto the 37 keys shown from r2, as far as they fit:
@ down while the top is past the last key, up while the bottom is below the first
.type fit_keys,%function
fit_keys:
    push    {r4-r6, lr}
    cmp     r1, #0
    beq     9f
    ldrb    r3, [r0]                @ r3 = lowest note
    mov     r4, r3                  @ r4 = highest note
    movs    r5, #1
1:  cmp     r5, r1
    bhs     2f
    ldrb    r6, [r0, r5]
    cmp     r6, r3
    it      lo
    movlo   r3, r6
    cmp     r6, r4
    it      hi
    movhi   r4, r6
    adds    r5, #1
    b       1b
2:  add     r6, r2, #36             @ r6 = last key shown, 127 at most
    cmp     r6, #127
    it      hi
    movhi   r6, #127
    movs    r5, #0                  @ r5 = shift
3:  cmp     r4, r6
    ble     4f
    sub     r12, r3, #12
    cmp     r12, r2
    blt     4f
    subs    r3, #12
    subs    r4, #12
    subs    r5, #12
    b       3b
4:  cmp     r3, r2
    bge     5f
    add     r12, r4, #12
    cmp     r12, r6
    bgt     5f
    adds    r3, #12
    adds    r4, #12
    adds    r5, #12
    b       4b
5:  subs    r1, #1
    ldrb    r3, [r0, r1]
    add     r3, r3, r5
    strb    r3, [r0, r1]
    cmp     r1, #0
    bne     5b
9:  pop     {r4-r6, pc}
.size fit_keys, .-fit_keys

@ SysEx bulk SET item 0x78 (project), param 0x7d, one index = track 2-4 (1-3), 80 bytes:
@ the track's 16 chord pads x 5 notes, 0x7f = unused. Called from setname_hook with
@ r0 = message, r1 = data, r2 = length. Writes the track's part of the project's chord block
@ in flash (an empty block first if the project has none) and drops the RAM copy.
.equ CS_BUF,        PAD_STATE + 0x200   @ make bass scratch, free outside the combo
.type chord_set,%function
chord_set:
    push    {r4-r7, lr}
    sub     sp, #12
    cmp     r2, #80
    bne     9f
    ldrb    r4, [r0, #2]            @ normalized slot 0..15
    cmp     r4, #15
    bhi     9f
    ldrb    r5, [r0, #4]            @ index, 0-based: 0..2 = track 2-4
    cmp     r5, #2
    bhi     9f
    ldr     r6, =CS_BUF
    movs    r2, #0
1:  ldrb    r3, [r1, r2]
    cmp     r3, #0x7f
    blo     2f
    movs    r3, #PAD_NONE
2:  strb    r3, [r6, r2]
    adds    r2, #1
    cmp     r2, #80
    blo     1b

    lsl     r1, r4, #17
    ldr     r2, =0x60010000
    add     r1, r1, r2
    movs    r0, #0
    call_abs SECTOR_READ

    ldr     r0, =(STAGE_BASE + CHORD_SECTOR_OFF)
    ldr     r0, [r0]
    ldr     r1, =CHORD_MAGIC
    cmp     r0, r1
    beq     4f
    add     r2, r6, #80             @ no block yet: an empty one
    str     r1, [r2]
    movs    r0, #0xff
    movs    r3, #4
3:  strb    r0, [r2, r3]
    adds    r3, #1
    cmp     r3, #256
    blo     3b
    ldr     r0, =STAGE_BASE
    str     r0, [sp]
    movs    r0, #0
    movw    r1, #CHORD_SECTOR_OFF
    movs    r3, #128                @ halfwords
    call_abs STAGE_WRITE
4:  ldr     r0, =STAGE_BASE
    str     r0, [sp]
    movs    r0, #0
    movs    r1, #80
    muls    r1, r5, r1
    movw    r2, #(CHORD_SECTOR_OFF + 8)
    add     r1, r1, r2
    mov     r2, r6
    movs    r3, #40                 @ halfwords
    call_abs STAGE_WRITE

    lsl     r1, r4, #17
    ldr     r2, =0x60010000
    add     r1, r1, r2
    movs    r0, #0
    call_abs SECTOR_WRITE
    ldr     r0, =0x20000671         @ as the name: no session left for the close handler
    movs    r1, #0
    strb    r1, [r0]
    ldr     r0, =PAD_STATE          @ the RAM copy reloads from flash on next use
    ldr     r1, [r0]
    ldr     r2, =PAD_MAGIC
    cmp     r1, r2
    bne     9f
    movs    r1, #0xff
    strb    r1, [r0, #ST_TAG]
    movs    r1, #0
    strb    r1, [r0, #ST_UNDO]
9:  add     sp, #12
    pop     {r4-r7, pc}
.size chord_set, .-chord_set
.ltorg

@ degree codes per step: scale degree above the root (0 = root), +0x40 octave up, +0x20 down
.equ U, 0x40
.equ D, 0x20
rc_table:
    .byte 0, 0+U, 0xff, 0xff, 0xff         @ 1  root + octave
    .byte 0, 1, 4, 0xff, 0xff              @ 2  sus2
    .byte 0, 2, 4, 0xff, 0xff              @ 3  triad
    .byte 0, 3, 4, 0xff, 0xff              @ 4  sus4
    .byte 0, 4, 0+U, 0xff, 0xff            @ 5  power
    .byte 0, 2, 4, 5, 0xff                 @ 6  sixth
    .byte 0, 2, 4, 6, 0xff                 @ 7  seventh
    .byte 0+U, 2+U, 4+U, 0xff, 0xff        @ 8  triad octave up
    .byte 0, 2, 4, 6, 8                    @ 9  ninth
    .byte 0, 2, 4, 8, 0xff                 @ 10 add9
    .byte 0, 2, 6, 8, 10                   @ 11 eleventh (no 5th)
    .byte 2, 4, 0+U, 0xff, 0xff            @ 12 1st inversion
    .byte 0, 2, 6, 8, 12                   @ 13 thirteenth (no 5th, no 11th)
    .byte 4, 0+U, 2+U, 0xff, 0xff          @ 14 2nd inversion
    .byte 0, 3, 4, 6, 0xff                 @ 15 7sus4
    .byte 0+D, 2+D, 4+D, 0xff, 0xff        @ 16 triad octave down
.balign 4

.ltorg
