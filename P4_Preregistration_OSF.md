# Pre-Registration — Reproducibility Shelf Life of Agentic AI Decisions (P4)

*OSF-style preregistration. Complete every field, then register (timestamp) on
OSF — or commit-and-tag in a public repo — **before** baseline data collection.
Leave no field blank; write "N/A" with a reason where a field does not apply.*

- **Title:** Measuring the Reproducibility Shelf Life of Agentic AI Decisions in Financial Tasks
- **Authors:** Henry Han (Baylor University); [RA/co-authors]
- **Corresponding author:** Henry_Han@baylor.edu
- **Registration date:** __________ (must precede baseline `t0`)
- **Linked paper:** "The Verifiability Gap: Governing Agentic AI in Financial Services," Proposition P4.
- **Frozen-stimuli commit hash / tag:** __________ (record at registration)

---

## A. Study Information

### A1. Description
Audit and supervisory regimes (e.g., SR 11-7 model validation, EU AI Act
record-keeping, FINRA reasoning-chain reconstruction) assume an AI decision can be
re-executed or reconstructed after the fact. We test whether reproduction fidelity
of agentic AI decisions decays with elapsed time between the decision and its
re-execution, and estimate an **auditability half-life**. The only quantity
allowed to vary across waves is elapsed time (and the provider's endpoint state);
all inputs and tools are frozen.

### A2. Hypotheses (directional, pre-specified)
- **H1 (within-session non-determinism).** At lag 0, mean reproduction fidelity
  across cases is **< 1.0** under nominally deterministic settings (temperature 0,
  fixed seed) for at least one hosted endpoint.
- **H2 (monotone decay).** Reproduction fidelity is **non-increasing** in elapsed
  time (negative slope on log-time).
- **H3 (drift discontinuity).** Fidelity exhibits a **downward step** at logged
  endpoint-version changes, beyond smooth decay.
- **H4 (autonomy gradient).** Decay rate λ is **larger** for multi-agent pipelines
  than for single-call decisions.
- **Control expectation.** The locally served open-weights model shows
  **negligible** time decay (isolating endpoint drift from sampling noise).

---

## B. Design Plan

### B1. Study type
Observational longitudinal repeated-measures measurement study. No experimental
manipulation of human participants; the "manipulation" is scheduled elapsed time.

### B2. Blinding
N/A for model execution (automated). Output grading is by deterministic schema
match (no human rater discretion); free-text rationale similarity is computed by a
fixed, pre-specified embedding model and threshold (see D3).

### B3. Design
Within-unit factor: **time lag** at 8 levels — 0 (immediate ×10), +1d, +3d, +1wk,
+2wk, +4wk, +8wk, +12wk. Between-unit factors: **model/provider** (≥3: one
volatile hosted API, one pinned/dated snapshot if available, one local
open-weights control) and **pipeline depth** (single-call; 3–5-step multi-agent).
Unit of analysis: (decision case × model × depth). K = 10 executions per cell per
wave.

### B4. Randomization
Execution order within each wave is randomized (seeded shuffle, seed recorded) to
avoid time-of-day/order confounds. Decision cases are fixed (not sampled per
wave). Case construction is fixed at t0.

---

## C. Sampling Plan

### C1. Existing data
No. All data collected after registration. Frozen stimuli are authored before
registration and hash-recorded; no model outputs exist at registration time.

### C2. Data collection procedures
For each wave, the identical frozen inputs (prompt + mocked tool responses,
committed at t0) are submitted K=10 times per cell. Every call logs: case id,
model, depth, run index, decision label, full response text, rationale,
provider-reported endpoint version, latency, UTC timestamp, wave lag. Tools are
**mocked** (recorded responses) so only the model/endpoint varies. A separate,
clearly-labeled secondary arm with live tools is exploratory only (C5).

### C3. Sample size
Confirmatory pilot: **30 decision cases** spanning 4 families (credit, trade, AML,
rebalance). Full design ≈ 30 × 3 models × 2 depths × 8 waves × 10 runs ≈ 14,400
executions. Minimal pilot sufficient to test H1–H3: 30 × (1 volatile + 1 local) ×
single-call × 6 waves × 10 ≈ 3,600 executions.

### C4. Stop rule
Stop a model's series when its mean fidelity is **< 0.5 for two consecutive
waves**, or at the +12-week wave, whichever comes first. Total study end: 12 weeks
after t0 (opportunistic extension permitted but reported as post-hoc).

### C5. Exploratory data
The live-tool arm and any waves beyond 12 weeks are exploratory and reported
separately from confirmatory tests.

---

## D. Variables

### D1. Measured variables
- **Reproduction fidelity (primary DV):** within a (case, model, depth, wave),
  the agreement rate of the categorical **decision label** across the K=10 runs,
  computed as the proportion of runs matching the cell's modal label.
- **Decision flip (secondary, audit-relevant):** indicator that a cell's modal
  label at wave *t* differs from its modal label at lag 0.
- **Rationale stability (secondary):** mean pairwise cosine similarity of
  rationale embeddings across the K runs (embedding model + version fixed at t0).
- **Endpoint version:** provider-reported model version string per call.

### D2. Indices
- **Auditability half-life:** ln(2)/λ from the fitted decay model (D3), per model.
- **Drift-step magnitude:** fitted level change at version-change dates (H3).

### D3. Pre-specified measurement parameters
- Decoding: temperature = 0, top_p = 1, fixed seed = 42 (where the API honors it).
- Output schema: each case constrains the label to a fixed enum; non-conforming
  outputs are coerced by a pre-registered parser, and parse-failures are recorded
  as a distinct category (not dropped).
- Rationale embedding model + similarity threshold: __________ (fix before t0).

---

## E. Analysis Plan

### E1. Statistical models
- **Decay (H2):** mixed-effects regression of fidelity on log(1+elapsed_days),
  random intercept per case, separate fits per model. Primary test: slope < 0
  (one-sided, α = .05).
- **Half-life:** nonlinear fit f(t)=a·exp(−λt)+c per model; report λ and
  ln(2)/λ with bootstrap 95% CIs over cases (10,000 resamples).
- **H1:** one-sample one-sided test that lag-0 mean fidelity < 1.0; also report
  count of cases with any within-session disagreement.
- **H3:** segmented regression / changepoint at logged version-change dates; test
  the level term < 0.
- **H4:** compare λ_single vs λ_multi via the depth × log-time interaction.

### E2. Transformations
Elapsed time modeled as log(1+days). Fidelity (a proportion) analyzed on the
logit scale with continuity adjustment for 0/1 cells.

### E3. Inference criteria
α = .05, one-sided for directional hypotheses. Confirmatory hypotheses: H1–H4.
Holm correction across the four confirmatory tests.

### E4. Data exclusion
No exclusion of model outputs. Parse-failures retained as their own category.
Excluded only: calls that errored at the transport layer (HTTP 5xx) — these are
retried up to 3×; persistent failures are logged and reported as missingness, not
as decision changes.

### E5. Missing data
Reported per cell. If a provider deprecates an endpoint mid-study, that is treated
as **terminal drift** (fidelity → undefined/0 for audit purposes) and reported as
a substantive finding for H3, not as missing-at-random.

### E6. Exploratory analysis
Live-tool arm; cross-provider comparison; rationale-vs-label divergence (cases
where labels match but rationales drift); cost/latency trends. All clearly labeled
exploratory.

---

## F. Other

- **Code & data availability:** analysis code and de-identified logs released on
  acceptance; frozen-stimuli repo public at registration (hash above).
- **Conflicts of interest:** none / [declare].
- **Deviations:** any deviation from this plan will be documented with date and
  rationale in a deviations log appended to the final report.

---

*Refutation summary (state up front in the paper):* P4 is **refuted** if lag-0
fidelity = 1.0 (no within-session non-determinism) **and** the time slope is not
negative for any hosted model. P4 is **corroborated** by a negative slope yielding
a finite auditability half-life, strengthened if fidelity steps down at logged
version changes.
