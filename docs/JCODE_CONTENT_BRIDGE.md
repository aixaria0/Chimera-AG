# Chimera: the jcode Content Bridge

A coding agent that prints a file-write tool call but never invokes its file-writing tool has **not modified the repository**. This happened in real runs with a small Ollama coding model: jcode completed inference, but the coding pipeline correctly stopped on an unchanged Git worktree. Repeating the same tool-use prompt is not a reliable product strategy.

Chimera now offers an **alternative real-model architecture**, called the Content Bridge. It uses the installed upstream [jcode](https://github.com/1jehuang/jcode) binary as the code-generation engine, reads the selected real [Agency Agents](https://github.com/msitarzewski/agency-agents) specialist's role instructions, and leaves file writing and acceptance testing to Chimera. There are no simulated model answers in the live workflow.

The operator selects exactly one NEW file path. jcode generates content inside a **separate disposable scratch directory**. Chimera extracts a single text/code block or a JSON `write` instruction's `arguments.content`, **ignores any path suggested by the model**, creates only the chosen new file, and runs a fixed, independently written pytest or cargo test suite. A model's text-form tool instruction is treated only as proposed file content, never as an executable command. The target repository must be a clean Git worktree. Nothing is committed, pushed, merged, or deployed.

### A real coding task on your machine

Install and configure actual jcode with your chosen authorized provider/model. The upstream jcode README documents using Ollama with `jcode login --provider ollama` or a local OpenAI-compatible profile. Start Ollama and install real model weights. Clone Agency Agents to a separate folder, and prepare a clean trusted Git project containing fixed tests for the task.

```bash
# After installing Chimera and real jcode:
chimera-jcode-artifact \
  --agency-checkout /path/to/agency-agents \
  --workspace /path/to/clean-git-worktree \
  --target solution.py \
  --task 'Write a complete Python solution.py that passes the prewritten tests.' \
  --test-suite pytest
# This first command is a dry run. To invoke jcode and modify the worktree:
chimera-jcode-artifact \
  --agency-checkout /path/to/agency-agents \
  --workspace /path/to/clean-git-worktree \
  --target solution.py \
  --task 'Write a complete Python solution.py that passes the prewritten tests.' \
  --test-suite pytest --execute
```

The model cannot pick another path; a mismatched or invented path in its response is not honored. The new-file limit is 16 KiB, and supported extensions are `.py`, `.txt`, `.md`, `.json`, and `.rs`. Existing files and symlink escapes are refused. On failure, the generated file, if already created, remains available for human inspection; use a fresh clean worktree for another run.

### Browser integration (explicit host configuration)

The default Docker chat/Council product **never enables coding**. On an operator-controlled loopback-only host with the installed jcode binary and an explicitly chosen clean worktree, set the existing coding variables plus `CHIMERA_CODE_ARTIFACT_TARGET=solution.py`. The browser's **jcode coding** mode then uses the Content Bridge for that exact new file instead of the older native tool-use workflow. This target is configured by the operator, not by an arbitrary web request.

```bash
CHIMERA_ENABLE_CODE=1 \
CHIMERA_AGENCY_CHECKOUT=/path/to/agency-agents \
CHIMERA_CODE_WORKSPACE=/path/to/clean-git-worktree \
CHIMERA_CODE_ARTIFACT_TARGET=solution.py \
CHIMERA_HOST=127.0.0.1 \
python -m chimera.product
```

Before calling this experimental local tool, use an isolated disposable project with tests you trust. Although the content-generation scratch directory is separate, jcode is a real executable and may have access to its own model-provider configuration and local tools. This is **not** an OS-level sandbox; do not execute it against sensitive or untrusted worktrees without independent isolation. The Content Bridge supports one new file per run and does not yet provide general multi-file editing or guarantee that the model's generated content will pass the tests. Test success is a task-specific signal, not an independent security audit or an assertion of general model superiority.

GitHub Actions runs a **real upstream jcode + actual downloaded Ollama weights + actual pytest acceptance test**, and fails rather than generating a canned answer when the model cannot complete the task. See `.github/workflows/real-jcode.yml` and `scripts/real_jcode_artifact_task.sh`.
