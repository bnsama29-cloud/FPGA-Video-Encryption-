/* sjpeg_rx.c -- the receiver's heavy work in C: tag, E5 un-permutation, Huffman decode, decryption,
 * canonical re-coding. Used by link/fastrx.py, which falls back to the golden model for anything it does
 * not handle (and for every malformed frame, so the reject reasons stay exactly the model's).
 *
 * Golden model: model/jpeg.py :: receive_frame (with _authenticated_scan, _receive_segmented,
 * unpermute_segments, segment_key), model/entropy.py :: huffman_decode / split_restart /
 * run_length_encode / huffman_encode, model/selective.py :: apply_keystream / shuffle_order,
 * model/ascon.py :: mac / Keystream. tests/test_fastrx.py checks every output byte against the model.
 *
 * Why: the Python receiver needs ~160 ms per 320x240 contract-v3 E5 frame (300 segments, 300 keystreams,
 * Ascon in Python), more than the 100 ms between frames at 10 fps; frames queued for seconds. */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

/* ------------------------------------------------------------------ Ascon-AEAD128 (SP 800-232) */
#define ROR(x, n) (((x) >> (n)) | ((x) << (64 - (n))))

static void perm(uint64_t s[5], int rounds) {
    for (int r = 12 - rounds; r < 12; r++) {
        s[2] ^= (uint64_t)(((0xF - r) << 4) | r);
        s[0] ^= s[4]; s[4] ^= s[3]; s[2] ^= s[1];
        uint64_t t0 = (~s[0]) & s[1], t1 = (~s[1]) & s[2], t2 = (~s[2]) & s[3], t3 = (~s[3]) & s[4],
                 t4 = (~s[4]) & s[0];
        s[0] ^= t1; s[1] ^= t2; s[2] ^= t3; s[3] ^= t4; s[4] ^= t0;
        s[1] ^= s[0]; s[0] ^= s[4]; s[3] ^= s[2]; s[2] = ~s[2];
        s[0] ^= ROR(s[0], 19) ^ ROR(s[0], 28);
        s[1] ^= ROR(s[1], 61) ^ ROR(s[1], 39);
        s[2] ^= ROR(s[2], 1) ^ ROR(s[2], 6);
        s[3] ^= ROR(s[3], 10) ^ ROR(s[3], 17);
        s[4] ^= ROR(s[4], 7) ^ ROR(s[4], 41);
    }
}

static uint64_t le64(const uint8_t *b) { uint64_t x = 0; for (int i = 7; i >= 0; i--) x = (x << 8) | b[i]; return x; }
static void st64(uint8_t *b, uint64_t x) { for (int i = 0; i < 8; i++) b[i] = (uint8_t)(x >> (8 * i)); }

static void ascon_init(uint64_t s[5], const uint8_t key[16], uint64_t n0, uint64_t n1) {
    uint64_t k0 = le64(key), k1 = le64(key + 8);
    s[0] = 0x00001000808C0001ULL; s[1] = k0; s[2] = k1; s[3] = n0; s[4] = n1;
    perm(s, 12);
    s[3] ^= k0; s[4] ^= k1;
}

/* Ascon-AEAD128 tag with AD = a || b and an empty message (model/ascon.py :: mac). */
void rx_mac2(const uint8_t key[16], uint64_t n0, uint64_t n1, const uint8_t *a, int32_t alen,
             const uint8_t *b, int32_t blen, uint8_t tag[16]) {
    uint64_t s[5];
    ascon_init(s, key, n0, n1);
    int64_t total = (int64_t)alen + blen, pos = 0;
    if (total > 0) {
        uint8_t blk[16];
        for (;;) {
            int k = 0;
            while (k < 16 && pos < total) { blk[k++] = pos < alen ? a[pos] : b[pos - alen]; pos++; }
            int last = k < 16;
            if (last) { blk[k++] = 0x01; while (k < 16) blk[k++] = 0; }
            s[0] ^= le64(blk); s[1] ^= le64(blk + 8);
            perm(s, 8);
            if (last) break;
            if (pos == total) {                        /* multiple of 16: a whole padding block */
                s[0] ^= 0x01;
                perm(s, 8);
                break;
            }
        }
    }
    s[4] ^= 1ULL << 63;
    s[0] ^= 0x01;                                      /* empty plaintext: its padding block */
    uint64_t k0 = le64(key), k1 = le64(key + 8);
    s[2] ^= k0; s[3] ^= k1;
    perm(s, 12);
    st64(tag, s[3] ^ k0); st64(tag + 8, s[4] ^ k1);
}

typedef struct { uint64_t s[5]; uint64_t w[2]; int word, bit; } ks_t;

static void ks_init(ks_t *k, const uint8_t key[16], uint64_t n0, uint64_t n1) {
    ascon_init(k->s, key, n0, n1);
    k->s[4] ^= 1ULL << 63;
    k->word = 2; k->bit = 0;
}

static uint32_t ks_take(ks_t *k, int n) {
    uint32_t v = 0;
    for (int j = 0; j < n; ) {
        if (k->word == 2) { k->w[0] = k->s[0]; k->w[1] = k->s[1]; perm(k->s, 8); k->word = 0; k->bit = 0; }
        int avail = 64 - k->bit, take = n - j < avail ? n - j : avail;
        uint64_t bits = (k->w[k->word] >> k->bit) & ((1ULL << take) - 1);
        v |= (uint32_t)(bits << j);
        j += take; k->bit += take;
        if (k->bit == 64) { k->bit = 0; k->word++; }
    }
    return v;
}

/* ---------------------------------------------------------------------------- segments */
/* model/entropy.py :: split_restart: an 0xFF followed by 0xD0..0xD7 ends a segment; after any other
 * 0xFF the search resumes two bytes on. Returns the number of segments or -1 if more than maxseg. */
static int32_t split_restart(const uint8_t *scan, int32_t len, int32_t *st, int32_t *ln, int32_t maxseg) {
    int32_t n = 0, start = 0, i = 0;
    for (;;) {
        const uint8_t *f = i < len ? memchr(scan + i, 0xFF, len - i) : NULL;
        if (!f) break;
        int32_t j = (int32_t)(f - scan);
        if (j + 1 >= len) break;
        if (scan[j + 1] >= 0xD0 && scan[j + 1] <= 0xD7) {
            if (n == maxseg) return -1;
            st[n] = start; ln[n] = j - start; n++;
            start = i = j + 2;
        } else {
            i = j + 2;
        }
    }
    if (n == maxseg) return -1;
    st[n] = start; ln[n] = len - start; n++;
    return n;
}

/* order[p] = raster segment carried at transmit position p (model/selective.py :: shuffle_order) */
static void shuffle_order(const uint8_t skey[16], uint64_t sid, uint64_t ctr, int32_t n, int32_t *order) {
    ks_t k;
    ks_init(&k, skey, sid, ctr << 1);
    for (int32_t i = 0; i < n; i++) order[i] = i;
    for (int32_t i = n - 1; i > 0; i--) {
        int bits = 0;
        for (int32_t x = i; x; x >>= 1) bits++;
        uint32_t j;
        do { j = ks_take(&k, bits); } while (j > (uint32_t)i);
        int32_t t = order[i]; order[i] = order[j]; order[j] = t;
    }
}

/* model/jpeg.py :: unpermute_segments with _shuffle_order: transmit order -> raster order, markers
 * renumbered. out has room for len bytes. Returns the length, or -1 if the segment count is not n. */
int32_t rx_unpermute(const uint8_t *scan, int32_t len, const uint8_t skey[16], uint64_t sid, uint64_t ctr,
                     int32_t n, uint8_t *out) {
    int32_t *st = malloc(sizeof(int32_t) * (n + 1)), *ln = malloc(sizeof(int32_t) * (n + 1)),
            *order = malloc(sizeof(int32_t) * (n + 1)), *inv = malloc(sizeof(int32_t) * (n + 1));
    int32_t r = -1;
    if (!st || !ln || !order || !inv) goto done;
    if (split_restart(scan, len, st, ln, n + 1) != n) goto done;
    shuffle_order(skey, sid, ctr, n, order);
    for (int32_t p = 0; p < n; p++) inv[order[p]] = p;        /* natural[order[p]] = segs[p] */
    r = 0;
    for (int32_t s = 0; s < n; s++) {
        if (s) { out[r++] = 0xFF; out[r++] = (uint8_t)(0xD0 + (s - 1) % 8); }
        memcpy(out + r, scan + st[inv[s]], ln[inv[s]]);
        r += ln[inv[s]];
    }
done:
    free(st); free(ln); free(order); free(inv);
    return r;
}

/* ------------------------------------------------------------------------- Huffman tables */
typedef struct { int32_t maxcode[18], valptr[17], mincode[17]; uint8_t vals[256]; } dhuff_t;
static dhuff_t DEC[4];                         /* 0 DC luma, 1 DC chroma, 2 AC luma, 3 AC chroma */
static uint16_t ECODE[4][256];
static uint8_t ELEN[4][256];
static int32_t ZZ[64];

/* bits[t*16 + i] = number of codes of length i+1, vals[t*256 + k] (T.81 Annex C/F, model/tables.py) */
void rx_set_tables(const uint8_t *bits, const uint8_t *vals, const int32_t zz[64]) {
    memcpy(ZZ, zz, sizeof ZZ);
    for (int t = 0; t < 4; t++) {
        dhuff_t *d = &DEC[t];
        int k = 0, code = 0;
        memset(ELEN[t], 0, 256);
        for (int l = 1; l <= 16; l++) {
            int n = bits[t * 16 + l - 1];
            d->valptr[l] = k; d->mincode[l] = code;
            for (int i = 0; i < n; i++, k++, code++) {
                uint8_t v = vals[t * 256 + k];
                d->vals[k] = v; ECODE[t][v] = (uint16_t)code; ELEN[t][v] = (uint8_t)l;
            }
            d->maxcode[l] = n ? code - 1 : -1;
            code <<= 1;
        }
        d->maxcode[17] = 0x7FFFFFFF;
    }
}

/* -------------------------------------------------------------------------------- bit I/O */
typedef struct { const uint8_t *d; int64_t nb, pos; } br_t;           /* unstuffed bytes */

static inline int getbit(br_t *b) {          /* past the end: 1s, like huffman_decode's padding */
    int64_t p = b->pos++;
    return p < b->nb ? (b->d[p >> 3] >> (7 - (p & 7))) & 1 : 1;
}

static inline uint32_t getbits(br_t *b, int n) { uint32_t v = 0; while (n--) v = (v << 1) | getbit(b); return v; }

static inline int decode(br_t *b, const dhuff_t *h) {          /* -1: no such code */
    if (b->pos >= b->nb) return -1;
    int32_t code = 0;
    for (int l = 1; l <= 16; l++) {
        code = (code << 1) | getbit(b);
        if (h->maxcode[l] >= 0 && code <= h->maxcode[l] && code >= h->mincode[l])
            return h->vals[h->valptr[l] + code - h->mincode[l]];
    }
    return -1;
}

typedef struct { uint8_t *out; int64_t n, cap; uint64_t acc; int nb; int err; } pk_t;

static inline void put_byte(pk_t *p, uint8_t v) {
    if (p->n + 2 > p->cap) { p->err = 1; return; }
    p->out[p->n++] = v; if (v == 0xFF) p->out[p->n++] = 0;
}
static inline void put_bits(pk_t *p, uint32_t v, int len) {
    p->acc = (p->acc << len) | (v & ((1u << len) - 1)); p->nb += len;
    while (p->nb >= 8) { p->nb -= 8; put_byte(p, (uint8_t)(p->acc >> p->nb)); }
    p->acc &= (1ULL << p->nb) - 1;
}

/* ------------------------------------------------------------------------- the decode */
static inline int category(int v) { int a = v < 0 ? -v : v, n = 0; while (a) { n++; a >>= 1; } return n; }

/* Decrypt and decode the authenticated scan (raster order) into quantised blocks (zig-zag order),
 * then re-code them canonically: one segment, DC prediction across the frame, no restart markers
 * (the plain JPEG of model/jpeg.py :: receive_frame).
 * contract 2: one segment, keystream (key, nonce(sid, ctr, 0)); contract 3: segments of per_seg MCUs,
 * keystream (K_seg, nonce(s, ctr, 0)), K_seg = mac(key, nonce(sid, ctr, 0), "lanes").
 * mode 0..5 (5 = E4 fields). Returns the plain scan length, or -1 (malformed: the caller asks the model). */
int32_t rx_decode(const uint8_t *scan, int32_t len, int32_t n_mcu, int32_t per_seg, int32_t mode,
                  int32_t contract, const uint8_t key[16], uint64_t sid, uint64_t ctr, uint8_t *out, int32_t cap) {
    int32_t nseg = n_mcu / per_seg, r = -1;
    int32_t *st = malloc(sizeof(int32_t) * (nseg + 1)), *ln = malloc(sizeof(int32_t) * (nseg + 1));
    int16_t *blk = malloc(sizeof(int16_t) * 64 * 6 * (size_t)n_mcu);
    uint8_t *un = malloc(len + 1);
    if (!st || !ln || !blk || !un) goto done;
    if (contract == 3) {
        if (split_restart(scan, len, st, ln, nseg + 1) != nseg) goto done;
    } else {
        if (nseg != 1) goto done;
        st[0] = 0; ln[0] = len;
    }
    uint8_t kk[16];
    const uint8_t *k = key;
    if (contract == 3) { rx_mac2(key, sid, ctr << 1, (const uint8_t *)"lanes", 5, NULL, 0, kk); k = kk; }
    int ac_sign = mode >= 1, dc_sign = mode >= 2, ac_all = mode >= 3, dc_all = mode >= 4;
    memset(blk, 0, sizeof(int16_t) * 64 * 6 * (size_t)n_mcu);
    for (int32_t s = 0; s < nseg; s++) {
        /* unstuff like scan.replace(b"\xff\x00", b"\xff") */
        const uint8_t *src = scan + st[s];
        int32_t m = 0;
        for (int32_t i = 0; i < ln[s]; i++) { un[m++] = src[i]; if (src[i] == 0xFF && i + 1 < ln[s] && src[i + 1] == 0) i++; }
        br_t b = { un, (int64_t)m * 8, 0 };
        ks_t ks;
        if (mode) ks_init(&ks, k, contract == 3 ? (uint64_t)s : sid, ctr << 1);
        int32_t pred[3] = {0, 0, 0};
        for (int32_t mc = s * per_seg; mc < (s + 1) * per_seg; mc++) {
            for (int bi = 0; bi < 6; bi++) {
                int c = bi < 4 ? 0 : bi - 3, t = c ? 1 : 0;
                int16_t *z = blk + ((size_t)mc * 6 + bi) * 64;
                int size = decode(&b, &DEC[t]);
                if (size < 0 || size > 11) goto done;
                uint32_t v = getbits(&b, size);
                if (size && (dc_sign || dc_all)) {
                    uint32_t full = (1u << size) - 1, kb = ks_take(&ks, dc_all ? size : 1);
                    uint32_t mask = (kb & 1) ? full : 0;
                    if (dc_all) mask ^= (kb >> 1) & (full >> 1);
                    v ^= mask;
                }
                int32_t diff = size == 0 ? 0 : (v >> (size - 1)) ? (int32_t)v : (int32_t)v - (1 << size) + 1;
                pred[c] += diff;
                z[0] = (int16_t)pred[c];
                for (int kx = 1; kx < 64; ) {
                    int rs = decode(&b, &DEC[2 + t]);
                    if (rs < 0) goto done;
                    int run = rs >> 4, sz = rs & 15;
                    if (sz == 0) {
                        if (run == 15) { kx += 16; continue; }
                        break;                                                  /* EOB */
                    }
                    uint32_t a = getbits(&b, sz);
                    if (ac_sign || ac_all) {
                        uint32_t full = (1u << sz) - 1, kb = ks_take(&ks, ac_all ? sz : 1);
                        uint32_t mask = (kb & 1) ? full : 0;
                        if (ac_all) mask ^= (kb >> 1) & (full >> 1);
                        a ^= mask;
                    }
                    kx += run;
                    if (kx > 63) goto done;
                    z[kx] = (int16_t)((a >> (sz - 1)) ? (int32_t)a : (int32_t)a - (1 << sz) + 1);
                    kx++;
                }
            }
        }
        if (b.pos > b.nb) goto done;                                        /* truncated */
    }
    /* canonical re-coding (model/entropy.py :: run_length_encode + huffman_encode) */
    pk_t p = { out, 0, cap, 0, 0, 0 };
    int32_t pred[3] = {0, 0, 0};
    for (int32_t mc = 0; mc < n_mcu; mc++)
        for (int bi = 0; bi < 6; bi++) {
            int c = bi < 4 ? 0 : bi - 3, t = c ? 1 : 0;
            const int16_t *z = blk + ((size_t)mc * 6 + bi) * 64;
            int32_t diff = z[0] - pred[c];
            pred[c] = z[0];
            int sz = category(diff);
            put_bits(&p, ECODE[t][sz], ELEN[t][sz]);
            if (sz) put_bits(&p, (uint32_t)(diff >= 0 ? diff : diff - 1) & ((1u << sz) - 1), sz);
            int run = 0;
            for (int kx = 1; kx < 64; kx++) {
                int32_t v = z[kx];
                if (v == 0) {
                    if (kx == 63) put_bits(&p, ECODE[2 + t][0], ELEN[2 + t][0]);
                    else run++;
                    continue;
                }
                while (run >= 16) { put_bits(&p, ECODE[2 + t][0xF0], ELEN[2 + t][0xF0]); run -= 16; }
                sz = category(v);
                put_bits(&p, ECODE[2 + t][(run << 4) | sz], ELEN[2 + t][(run << 4) | sz]);
                put_bits(&p, (uint32_t)(v >= 0 ? v : v - 1) & ((1u << sz) - 1), sz);
                run = 0;
            }
        }
    if (p.nb) put_byte(&p, (uint8_t)(((p.acc << (8 - p.nb)) | ((1u << (8 - p.nb)) - 1)) & 0xFF));
    r = p.err ? -1 : (int32_t)p.n;
done:
    free(st); free(ln); free(blk); free(un);
    return r;
}
