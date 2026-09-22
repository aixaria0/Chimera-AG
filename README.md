# Chimera v0.1 — Hybrid Agent Coordination

An experimental, bounded strategy-selection engine for local and optional cloud agents. **This is a working scaffold, not an autonomous production fabric.** Offline `LocalAgent` is a deterministic test fixture, not a language model. Cloud calls require an OpenAI-compatible HTTPS chat-completions API and may incur charges.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e '.[test]'
pytest -q
chimera
```

To enable optional cloud calls, configure `CHIMERA_CLOUD_API_KEY`, `CHIMERA_CLOUD_MODEL`, and optionally `CHIMERA_CLOUD_URL`, then run `chimera --cloud`. Do not commit API keys. Only send non-sensitive benchmark prompts to the configured provider.

## Design

`chimera/core.py` defines an agent protocol, local fixture, optional cloud adapter, four coordination strategies, deterministic exact-match evaluator, strict no-regression selection gate, and hash-linked JSONL experiment ledger. `chimera/cli.py` exposes the experiment. `benchmarks/tasks.json` contains toy routing tasks; replace these with meaningful held-out coordination tasks before making performance claims.

## Current limitations

- The local agent extracts an answer explicitly embedded in toy benchmark prompts; this is a wiring check, **not evidence of intelligence or improved coordination**.
- Verification compares outputs and cannot establish factual correctness beyond benchmark labels.
- The ledger is tamper-evident only relative to a trusted external copy of its last hash; it is not immutable.
- Cloud requests have no automatic retries, budget enforcement, or production-grade sandboxing.
- Evolution selects among predefined strategies, not self-modifying code or model weights.

## Next milestone

Introduce real local model adapter, independent held-out tasks, separate worker roles, explicit cloud budget, latency/cost-aware scoring, and approval-gated promotion.
