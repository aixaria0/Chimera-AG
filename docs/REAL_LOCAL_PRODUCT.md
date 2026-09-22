# Chimera Local — real model, real machine, usable web app

This is a **self-hosted application** in the existing Chimera-AG repository. It serves a browser chat interface and sends requests to **actual Ollama model weights** running on the same physical machine or an explicitly configured Ollama host. Answers are never fabricated by the web app. It does not require API keys, simulated agents, or an external hosted LLM account.

The default local model is `qwen2.5:1.5b` (a real, compact language model suitable for a CPU-only first run). It is **not** advertised as the strongest available model. If your machine has sufficient RAM/VRAM, replace it with a larger installed Ollama model using `CHIMERA_MODEL`.

## Start on your computer or dedicated server

Requirements: Docker Engine and Docker Compose v2, enough available disk space for model weights, and CPU/RAM or GPU appropriate for your chosen model.

```bash
git clone https://github.com/aixaria0/Chimera-AG.git
cd Chimera-AG
docker compose up -d --build
```

Compose's `model-init` service downloads the selected model weights automatically before starting Chimera. The first startup needs an internet connection and free disk space; later startups reuse the Ollama Docker volume.\n\nOpen **http://127.0.0.1:8080** on that same machine. The browser status display queries the live model registry. Before the model is downloaded, it reports that the model is missing rather than pretending to respond.

To use a different model:

```bash
CHIMERA_MODEL=qwen2.5:7b docker compose up -d --build
```

You can see the actual installed weights with `docker compose exec -T ollama ollama list`. The Ollama model directory lives in the persistent Docker volume `ollama_models`, so normal container restarts do not discard your downloaded weights.

On a Linux NVIDIA GPU host, configure Docker's NVIDIA Container Toolkit and appropriate GPU device access for the `ollama` service. The checked-in Compose file defaults to CPU operation and does not assume you own a GPU.

## Validate real inference yourself

```bash
CHIMERA_MODEL=qwen2.5:1.5b python scripts/real_model_smoke.py
```

The smoke test calls the deployed app's health and chat endpoints and **requires a genuine nonempty model response with a positive generated-token count**. It does not accept hardcoded or canned example text.

GitHub Actions also runs this same application and a real, small `smollm2:135m` Ollama model on an actual GitHub-hosted CPU runner. See the `Real local model inference` workflow. That GitHub runner is an **ephemeral test machine**, not a continuously hosted deployment; to keep your application online, run Compose on a machine you own or lease and operate.

## Product scope

The UI supports conversational history, real model replies, status and model identification, reset, mobile layout, bounded request sizes, and an explicit error when the inference engine is unavailable. It uses only Python's standard library and locally served HTML/CSS/JS.

The Docker Compose app binds **only to 127.0.0.1:8080** and keeps Ollama off publicly published ports. There is no public authentication layer. Do **not** expose this application directly to the internet or bind it to all network interfaces; use an authenticated HTTPS reverse proxy and access controls before offering multi-user hosting. The browser does not send requests to a third-party hosted AI API. Chat history is held in memory in the browser tab and is cleared when the page is closed/reloaded; the product does not offer persistent accounts.

This release provides **real single-model inference**. Existing Chimera council/routing/jcode modules remain separately available but have not been wired into the browser product or tested with live models in this release. More models or agents do not automatically make an application more intelligent.

## Upstream and data

- Ollama: https://ollama.com
- CPU smoke model: https://ollama.com/library/smollm2:135m
- Default local model: https://ollama.com/library/qwen2.5:1.5b

Use model licenses and hardware you are entitled to operate. Previously disclosed credentials should be rotated; none are needed for this local product.
