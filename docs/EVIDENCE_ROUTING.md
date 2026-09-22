# Chimera v0.5 — Evidence-Routed Specialist Councils

An immense model pool is a resource, not evidence of intelligence. This milestone introduces domain-specific routing based **only on independently measured training observations**, paired held-out evaluation, and a promotion gate requiring strictly improved exact-match accuracy without exceeding the configured cost-increase allowance. No production model deployment occurs automatically.

## Agent observations

Create a private JSON list of measured observations, for example:

```json
[
  {"agent":"ollama-00000","domain":"coding","correct":true,"latency_ms":1000,"cost_usd":0},
  {"agent":"ollama-00000","domain":"coding","correct":false,"latency_ms":1200,"cost_usd":0}
]
```

Each observation must represent an independent **training** task with a known reference label. Use the exact agent `name` from your current runtime manifest. Scores use Laplace-smoothed accuracy `(successes + 1) / (trials + 2)`; by default each agent needs at least three training observations per task domain. No unknown agent receives a fabricated score. A routing policy selected from training labels must not be tuned using held-out examples.

## Choose a council without making cloud calls

```bash
chimera-route --config configs/power_agents.json \
  --observations path/to/training_observations.json \
  --domain coding --max-workers 3
```

Dry-run is the default and prints selected model IDs, provider and role. Run live inference only by adding `--execute --task "your non-sensitive task"`. The council retains explicitly enabled synthesizers and verifiers, and selects distinct measured worker models using task-domain accuracy, optional latency/cost penalties and an optional estimated worker-cost cap.

**Measured cost is not a hard billing limit.** The router cannot guarantee provider costs, and live calls may incur charges. Any provider rates, authentication, quotas, GPU limits and account entitlements still apply. Do not use exposed or previously shared credentials.

## Paired held-out evaluation

Capture outcomes separately for the fixed baseline and the routed council using the same independently labeled held-out tasks:

```json
[
  {"task_id":"heldout-1","domain":"coding","expected":"yes","answer":"yes",
   "requests":3,"cost_usd":0,"latency_ms":2000}
]
```

Keep task IDs used for training in a separate JSON list, e.g. `["train-1","train-2"]`. Then:

```bash
chimera-benchmark --baseline path/to/baseline.json \
  --candidate path/to/candidate.json \
  --training-task-ids path/to/training_ids.json
```

The evaluation refuses mismatched paired task IDs, contradictory labels, duplicate tasks and any training/held-out task ID overlap. An eligible candidate must improve exact-match accuracy strictly and remain within the declared cost allowance. The report is **eligible for human review**, not a license for automated promotion. This benchmark cannot establish factual truth beyond its reference labels; tasks should have independently audited answers.

## Research priorities

Build a reproducible, independent evaluation suite for code execution, factual question-answering, reasoning, long-context and multilingual tasks; sample across providers, control prompt variability, log real token usage and current pricing, and compare latency/cost/accuracy with confidence intervals. Keep evaluator labels and prompts inaccessible to candidate models during training and selection. Calibrate role separation and verifier errors. The existing `benchmarks/tasks.json` is only a toy wiring check, not an intelligence benchmark.
