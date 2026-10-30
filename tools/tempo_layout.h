/* The gap after ST_BSTYLE ends at offset 483; chord/bass scratch starts at 512. */
#define TEMPO_OFFSET 484
#define TEMPO_BYTES 28
#define TEMPO_ADDRESS (0xC01EF800 + TEMPO_OFFSET)
#define TEMPO_MAGIC 0x32504D54
#define TEMPO_ACTIVE (TEMPO_MAGIC | 1)
#define TEMPO_BPM_ADDRESS (0xC01EF800 + 8)
#define TEMPO_DRAWN_ADDRESS (0xC01EF800 + 12)
#define TEMPO_TX_PACKETS 5
/* The application overrides HAL's initial 1ms SysTick with a 100us period. */
#define TEMPO_TICKS_PER_MS 10
#define TEMPO_LEASE_TICKS (3000 * TEMPO_TICKS_PER_MS)
#define TEMPO_FRAME_TICKS (250 * TEMPO_TICKS_PER_MS)

#ifndef __ASSEMBLER__
typedef unsigned char tempo_u8;
typedef unsigned int tempo_u32;
struct tempo_state {
    tempo_u32 magic, heartbeat, heartbeat_inverse, session, rx_tick;
    tempo_u8 rx_payload[7], rx_pos;
};
_Static_assert(sizeof(struct tempo_state) == TEMPO_BYTES, "tempo state size");
_Static_assert(TEMPO_OFFSET >= 483 && TEMPO_OFFSET + TEMPO_BYTES <= 512, "pad scratch overlap");
_Static_assert(TEMPO_BPM_ADDRESS + 4 == TEMPO_DRAWN_ADDRESS &&
               TEMPO_DRAWN_ADDRESS + 4 == 0xC01EF810, "auxiliary pad scratch overlap");
#endif
