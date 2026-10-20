/* sjpeg_sw.c -- the whole secure JPEG encoder in software, for the PYNQ-Z2's processing system (PS).
 *
 * Golden model: model/hw.py :: encode_frame (contract v2) and encode_frame_v3 (contract v3, E0..E5).
 * Same arithmetic, same bytes as the programmable logic (PL):
 *   colour conversion + 4:2:0  (rgb_to_ycbcr, planes)      two-pass integer DCT (dct_stage, dct2d)
 *   reciprocal quantiser (quantise)                        zig-zag + run length (run_length)
 *   selective encryption with the Ascon keystream (selective_encrypt, bits_needed, encrypt_symbol)
 *   Huffman + bit packing with 0xFF00 stuffing (huffman_bits, pack_bytes)
 *   restart segments, K_seg (segment_key), RST0..7 (encode_frame_v3), frame tag (frame_tag)
 * The constant tables (DCT, zig-zag, Huffman codes, reciprocals) are handed in by the Python wrapper
 * (future_work/arm/sw_encoder.py) from the model itself, so they cannot drift.
 *
 * Why it exists: (1) the ARM baseline (A3) -- the identical work on the Cortex-A9, so the PL's speed-up
 * is measured on the same function, not against a different codec; (2) a PS-only fallback of the board
 * sender; (3) a split in which the PS codes some segments and the PL the others (segments are
 * independent in contract v3, so the two cores of the A9 act as two more "lanes").
 * Segments are spread over `nthreads` POSIX threads round robin, like the PL spreads MCU rows over lanes.
 * tests/test_arm_software.py checks every byte against the model. */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>

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

static uint64_t le64(const uint8_t *b, int n) {         /* n <= 8 bytes, little-endian */
    uint64_t x = 0;
    for (int i = n - 1; i >= 0; i--) x = (x << 8) | b[i];
    return x;
}

static void st64(uint8_t *b, uint64_t x) { for (int i = 0; i < 8; i++) b[i] = (uint8_t)(x >> (8 * i)); }

static void ascon_init(uint64_t s[5], const uint8_t key[16], uint64_t n0, uint64_t n1) {
    uint64_t k0 = le64(key, 8), k1 = le64(key + 8, 8);
    s[0] = 0x00001000808C0001ULL; s[1] = k0; s[2] = k1; s[3] = n0; s[4] = n1;
    perm(s, 12);
    s[3] ^= k0; s[4] ^= k1;
}

/* Ascon-AEAD128 over AD = a || b, empty plaintext: the 16-byte tag (model/ascon.py :: mac). */
void sjpeg_ascon_mac2(const uint8_t key[16], uint64_t n0, uint64_t n1, const uint8_t *a, int32_t alen,
                      const uint8_t *b, int32_t blen, uint8_t tag[16]) {
    uint64_t s[5];
    ascon_init(s, key, n0, n1);
    int64_t total = (int64_t)alen + blen;
    if (total > 0) {
        uint8_t blk[16];
        int64_t pos = 0;
        int done = 0;
        while (!done) {
            int k = 0;
            while (k < 16 && pos < total) { blk[k++] = pos < alen ? a[pos] : b[pos - alen]; pos++; }
            if (k < 16) { blk[k++] = 0x01; while (k < 16) blk[k++] = 0; done = 1; }
            s[0] ^= le64(blk, 8); s[1] ^= le64(blk + 8, 8);
            perm(s, 8);
            if (!done && pos == total) {                 /* AD a multiple of 16: one more padding block */
                memset(blk, 0, 16); blk[0] = 0x01;
                s[0] ^= le64(blk, 8); s[1] ^= le64(blk + 8, 8);
                perm(s, 8);
                done = 1;
            }
        }
    }
    s[4] ^= 1ULL << 63;
    /* empty plaintext: the padding block 0x01 */
    s[0] ^= 0x01;
    uint64_t k0 = le64(key, 8), k1 = le64(key + 8, 8);
    s[2] ^= k0; s[3] ^= k1;
    perm(s, 12);
    st64(tag, s[3] ^ k0); st64(tag + 8, s[4] ^ k1);
}

/* Full-frame Ascon-AEAD128 encryption of a buffer (the "encrypt the whole JPEG" baseline):
 * out = ciphertext || tag, out has room for len + 16 bytes. No AD. */
void sjpeg_ascon_encrypt(const uint8_t key[16], const uint8_t nonce[16], const uint8_t *pt, int32_t len,
                         uint8_t *out) {
    uint64_t s[5];
    ascon_init(s, key, le64(nonce, 8), le64(nonce + 8, 8));
    s[4] ^= 1ULL << 63;
    int32_t i = 0;
    for (; i + 16 <= len; i += 16) {
        s[0] ^= le64(pt + i, 8); s[1] ^= le64(pt + i + 8, 8);
        st64(out + i, s[0]); st64(out + i + 8, s[1]);
        perm(s, 8);
    }
    uint8_t blk[16] = {0}, c[16];
    int last = len - i;
    memcpy(blk, pt + i, last);
    blk[last] = 0x01;
    s[0] ^= le64(blk, 8); s[1] ^= le64(blk + 8, 8);
    st64(c, s[0]); st64(c + 8, s[1]);
    memcpy(out + i, c, last);
    uint64_t k0 = le64(key, 8), k1 = le64(key + 8, 8);
    s[2] ^= k0; s[3] ^= k1;
    perm(s, 12);
    st64(out + len, s[3] ^ k0); st64(out + len + 8, s[4] ^ k1);
}

/* keystream: Ascon-AEAD128 ciphertext of zeros, no AD; bits handed out LSB first (model Keystream) */
typedef struct { uint64_t s[5]; uint64_t w[2]; int word, bit; } ks_t;

static void ks_init(ks_t *k, const uint8_t key[16], uint64_t n0, uint64_t n1) {
    ascon_init(k->s, key, n0, n1);
    k->s[4] ^= 1ULL << 63;
    k->word = 2; k->bit = 0;
}

static uint32_t ks_take(ks_t *k, int n) {               /* bit j of the result = j-th bit handed out */
    uint32_t v = 0;
    for (int j = 0; j < n; ) {
        if (k->word == 2) { k->w[0] = k->s[0]; k->w[1] = k->s[1]; perm(k->s, 8); k->word = 0; k->bit = 0; }
        int avail = 64 - k->bit, take = n - j < avail ? n - j : avail;
        uint64_t bits = (k->w[k->word] >> k->bit) & ((take == 64) ? ~0ULL : ((1ULL << take) - 1));
        v |= (uint32_t)(bits << j);
        j += take; k->bit += take;
        if (k->bit == 64) { k->bit = 0; k->word++; }
    }
    return v;
}

/* ------------------------------------------------------------------------------- tables */
static int32_t DCT_C[64];          /* DCT_C[u*8+x] */
static int32_t ZZ[64];
static uint16_t DC_CODE[2][12], AC_CODE[2][256];
static uint8_t DC_LEN[2][12], AC_LEN[2][256];
static int S1, S2;

void sjpeg_set_tables(const int32_t dct[64], const int32_t zz[64], const uint16_t dc_code[24],
                      const uint8_t dc_len[24], const uint16_t ac_code[512], const uint8_t ac_len[512],
                      int32_t shift1, int32_t shift2) {
    memcpy(DCT_C, dct, sizeof DCT_C); memcpy(ZZ, zz, sizeof ZZ);
    memcpy(DC_CODE, dc_code, sizeof DC_CODE); memcpy(DC_LEN, dc_len, sizeof DC_LEN);
    memcpy(AC_CODE, ac_code, sizeof AC_CODE); memcpy(AC_LEN, ac_len, sizeof AC_LEN);
    S1 = shift1; S2 = shift2;
}

/* --------------------------------------------------------------------------- bit packer */
typedef struct { uint8_t *out; int32_t n; uint64_t acc; int nb; } pk_t;

static inline void put_byte(pk_t *p, uint8_t b) { p->out[p->n++] = b; if (b == 0xFF) p->out[p->n++] = 0x00; }

static inline void put_bits(pk_t *p, uint32_t val, int len) {
    p->acc = (p->acc << len) | (val & ((1u << len) - 1));
    p->nb += len;
    while (p->nb >= 8) { p->nb -= 8; put_byte(p, (uint8_t)(p->acc >> p->nb)); }
    p->acc &= (1ULL << p->nb) - 1;
}

static void flush_bits(pk_t *p) {
    if (p->nb) put_byte(p, (uint8_t)(((p->acc << (8 - p->nb)) | ((1u << (8 - p->nb)) - 1)) & 0xFF));
    p->nb = 0; p->acc = 0;
}

/* ------------------------------------------------------------------------- one segment */
static inline int clamp255(int v) { return v < 0 ? 0 : v > 255 ? 255 : v; }
static inline int category(int v) { int a = v < 0 ? -v : v, n = 0; while (a) { n++; a >>= 1; } return n; }

static void dct_stage(const int32_t *in, int32_t *out, int shift) {
    int32_t half = 1 << (shift - 1);
    for (int u = 0; u < 8; u++)
        for (int y = 0; y < 8; y++) {
            int32_t acc = 0;
            for (int x = 0; x < 8; x++) acc += DCT_C[u * 8 + x] * in[y * 8 + x];
            out[u * 8 + y] = (acc + half) >> shift;       /* arithmetic shift = floor, as in the model */
        }
}

typedef struct {
    const uint8_t *rgb; int w, h;
    const uint32_t *recip;          /* 128: luma 0..63, chroma 64..127 */
    int mode;                       /* field mode: 0..4 (E5 codes E4 fields) */
} frame_t;

/* Code one symbol: encryption (selective_enc.v) + Huffman + amplitude bits. */
static inline void emit(pk_t *pk, ks_t *ks, int mode, int is_dc, int t, int run, int size, uint32_t amp) {
    if (size) {
        int sgn = mode >= (is_dc ? 2 : 1), am = mode >= (is_dc ? 4 : 3);
        int n = (sgn ? 1 : 0) + (am ? size - 1 : 0);
        if (n) {
            uint32_t k = ks_take(ks, n);
            if (k & 1) amp ^= (1u << size) - 1;
            if (n > 1) amp ^= (k >> 1);           /* bits 1.. XOR the low size-1 bits, LSB first */
            /* when !sgn && am cannot happen (am implies sgn for every mode) */
        }
    }
    if (is_dc) put_bits(pk, DC_CODE[t][size], DC_LEN[t][size]);
    else put_bits(pk, AC_CODE[t][(run << 4) | size], AC_LEN[t][(run << 4) | size]);
    if (size) put_bits(pk, amp, size);
}

static void code_block(const frame_t *f, pk_t *pk, ks_t *ks, int comp, const int32_t smp[64], int32_t pred[3]) {
    int32_t x[64], a[64], F[64], q[64];
    for (int i = 0; i < 64; i++) x[i] = smp[i] - 128;
    dct_stage(x, a, S1);
    dct_stage(a, F, S2);
    const uint32_t *R = f->recip + (comp ? 64 : 0);
    for (int i = 0; i < 64; i++) {
        int32_t v = F[i], av = v < 0 ? -v : v;
        int32_t m = (int32_t)(((uint64_t)av * R[i] + 32768) >> 16);
        int32_t qq = v < 0 ? -m : m;
        int32_t lo = i == 0 ? -1024 : -1023;
        q[i] = qq < lo ? lo : qq > 1023 ? 1023 : qq;
    }
    int t = comp ? 1 : 0;
    int32_t diff = q[0] - pred[comp];
    pred[comp] = q[0];
    int s = category(diff);
    emit(pk, ks, f->mode, 1, t, 0, s, (uint32_t)(diff >= 0 ? diff : diff - 1) & ((1u << s) - 1));
    int run = 0;
    for (int k = 1; k < 64; k++) {
        int32_t c = q[ZZ[k]];
        if (c == 0) {
            if (k == 63) emit(pk, ks, f->mode, 0, t, 0, 0, 0);          /* EOB */
            else run++;
            continue;
        }
        while (run >= 16) { emit(pk, ks, f->mode, 0, t, 15, 0, 0); run -= 16; }   /* ZRL */
        s = category(c);
        emit(pk, ks, f->mode, 0, t, run, s, (uint32_t)(c >= 0 ? c : c - 1) & ((1u << s) - 1));
        run = 0;
    }
}

/* One MCU (mx, my): four Y blocks, then Cb, Cr (4:2:0 average of the clamped per-pixel values). */
static void code_mcu(const frame_t *f, pk_t *pk, ks_t *ks, int mx, int my, int32_t pred[3]) {
    int32_t Y[16][16], CB[16][16], CR[16][16];
    for (int i = 0; i < 16; i++) {
        const uint8_t *p = f->rgb + ((size_t)(my * 16 + i) * f->w + mx * 16) * 3;
        for (int j = 0; j < 16; j++, p += 3) {
            int r = p[0], g = p[1], b = p[2];
            Y[i][j] = clamp255((77 * r + 150 * g + 29 * b + 128) >> 8);
            CB[i][j] = clamp255((-43 * r - 85 * g + 128 * b + 32896) >> 8);
            CR[i][j] = clamp255((128 * r - 107 * g - 21 * b + 32896) >> 8);
        }
    }
    int32_t blk[64];
    for (int k = 0; k < 4; k++) {
        int r0 = (k >> 1) * 8, c0 = (k & 1) * 8;
        for (int i = 0; i < 8; i++) for (int j = 0; j < 8; j++) blk[i * 8 + j] = Y[r0 + i][c0 + j];
        code_block(f, pk, ks, 0, blk, pred);
    }
    for (int c = 1; c <= 2; c++) {
        int32_t (*P)[16] = c == 1 ? CB : CR;
        for (int i = 0; i < 8; i++)
            for (int j = 0; j < 8; j++)
                blk[i * 8 + j] = (P[2 * i][2 * j] + P[2 * i][2 * j + 1] + P[2 * i + 1][2 * j] + P[2 * i + 1][2 * j + 1] + 2) >> 2;
        code_block(f, pk, ks, c, blk, pred);
    }
}

/* ------------------------------------------------------------------------ whole frame */
#define MCU_WORST 2600        /* 6 blocks x 64 symbols x <= 27 bits, every byte stuffed: < 2600 bytes */

typedef struct {
    const frame_t *f; int contract, per_seg, nseg, tid, nthreads, per_row;
    const uint8_t *key;              /* master key (v2) or K_seg (v3) */
    uint64_t sid, ctr;
    uint8_t *work; int32_t *seglen;
} job_t;

static void *worker(void *arg) {
    job_t *j = (job_t *)arg;
    for (int s = j->tid; s < j->nseg; s += j->nthreads) {
        ks_t ks;
        if (j->contract == 2) ks_init(&ks, j->key, j->sid, j->ctr << 1);           /* N_enc */
        else ks_init(&ks, j->key, (uint64_t)s, j->ctr << 1);                      /* nonce(s, t, 0) */
        pk_t pk = { j->work + (size_t)s * j->per_seg * MCU_WORST, 0, 0, 0 };
        int32_t pred[3] = {0, 0, 0};
        for (int m = s * j->per_seg; m < (s + 1) * j->per_seg; m++)
            code_mcu(j->f, &pk, &ks, m % j->per_row, m / j->per_row, pred);
        flush_bits(&pk);
        j->seglen[s] = pk.n;
    }
    return NULL;
}

/* Encode one frame. contract 2: modes 0..4, one segment. contract 3: modes 0..5, segment = MCU row
 * (one MCU for E5), K_seg, RST markers. prefix = the 26 tag bytes (model/hw.py :: tag_prefix).
 * Returns the scan length (scan in raster order, as the PL returns it), or -1 if `cap` is too small;
 * tag gets the 16-byte frame tag. */
int32_t sjpeg_encode(const uint8_t *rgb, int32_t w, int32_t h, const uint32_t recip[128], int32_t mode,
                     int32_t contract, const uint8_t key[16], uint64_t sid, uint64_t ctr,
                     const uint8_t prefix[26], uint8_t *scan, int32_t cap, uint8_t tag[16], int32_t nthreads) {
    int per_row = w / 16, nmcu = per_row * (h / 16);
    frame_t f = { rgb, w, h, recip, mode == 5 ? 4 : mode };
    int per_seg = contract == 2 ? nmcu : (mode == 5 ? 1 : per_row);
    int nseg = nmcu / per_seg;
    uint8_t kseg[16];
    const uint8_t *k = key;
    if (contract == 3) {                         /* K_seg = Ascon-MAC(K, N_enc, "lanes") */
        sjpeg_ascon_mac2(key, sid, ctr << 1, (const uint8_t *)"lanes", 5, NULL, 0, kseg);
        k = kseg;
    }
    uint8_t *work = (uint8_t *)malloc((size_t)nmcu * MCU_WORST);
    int32_t *seglen = (int32_t *)malloc(sizeof(int32_t) * nseg);
    if (!work || !seglen) { free(work); free(seglen); return -2; }
    if (nthreads < 1) nthreads = 1;
    if (nthreads > nseg) nthreads = nseg;
    job_t jobs[16];
    pthread_t th[16];
    if (nthreads > 16) nthreads = 16;
    for (int t = 0; t < nthreads; t++) {
        jobs[t] = (job_t){ &f, contract, per_seg, nseg, t, nthreads, per_row, k, sid, ctr, work, seglen };
        if (t) pthread_create(&th[t], NULL, worker, &jobs[t]);
    }
    worker(&jobs[0]);
    for (int t = 1; t < nthreads; t++) pthread_join(th[t], NULL);
    int32_t n = 0;
    for (int s = 0; s < nseg; s++) {
        if (s) {
            if (n + 2 > cap) { n = -1; break; }
            scan[n++] = 0xFF; scan[n++] = (uint8_t)(0xD0 + (s - 1) % 8);
        }
        if (n + seglen[s] > cap) { n = -1; break; }
        memcpy(scan + n, work + (size_t)s * per_seg * MCU_WORST, seglen[s]);
        n += seglen[s];
    }
    free(work); free(seglen);
    if (n >= 0) sjpeg_ascon_mac2(key, sid, (ctr << 1) | 1, prefix, 26, scan, n, tag);   /* N_mac */
    return n;
}
