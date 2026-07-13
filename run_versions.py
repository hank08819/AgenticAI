"""
Cross-version drift study (real, calendar-dated proxy for the auditability
half-life). Runs the same frozen cases across successive dated versions of ONE
model line, at temperature 0, and measures how often each later version still
returns the BASELINE verdict. Fidelity vs elapsed release-time -> half-life.

Honest scope: successive versions also improve capability, so this measures
release-timeline drift (capability + drift combined), within one model line.
That is precisely the auditability concern: re-running "the same" agent months
later, on the then-current model, yields different verdicts.

Usage:
    export P4_API_BASE=https://api.anthropic.com/v1 P4_API_KEY=sk-ant-...
    python run_versions.py --k 3
"""
import argparse, json, os, collections, math
from datetime import date
from p4_harness import build_frozen_cases, fit_half_life
import real_model as rm

# one model line, with real release dates (baseline first)
VERSIONS = [
    ("claude-opus-4-5-20251101", date(2025,11,24)),
    ("claude-opus-4-6",          date(2026, 2, 4)),
    ("claude-opus-4-7",          date(2026, 4,14)),
    ("claude-opus-4-8",          date(2026, 5,28)),
]

def modal_verdicts(model, cases, k):
    os.environ["P4_MODEL"] = model
    m = rm.RealModel(model)
    out = {}
    for c in cases:
        labs = [m.decide(c, "single", 0.0, None).label for _ in range(k)]
        out[c.id] = collections.Counter(labs).most_common(1)[0][0]
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--cases-per-family", type=int, default=8)
    ap.add_argument("--out", default="versions_runs.jsonl"); a = ap.parse_args()

    os.environ["P4_OMIT_TEMPERATURE"] = "1"   # consistent default decoding across versions
    cases = build_frozen_cases(a.cases_per_family)
    base_date = VERSIONS[0][1]
    verdicts = {}
    rows = []
    for model, d in VERSIONS:
        print(f"[run] {model} ({d})  ...")
        verdicts[model] = modal_verdicts(model, cases, a.k)
        for cid, v in verdicts[model].items():
            rows.append(dict(model=model, release=str(d), case=cid, verdict=v))
    with open(a.out, "w") as fh:
        for r in rows: fh.write(json.dumps(r) + "\n")

    base = verdicts[VERSIONS[0][0]]
    print("\n=== Fidelity to baseline verdict vs release date ===")
    ts, fs = [], []
    for model, d in VERSIONS:
        same = sum(verdicts[model][c.id] == base[c.id] for c in cases)
        fid = same / len(cases); elapsed = (d - base_date).days
        ts.append(elapsed); fs.append(fid)
        print(f"  {model:28s} +{elapsed:4d}d  fidelity-to-baseline = {fid:.3f} "
              f"({same}/{len(cases)})")
    lam, hl, A, c = fit_half_life(ts, fs)
    hl_s = "inf" if hl == float("inf") else f"{hl:.0f} days"
    print(f"\n  fit f(t)=a*exp(-lambda t)+c : lambda={lam:.4f}/day, "
          f"a={A:.2f}, c={c:.2f}")
    print(f"  >>> AUDITABILITY HALF-LIFE (verdict) = {hl_s}")
    print(f"\n[written] {len(rows)} rows -> {a.out}")

if __name__ == "__main__":
    main()
