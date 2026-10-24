/* E5 segment order for the ARM (docs/INTERFACES.md 8.6), a C copy of model/hw.py :: e5_order.
 * Keystream = Ascon-AEAD128 encryption of zeros under (shuffle key, nonce), no AD (model/ascon.py ::
 * Keystream); keystream bits are handed out LSB first; Fisher-Yates with rejection sampling.
 * Built and loaded by system/board/fast_e5.py; tests/test_system.py checks it against the model. */
#include <stdint.h>

#define ROR(x, n) (((x) >> (n)) | ((x) << (64 - (n))))

static void perm(uint64_t s[5], int rounds) {
    for (int r = 12 - rounds; r < 12; r++) {
        s[2] ^= (uint64_t)(((0xF - r) << 4) | r);
        s[0] ^= s[4]; s[4] ^= s[3]; s[2] ^= s[1];
        uint64_t t[5];
        for (int i = 0; i < 5; i++) t[i] = (~s[i]) & s[(i + 1) % 5];
        for (int i = 0; i < 5; i++) s[i] ^= t[(i + 1) % 5];
        s[1] ^= s[0]; s[0] ^= s[4]; s[3] ^= s[2]; s[2] = ~s[2];
        s[0] ^= ROR(s[0], 19) ^ ROR(s[0], 28);
        s[1] ^= ROR(s[1], 61) ^ ROR(s[1], 39);
        s[2] ^= ROR(s[2], 1) ^ ROR(s[2], 6);
        s[3] ^= ROR(s[3], 10) ^ ROR(s[3], 17);
        s[4] ^= ROR(s[4], 7) ^ ROR(s[4], 41);
    }
}

static uint64_t le64(const uint8_t *b) {
    uint64_t x = 0;
    for (int i = 7; i >= 0; i--) x = (x << 8) | b[i];
    return x;
}

typedef struct { uint64_t s[5]; uint64_t w[2]; int word, bit; } ks_t;

static void ks_init(ks_t *k, const uint8_t key[16], const uint8_t nonce[16]) {
    uint64_t k0 = le64(key), k1 = le64(key + 8);
    k->s[0] = 0x00001000808C0001ULL; k->s[1] = k0; k->s[2] = k1;
    k->s[3] = le64(nonce); k->s[4] = le64(nonce + 8);
    perm(k->s, 12);
    k->s[3] ^= k0; k->s[4] ^= k1;
    k->s[4] ^= 1ULL << 63;                 /* empty AD: domain separation only */
    k->word = 2; k->bit = 0;
}

static unsigned ks_bit(ks_t *k) {
    if (k->word == 2) {                    /* next 128-bit block: S0 || S1, little-endian */
        k->w[0] = k->s[0]; k->w[1] = k->s[1];
        perm(k->s, 8);
        k->word = 0; k->bit = 0;
    }
    unsigned b = (unsigned)((k->w[k->word] >> k->bit) & 1);
    if (++k->bit == 64) { k->bit = 0; k->word++; }
    return b;
}

static uint32_t ks_take(ks_t *k, int n) {  /* bit j of the result = j-th bit handed out */
    uint32_t v = 0;
    for (int j = 0; j < n; j++) v |= (uint32_t)ks_bit(k) << j;
    return v;
}

void e5_order(const uint8_t key[16], const uint8_t nonce[16], int32_t n, int32_t *order) {
    ks_t k;
    ks_init(&k, key, nonce);
    for (int32_t i = 0; i < n; i++) order[i] = i;
    for (int32_t i = n - 1; i > 0; i--) {
        int bits = 0;
        for (int32_t x = i; x; x >>= 1) bits++;
        uint32_t j;
        do { j = ks_take(&k, bits); } while (j > (uint32_t)i);
        int32_t t = order[i]; order[i] = order[j]; order[j] = t;
    }
}

/* The whole ARM step of E5 in one call (21 Oct 2026, board speed-up): split the raster-order scan at
 * its RSTm markers exactly like model/hw.py :: split_segments (an 0xFF followed by 0xD0..0xD7; a
 * stuffed 0xFF00 is not a marker), draw the keyed order, and write the segments in that order with
 * the markers renumbered RST((p-1) mod 8). `out` has room for `len` bytes (the length does not
 * change). Returns the number of segments, or -1 if there are more than `maxseg`. */
int32_t e5_shuffle(const uint8_t key[16], const uint8_t nonce[16], const uint8_t *scan, int32_t len,
                   uint8_t *out, int32_t *starts, int32_t *lens, int32_t *order, int32_t maxseg) {
    int32_t n = 0, start = 0, j = 0;
    while (j < len - 1) {
        if (scan[j] == 0xFF && scan[j + 1] >= 0xD0 && scan[j + 1] <= 0xD7) {
            if (n == maxseg) return -1;
            starts[n] = start; lens[n] = j - start; n++;
            start = j + 2; j += 2;
        } else {
            j++;
        }
    }
    if (n == maxseg) return -1;
    starts[n] = start; lens[n] = len - start; n++;
    e5_order(key, nonce, n, order);
    int32_t o = 0;
    for (int32_t p = 0; p < n; p++) {
        if (p) { out[o++] = 0xFF; out[o++] = (uint8_t)(0xD0 + (p - 1) % 8); }
        const uint8_t *s = scan + starts[order[p]];
        for (int32_t b = 0; b < lens[order[p]]; b++) out[o++] = s[b];
    }
    return n;
}
