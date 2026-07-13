"""
P4 reproducibility-shelf-life harness (smoke-testable with a synthetic backend).

Implements the measurement pipeline from P4_Reproducibility_Pilot.md:
  - frozen decision cases (prompt + mocked tool responses)
  - K executions per (case, model, depth) cell per wave
  - logging of label / rationale / endpoint_version / timestamp
  - fidelity = agreement of decision label within a cell
  - exponential decay fit -> auditability half-life

The MODEL BACKEND is pluggable. A SyntheticModel ships here so the entire
pipeline can be exercised end-to-end with ZERO API cost or network. Swap in a
real client (see RealModel stub) once the logic is verified.

Run:
    python p4_harness.py --smoke         # synthetic, all waves, instant
    python p4_harness.py --analyze runs.jsonl
"""
from __future__ import annotations
import argparse, json, math, hashlib, random
from dataclasses import dataclass, asdict, field
from collections import Counter, defaultdict
from datetime import datetime, timezone

# --------------------------------------------------------------------------
# 1. Frozen decision cases. In the real study these live in a versioned repo
#    and the commit hash is recorded at preregistration. Tools are MOCKED so
#    the only moving part is the model/endpoint.
# --------------------------------------------------------------------------
LABELS = {
    "credit":    ["approve", "deny", "refer"],
    "trade":     ["buy", "hold", "sell"],
    "aml":       ["clear", "escalate"],
    "rebalance": ["rebalance", "hold"],
}

@dataclass(frozen=True)
class Case:
    id: str
    family: str
    prompt: str
    tool_payload: str          # recorded/mocked tool output, frozen at t0

def _rng_for(cid: str) -> random.Random:
    """Deterministic RNG per case id, so generated case content is FROZEN."""
    return random.Random(int(hashlib.sha256(cid.encode()).hexdigest(), 16) % (2**32))

def build_frozen_cases(n_per_family: int = 8) -> list[Case]:
    """Realistic, self-contained financial decision cases with concrete numbers,
    generated deterministically from the case id (frozen at t0). Realistic
    content matters: capable models refuse to decide on placeholder inputs, so
    placeholder cases would bias the measurement."""
    cases = []
    for fam in LABELS:
        for i in range(n_per_family):
            cid = f"{fam}-{i:02d}"
            r = _rng_for(cid)
            if fam == "credit":
                fico = r.randint(560, 800); dti = r.randint(15, 55)
                inc = r.choice([35, 48, 62, 85, 120]); loan = r.choice([10, 25, 40, 75])
                delinq = r.randint(0, 3)
                prompt = ("Underwrite this consumer loan. Choose approve, deny, or "
                          "refer (to a human underwriter).")
                payload = (f"FICO={fico}; debt-to-income={dti}%; annual_income=${inc}k; "
                           f"loan_request=${loan}k; delinquencies_24mo={delinq}")
            elif fam == "trade":
                rsi = r.randint(20, 80); vol_pct = r.randint(10, 95)
                ret5 = round(r.uniform(-3, 3), 2)
                prompt = "Choose a trading action: buy, hold, or sell."
                payload = (f"RSI={rsi}; volatility_percentile={vol_pct}; "
                           f"5min_return={ret5}%; position=flat")
            elif fam == "aml":
                amt = r.choice([4.8, 9.5, 25, 80, 150]); cp = r.choice(["low","medium","high"])
                struct = r.choice(["none","possible structuring","rapid pass-through"])
                prompt = "Disposition this transaction alert: clear or escalate."
                payload = (f"amount=${amt}k; counterparty_risk={cp}; "
                           f"pattern={struct}; customer_tenure_mo={r.randint(1,90)}")
            elif fam == "rebalance":
                drift = r.randint(1, 18); cost = round(r.uniform(0.02, 0.6), 2)
                prompt = "Decide portfolio action: rebalance or hold."
                payload = (f"max_asset_drift_from_target={drift}%; "
                           f"est_transaction_cost={cost}%; days_since_last_rebalance={r.randint(5,200)}")
            else:
                prompt = f"[{fam}] decide."; payload = "n/a"
            cases.append(Case(id=cid, family=fam, prompt=prompt, tool_payload=payload))
    return cases

def stimuli_hash(cases: list[Case]) -> str:
    h = hashlib.sha256()
    for c in sorted(cases, key=lambda c: c.id):
        h.update(json.dumps(asdict(c), sort_keys=True).encode())
    return h.hexdigest()[:16]

# --------------------------------------------------------------------------
# 2. Model backends. Contract: decide(case, depth, seed) -> (label, rationale).
# --------------------------------------------------------------------------
@dataclass
class ModelResult:
    label: str
    rationale: str
    endpoint_version: str

class SyntheticModel:
    """Synthetic backend with TUNABLE non-determinism and time drift, so the
    analysis code can be validated against a known ground truth.

      - p_flip:        within-session sampling noise (P4/H1)
      - drift_per_day: probability mass that migrates to a 'drifted' label as
                       elapsed time grows (P4/H2)
      - version_jumps: {day: version_str} step changes in behavior (P4/H3)
      - depth_factor:  multiplies noise for multi-agent depth (P4/H4)
    """
    def __init__(self, name, p_flip=0.05, drift_per_day=0.01,
                 version_jumps=None, depth_factor=2.0, local=False):
        self.name = name
        self.p_flip = 0.0 if local else p_flip
        self.drift_per_day = 0.0 if local else drift_per_day
        self.version_jumps = version_jumps or {}
        self.depth_factor = depth_factor
        self.local = local

    def _version(self, elapsed_days):
        v = "v0"
        for day in sorted(self.version_jumps):
            if elapsed_days >= day:
                v = self.version_jumps[day]
        return v

    def decide(self, case: Case, depth: str, elapsed_days: float,
               rng: random.Random) -> ModelResult:
        labels = LABELS[case.family]
        # deterministic "true" label from the frozen case
        base_idx = int(hashlib.sha256(case.id.encode()).hexdigest(), 16) % len(labels)
        idx = base_idx
        noise = self.p_flip * (self.depth_factor if depth == "multi" else 1.0)
        # endpoint drift grows with elapsed time (capped)
        drift = min(0.9, self.drift_per_day * elapsed_days)
        # version jump adds a discrete kick
        ver = self._version(elapsed_days)
        if ver != "v0":
            drift = min(0.95, drift + 0.25)
        if rng.random() < noise + drift:
            idx = rng.randrange(len(labels))      # flip to some other label
        label = labels[idx]
        return ModelResult(label=label,
                           rationale=f"{case.family} rationale -> {label} ({ver})",
                           endpoint_version=ver)

class RealModel:
    """Stub. Wire to your provider SDK; keep decoding pinned (temp=0, seed)."""
    def __init__(self, name): self.name = name
    def decide(self, case, depth, elapsed_days, rng):  # pragma: no cover
        raise NotImplementedError(
            "Plug a real client here. Log the provider-reported version string.")

# --------------------------------------------------------------------------
# 3. Execution: K runs per (case, model, depth) cell at a given wave lag.
# --------------------------------------------------------------------------
WAVES_DAYS = [0, 1, 3, 7, 14, 28, 56, 84]   # lag schedule (days)
DEPTHS = ["single", "multi"]
K = 10

def run_wave(cases, models, elapsed_days, k=K, seed0=42):
    rows = []
    for model in models:
        for depth in DEPTHS:
            for case in cases:
                for run in range(k):
                    # seeded per (model,case,depth,run,wave) -> reproducible *harness*,
                    # while the model itself may be non-deterministic.
                    seed = hash((model.name, case.id, depth, run, elapsed_days)) & 0xffffffff
                    rng = random.Random(seed0 ^ seed)
                    res = model.decide(case, depth, elapsed_days, rng)
                    rows.append(dict(
                        case=case.id, family=case.family, model=model.name,
                        depth=depth, run=run, wave_lag_days=elapsed_days,
                        label=res.label, rationale=res.rationale,
                        endpoint_version=res.endpoint_version,
                        ts=datetime.now(timezone.utc).isoformat(),
                    ))
    return rows

# --------------------------------------------------------------------------
# 4. Metrics: fidelity per cell; decay fit -> half-life.
# --------------------------------------------------------------------------
def cell_fidelity(rows):
    """Return {(model,depth,wave): mean modal-agreement fidelity over cases}."""
    by_cell = defaultdict(list)          # (model,depth,wave,case) -> [labels]
    for r in rows:
        by_cell[(r["model"], r["depth"], r["wave_lag_days"], r["case"])].append(r["label"])
    agg = defaultdict(list)              # (model,depth,wave) -> [per-case fidelity]
    for (model, depth, wave, _case), labels in by_cell.items():
        c = Counter(labels)
        modal = c.most_common(1)[0][1]
        agg[(model, depth, wave)].append(modal / len(labels))
    return {k: sum(v) / len(v) for k, v in agg.items()}

def fit_half_life(waves, fidelities):
    """Fit f(t)=a*exp(-lambda t)+c via coarse grid search (no SciPy dep).
    Returns (lambda, half_life_days, a, c). half_life = ln 2 / lambda."""
    best = None
    for a in [x / 20 for x in range(2, 21)]:          # 0.1..1.0
        for c in [x / 20 for x in range(0, 11)]:      # 0.0..0.5
            for lam in [x / 1000 for x in range(1, 300)]:  # 0.001..0.3 /day
                err = sum((a * math.exp(-lam * t) + c - f) ** 2
                          for t, f in zip(waves, fidelities))
                if best is None or err < best[0]:
                    best = (err, lam, a, c)
    _, lam, a, c = best
    hl = math.log(2) / lam if lam > 0 else float("inf")
    return lam, hl, a, c

# --------------------------------------------------------------------------
# 5. Drivers.
# --------------------------------------------------------------------------
def smoke():
    cases = build_frozen_cases()
    print(f"[frozen] {len(cases)} cases  stimuli_hash={stimuli_hash(cases)}")
    models = [
        SyntheticModel("volatile-api", p_flip=0.05, drift_per_day=0.012,
                       version_jumps={28: "v1", 56: "v2"}),
        SyntheticModel("pinned-api",   p_flip=0.03, drift_per_day=0.002),
        SyntheticModel("local-open",   local=True),     # control: ~no drift
    ]
    all_rows = []
    for d in WAVES_DAYS:
        all_rows += run_wave(cases, models, d)
    with open("runs.jsonl", "w") as fh:
        for r in all_rows:
            fh.write(json.dumps(r) + "\n")
    print(f"[runs]  {len(all_rows)} executions -> runs.jsonl")
    analyze_rows(all_rows)

def analyze_rows(rows):
    fid = cell_fidelity(rows)
    print("\n[fidelity by model x depth x wave]")
    models = sorted({m for (m, _, _) in fid})
    for model in models:
        print(f"\n  {model}")
        for depth in DEPTHS:
            series = [(w, fid[(model, depth, w)]) for w in WAVES_DAYS
                      if (model, depth, w) in fid]
            waves = [w for w, _ in series]
            vals = [round(v, 3) for _, v in series]
            print(f"    {depth:6s} fidelity@waves {dict(zip(waves, vals))}")
            lam, hl, a, c = fit_half_life([w for w, _ in series],
                                          [v for _, v in series])
            hl_s = "inf" if hl == float("inf") else f"{hl:.1f}d"
            print(f"           lambda={lam:.4f}/day  half_life={hl_s}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true",
                    help="run synthetic end-to-end (no API, no network)")
    ap.add_argument("--analyze", metavar="runs.jsonl",
                    help="re-analyze an existing runs file")
    args = ap.parse_args()
    if args.analyze:
        rows = [json.loads(l) for l in open(args.analyze)]
        analyze_rows(rows)
    else:
        smoke()    # default = smoke test

if __name__ == "__main__":
    main()
