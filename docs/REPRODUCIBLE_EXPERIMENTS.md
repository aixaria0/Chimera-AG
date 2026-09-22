# Chimera v0.6 — Reproducible experiments

The research question is **whether a routed multi-agent council performs better than a fixed single-model baseline on previously unseen tasks**. This project does not claim an accuracy gain until it has measured one.

## Before running

Use newly rotated provider credentials in the private runtime environment, never in GitHub. Install Chimera, prepare a runtime agent manifest with enabled workers, synthesizer and verifier(s), and choose one enabled agent as the baseline. Make a fixed, independently labeled JSON task file with objects containing `id`, `domain`, `prompt`, and `expected`. Use non-sensitive tasks.

Store task IDs used to train routing policies in a separate JSON list. Ensure test prompts and labels were not used to pick models or tune prompts. Select the same task set for both arms. Do not use the toy ANSWER-labeled wiring tasks as an intelligence benchmark.

## Explicit experiment

```bash
chimera-experiment --suite path/to/heldout_tasks.json \
  --config configs/power_agents.json \
  --baseline-agent your-enabled-model-name \
  --training-task-ids path/to/training_ids.json \
  --output experiments/paired_run.json --execute
```

The runner sends each task to the baseline and the council, captures answers, wall-clock latency, attempted requests and failures, and refuses to overwrite a prior run. Running it can incur cloud charges. There is no automatic deployment or self-modification.

**Cost reporting:** this runner cannot verify billable cost because providers may report differing token/charge metadata. It labels costs as *unmeasured* and does not run a cost-based promotion gate. Placeholder zero values in the raw Outcome records MUST NOT be interpreted as free execution. Independently record actual provider charges before making cost or superiority claims.

**Verification:** the council now requires an explicit approval response from every assigned verifier. A verifier error cannot be silently treated as successful verification. Model agreement is not proof of factual correctness.

## What would constitute real evidence

Collect several independent, licensed, held-out benchmark suites with independently auditable labels. Report baseline and council accuracy, absolute paired differences, sample counts, abstentions, latency distributions, and actual provider cost, including failures. Repeat across task domains and providers, and publish a reproducible methodology. A successful offline CI run only tests software behavior, not live intelligence.
