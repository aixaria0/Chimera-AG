# Chimera free-first agent pool

Chimera can register many agent **slots** from models already hosted on your own local inference services and from model IDs explicitly reported as zero-priced by OpenRouter's catalog. This does not install model weights, provision cloud machines, grant subscriptions, or create unlimited free tokens.

## Security first

If an API token was posted in chat, a repository, a log, or a screenshot, **revoke it and create a replacement** at the provider's security/settings page. Do not use old exposed keys for Chimera. Do not put token values in GitHub files, issues, pull requests, comments, or model prompts. Store new credentials in the private environment of the machine running the agent pool (or an approved secret manager). GitHub Secrets are for workflows, not a replacement for securing your own runtime.

Only model IDs and endpoint URLs go into agent manifests. Generated `configs/agents.json` and `configs/free_agents.json` must stay untracked and private.

## Run local free agents

Install and launch local open-weight models using an authorized local inference engine. For Ollama, use its official download instructions and start the service yourself; the default loopback URL is `http://127.0.0.1:11434`. For vLLM, run its own OpenAI-compatible endpoint on `127.0.0.1:8000` with hardware adequate for the model. This repository never silently downloads weights or starts GPU servers.

```bash
python -m pip install -e '.[test]'
chimera-free-pool --providers ollama vllm --max-per-provider 128 --max-total 256
```

The command registers discovered locally installed models and enables them by default. Where at least two distinct enabled models exist, one is reserved as a verifier. Registration is not evidence that your machine can run them simultaneously. Select a manageable worker subset in the generated manifest if RAM/VRAM is limited.

## Discover zero-priced cloud slots

After **rotating any exposed token**, set the newly issued credential in your shell without committing it, then:

```bash
chimera-free-pool --providers ollama openrouter --max-per-provider 128 --max-total 256
```

OpenRouter cloud entries are **disabled by default**. The scanner requires an advertised `:free` model ID with exactly zero prompt and completion per-token prices. This conservative filter does not guarantee quota, continued availability, account access, full zero cost (other charges may exist), or that the provider offers an open-source model. Inspect licensing and service terms per model.

To opt in to cloud inference with a newly issued private key, choose `--enable-cloud` when generating a fresh manifest, or deliberately set `enabled: true` for selected entries in your private file. Check provider account quotas and usage before making calls. The fabric's `--max-requests` caps attempted calls **per invocation**, not across sessions or monetary spend.

```bash
chimera-fabric --config configs/free_agents.json --task 'Classify a fictional support request' --workers 4 --max-requests 8
```

With a single model/no distinct verifier, the fabric will return `unverified` rather than claim consensus. Majority agreement between agents does not prove factual correctness.

## Other providers

The existing discovery catalog supports NVIDIA and manual OpenAI-compatible model entries. Hugging Face Inference Providers is also compatible with OpenAI-style chat-completions requests using `https://router.huggingface.co/v1/chat/completions`, `HF_TOKEN`, and a model ID supported by that endpoint. **Hugging Face monthly free credits are small and limited, not unlimited free inference.** NVIDIA hosted inference may involve quotas, pricing, and entitlement, so neither service is automatically enrolled in the *zero-price* catalog. Add those providers manually only after reviewing current access and pricing.

## Scaling principles

The generated pool can contain up to 1024 registered slots, with up to 512 discovered per provider when limits are configured accordingly. The current runtime still limits concurrent workers to 32 and attempted requests per run to its configured cap. Agent slots are not actual provisioned compute, and 100 copies of one model are not 100 independent intelligences.

This is a prototype: it has no global monthly spend guard, weighted routing, checkpointed tasks, provider-specific quota management, distributed scheduling, scientific truth oracle, or automatic model deployment. Do not run untrusted tasks or send secrets to cloud models. No sandbox escape, unauthorized infrastructure access, free-tier evasion, or provider rate-limit bypass is part of Chimera.
