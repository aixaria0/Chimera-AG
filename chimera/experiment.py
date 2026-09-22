"""Run a fixed, independently labeled suite on one baseline and one council.

Explicit --execute is required by the CLI. This module does not manufacture
labels, benchmark gains, token costs, or provider access.
"""
from __future__ import annotations
import argparse
import json
import time
from pathlib import Path
from .fabric import AgentSpec, ChatEndpoint, RequestBudget, load_specs
from .council import Council
from .evaluation import Outcome, compare_heldout


def read_suite(path: Path) -> list[dict]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise ValueError("Expected a nonempty JSON task list")
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not all(
            isinstance(row.get(key), str) and row[key].strip()
            for key in ("id", "domain", "prompt", "expected")
        ):
            raise ValueError("Each task needs id, domain, prompt and expected strings")
        if row["id"] in seen:
            raise ValueError("Duplicate task ID")
        seen.add(row["id"])
    return rows


def run_suite(tasks: list[dict], baseline: AgentSpec, council: Council,
              *, baseline_factory=None) -> tuple[list[Outcome], list[Outcome], list[dict]]:
    """Run both arms on precisely the same task prompts, in fixed task order.

    Cost is unknown unless separately measured by the provider; do not report a
    fictitious zero cost. This runner therefore records latency and requests but
    DOES NOT approve any cost-based promotion.
    """
    baseline_factory = baseline_factory or (lambda spec, budget: ChatEndpoint(spec, budget))
    old, new, failures = [], [], []
    for task in tasks:
        budget = RequestBudget(1)
        start = time.monotonic()
        answer = None
        try:
            answer = baseline_factory(baseline, budget).answer(task["prompt"])
        except Exception as exc:
            failures.append({"task_id": task["id"], "arm": "baseline",
                             "error_type": type(exc).__name__})
        old.append(Outcome(task["id"], task["domain"], task["expected"], answer,
                           budget.used, 0.0, (time.monotonic()-start)*1000))
        start = time.monotonic()
        report = council.run(task["prompt"])
        if report["status"] != "accepted":
            failures.append({"task_id": task["id"], "arm": "council",
                             "status": report["status"]})
        new.append(Outcome(task["id"], task["domain"], task["expected"],
                           report["answer"], report["requests_used"], 0.0,
                           (time.monotonic()-start)*1000))
    return old, new, failures


def main():
    parser = argparse.ArgumentParser(description="Paired Chimera live benchmark")
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--baseline-agent", required=True)
    parser.add_argument("--training-task-ids", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true",
                        help="Make real provider requests; may incur charges")
    args = parser.parse_args()
    if not args.execute:
        parser.error("Real benchmark requires --execute; no model requests were made")
    if args.output.exists():
        parser.error("Output exists; refusing to overwrite an existing experiment")
    tasks = read_suite(args.suite)
    training = json.loads(args.training_task_ids.read_text(encoding="utf-8"))
    if not isinstance(training, list) or not all(isinstance(x, str) for x in training):
        parser.error("training-task-ids must be a JSON string list")
    if {row["id"] for row in tasks} & set(training):
        parser.error("Held-out task IDs overlap with training tasks")
    specs = load_specs(args.config)
    baseline = next((s for s in specs if s.name == args.baseline_agent and s.enabled), None)
    if baseline is None:
        parser.error("Baseline must identify an enabled manifest agent")
    old, new, failures = run_suite(tasks, baseline, Council(specs))
    # Zero costs are only placeholders for unknown billing, not proof of no charge.
    report = {"costs_measured": False, "promotion_evaluated": False,
              "baseline": [vars(item) for item in old],
              "candidate": [vars(item) for item in new], "failures": failures,
              "note": "Cost unknown; independently collect billable usage before promotion."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "tasks": len(tasks),
                      "failures": len(failures), "promotion_evaluated": False}, indent=2))


if __name__ == "__main__":
    main()
