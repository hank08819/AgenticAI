# P4 Wave-0 Two-Arm Result (local control vs hosted)

**Date:** 2026-06-29
**Script:** `run_wave0.py` (lag-0, within-session non-determinism / H1)
**Decoding:** temperature = 0, fixed seed where honored
**Frozen stimuli:** 32 realistic financial decision cases (8 per family:
credit, trade, AML, rebalancing); hash **`696afd1033747a41`**
**Repetitions:** 10 per case → 320 executions per arm (640 total)
**Raw data:** `wave0_local_control_v2.jsonl`, `wave0_hosted_anthropic.jsonl`

## Result
| Arm | Model | Mean lag-0 fidelity | Cases w/ disagreement | Failures |
|---|---|---|---|---|
| Local control | `llama3.2:3b` (Ollama) | **1.000** | 0 / 32 | 0 / 320 |
| Hosted | `claude-haiku-4-5-20251001` | **0.997** | 1 / 32 | 0 / 320 |

### The divergence (hosted)
- **Case `credit-05`** — FICO 579, DTI 47%, income $35k, loan $25k, 1 delinquency.
- 10 identical runs, temperature 0 → **deny ×9, refer ×1**.
- A borderline, fair-lending-sensitive credit decision where a deny↔refer flip
  changes the applicant's outcome.

## Interpretation (for the paper)
1. **H1 corroborated, directionally:** even nominally deterministic hosted
   inference is not perfectly reproducible within a session, while the local
   single-stream control is. The contrast is clean (1.000 vs 0.997).
2. **Effect is real but small at lag 0** on simple categorical decisions
   (1/32). This is consistent with the larger reproducibility threat living in
   endpoint **drift over time** (H2/H3), not in single-session sampling.
3. **Localization → supports P7:** non-determinism appears on the shared hosted
   endpoint, not on local execution; irreproducibility is a property of shared
   hosted infrastructure, expected to correlate across institutions on the same
   provider.
4. **Qualitatively pointed:** the single flip landed on the most borderline,
   highest-stakes credit case — exactly where verifiability and fair-lending
   accountability matter most.

## Exploratory (NOT a paper claim): cross-model decision agreement
The local and hosted models reached the **same decision on only 15/32 cases
(47%)** — including opposite trade calls (local *sell* vs hosted *buy*) and
credit *approve* vs *refer*. See `figs/fig_p4_crossmodel.pdf`.
**Caveat — do not use as a finding:** this compares a small 3B local model to a
frontier hosted model, so the disagreement is dominated by **capability**, not
by provider or reproducibility. It is kept only as exploratory color. A valid
cross-provider comparison would hold capability roughly constant (e.g., two
frontier models of similar tier).

## Honest limits
- Small lag-0 effect; not a dramatic within-session contrast.
- The headline number (auditability half-life) requires the longitudinal
  H2/H3 waves (real elapsed time) — not yet run.
- Single hosted model, single task family set; broaden before strong claims.

## Reproducing
Local:
```bash
export P4_API_BASE=http://localhost:11434/v1 P4_API_KEY=ollama P4_MODEL=llama3.2:3b
python run_wave0.py --k 10 --cases-per-family 8 --out wave0_local_control_v2.jsonl
```
Hosted (Anthropic native; use YOUR key locally):
```bash
export P4_API_BASE=https://api.anthropic.com/v1 P4_API_KEY=sk-ant-... \
       P4_MODEL=claude-haiku-4-5-20251001
python run_wave0.py --k 10 --cases-per-family 8 --out wave0_hosted_anthropic.jsonl
```

## Cross-version drift (REAL, dated) — versions_runs.jsonl
Same 32 frozen cases across one frontier line's dated releases (Opus 4.5→4.8,
2025-11-24 to 2026-05-28), K=3, default decoding:
| version | +days | verdict fidelity to baseline |
|---|---|---|
| opus-4-5 | 0 | 1.000 |
| opus-4-6 | 72 | 1.000 |
| opus-4-7 | 141 | 0.906 (29/32) |
| opus-4-8 | 185 | 0.906 (29/32) |
~9% of verdicts drift over ~6 months (trade buy→hold; one rebalance→hold).
NOTE: fidelity never reaches 0.5 → NO half-life estimable (the fitted 693d is a
grid artifact, NOT reported). Bounds release-timeline drift (capability + drift),
not silent same-version drift.
FINDING: Opus 4.7/4.8 DEPRECATED the `temperature` parameter — API-contract drift
that removes a reproducibility control.
