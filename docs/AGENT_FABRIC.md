# Chimera agent fabric (experimental)

The agent fabric supports arbitrary manifest entries with a bounded thread pool and a hard attempted-request cap. More agent slots do **not** imply free compute, model independence, or better answers. The original v0.1 CLI remains available as `chimera`.

## Run locally

1. Copy `configs/agents.example.json` to `configs/agents.json`.
2. Enable one or more worker entries and an **independent** verifier entry. Point a local worker to a running local OpenAI-compatible chat endpoint (for example an Ollama instance exposing `/v1/chat/completions`). Set actual model IDs supported by your server.
3. Optionally configure `OPENROUTER_API_KEY` and/or `NVIDIA_API_KEY` in your shell (never paste them into chat or commit them). Enable the relevant cloud entries after confirming provider availability, billing, and model IDs.
4. Run `python -m chimera.fabric_cli --task "Classify a fictional support ticket" --workers 4 --max-requests 8`.

## Safety and correctness limits

- Requests are **opt-in**: example manifest enables no agents. Each invocation has bounded concurrency and maximum requests, but NOT monetary/token budgets. Set external provider spending caps before enabling paid cloud calls.
- A strict worker majority and one separately assigned verifier must agree for a provisional answer. The verifier receives the original task and is not a guaranteed independent ground truth; agreement is not proof of correctness.
- Independent workers may be different models or providers. A shared underlying model/API is a correlated failure risk.
- The status `accepted` means consensus checks passed, NOT validated factual truth. No external commands, automated deployments, model training, or self-modification occur.
- Endpoint URLs and credentials must be configured by a trusted operator. Do not load untrusted agent manifests. Cloud tasks can contain sensitive data: only send content approved for the provider.
- Provider APIs may change, require model-specific fields, and impose rate/usage limits. No live provider integration is asserted by offline CI.
- A next milestone is held-out coordination benchmarks, proper verifier evidence, per-provider rate/cost limits, retries and circuit breakers, audited agent role permissions, and approval-gated evolution.
