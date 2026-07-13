# P4 Pilot Protocol — Measuring the Reproducibility Shelf Life of Agentic Decisions

**Proposition tested (P4).** *Audit regimes that assume ex-post re-execution are
undermined by endpoint drift; the enforceability of such mandates decays with the
time elapsed between action and audit.*

This is the agenda's empirical anchor: it needs **no firm cooperation and no human
subjects**, and it converts the reproducibility deficit from argument into a
measured quantity — an **auditability half-life**. A motivated student or RA can
execute the core pilot in 2–4 weeks of wall-clock time (most of it waiting).

---

## 1. Research question & hypotheses

**RQ.** When an agentic financial decision is re-executed on identical inputs at
increasing time lags, how fast does reproduction fidelity decay, and what is the
half-life?

- **H1 (within-session non-determinism).** Even at lag 0 (immediate re-runs),
  fidelity < 1.0 under nominally deterministic settings (temperature 0, fixed
  seed). *Refuted if fidelity = 1.0.*
- **H2 (monotone decay).** Reproduction fidelity is non-increasing in elapsed
  time. *Refuted if fidelity is flat across the audit window.*
- **H3 (drift discontinuity).** Fidelity drops sharply at logged endpoint-version
  changes, beyond smooth decay. *Refuted if version changes have no effect.*
- **H4 (autonomy gradient, optional).** Multi-step / multi-agent pipelines decay
  faster than single-call decisions (variance compounds across steps).

---

## 2. Design

Longitudinal repeated-measures measurement study. **Unit of analysis:** a
(decision case × model endpoint) pair. **Within-unit factor:** elapsed time lag.
**Between-unit factors:** model/provider; pipeline depth (single-call vs
multi-agent).

### Factors
- **Time lag (primary):** re-execute at lag 0 (10 immediate repeats), then
  +1 day, +3 d, +1 wk, +2 wk, +4 wk, +8 wk, +12 wk. Extend opportunistically.
- **Model/provider (≥3):** at least one frequently-updated hosted API
  (e.g., a flagship commercial endpoint), one pinned/dated snapshot of the same
  family if available, and one open-weights model served locally (the
  near-deterministic control — isolates endpoint drift from sampling noise).
- **Pipeline depth:** (a) single-call decision; (b) 3–5 step multi-agent pipeline
  (e.g., retrieve → analyze → risk-check → decide), to test H4.

### Decision cases (N = 30–50)
Realistic, finance-flavored, with a **structured, gradable output** so agreement
is unambiguous. Each case = fixed prompt + fixed tool outputs (mock/recorded, so
the *only* moving part is the model). Example families:
1. **Credit decision:** applicant profile → {approve, deny, refer} + rationale.
2. **Trade action:** market snapshot → {buy, hold, sell} + size bucket.
3. **AML disposition:** alert → {clear, escalate} + reason code.
4. **Portfolio rebalance:** holdings + targets → ordered action list.

Freeze each case's inputs at t0 in a versioned file. **Mock all tools** (return
recorded responses) so external state is held constant and you measure model
non-determinism + endpoint drift, not data drift. (A second arm can *allow* live
tools to estimate the environmental layer separately — keep it separate.)

---

## 3. Constructs & measures

| Construct | Operationalization |
|---|---|
| **Reproduction fidelity (primary DV)** | For each case at each lag: run K=10 executions. Fidelity = agreement rate of the **decision label** (exact match on the categorical action). Report mean across cases per lag. |
| **Rationale stability (secondary)** | Semantic similarity of free-text rationale across runs (embedding cosine, plus exact-token agreement). Decisions can match while reasoning diverges — both matter for audit. |
| **Decision flip rate** | Fraction of cases whose *majority* label at lag *t* differs from the majority label at t0. The audit-relevant event. |
| **Endpoint version** | Provider-reported model version/string logged at every call; note any deprecation notices. |
| **Auditability half-life** | Time at which mean fidelity crosses 0.5 (or, better, at which decision-flip probability reaches 0.5), estimated from the fitted decay curve. |

Use established agreement metrics for non-deterministic systems (e.g.,
run-agreement / TARr@N-style measures) so results are comparable to the
LLM-non-determinism literature.

---

## 4. Procedure

1. **Freeze cases** (t0): commit prompts + mocked tool responses to a versioned
   repo. Tag the commit.
2. **Baseline (lag 0):** for each (case × model × depth), run K=10 executions at
   temperature 0 / fixed seed. Record label, rationale, full response, latency,
   endpoint version, timestamp.
3. **Scheduled re-runs:** at each lag, re-execute the *identical* frozen inputs,
   K=10 each. **Change nothing but the clock.** Automate via cron; log every call.
4. **Log drift:** at each wave, capture the provider's model-version string and
   any release-note changes.
5. **Stop rule:** continue until mean fidelity < 0.5 for the volatile endpoint or
   12 weeks elapse, whichever first.

Everything is logged to append-only storage (the irony of needing reproducible
logging to study irreproducibility is the point — note it).

---

## 5. Analysis plan

- **Decay curve:** fit fidelity(t) per model with an exponential decay
  `f(t)=a·exp(−λt)+c`; half-life = ln(2)/λ. Report λ and half-life with CIs
  (bootstrap over cases).
- **H1:** one-sample test that lag-0 fidelity < 1 (and report the raw count of
  cases with any within-session disagreement).
- **H2:** test monotonic trend (e.g., mixed-effects model with random intercept
  per case, fixed effect of log-time); negative slope corroborates.
- **H3:** segmented/changepoint regression; test for a level drop at logged
  version-change dates (event-study style — this is the bridge to P7).
- **H4:** compare λ between single-call and multi-agent depth (interaction term).
- **Controls:** the open-weights local model isolates how much decay is sampling
  vs endpoint drift (if local is ~flat and hosted decays, drift dominates).

---

## 6. Power / scale (rough)

30 cases × 3 models × 2 depths × 8 lags × 10 runs ≈ **14,400 executions**.
At single-call cost this is cheap; the multi-agent arm dominates cost and time.
For a minimal pilot to demonstrate the effect: 30 cases × 1 volatile + 1 local
model × single-call × 6 lags × 10 runs ≈ **3,600 calls** — enough to estimate a
half-life and test H1–H3.

---

## 7. Threats to validity & mitigations

- **Confounding data drift with model drift** → mock all tools; freeze inputs.
- **Provider-side caching** masking non-determinism → vary a no-op nonce; confirm
  cache headers; the literature shows temp-0 ≠ deterministic regardless.
- **Label-grading subjectivity** → constrain outputs to a fixed schema/enum;
  grade by exact match; pre-register the schema.
- **Single-provider idiosyncrasy** → ≥3 models across ≥2 providers + 1 local.
- **Generalizability to "real" agents** → the multi-agent depth arm; state the
  pilot's scope honestly (controlled cases, not production trades).

## 8. Pre-registration & deliverables

Pre-register RQ, hypotheses, output schemas, decay model, and stop rule before
baseline. Deliverables: (i) the half-life estimate per model (the headline
number for the paper), (ii) the decay-curve figure, (iii) the version-change
event-study figure (feeds P7), (iv) released code + logs.

## 9. Minimal execution sketch (pseudocode)

```python
# one wave; schedule this at each time lag via cron
for case in frozen_cases:            # fixed prompt + mocked tool responses
    for model in [VOLATILE_API, PINNED_API, LOCAL_OPEN_WEIGHTS]:
        for depth in ["single", "multi_agent"]:
            for k in range(10):
                resp = run_decision(case, model, depth,
                                    temperature=0, seed=42)   # hold all knobs
                log(dict(case=case.id, model=model, depth=depth, run=k,
                         label=resp.label, rationale=resp.rationale,
                         endpoint_version=resp.version,
                         ts=now(), wave_lag=CURRENT_LAG))
# offline: fidelity = agreement of `label` within (case,model,depth,wave)
#          fit f(t)=a*exp(-lambda*t)+c ; half_life = ln(2)/lambda
```

---

**Why this is the right first study.** It is self-contained, falsifiable, and
produces a single citable number (the auditability half-life) that no prior
finance or IS paper reports. A flat curve refutes P4 cleanly; a measured
half-life of, say, weeks would be a striking, quotable result that grounds the
entire Verifiability Gap thesis in evidence rather than argument.
