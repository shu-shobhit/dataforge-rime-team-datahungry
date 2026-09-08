#!/usr/bin/env python3
"""Gate 4: how far the agent's idea of playback sits from the listener's.

The framework computes `playback_position` at the agent, from frames it has
handed to the transport. What actually left the speaker is later than that, by
the network hop and the receiver's jitter buffer. Both numbers are logged on
every cut; this prints the difference rather than leaving it assumed.

Nothing gates on either number (architecture 7.4). This is a measurement of how
wrong the agent-side figure would have been if anything did.

    conda run -n ML python scripts/gate4_probe_delta.py runs/<stamp>/events.jsonl
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wetlab import events  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("log", type=Path, nargs="?", default=None, help="an events.jsonl")
    ap.add_argument("--out", type=Path, default=Path("runs/gates/gate4"))
    args = ap.parse_args()

    log = args.log
    if log is None:
        runs = sorted(Path("runs").glob("*/events.jsonl"))
        if not runs:
            print("no runs under runs/; pass a path", file=sys.stderr)
            return 2
        log = runs[-1]

    cuts = [row for row in events.read(log) if row["type"] == "cut"]
    if not cuts:
        print(f"{log}: no cuts recorded")
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    csv_path = args.out / "deltas.csv"
    with csv_path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "context_id",
                "step_id",
                "agent_s",
                "listener_s",
                "delta_s",
                "report_age_ms",
                "stale_dropped",
                "after_cut",
            ]
        )
        for row in cuts:
            writer.writerow(
                [
                    row.get("context_id"),
                    row.get("step_id"),
                    row.get("agent_playback_position"),
                    row.get("probe_rendered_s"),
                    row.get("delta_s"),
                    row.get("probe_age_ms"),
                    row.get("stale_dropped"),
                    row.get("after_cut"),
                ]
            )

    print(f"{log}: {len(cuts)} cuts, {csv_path}")
    for row in cuts:
        delta = row.get("delta_s")
        shown = f"{delta:+.3f} s" if delta is not None else "no listener report"
        flag = "  after a cut" if row.get("after_cut") else ""
        print(
            f"  {row.get('context_id'):8s} {row.get('step_id'):6s} "
            f"agent {row.get('agent_playback_position', 0.0):6.3f} s   {shown:>22s}   "
            f"report age {row.get('probe_age_ms', float('inf')):7.1f} ms   "
            f"stale dropped {row.get('stale_dropped', 0)}{flag}"
        )

    # Only a cut on an utterance that started from silence compares cleanly. The
    # listener's counter is one monotonic sample total for the whole track, so an
    # utterance that began while the previous one was still draining has that
    # drainage inside its own baseline. Reporting the two together would average
    # a measurement with an artefact.
    clean = [r for r in cuts if r.get("delta_s") is not None and not r.get("after_cut")]
    dirty = [r for r in cuts if r.get("delta_s") is not None and r.get("after_cut")]
    ages = [r["probe_age_ms"] for r in cuts if r.get("probe_age_ms") not in (None, math.inf)]
    unprobed = len([r for r in cuts if r.get("delta_s") is None])

    print()
    if clean:
        deltas = [r["delta_s"] for r in clean]
        print(
            f"  clean cuts (n={len(clean)}): delta median {statistics.median(deltas):+.3f} s, "
            f"range {min(deltas):+.3f} to {max(deltas):+.3f} s"
        )
    else:
        print("  no clean cuts: every cut here followed another one, so no delta is usable")
    if dirty:
        print(
            f"  cuts following a cut (n={len(dirty)}): not comparable, the listener's "
            f"counter still held the previous utterance"
        )
    if ages:
        print(f"  report age median {statistics.median(ages):.1f} ms, max {max(ages):.1f} ms")
    if unprobed:
        print(
            f"  {unprobed} cut(s) had no listener report. Expected for a cut inside the "
            f"first poll interval; the evidence is missing, the decision is not."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
