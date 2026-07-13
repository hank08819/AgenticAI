"""
RealModel adapter for the P4 harness — provider-agnostic, OpenAI-compatible.

Implements the same contract as SyntheticModel in p4_harness.py:
    decide(case, depth, elapsed_days, rng) -> ModelResult(label, rationale, endpoint_version)

Supports TWO API styles, auto-selected (or forced via P4_PROVIDER):
  - OpenAI-compatible  /chat/completions   (OpenAI, vLLM, Ollama, LM Studio, ...)
  - Anthropic native   /v1/messages        (api.anthropic.com)

Configured via env:
    P4_API_BASE   e.g. https://api.openai.com/v1            (openai-compatible)
                       https://api.anthropic.com/v1          (anthropic native)
                       http://localhost:11434/v1             (ollama)
    P4_API_KEY    your key (do NOT hardcode; export it in the shell)
    P4_MODEL      model id string (also recorded as endpoint_version)
                  anthropic e.g. claude-haiku-4-5-20251001
                  openai    e.g. gpt-4o-mini
    P4_PROVIDER   optional: "anthropic" | "openai"; if unset, inferred from
                  P4_API_BASE (contains "anthropic" -> anthropic, else openai)
    ANTHROPIC_VERSION  optional, default "2023-06-01"

NO KEY IS STORED HERE. Nothing runs until you export the env vars.

The model is asked to return STRICT JSON {"label": <enum>, "rationale": <str>}.
Decoding is pinned (temperature=0, seed if supported) so that any observed
non-determinism is the endpoint's, not ours — exactly what P4 measures.
"""
from __future__ import annotations
import os, json, re, time
import urllib.request, urllib.error
from p4_harness import ModelResult, LABELS, Case   # reuse the harness contract


def _provider():
    p = os.environ.get("P4_PROVIDER")
    if p:
        return p.lower()
    return "anthropic" if "anthropic" in os.environ.get("P4_API_BASE", "") \
        else "openai"


def _post_openai(system, user, model, temperature=0.0, seed=42, timeout=60):
    base = os.environ["P4_API_BASE"].rstrip("/")
    key  = os.environ["P4_API_KEY"]
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": temperature,
        "seed": seed,            # honored by some providers; harmless otherwise
        "max_tokens": 400,
    }
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        resp = json.loads(r.read().decode())
    return resp["choices"][0]["message"]["content"], resp.get("model", model)


def _post_anthropic(system, user, model, temperature=0.0, timeout=60):
    base = os.environ["P4_API_BASE"].rstrip("/")
    key  = os.environ["P4_API_KEY"]
    ver  = os.environ.get("ANTHROPIC_VERSION", "2023-06-01")
    body = {
        "model": model,
        "max_tokens": 400,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    # Newer models (e.g. Opus 4.7/4.8) DEPRECATE `temperature` -> 400 error.
    # Omit it when requested so one decoding setting works across all versions.
    if not os.environ.get("P4_OMIT_TEMPERATURE"):
        body["temperature"] = temperature
    req = urllib.request.Request(
        f"{base}/messages",
        data=json.dumps(body).encode(),
        headers={"x-api-key": key, "anthropic-version": ver,
                 "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        resp = json.loads(r.read().decode())
    # content is a list of blocks; concatenate text blocks
    text = "".join(b.get("text", "") for b in resp.get("content", [])
                   if b.get("type") == "text")
    return text, resp.get("model", model)


def _generate(system, user, model):
    if _provider() == "anthropic":
        return _post_anthropic(system, user, model)
    return _post_openai(system, user, model)


def _extract_json(text):
    """Pull the first {...} JSON object out of a possibly chatty response."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


class RealModel:
    """Live OpenAI-compatible endpoint. Retries transient 5xx up to 3x."""
    def __init__(self, name=None):
        self.model = os.environ.get("P4_MODEL", "gpt-4o-mini")
        self.name = name or self.model

    def decide(self, case: Case, depth: str, elapsed_days: float, rng) -> ModelResult:
        labels = LABELS[case.family]
        system = (
            "You are a financial decision agent. Based ONLY on the data provided, "
            "choose exactly ONE label from the allowed set. You MUST decide even "
            "under uncertainty; do NOT ask for more information and do NOT refuse. "
            'Output ONLY a JSON object on a single line, no preamble, no code '
            'fences: {"label": "<one allowed label>", "rationale": "<one sentence>"}.'
        )
        user = (
            f"FAMILY: {case.family}\n"
            f"ALLOWED LABELS: {labels}\n"
            f"PROMPT: {case.prompt}\n"
            f"TOOL OUTPUT (frozen): {case.tool_payload}\n"
        )
        # depth == 'multi' could chain analyze->risk->decide; kept single here.
        last_err = None
        for attempt in range(3):
            try:
                text, ver = _generate(system, user, self.model)
                obj  = _extract_json(text) or {}
                label = str(obj.get("label", "")).strip().lower()
                if label not in labels:
                    label = "PARSE_FAIL"           # recorded, not dropped (per prereg)
                rationale = str(obj.get("rationale", ""))[:300]
                return ModelResult(label=label, rationale=rationale,
                                   endpoint_version=ver)
            except urllib.error.HTTPError as e:
                last_err = e
                if 500 <= e.code < 600:
                    time.sleep(2 * (attempt + 1)); continue
                raise
            except Exception as e:                 # noqa
                last_err = e
                time.sleep(2 * (attempt + 1))
        return ModelResult(label="TRANSPORT_FAIL",
                           rationale=f"{type(last_err).__name__}: {last_err}",
                           endpoint_version=self.model)
