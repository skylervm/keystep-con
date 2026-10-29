/* Note / chord names on the screen (KeyStep Pro 2.5.20, KSCON build 7).
 *
 * Called from the hooks in pad_hooks.S:
 *   ns_key(slot)   after a key's note-on is sent: the notes held on that key's track. On a track in
 *                  Chord mode each key adds the chord it plays (key + the track's chord offsets, each
 *                  note through the track's scale map, as the stock chord expansion 080382e0 does).
 *   ns_pad(notes)  after a chord pad or root-chord step plays: its 5 note bytes (> 127 = unused).
 *   ns_root(note)  a key on the root-chords track picked a new root.
 *   ns_drum(lane, note)  a drum pad hit: "Drum 3" and its note.
 *   ns_leds(leds, chord_notes)  before every LED send (08054c2c): while a pad mode is on, the 16 step
 *                  lights show the pads (see ns_leds); when it is turned off they get back what the
 *                  stock firmware last asked for.
 * One note shows as its name and octave ("E3", C4 = 60). Two or more show the chord name on the first
 * line (root position first, else a slash chord over the lowest note; notes that make no known chord
 * are listed) and the notes on the second. The popup is the one Make bass uses (about a second), and it
 * is skipped where the stock popup would be (menus, other screens).
 *
 * Built with clang -fropi into the hook block (build_ksp_patch.py): no library calls, constant data in
 * .text, firmware functions called by absolute address.
 */
typedef unsigned char u8;
typedef signed char s8;
typedef unsigned short u16;
typedef unsigned int u32;

#define SEQ         (*(u8 *volatile *)0x20001498)
#define CUR_PROJECT (*(volatile u8 *)0x20004dad)
#define HELD        ((volatile u8 *)0x20004ddc)       /* 37 x {note (0xff up), channel, track} */
#define KEY_MAP     ((volatile u8 *)0x20000674)       /* per track 128 bytes: note -> note in the scale */
#define UI          (*(u8 *volatile *)0x20001510)
#define POPUP_CTX   (*(u32 *volatile *)0x200017f8)
#define POPUP_GATE  (*(volatile u8 *)0x200014d7)
#define POPUP_TABLE ((const u8 *)0x08020e4e)
#define TEXT        ((char *)0xC01EFF00)              /* 64 bytes in the pad state block, below Make bass's text */
#define LEDS_PTR    (*(u8 *volatile *)0x20001490)
#define TRACK_COLOURS ((volatile u8 *)0x20000058)
#define PAD         ((u8 *)0xC01EF800)                /* pad state (pad_hooks.S) */
#define PAD_MAGIC   0x5241445au
enum { ST_MODE = 4, ST_TAG = 6, ST_NOTE = 16, ST_TABLE = 128 };

typedef u32 (*f_chord_flag)(u8 *seq, u32 track, u32 project);                 /* 0802d160 */
typedef void (*f_ui)(u8 *ui, u32 what);                                       /* 0801f96c */
typedef void (*f_popup)(u32 *ctx, const char *text, u32 ms);                  /* 08025274 */
typedef u32 (*f_scale_chord)(u32 track, u32 pad, u8 *out);                    /* chord_notes (pad_hooks.S) */

#define NS_MAX   12     /* notes kept */
#define NS_LINE  16     /* characters per screen line */

static const char ns_names[12][3] = {"C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"};

/* chord shapes as 12-bit masks above the root (bit n = n semitones up), best names first */
struct ns_shape { u16 mask; char name[6]; };
static const struct ns_shape ns_shapes[] = {
    {0x091, ""},      {0x089, "m"},     {0x081, "5"},     {0x0A1, "sus4"},  {0x085, "sus2"},
    {0x049, "dim"},   {0x111, "aug"},   {0x491, "7"},     {0x891, "maj7"},  {0x489, "m7"},
    {0x449, "m7b5"},  {0x249, "dim7"},  {0x889, "mMaj7"}, {0x291, "6"},     {0x289, "m6"},
    {0x4A1, "7sus4"}, {0x095, "add9"},  {0x08D, "madd9"}, {0x495, "9"},     {0x895, "maj9"},
    {0x48D, "m9"},    {0x4B5, "11"},    {0x4AD, "m11"},   {0x695, "13"},    {0x68D, "m13"},
    {0x411, "7"},     {0x811, "maj7"},  {0x409, "m7"},    {0x415, "9"},     {0x815, "maj9"},
    {0x40D, "m9"},    {0x435, "11"},    {0x42D, "m11"},   {0x615, "13"},    {0x60D, "m13"},
};
#define NS_SHAPES (sizeof ns_shapes / sizeof ns_shapes[0])

static char *ns_put(char *d, const char *s)
{
    while (*s) *d++ = *s++;
    return d;
}

static char *ns_note(char *d, u32 note)
{
    d = ns_put(d, ns_names[note % 12]);
    u32 octave = note / 12;               /* C4 = 60: octave - 1 */
    if (octave == 0) return ns_put(d, "-1");
    *d++ = (char)('0' + octave - 1);
    return d;
}

static void ns_popup(void)
{
    u8 *ui = UI;
    u32 state = ui[0xC];
    if (state > 0x60) return;
    u8 path = POPUP_TABLE[state];          /* as 08020e3c: 0x31 shows, 0x6c shows when the gate is 0 */
    if (path == 0xa9 || (path == 0x6c && POPUP_GATE)) return;
    ((f_ui)0x0801f96d)(ui, 3);
    ((f_ui)0x0801f96d)(ui, 4);
    ((f_ui)0x0801f96d)(ui, 5);
    ((f_ui)0x0801f96d)(ui, 0x50);
    ((f_popup)0x08025275)(POPUP_CTX, TEXT, 1000);
    ui[0xC] = 0xf;
}

static u32 ns_add(u8 *notes, u32 n, int note)
{
    if (note < 0 || note > 127 || n >= NS_MAX) return n;
    for (u32 i = 0; i < n; i++)
        if (notes[i] == note) return n;
    notes[n] = (u8)note;
    return n + 1;
}

static u32 ns_rotate(u32 mask, u32 root)
{
    return ((mask >> root) | (mask << (12 - root))) & 0xFFF;
}

/* chord name of the pitch classes in mask over the bass pitch class, or 0 */
static char *ns_chord(char *d, u32 mask, u32 bass)
{
    for (u32 k = 0; k < 12; k++) {
        u32 root = (bass + k) % 12;
        if (!(mask >> root & 1)) continue;
        u32 rel = ns_rotate(mask, root);
        for (u32 s = 0; s < NS_SHAPES; s++) {
            if (ns_shapes[s].mask != rel) continue;
            d = ns_put(d, ns_names[root]);
            d = ns_put(d, ns_shapes[s].name);
            if (root != bass) {
                *d++ = '/';
                d = ns_put(d, ns_names[bass]);
            }
            return d;
        }
    }
    return 0;
}

static void ns_show(u8 *notes, u32 n)
{
    if (!n) return;
    for (u32 i = 1; i < n; i++) {          /* lowest first */
        u8 v = notes[i];
        u32 j = i;
        for (; j && notes[j - 1] > v; j--) notes[j] = notes[j - 1];
        notes[j] = v;
    }
    char *d = TEXT;
    if (n == 1) {
        d = ns_note(d, notes[0]);
        *d = 0;
        ns_popup();
        return;
    }
    u32 mask = 0;
    for (u32 i = 0; i < n; i++) mask |= 1u << (notes[i] % 12);
    char *named = (mask & (mask - 1)) ? ns_chord(d, mask, notes[0] % 12) : 0;
    if (named) {
        d = named;
    } else {                                /* no known chord (or octaves of one note): the pitch classes */
        u32 seen = 0;
        for (u32 i = 0; i < n; i++) {
            u32 pc = notes[i] % 12;
            if (seen >> pc & 1) continue;
            if (d - TEXT + 3 > NS_LINE) break;
            if (seen) *d++ = ' ';
            d = ns_put(d, ns_names[pc]);
            seen |= 1u << pc;
        }
    }
    *d++ = '\n';
    char *line = d;
    for (u32 i = 0; i < n; i++) {
        if (d - line + (i ? 5 : 4) > NS_LINE) {   /* " G#-1" at most */
            d = ns_put(d, "..");
            break;
        }
        if (i) *d++ = ' ';
        d = ns_note(d, notes[i]);
    }
    *d = 0;
    ns_popup();
}

/* the notes held on a track's keys, each key with its Chord-mode chord; count */
static u32 ns_held(u32 track, u8 *notes)
{
    u8 *seq = SEQ;
    u32 p = CUR_PROJECT;
    const u8 *trk = seq + p * 0xFEC + track * 0x16 + 0x1754;    /* chord root, then offsets (0 ends) */
    u32 chord = trk[0] != 0xFF && ((f_chord_flag)0x0802d161)(seq, track, p);
    u32 n = 0;
    for (u32 k = 0; k < 37; k++) {
        if (HELD[k * 3 + 2] != track) continue;
        u32 key = HELD[k * 3];
        if (key > 127) continue;
        n = ns_add(notes, n, (int)key);
        if (!chord) continue;
        for (u32 i = 1; i < 16 && trk[i]; i++) {
            int x = (int)key + (s8)trk[i];
            if (x >= 0 && x <= 127) n = ns_add(notes, n, KEY_MAP[track * 128 + x]);
        }
    }
    return n;
}

void ns_key(u32 slot)
{
    u32 track = HELD[slot * 3 + 2];
    if (track > 3) return;
    if (track == 0 && (SEQ[CUR_PROJECT * 0xFEC + 0x1753] & 1)) return;   /* track 1 in drum mode */
    u8 notes[NS_MAX];
    ns_show(notes, ns_held(track, notes));
}

void ns_pad(const u8 *pad)
{
    u8 notes[NS_MAX];
    u32 n = 0;
    for (u32 i = 0; i < 5; i++) n = ns_add(notes, n, pad[i] > 127 ? -1 : pad[i]);
    ns_show(notes, n);
}

void ns_root(u32 note)
{
    char *d = ns_put(TEXT, "Root: ");
    d = ns_put(d, ns_names[note % 12]);
    *d = 0;
    ns_popup();
}

void ns_drum(u32 lane, u32 note)
{
    char *d = ns_put(TEXT, "Drum ");
    if (lane >= 9) *d++ = (char)('0' + (lane + 1) / 10);
    *d++ = (char)('0' + (lane + 1) % 10);
    *d++ = '\n';
    d = ns_note(d, note);
    *d = 0;
    ns_popup();
}

/* Step lights while a pad mode is on. Each LED is 3 bytes at leds + 0x1c + id*3 {on, dim, colour (low
   nibble)}, with a send flag at leds + 0x184 + id; the steps are ids 0x35-0x44. Colours: the track's
   (0x20000058 + track), 5 white; dim = the firmware's low brightness (0802b588).
     pad held                                 white, bright
     chord pad holding the chord on the keys  track colour, bright
     kept chord; any drum or root-chord pad   track colour, dim
     empty chord pad (plays the scale chord)  white, dim
   The stock firmware keeps setting the steps (pattern, playhead); what it last asked for is kept in
   stock[] and put back when the pad mode ends. */
struct ns_lights {
    u32 magic;
    u8 active, pad_[3];
    u8 mine[16][3];                         /* what we last wrote */
    u8 stock[16][3];                        /* what the stock firmware last asked for */
    u16 held_mask, match;                   /* match cache: pitch classes held, pads that match */
    u8 key_track, key_project;
    u32 key_sum;
};
#define LIGHTS      ((struct ns_lights *)0xC01EFC00)    /* free scratch in the pad state block */
#define LIGHTS_MAGIC 0x3154474cu                        /* "LGT1" */

static u32 ns_mask(const u8 *notes, u32 n)
{
    u32 m = 0;
    for (u32 i = 0; i < n; i++)
        if (notes[i] <= 127) m |= 1u << (notes[i] % 12);
    return m;
}

/* pads of chord-pad track t (1-3) whose chord has the same notes (any octave) as the keys held */
static u32 ns_match(struct ns_lights *ls, u32 t, f_scale_chord scale_chord)
{
    u8 notes[NS_MAX];
    u32 held = ns_mask(notes, ns_held(t, notes));
    if (!held || !(held & (held - 1))) return 0;            /* nothing or one note: no chord */
    u32 p = CUR_PROJECT;
    const u8 *kept = PAD[ST_TAG] == p ? PAD + ST_TABLE + 8 + (t - 1) * 80 : 0;
    u32 sum = 0;
    if (kept)
        for (u32 i = 0; i < 80; i++) sum = sum * 31 + kept[i];
    if (held == ls->held_mask && t == ls->key_track && p == ls->key_project && sum == ls->key_sum)
        return ls->match;
    u32 match = 0;
    for (u32 pad = 0; pad < 16; pad++) {
        u32 m;
        if (kept && kept[pad * 5] <= 127) {
            m = ns_mask(kept + pad * 5, 5);
        } else {
            u8 sc[8];
            m = ns_mask(sc, scale_chord(t, pad, sc));
        }
        if (m == held) match |= 1u << pad;
    }
    ls->held_mask = (u16)held;
    ls->key_track = (u8)t;
    ls->key_project = (u8)p;
    ls->key_sum = sum;
    ls->match = (u16)match;
    return match;
}

static void ns_led_put(u8 *leds, u32 i, const u8 *v)
{
    u8 *e = leds + 0x1c + (0x35 + i) * 3;
    if (e[0] == v[0] && e[1] == v[1] && (e[2] & 0xf) == v[2]) return;
    e[0] = v[0];
    e[1] = v[1];
    e[2] = (u8)((e[2] & 0xf0) | v[2]);
    leds[0x184 + 0x35 + i] = 1;
}

void ns_leds(u8 *leds, f_scale_chord scale_chord)
{
    if (leds != LEDS_PTR) return;
    struct ns_lights *ls = LIGHTS;
    if (ls->magic != LIGHTS_MAGIC) {
        ls->magic = LIGHTS_MAGIC;
        ls->active = 0;
        ls->held_mask = 0;
    }
    u32 mode = *(u32 *)PAD == PAD_MAGIC ? PAD[ST_MODE] : 0;
    if (mode == 0 || mode > 8) {
        if (ls->active) {                   /* pad mode ended: the stock lights back (unless it set new ones) */
            for (u32 i = 0; i < 16; i++) {
                const u8 *e = leds + 0x1c + (0x35 + i) * 3;
                if (e[0] == ls->mine[i][0] && e[1] == ls->mine[i][1] && (e[2] & 0xf) == ls->mine[i][2])
                    ns_led_put(leds, i, ls->stock[i]);
            }
            ls->active = 0;
        }
        return;
    }
    u32 t = mode == 1 ? 0 : mode < 5 ? mode - 1 : mode - 5;
    u8 colour = TRACK_COLOURS[t] & 0xf;
    u32 match = mode >= 2 && mode <= 4 ? ns_match(ls, t, scale_chord) : 0;
    const u8 *kept = mode >= 2 && mode <= 4 && PAD[ST_TAG] == CUR_PROJECT ? PAD + ST_TABLE + 8 + (t - 1) * 80 : 0;
    for (u32 i = 0; i < 16; i++) {
        const u8 *e = leds + 0x1c + (0x35 + i) * 3;
        u8 cur[3] = {e[0], e[1], (u8)(e[2] & 0xf)};
        if (!ls->active || cur[0] != ls->mine[i][0] || cur[1] != ls->mine[i][1] || cur[2] != ls->mine[i][2])
            for (u32 k = 0; k < 3; k++) ls->stock[i][k] = cur[k];      /* the stock firmware set it */
        u8 v[3] = {1, 1, colour};
        if (PAD[ST_NOTE + i * 5] != 0xFF) {
            v[1] = 0, v[2] = 5;                                         /* held */
        } else if (match >> i & 1) {
            v[1] = 0;                                                   /* the chord on the keys */
        } else if (mode >= 2 && mode <= 4 && !(kept && kept[i * 5] <= 127)) {
            v[2] = 5;                                                   /* empty chord pad */
        }
        ns_led_put(leds, i, v);
        for (u32 k = 0; k < 3; k++) ls->mine[i][k] = v[k];
    }
    ls->active = 1;
}
