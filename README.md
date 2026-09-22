# Chimera-AG v0.12 — Measured Real-Model Product

**A real, self-hosted AI product with three live execution modes.** Single-model chat, Chimera’s existing multi-agent Council using actual Ollama inference, and an explicitly enabled local Agency Agents × jcode coding workflow all connect to the same browser product. The default Docker installation runs local chat and Council; jcode file execution stays disabled unless configured on an authorized local host. See [the complete live integration guide](docs/LIVE_COUNCIL_PRODUCT.md).

## Start the product (real model; no API keys)

Requires Docker Engine and Docker Compose v2:

```bash
git clone https://github.com/aixaria0/Chimera-AG.git
cd Chimera-AG
docker compose up -d --build
```

The first launch automatically downloads the real default `qwen2.5:1.5b` Ollama model. Open **http://127.0.0.1:8080** on that machine. Choose **Agent council** for real worker → synthesis → verifier model calls. To use a larger model, set `CHIMERA_MODEL` as described in [the product runbook](docs/REAL_LOCAL_PRODUCT.md).

The GitHub Actions [real-model workflow](.github/workflows/real-model.yml) downloads actual model weights, exercises genuine Council inference, and compares Council and single-model answers on the same fixed tasks. The [real-jcode workflow](.github/workflows/real-jcode.yml) installs the actual upstream coding agent and tests its connection to Ollama. See [v0.12 validation and limitations](docs/REAL_VALIDATION_V12.md) for actual evidence, a measured 0/2 smoke-benchmark result for both arms, and the opt-in bounded coding compatibility adapter. For an always-on service, operate Docker Compose on your own machine/server.

---

Chimera is an experimental multi-model coordination system for local and cloud AI endpoints. It can discover model catalogs, register large heterogeneous agent pools, fan tasks out across workers, synthesize competing answers, and independently verify the synthesis.

**It is an orchestration prototype, not evidence of AGI, autonomous self-improvement, or guaranteed correctness.**

## Install and test

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e '.[test]'
pytest -q
```

## Four operating modes

### 1. Offline v0.1 benchmark
`chimera` keeps the original deterministic coordination experiment for reproducible CI.

### 2. Free-first pool
`chimera-free-pool` discovers already-installed Ollama/vLLM models plus conservatively identified zero-priced OpenRouter entries. See `docs/FREE_POOL.md`.

### 3. Maximum authorized pool
`chimera-power-pool` discovers Ollama, vLLM, OpenRouter, Hugging Face Inference Providers, NVIDIA, Groq and Cerebras. With default zero registration limits it does not impose an arbitrary model-count cap. Cloud entries only activate when `--activate-cloud` is explicit and a credential exists in the runtime environment.

`chimera-council` uses all enabled workers by default, sends their responses to a dedicated synthesizer, and then requests independent verifier decisions. OpenRouter models are discovered using the provider's live intelligence ordering when available. See `docs/MAX_POWER.md`.

### 4. Measured specialist routing

`chimera-route` selects workers using domain-specific training observations and preserves independent synthesis/verification roles. It defaults to a zero-network dry run. `chimera-benchmark` compares candidate and baseline on identical held-out tasks with a no-leakage check and human-reviewed promotion gate. See `docs/EVIDENCE_ROUTING.md`.

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

## Agency Agents × jcode coding workflows

`chimera-agency` discovers specialist roles from a trusted local checkout of [Agency Agents](https://github.com/msitarzewski/agency-agents) and can invoke an independently installed [jcode](https://github.com/1jehuang/jcode) coding runtime in an explicit local workspace. It defaults to dry-run; `--execute` is required to run jcode. See `docs/JCODE_AGENCY_INTEGRATION.md` for setup, attribution and security.

## End-to-end coding workflow

`chimera-code` composes Agency Agents planning, implementation and review roles using an installed jcode runtime, then executes a fixed Python or Rust test suite. It starts in dry-run mode and requires an explicitly clean local worktree and `--execute` before model calls or file modifications. The result is **a candidate for human review**, not an auto-committed or deployed patch. See `docs/VERIFIED_CODING_WORKFLOW.md` for setup and failure gates.
