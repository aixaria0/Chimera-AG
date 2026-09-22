# Chimera v0.4 — maximum authorized intelligence profile

This profile removes Chimera's previous artificial 32-worker ceiling and can register every model advertised by configured providers. It does **not** bypass provider quotas, billing, account permissions, model licenses, hardware capacity, network policy, or operating-system isolation.

## Provider surface researched on 2026-09-22

The implementation uses official OpenAI-compatible interfaces where available:

- **OpenRouter** — unified catalog with 500+ models on paid plans and 25+ free models on the free plan. `GET /api/v1/models` supports `sort=intelligence-high-to-low`; Chimera uses that live ordering instead of hard-coding a "best" model. `openrouter/free` routes among free models. OpenRouter Fusion is a compound panel + judge pipeline; when a replacement private key is configured and `--activate-cloud` is explicit, Chimera reserves `openrouter/fusion` as a synthesizer.
- **Hugging Face Inference Providers** — OpenAI-compatible `/v1/chat/completions` and `/v1/models`, with hundreds of models routed across providers. The free account currently receives a small monthly inference credit, not unlimited free inference.
- **NVIDIA NIM / API Catalog** — OpenAI-compatible LLM APIs. NVIDIA's public catalog currently includes many "Free Endpoint" models and its Developer Program supports self-hosting eligible NIMs on owned/authorized GPU infrastructure.
- **GroqCloud** — OpenAI-compatible API and model-list endpoint. Free-tier accounts have model-specific rate limits; free-tier capacity is not equivalent to unlimited usage.
- **Cerebras Inference** — OpenAI-compatible inference plus a public model catalog. Some models have free-tier rate limits; current access and limits must be checked at runtime.
- **Ollama / vLLM** — local OpenAI-compatible endpoints. Chimera can use every model already loaded/advertised by these servers; actual simultaneous capacity is determined by your RAM/VRAM/CPU/GPU resources.

Official references:
- https://openrouter.ai/docs/api/api-reference/models/get-models
- https://openrouter.ai/docs/guides/features/plugins/fusion
- https://openrouter.ai/pricing
- https://huggingface.co/docs/inference-providers/index
- https://huggingface.co/docs/inference-providers/pricing
- https://docs.nvidia.com/nim/large-language-models/latest/api-reference.html
- https://console.groq.com/docs/openai
- https://console.groq.com/docs/rate-limits
- https://inference-docs.cerebras.ai/resources/openai
- https://docs.vllm.ai/en/latest/serving/online_serving/openai_compatible_server/
- https://ollama.com/blog/openai-compatibility

## Maximum profile

After revoking any credential ever exposed in chat/logs and setting newly issued credentials only on the runtime machine:

```bash
export OPENROUTER_API_KEY='NEW_REPLACEMENT_KEY'
export HF_TOKEN='NEW_REPLACEMENT_TOKEN'
# Optional additional providers:
export NVIDIA_API_KEY='...'
export GROQ_API_KEY='...'
export CEREBRAS_API_KEY='...'

chimera-power-pool --activate-cloud --output configs/power_agents.json
chimera-council --config configs/power_agents.json --task 'Your task'
```

With `--max-per-provider 0 --max-total 0` (the defaults), Chimera imposes no registration cap. `chimera-council` with `--workers 0` uses every enabled worker concurrently. The council then sends worker outputs to one synthesizer and asks up to three provider-diverse verifier models for independent approval.

This is intentionally different from firing duplicate copies of one model: the power-pool generator prefers distinct models/providers for verifier roles. Diversity reduces some correlated failures but does not make consensus true.

## Credentials

Never commit credentials. Runtime manifests are ignored by git. Tokens pasted into a chat must be considered exposed and revoked. This repository cannot rotate provider credentials or create account entitlements.

## What "maximum" does and does not mean

Maximum means **no arbitrary Chimera registration/concurrency ceiling** when the operator chooses the all-enabled profile. It does not mean unbounded compute. Python threads, file descriptors, memory, GPUs, upstream RPM/TPM/RPD quotas and account limits still exist. If thousands of agents are enabled against a provider with a low quota, many calls will correctly fail with rate-limit errors.

The code does not attempt sandbox escape, quota evasion, credential harvesting, rate-limit bypass, unauthorized compute, or provider-account circumvention. Those would make the system less reliable and expose the operator to account/security risk.

## Quality path

For OpenRouter, the live catalog is requested in `intelligence-high-to-low` order, which OpenRouter documents as based on the Artificial Analysis intelligence index. This is a useful prior, not proof that the first model is best for your task. Chimera's next research milestone is task-specific routing using held-out benchmarks (coding, agentic, research, long-context, multilingual) and cost/latency telemetry rather than one global ordering.
