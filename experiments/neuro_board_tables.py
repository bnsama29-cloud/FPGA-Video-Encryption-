"""N10 tables: PYNQ-Z2 replay results (bit-exactness, PL vs end-to-end rate, stall counters, first contact).

Usage:
    python experiments/neuro_board_tables.py [--dir sim_out/neuro/n10] [--fclk-mhz 100]

Reads the JSON files written on the board by software/system/board/neuro/nv_first_contact.py
(first_contact.json) and nv_replay.py (replay_<recording>_<mode>.json), copied back with
software/scripts/pull_board_results.py, and writes one table. PL throughput (WORDS_IN over CYCLES at FCLK) and the
end-to-end rate (DMA + ARM + UDP, wall clock) are kept in separate columns (DESIGN §8.2 N10); runs made with the
mock backend are labelled and never mixed into the board table.
Writes <dir>/board_tables.{json,md}.
"""
import argparse
import json
from pathlib import Path

import neuro_common as C


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", type=Path, default=C.OUT / "n10")
    a = ap.parse_args()
    runs, fc = [], None
    for f in sorted(a.dir.glob("replay_*.json")):
        runs.append(json.loads(f.read_text(encoding="utf-8")))
    if (a.dir / "first_contact.json").exists():
        fc = json.loads((a.dir / "first_contact.json").read_text(encoding="utf-8"))
    rows = []
    for r in runs:
        c = r.get("counters", {})
        cyc = c.get("CYCLES") or 0

        def share(k):
            return (c.get(k, 0) / cyc) if cyc else float("nan")
        rows.append((r["recording"], r["mode"], "mock" if r["mock"] else "board", r["level"], r["T_us"],
                     r["words_in"], r["packets"], "yes" if r["bit_exact"] else f"NO {r['first_mismatch']}",
                     (r["pl_words_per_s"] or 0) / 1e6 if not r["mock"] else "-",
                     r["end_to_end_words_per_s"] / 1e6, share("IN_WAIT"), share("OUT_STALL"), share("TABLE_WAIT"),
                     share("KS_WAIT")))
    data = {"first_contact": fc, "replays": runs, "meta": C.meta(a)}
    md = ["# N10 board (PYNQ-Z2)", ""]
    if fc:
        ok = sum(1 for v in fc["cases"].values() if v["pass"])
        md += [f"First contact ({'mock' if fc['mock'] else 'board'}): VERSION {fc['version']}, build {fc['build']}, "
               f"{ok}/{len(fc['cases'])} cases bit-exact.", ""]
    md.append(C.table(["recording", "mode", "backend", "level", "T µs", "words in", "packets", "bit-exact",
                       "PL Mwords/s", "end-to-end Mwords/s", "IN_WAIT", "OUT_STALL", "TABLE_WAIT", "KS_WAIT"], rows)
              if rows else "No replay found: run software/system/board/neuro/nv_replay.py on the board first.")
    C.write("n10", "board_tables", data, "\n".join(md), a.dir)


if __name__ == "__main__":
    main()
