# Model discovery and activation

Chimera's provider discovery requests each configured `/v1/models` endpoint and registers **advertised IDs**; it does not claim that models are open-source, entitled, free, strong, installed locally, or callable. OpenRouter catalogs mix licenses and pricing. NVIDIA's hosted catalog and local server catalogs may have different coverage and availability.

## Make a local model available

Start an OpenAI-compatible local endpoint (for example, Ollama on loopback) and ensure the model is downloaded according to its own license and hardware requirements. Chimera does not download model weights, provision GPUs, or install hundreds of models automatically.

```bash
python -m chimera.discover_cli --providers ollama --max-agents-per-provider 32 --output configs/agents.json
```

This generates **disabled** entries. Inspect the discovered IDs and configure at least one worker and an independent verifier before enabling your actual workload. If you deliberately want to enable the listed entries during generation, add `--activate`. Generate into a NEW file path, because discovery refuses to overwrite an existing manifest.

## Cloud discovery

Supply credentials as environment variables on the **runtime machine**, not in the public repository, chats, issue comments, logs, or CI:

```bash
export OPENROUTER_API_KEY='...'
export NVIDIA_API_KEY='...'
python -m chimera.discover_cli --providers ollama openrouter nvidia --max-agents-per-provider 32 --output configs/agents.json
```

The CLI uses authenticated catalog discovery for cloud providers; available IDs depend on current provider responses. Inspect the generated manifest and select models you are entitled to use, with permitted licenses, suitable capacity, and acceptable pricing. The local and cloud models require working endpoints. Some provider-model combinations may not support the generic `temperature` or chat-completions interface.

To run a deliberately small experiment after configuration:

```bash
python -m chimera.fabric_cli --config configs/agents.json --task 'Summarize a fictional support request' --workers 4 --max-requests 8
```

Request caps prevent *unbounded calls in one fabric invocation*, not cost overruns across repeated invocations. This project cannot set GitHub Secrets or enable paid provider accounts using its GitHub connector. Set separate provider billing limits. The API keys are never required for offline unit tests.

## Current limitations

Discovery is sequential per provider and bounded at 512 registrations per provider. The runtime fan-out is constrained to 32 concurrent workers and an operator-defined request cap. More registered models need not provide independent verification or better results. There is no automatic provider failover, model benchmarking, pricing inference, distributed scheduler, per-model billing, provider entitlements check, or unattended deployment yet.

Do not mistake majority agreement for factual truth. Human review or externally verifiable checks remain necessary for consequential tasks.
