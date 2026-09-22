"""Explicit task-aware council selection and offline held-out gate CLI."""
import argparse
import json
from pathlib import Path
from .council import Council
from .fabric import load_specs
from .router import load_observations, select_committee
from .evaluation import load_outcomes, compare_heldout


def main() -> None:
    parser = argparse.ArgumentParser(description="Measured specialist council")
    parser.add_argument("--config", type=Path, default=Path("configs/power_agents.json"))
    parser.add_argument("--observations", type=Path, required=True,
                        help="Only TRAINING observations; never include held-out labels")
    parser.add_argument("--domain", required=True,
                        choices=("coding", "reasoning", "research", "multilingual",
                                 "long_context", "general"))
    parser.add_argument("--max-workers", type=int, default=3)
    parser.add_argument("--min-trials", type=int, default=3)
    parser.add_argument("--latency-weight", type=float, default=0)
    parser.add_argument("--cost-weight", type=float, default=0)
    parser.add_argument("--max-estimated-cost-usd", type=float)
    parser.add_argument("--task", help="An actual task; requires --execute to send to providers")
    parser.add_argument("--execute", action="store_true",
                        help="Explicitly perform provider calls; can incur costs")
    args = parser.parse_args()
    chosen = select_committee(
        load_specs(args.config), load_observations(args.observations),
        args.domain, max_workers=args.max_workers, min_trials=args.min_trials,
        latency_weight=args.latency_weight, cost_weight=args.cost_weight,
        max_estimated_cost_usd=args.max_estimated_cost_usd)
    if args.execute:
        if not args.task:
            parser.error("--execute requires --task")
        result = Council(chosen, max_workers=args.max_workers).run(args.task)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"status": "dry_run", "selected": [
            {"name": spec.name, "provider": spec.provider,
             "model": spec.model, "role": spec.role} for spec in chosen],
            "network_requests": 0}, indent=2))


def benchmark_main() -> None:
    parser = argparse.ArgumentParser(description="Compare paired held-out outcomes")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--training-task-ids", type=Path, required=True)
    parser.add_argument("--max-cost-increase-usd", type=float, default=0)
    args = parser.parse_args()
    training = json.loads(args.training_task_ids.read_text(encoding="utf-8"))
    if not isinstance(training, list) or not all(isinstance(x, str) for x in training):
        parser.error("--training-task-ids must contain a JSON list of strings")
    report = compare_heldout(
        load_outcomes(args.baseline), load_outcomes(args.candidate), set(training),
        max_cost_increase_usd=args.max_cost_increase_usd)
    print(json.dumps(report, indent=2))
