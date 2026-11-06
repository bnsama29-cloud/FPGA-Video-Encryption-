"""Rekeys while the video runs (journal experiment X25): what a key change costs the viewer.

    python experiments/rekey_load.py                                   # simulation, scenarios/rekey_load.json
    python experiments/rekey_load.py --external-sender <BOARD IP> --board-max-mode E5   # the board as camera
    python experiments/rekey_load.py --analyse sim_out/rekey_load/run/events.jsonl      # re-analyse a run

The scenario asks the sender for a rekey every 10 s (on a clean link, then with 3 % loss). Each rekey ratchets
the video key one epoch forward and erases the old key; the receiver follows from the epoch in the session id
of the next valid frame, with no handshake. Per rekey this reports: frames the receiver did not show in the
2 s after it (rejected, stale epoch, or missing by counter), the time from the rekey to the first verified frame
of the new epoch, and whether that epoch was adopted at all. Writes <out>/rekey_load.json and .md.
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
import scenario as sc_mod      # noqa: E402

WINDOW_S = 2.0


def analyse_rekeys(events, window_s=WINDOW_S):
    """events: the run's event list. -> list of per-rekey dicts and a summary."""
    rekeys = [e for e in events if e.get("src") == "sender" and e.get("kind") == "rekey"]
    frames = [e for e in events if e.get("src") == "receiver" and e.get("kind") == "frame"]
    out = []
    for r in rekeys:
        t, epoch = r["t"], r.get("epoch")
        near = [f for f in frames if t <= f["t"] <= t + window_s]
        before = [f for f in frames if t - window_s <= f["t"] < t and f.get("verdict") == "ok"]
        ok_new = [f for f in near if f.get("verdict") == "ok" and f.get("epoch") == epoch]
        bad = [f for f in near if f.get("verdict") not in ("ok", "late")]
        ctrs = sorted(f["ctr"] for f in near if f.get("verdict") == "ok" and f.get("ctr") is not None)
        missing = sum(b - a - 1 for a, b in zip(ctrs, ctrs[1:]) if b > a + 1)
        fps_before = len(before) / window_s
        out.append(dict(t=t, epoch=epoch, adopted=bool(ok_new),
                        first_new_epoch_ms=round(1000 * (ok_new[0]["t"] - t), 1) if ok_new else None,
                        rejected=len(bad), stale_epoch=sum(f.get("verdict") == "stale-epoch" for f in near),
                        missing_by_counter=missing, shown=sum(f.get("verdict") == "ok" for f in near),
                        expected=round(fps_before * window_s)))
    lat = [x["first_new_epoch_ms"] for x in out if x["first_new_epoch_ms"] is not None]
    summary = dict(rekeys=len(out), adopted=sum(x["adopted"] for x in out),
                   rejected_total=sum(x["rejected"] for x in out),
                   stale_epoch_total=sum(x["stale_epoch"] for x in out),
                   missing_total=sum(x["missing_by_counter"] for x in out),
                   first_new_epoch_ms_median=round(statistics.median(lat), 1) if lat else None,
                   first_new_epoch_ms_max=max(lat) if lat else None, window_s=window_s)
    return out, summary


def write(per, summary, out):
    md = ["# Rekeys while the video runs", "",
          f"{summary['rekeys']} rekeys; the receiver adopted {summary['adopted']} new epochs. In the "
          f"{summary['window_s']:.0f} s after each rekey: {summary['rejected_total']} frames rejected "
          f"({summary['stale_epoch_total']} of them from the old epoch), {summary['missing_total']} missing by "
          f"counter (all causes, including channel loss).",
          f"First verified frame of the new epoch: median {summary['first_new_epoch_ms_median']} ms, "
          f"worst {summary['first_new_epoch_ms_max']} ms after the rekey.", "",
          "| Rekey | epoch | adopted | first new-epoch frame (ms) | rejected | stale epoch | missing | shown / expected |",
          "|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(per, 1):
        md.append(f"| {i} | {r['epoch']} | {'yes' if r['adopted'] else 'no'} | {r['first_new_epoch_ms']} | "
                  f"{r['rejected']} | {r['stale_epoch']} | {r['missing_by_counter']} | {r['shown']} / {r['expected']} |")
    out.mkdir(parents=True, exist_ok=True)
    (out / "rekey_load.json").write_text(json.dumps(dict(summary=summary, rekeys=per), indent=1))
    (out / "rekey_load.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", default=str(ROOT / "experiments" / "scenarios" / "rekey_load.json"))
    ap.add_argument("--base-port", type=int, default=47600)
    ap.add_argument("--external-sender", metavar="BOARD_IP")
    ap.add_argument("--board-max-mode", default="E5", choices=["E4", "E5"])
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--out")
    ap.add_argument("--analyse", metavar="EVENTS_JSONL")
    a = ap.parse_args()
    if a.analyse:
        ev = [json.loads(line) for line in Path(a.analyse).read_text().splitlines() if line.strip()]
        write(*analyse_rekeys(ev), Path(a.analyse).parent)
        return
    out = Path(a.out or ROOT / "sim_out" / "rekey_load" / ("board" if a.external_sender else "sim"))
    # rekey_min_interval_s only limits automatic rekeys of the policy; operator rekeys always go through
    sc_mod.run(a.scenario, "fixed", out / "run", base_port=a.base_port, extra_sets=a.set, quiet=True,
               external_sender=a.external_sender, board_max_mode=a.board_max_mode)
    ev = [json.loads(line) for line in (out / "run" / "events.jsonl").read_text().splitlines() if line.strip()]
    write(*analyse_rekeys(ev), out)


if __name__ == "__main__":
    main()
