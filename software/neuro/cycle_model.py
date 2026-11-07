"""Cycle model of nv_top for timed replay of real event traces (DESIGN §6.3, §8.2 N9).

Not a golden model of any output word: it estimates *when* words move, so that N9 can size the FIFO and report
replay throughput and authenticated latency on traces too long for RTL simulation. It is checked against the
RTL's CYCLES counter on the §7.2 cases by experiments/neuro_rtl_exact.py (N1).

Model (one word per clock unless stated; numbers from the RTL, `nv_*.v`):
    front end   packetizer + trailer + nv_xor + skid + credit gate: 1 word/clk; 12 header words and the trailer
                words (bitmap, 3 fixed) per packet; K_pol restart KS_RESTART clk after each header; at V2/V3 the
                first CD word of a packet waits until its tables are filled (fill_clk(W, H), started when the
                previous packet's tables are done, i.e. one-packet prefetch); a word enters nv_feistel only while
                the FIFO has credit (DEPTH)
    Feistel     fixed latency LAT
    tag         per packet: header wait + init (12/U + 1), 3 header blocks, then one block per 4 words
                (8/U + 1 clk each), final block(s) + p12 (12/U + 1); MAC at V0-V3, ENC at V4 (same block cost)
    output      4 tag words after the body; output never stalls (replay into DMA)

replay(words_per_packet, ...) returns cycles, throughput (input words/clk), FIFO high-water mark, per-packet
authenticated latency (clk from the packet's last input word to its tag), and input backlog.
"""
from dataclasses import dataclass

import numpy as np

LAT = 16
KS_RESTART = 15
HEADER_WORDS = 12
TRAILER_FIXED_WORDS = 3


def fill_clk(W, H):
    """nv_table_gen fill time: 4 (W + H) entries, 2 keystream takes of 8 bits each, ~9 clk per 128 bits."""
    entries = 4 * (W + H)
    bits = 16 * entries
    return int(entries * 2 + (bits / 128) * 9 * 0.5) + 15


@dataclass
class PacketLoad:
    n_words: int              # payload words (incl. TIME_HIGH, dummies)
    n_cd: int                 # CD words (for the bitmap and the table need)
    t_last_in: int = 0        # clock at which the packet's last input word (or its closing TIME_HIGH) arrives
    bitmap_words: int = 0


@dataclass
class ReplayResult:
    cycles: int
    words_in: int
    words_out: int
    fifo_max: int
    latency: np.ndarray
    backlog_max: int

    @property
    def throughput(self):
        return self.words_in / max(1, self.cycles)


def tag_clk(n_body_words, U):
    """Clocks nv_tag32 needs for one packet whose body (header + payload + trailer) has n words."""
    blk = 8 // U + 1
    init = 12 // U + 1
    n_bytes = 4 * n_body_words
    n_blocks = n_bytes // 16 + 1          # full blocks + the final (partial or empty) block
    return init + n_blocks * blk + (12 // U + 1)


def replay(packets, level=3, U=2, W=128, H=128, depth=512, timed=True):
    """Simulate packets in order.

    timed=True: a packet's payload words arrive spread evenly up to its t_last_in (sensor timing);
    timed=False: maximum rate (input always available).
    """
    perm = level in (2, 3)
    fc = fill_clk(W, H) if perm else 0
    blk = 8 // U + 1
    t_front = t_tag = 0
    fill_done = 0
    enters, pops, arrivals, accepts, lat = [], [], [], [], []
    words_in = words_out = 0
    prev_last = 0
    for p in packets:
        n_tail = p.bitmap_words + TRAILER_FIXED_WORDS
        start = t_front
        if perm and p.n_cd:
            start = max(start, fill_done)
            fill_done = start + fc                       # one-packet prefetch of the next tables
        t = start + HEADER_WORDS + KS_RESTART
        span = max(0, p.t_last_in - prev_last)
        times = []
        for i in range(p.n_words + n_tail):
            a = 0
            if timed and i < p.n_words:
                a = prev_last + (span * (i + 1)) // max(1, p.n_words)
            t = max(t + 1, a)
            k = len(enters) + len(times) - depth          # credit gate
            if 0 <= k < len(pops):
                t = max(t, pops[k])
            times.append(t)
            if i < p.n_words:
                arrivals.append(a)
                accepts.append(t)
        t_front = t
        enters.extend(times)
        words_in += p.n_words
        # tag: header blocks while the payload flows, then one block per 4 words as they leave the Feistel
        ready = [x + LAT for x in times]
        tt = max(t_tag, start + HEADER_WORDS + LAT) + (12 // U + 1) + 3 * blk
        for j in range(0, len(ready), 4):
            tt = max(tt, ready[min(j + 3, len(ready) - 1)]) + blk
            pops.extend([tt] * min(4, len(ready) - j))
        tt += 12 // U + 1
        t_tag = tt + 4
        words_out += HEADER_WORDS + p.n_words + n_tail + 4
        lat.append(t_tag - (p.t_last_in if timed else times[-1]))
        prev_last = p.t_last_in
    ent = np.sort(np.asarray(enters, dtype=np.int64) + LAT)
    pop = np.sort(np.asarray(pops, dtype=np.int64))
    fifo_max = int(np.max(np.arange(1, len(ent) + 1) - np.searchsorted(pop, ent, side="right"))) if len(ent) else 0
    backlog = 0
    if accepts:
        arr = np.sort(np.asarray(arrivals, dtype=np.int64))
        acc = np.asarray(accepts, dtype=np.int64)
        backlog = int(np.max(np.searchsorted(arr, acc, side="right") - np.arange(len(acc))))
    return ReplayResult(int(max(t_front, t_tag)), words_in, words_out, max(0, fifo_max), np.array(lat), backlog)


def packets_from_sender(packet_bytes, T_us=1024, clk_mhz=100):
    """PacketLoad list from sealed packets (V0-V3 public framing), with t_last_in at the packet end."""
    from .packet import from_bytes, bitmap_len
    out = []
    for raw in packet_bytes:
        p = from_bytes(raw)
        h = p.header
        n_words = p.trailer.n_words if h.level != 4 else 0
        n_cd = p.trailer.n_cd if h.level != 4 else 0
        bm = bitmap_len(n_cd) // 4 if h.pad else 0
        out.append(PacketLoad(n_words, n_cd, int((h.t_start + h.T_us) * clk_mhz), bm))
    if out:
        t0 = out[0].t_last_in - T_us * clk_mhz
        for q in out:
            q.t_last_in -= t0
    return out
