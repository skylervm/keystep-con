/* USB-only relative tempo control. Original-model addresses are mapped at build time. */
#include "tempo_layout.h"
#define USB_QUEUE ((volatile tempo_u32 *)0x20004F14)
#define MIDI_OBJECT (*(tempo_u8 *volatile *)0x20001800)
#define BUTTONS (*(tempo_u8 *volatile *)0x200014B8)
#define HOST_BPM (*(volatile tempo_u32 *)TEMPO_BPM_ADDRESS)
#define DRAWN_BPM (*(volatile tempo_u32 *)TEMPO_DRAWN_ADDRESS)
#define UI (*(tempo_u8 *volatile *)0x20001510)
#define DISPLAY (*(tempo_u8 *volatile *)0x200017F8)
#define PROJECT (*(volatile tempo_u8 *)0x20004DAD)
typedef tempo_u32 (*get_tick_fn)(void);
typedef tempo_u32 (*held_fn)(tempo_u8 *, tempo_u32);
typedef void (*page_fn)(tempo_u8 *);
typedef void (*timed_page_fn)(tempo_u8 *, tempo_u32);

static tempo_u32 now(void) { return ((get_tick_fn)0x0803E441)(); }
static tempo_u32 leased(volatile struct tempo_state *s);

static volatile struct tempo_state *state(void)
{
    volatile struct tempo_state *s = (volatile struct tempo_state *)TEMPO_ADDRESS;
    if (s->magic != TEMPO_MAGIC && s->magic != TEMPO_ACTIVE) {
        volatile tempo_u32 *words = (volatile tempo_u32 *)s;
        for (tempo_u32 i = 0; i < TEMPO_BYTES / 4; i++) words[i] = 0;
        HOST_BPM = 0;
        s->magic = TEMPO_MAGIC;
    }
    return s;
}

static tempo_u32 decode21(const volatile tempo_u8 *bytes)
{
    return bytes[0] | ((tempo_u32)bytes[1] << 7) | ((tempo_u32)bytes[2] << 14);
}

static tempo_u32 read16(const tempo_u8 *bytes)
{
    return bytes[0] | ((tempo_u32)bytes[1] << 8);
}

static void queue_visible_bpm(tempo_u32 force)
{
    tempo_u8 *ui = UI, *display = DISPLAY;
    if (!ui || !display || ui[0xC] > 1) return;
    tempo_u32 page = ui[0xC];
    const tempo_u8 *record = ui + (page ? 0x20 : 0x1A);
    if (record[0] != (tempo_u32)PROJECT + 1) return;
    tempo_u32 cache = read16(display + (page ? 0x118 : 0x112));
    if (!force && DRAWN_BPM == HOST_BPM && cache == (HOST_BPM & 0xFFFF)) return;
    /* Queue only. Page-selection helpers would clear other cached edit flags. */
    if (page) ((timed_page_fn)0x08025495)(display, (tempo_u32)-1);
    else ((page_fn)0x0802546D)(display);
}

void tempo_receive_byte(tempo_u8 *parser, tempo_u32 byte)
{
    /* Only the buffered USB parser is tapped. Also reject an unknown object. */
    if (byte >= 0xF8 || !MIDI_OBJECT || parser != MIDI_OBJECT + 0x164) return;
    volatile struct tempo_state *s = state();
    tempo_u32 tick = now();
    if (byte == 0xF0) {
        s->rx_pos = 1;
        s->rx_tick = tick;
        return;
    }
    if (!s->rx_pos) return;
    if ((tempo_u32)(tick - s->rx_tick) > TEMPO_FRAME_MS) { s->rx_pos = 0; return; }
    if (byte == 0xF7) {
        tempo_u8 pos = s->rx_pos;
        s->rx_pos = 0;
        if (pos != 13) return;
        tempo_u32 session = decode21(s->rx_payload + 1);
        tempo_u32 bpm = decode21(s->rx_payload + 4);
        tempo_u8 enabled = s->rx_payload[0];
        if (enabled > 1 || !session || bpm < 2000 || bpm > 99900) return;
        if (!enabled) {
            if (session == s->session) {
                s->magic = TEMPO_MAGIC;
                if (DRAWN_BPM) queue_visible_bpm(1);
            }
            return;
        }
        tempo_u32 changed = bpm != HOST_BPM || session != s->session;
        if (session != s->session) DRAWN_BPM = 0;
        s->session = session;
        HOST_BPM = bpm;
        s->heartbeat = tick;
        s->heartbeat_inverse = ~tick;
        s->magic = TEMPO_ACTIVE;
        queue_visible_bpm(changed);
        return;
    }
    if (byte >= 0x80 || s->rx_pos >= 13) { s->rx_pos = 0; return; }
    static const tempo_u8 header[5] = {0x7D, 0x4B, 0x53, 1, 1};
    tempo_u8 pos = s->rx_pos;
    if (pos <= 5) {
        if (byte != header[pos - 1]) { s->rx_pos = 0; return; }
    } else {
        s->rx_payload[pos - 6] = (tempo_u8)byte;
    }
    s->rx_pos = pos + 1;
}

tempo_u8 *tempo_display_values(tempo_u8 *display, const tempo_u8 *source,
                              tempo_u8 *record, tempo_u32 *values, tempo_u32 cache_offset)
{
    tempo_u32 stock = read16(source + 2);
    if (!leased(state()) || source[0] != (tempo_u32)PROJECT + 1) {
        values[0] = DRAWN_BPM ? stock ^ 1 : read16(display + cache_offset);
        values[1] = stock;
        DRAWN_BPM = 0;             /* Force one stock redraw when leaving host mode. */
        return (tempo_u8 *)source;
    }
    tempo_u32 bpm = HOST_BPM, cached = DRAWN_BPM;
    if (read16(display + cache_offset) != (cached & 0xFFFF)) cached = 0;
    values[0] = cached;
    values[1] = bpm;
    DRAWN_BPM = bpm;
    record[0] = source[0];
    record[1] = source[1];
    record[2] = (tempo_u8)bpm;
    record[3] = (tempo_u8)(bpm >> 8);
    record[4] = 1;                /* Fractional display on the project screen. */
    return record;
}

static tempo_u32 leased(volatile struct tempo_state *s)
{
    if (s->magic != TEMPO_ACTIVE) return 0;
    if (s->heartbeat_inverse == ~s->heartbeat &&
        s->session && s->session < (1u << 21) && HOST_BPM >= 2000 && HOST_BPM <= 99900 &&
        (tempo_u32)(now() - s->heartbeat) <= TEMPO_LEASE_MS) return 1;
    s->magic = TEMPO_MAGIC;
    return 0;
}

static void send_turn(tempo_u32 session, tempo_u32 flags, tempo_u32 magnitude)
{
    tempo_u32 interrupt_mask;
    /* Reserve and publish the whole frame atomically, including against ISR producers. */
    __asm__ volatile ("mrs %0, primask\n\tcpsid i" : "=r"(interrupt_mask) :: "memory");
    tempo_u32 head = USB_QUEUE[0], tail = USB_QUEUE[1];
    if (head < 64 && tail < 64 && ((tail - head - 1) & 63) >= TEMPO_TX_PACKETS) {
        USB_QUEUE[2 + head] = 0x4B7DF004; head = (head + 1) & 63;
        USB_QUEUE[2 + head] = 0x02015304; head = (head + 1) & 63;
        USB_QUEUE[2 + head] = 4 | ((session & 127) << 8) | (((session >> 7) & 127) << 16) | ((session >> 14) << 24);
        head = (head + 1) & 63;
        USB_QUEUE[2 + head] = 4 | (flags << 8) | ((magnitude & 127) << 16) | ((magnitude >> 7) << 24);
        head = (head + 1) & 63;
        USB_QUEUE[2 + head] = 0x0000F705; head = (head + 1) & 63;
        __asm__ volatile ("dmb sy" ::: "memory");
        USB_QUEUE[0] = head;
    }
    __asm__ volatile ("msr primask, %0" :: "r"(interrupt_mask) : "memory");
}

tempo_u32 tempo_turn(const tempo_u8 *frame, tempo_u32 direction)
{
    if (frame[0x6A] != 0) return frame[0x6A];
    volatile struct tempo_state *s = state();
    if (!leased(s)) return frame[0x6A];
    tempo_u32 magnitude = frame[0x6B];
    if (magnitude) {
        tempo_u32 fine = BUTTONS && ((held_fn)0x0804AEBB)(BUTTONS, 1);
        send_turn(s->session, (direction & 1) | (fine ? 2 : 0), magnitude);
        if (UI) ((page_fn)0x0801FAA1)(UI);  /* Preserve the knob's native screen/menu guards. */
    }
    return 0xFF;                   /* stock dispatch drops a consumed event */
}
