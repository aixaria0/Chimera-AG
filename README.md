# Chimera-AG v0.4 — Hybrid Intelligence Council

Chimera is an experimental multi-model coordination system for local and cloud AI endpoints. It can discover model catalogs, register large heterogeneous agent pools, fan tasks out across workers, synthesize competing answers, and independently verify the synthesis.

**It is an orchestration prototype, not evidence of AGI, autonomous self-improvement, or guaranteed correctness.**

## Install and test

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e '.[test]'
pytest -q
```

## Three operating modes

### 1. Offline v0.1 benchmark
`chimera` keeps the original deterministic coordination experiment for reproducible CI.

### 2. Free-first pool
`chimera-free-pool` discovers already-installed Ollama/vLLM models plus conservatively identified zero-priced OpenRouter entries. See `docs/FREE_POOL.md`.

### 3. Maximum authorized pool
`chimera-power-pool` discovers Ollama, vLLM, OpenRouter, Hugging Face Inference Providers, NVIDIA, Groq and Cerebras. With default zero registration limits it does not impose an arbitrary model-count cap. Cloud entries only activate when `--activate-cloud` is explicit and a credential exists in the runtime environment.

`chimera-council` uses all enabled workers by default, sends their responses to a dedicated synthesizer, and then requests independent verifier decisions. OpenRouter models are discovered using the provider's live intelligence ordering when available. See `docs/MAX_POWER.md`.

## Example

```bash
# Use NEW replacement credentials only; never commit secrets.
export OPENROUTER_API_KEY='...'
export HF_TOKEN='...'

chimera-power-pool --activate-cloud --output configs/power_agents.json
chimera-council --config configs/power_agents.json --task 'Analyze this benchmark problem'
```

Generated runtime manifests and environment files are git-ignored.

## Boundaries that remain real

"No Chimera cap" does not remove provider quotas, pricing, licensing, account permissions, hardware limits, network policy, or OS isolation. The project does not bypass rate limits, escape sandboxes, obtain unauthorized compute, or use exposed credentials. More agents can also reduce quality through correlated errors; evaluation remains mandatory.

## Repository map

- `chimera/fabric.py` — OpenAI-compatible endpoint and bounded request accounting.
- `chimera/council.py` — worker fan-out, synthesis, multi-verifier gate.
- `chimera/discovery.py` — provider catalog registry.
- `chimera/free_pool.py` — free-first pool.
- `chimera/power_pool.py` — maximum authorized provider/model registration.
- `benchmarks/` and `tests/` — deterministic checks and unit tests.
- `docs/` — provider, security and operating runbooks.

## Research direction

The next step is not merely increasing agent count. It is task-aware routing: benchmark each model on held-out coding, reasoning, research, multilingual and long-context tasks; learn which small committee gives the highest quality per unit of latency/cost; and promote coordination policies only when they beat a fixed baseline.
