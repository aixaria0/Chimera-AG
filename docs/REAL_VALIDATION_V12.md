# Chimera v0.12: a real product with measured model and coding workflows

This release prioritizes a **running product and actual model weights** over agent-count claims. Three different levels of evidence must not be conflated:

**Real inference:** GitHub Actions runs the Chimera Docker application and a downloaded Ollama model, verifies real generated token counts, and exercises the single-model and four-stage Council paths. The local application remains self-hosted on a machine the operator controls.

**Real comparative measurement:** `chimera-live-benchmark` measures the *same held-out questions* through a single model and through Chimera's Council. It reports exact-match counts, abstentions, response times and actual generated token counts for each path. It does not mistake prompt agreement for an independent source of truth; a tiny arithmetic smoke suite is a wiring check, not a general intelligence benchmark. The real `smollm2:135m` CPU smoke run on September 22, 2026 returned **0/2 exact matches in both arms**, with **2/2 Council abstentions**. This is not a win for the Council or the individual model. See [that reproducible run](https://github.com/aixaria0/Chimera-AG/actions/runs/35760721715).

**Real jcode inference:** The official upstream jcode binary was installed on a GitHub-hosted Linux machine, configured with a local Ollama-compatible profile and the downloaded `qwen2.5-coder:1.5b` model, and genuinely generated a coding-agent answer. See [the successful binary-to-model smoke](https://github.com/aixaria0/Chimera-AG/actions/runs/35760840778). That simple model cannot be assumed to operate jcode's native tools correctly.

## Run the measured benchmark on your actual Ollama machine

```bash
python -m pip install -e '.[test]'
ollama pull qwen2.5:1.5b
chimera-live-benchmark \
  --suite benchmarks/live_arithmetic_smoke.json \
  --model qwen2.5:1.5b \
  --output experiments/local-real-benchmark.json --execute
```

The real Ollama server must be running at `127.0.0.1:11434` or pass `--ollama-host`. Do not use the tiny smoke suite to choose a production model. Build your own independently labeled, held-out task set with enough samples, diverse domains, and repeated runs. This benchmark does not measure billed cloud cost, independent correctness beyond the reference labels, or confidence intervals.

To run inside the standard Docker product instead of an Ollama host install:

```bash
docker compose exec -T chimera python -m chimera.live_benchmark \
  --suite benchmarks/live_arithmetic_smoke.json \
  --model qwen2.5:1.5b \
  --ollama-host http://ollama:11434 \
  --output /tmp/chimera-real-benchmark.json --execute
docker compose cp chimera:/tmp/chimera-real-benchmark.json \
  ./experiments/chimera-real-benchmark.json
```

## jcode's small-model tool-call compatibility

A genuine `qwen2.5-coder:1.5b` jcode session may answer with a JSON file-writing instruction **as text rather than invoking the native write tool**. This is a real model output, but it has not edited a real file. Chimera must **not** falsely report it as successful code execution.

For an operator-authorized development worktree only, the real coding command has an optional constrained adapter: pass an exact `--declarative-write-path` to allow Chimera to create **one new file of that precise name** when the real model outputs a structured `write` intent. The adapter does not execute arbitrary shell, change tracked files, overwrite existing files, traverse outside the workspace, or commit or deploy. The file must be at most 4 KiB and have one of the supported text/source suffixes. The existing fixed test suite must then pass. A model reviewer that merely outputs another write instruction is marked **inconclusive**, even if tests pass.

Example on a separate trusted clean Git worktree with jcode installed and Agency Agents checked out:

```bash
chimera-code --agency-checkout /path/to/agency-agents \
  --workspace /path/to/clean-task-repository \
  --task 'Create ANSWER.txt with the requested one-line content' \
  --declarative-write-path ANSWER.txt --test-suite pytest --execute
```

The existing browser coding mode remains disabled in the default Docker product. On an explicitly operator-configured **loopback-only** host, the optional environment variable `CHIMERA_CODE_WRITE_PATHS=ANSWER.txt` allowlists this exact new-file compatibility behavior. Never enable it in an exposed, multi-user, sensitive or untrusted worktree. Models, prompts, repository tests and jcode's own tools can still execute code; a path allowlist is not an OS sandbox.

Actual file creation plus passing tests demonstrates task-specific execution; it does **not** demonstrate a generally competent coding model, meaningful independent model review, or safe unattended deployment. The operator must inspect the resulting diff and any inconclusive review before approving or committing it.

## Upstream credits and access

[1jehuang/jcode](https://github.com/1jehuang/jcode) is used as the real independent coding-agent executable; [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents) supplies specialist role definitions. Keep their upstream MIT licenses with redistributions. No previously shared credentials are used by these local-model tests. Rotate any credentials disclosed in a conversation and provide new ones only through private provider configuration, never through source code.
