"""
Wave-0 runner — the IMMEDIATELY measurable part of P4 (hypothesis H1).

H1 (within-session non-determinism): even at lag 0, with temperature=0 and a
fixed seed, a hosted model's reproduction fidelity is < 1.0. This needs NO
elapsed time — only minutes and a working endpoint. It is a real, citable result.

Usage:
    export P4_API_BASE="https://api.openai.com/v1"
    export P4_API_KEY="sk-..."
    export P4_MODEL="gpt-4o-mini"
    python run_wave0.py            # default K=10, 8 cases/family
    python run_wave0.py --k 20 --cases-per-family 4

Output:
    wave0_runs.jsonl   one line per execution (full provenance)
    console summary    per-family and overall fidelity, + H1 verdict

For the FULL shelf-life study (H2/H3, the half-life), schedule p4_harness-style
re-runs of the SAME frozen cases at later dates (cron) and analyze with
cell_fidelity + fit_half_life. That part requires real elapsed time.
"""
from __future__ import annotations
import argparse, json
from collections import Counter, defaultdict
from datetime import datetime, timezone

from p4_harness import build_frozen_cases, stimuli_hash
from real_model import RealModel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=10, help="repeats per case")
    ap.add_argument("--cases-per-family", type=int, default=8)
    ap.add_argument("--out", default="wave0_runs.jsonl")
    args = ap.parse_args()

    cases = build_frozen_cases(args.cases_per_family)
    print(f"[frozen] {len(cases)} cases  stimuli_hash={stimuli_hash(cases)}")
    model = RealModel()
    print(f"[model]  {model.name}  (temp=0, seed=42, lag=0)")

    rows, by_case = [], defaultdict(list)
    for ci, case in enumerate(cases, 1):
        for run in range(args.k):
            res = model.decide(case, "single", 0.0, rng=None)
            row = dict(case=case.id, family=case.family, model=model.name,
                       depth="single", run=run, wave_lag_days=0,
                       label=res.label, rationale=res.rationale,
                       endpoint_version=res.endpoint_version,
                       ts=datetime.now(timezone.utc).isoformat())
            rows.append(row); by_case[case.id].append(res.label)
        print(f"  [{ci}/{len(cases)}] {case.id}: {Counter(by_case[case.id])}")

    with open(args.out, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")

    # --- H1 metric: within-session modal-agreement fidelity per case ---
    fams = defaultdict(list)
    any_disagree = 0
    for case in cases:
        labels = by_case[case.id]
        modal = Counter(labels).most_common(1)[0][1]
        fid = modal / len(labels)
        fams[case.family].append(fid)
        if fid < 1.0:
            any_disagree += 1

    print("\n=== H1 result (lag-0 reproduction fidelity) ===")
    allfids = []
    for fam, fids in sorted(fams.items()):
        m = sum(fids) / len(fids); allfids += fids
        print(f"  {fam:10s} mean fidelity = {m:.3f}  (n={len(fids)})")
    overall = sum(allfids) / len(allfids)
    print(f"  {'OVERALL':10s} mean fidelity = {overall:.3f}")
    print(f"  cases with ANY within-session disagreement: "
          f"{any_disagree}/{len(cases)}")
    verdict = ("H1 CORROBORATED (fidelity < 1.0 at lag 0)" if overall < 1.0
               else "H1 not supported here (perfect lag-0 reproduction)")
    print(f"  -> {verdict}")
    print(f"\n[written] {len(rows)} executions -> {args.out}")


if __name__ == "__main__":
    main()
