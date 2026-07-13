# Reproducibility package — *Governing Agentic AI in FinTech*

This folder contains the code, data, and documentation behind the paper's
empirical results (Section on the Verifiability Gap / propositions). It is
self-contained: with Python 3.9+, `matplotlib`, and `numpy`, you can regenerate
every real-data figure from the bundled data **without any API key or network**.

Re-running the live experiments (to collect new data) does require an API key;
that path is documented but optional.

---

## 1. What is here

**Code**
| file | purpose |
|---|---|
| `p4_harness.py` | Core pipeline: frozen decision cases, fidelity metric, decay fit; includes a `SyntheticModel` for offline validation. |
| `real_model.py` | Provider-agnostic adapter (OpenAI-compatible **and** Anthropic-native). Reads the key from an env var; **no key is stored**. |
| `run_wave0.py` | Within-session experiment (H1): K repeats per case at temperature 0. |
| `run_versions.py` | Cross-version drift experiment: same cases across dated releases of one model line. |


**Data (real, used in the paper)**
| file | rows | provenance |
|---|---|---|
| `wave0_local_control_v2.jsonl` | 320 | 32 frozen cases × 10 runs, local `llama3.2:3b` (Ollama), temp 0 |
| `wave0_hosted_anthropic.jsonl` | 320 | same cases, hosted `claude-haiku-4-5-20251001`, temp 0 |
| `versions_runs.jsonl` | 128 | same cases across Opus 4.5→4.8 (dated 2025-11-24 … 2026-05-28) |

**Docs**
| file | purpose |
|---|---|
| `RESULTS_wave0_two_arm.md` | The measured results + honest caveats. |
| `P4_Reproducibility_Pilot.md` | Full experimental protocol. |
| `P4_Preregistration_OSF.md` | OSF-style preregistration template. |

---

## 2. Reproduce the figures (no key, ~seconds)

```bash
pip install -r requirements.txt
python make_figures.py          # writes ./figs/*.pdf and *.png
```
The real-data figures (`fig_p4_twoarm`, `fig_p4_percase`, `fig_p4_crossmodel`,
`fig_versions`) are computed directly from the bundled `.jsonl` files, so their
numbers can be checked against the paper.

Validate the analysis pipeline against a known ground truth (synthetic, offline):
```bash
python p4_harness.py --smoke    # local control stays flat; volatile arm decays
```

---

## 3. Data dictionary

`wave0_*.jsonl` — one JSON object per model execution:
`case`, `family`, `model`, `depth`, `run`, `wave_lag_days`, `label` (the decision),
`rationale`, `endpoint_version`, `ts`.

`versions_runs.jsonl` — one object per (version × case):
`model`, `release` (date), `case`, `verdict` (modal decision over K runs).

The 32 frozen cases are generated deterministically from their ids by
`build_frozen_cases()` in `p4_harness.py` (stimuli hash `696afd1033747a41`), so the
exact inputs are reconstructible from code alone.

---

## 4. Re-run the live experiments (optional; needs a key)

Set a key **in your own shell** (never commit it):
```bash
# Hosted (Anthropic native):
export P4_API_BASE=https://api.anthropic.com/v1
export P4_API_KEY=sk-ant-...            # your key
export P4_MODEL=claude-haiku-4-5-20251001
python run_wave0.py --k 10 --cases-per-family 8 --out wave0_hosted_anthropic.jsonl

# Cross-version drift (Opus line):
python run_versions.py --k 3

# Local control (free; needs Ollama running):
export P4_API_BASE=http://localhost:11434/v1 P4_API_KEY=ollama P4_MODEL=llama3.2:3b
python run_wave0.py --k 10 --cases-per-family 8 --out wave0_local_control_v2.jsonl
```

---

## 5. Honest scope of the empirical claims

- **Within-session (temp 0):** local control reproduces perfectly (fidelity 1.000);
  the hosted model does not (0.997), with one divergence on a borderline credit
  case. Real but small at lag 0.
- **Cross-version drift:** ~9% of verdicts change across Opus 4.5→4.8 over ~6
  months. This bounds *release-timeline* drift (capability improvements + drift
  combined), not silent *same-version* drift; and fidelity does not reach 0.5
  within the window, so **no half-life is estimable** — the code's decay fit is a
  formatting default, not a reported result.
- A separate finding: Opus 4.7/4.8 **deprecated the `temperature` parameter** — an
  API-contract change that itself removes a reproducibility control.
- The `fig_p4_crossmodel` comparison (local vs hosted verdicts) is **exploratory**;
  the two models differ in capability, so it illustrates model-dependence of the
  verdict, not a controlled provider comparison.

These caveats are stated in the paper and in `RESULTS_wave0_two_arm.md`. Integrity
choices: decoding pinned where the API allows it; parse/transport failures recorded
as their own labels, never silently dropped; tools mocked/frozen so only the model
varies.
