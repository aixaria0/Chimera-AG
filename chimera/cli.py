import argparse
import json
from pathlib import Path
from .core import CloudAgent, LocalAgent, evolve, load_tasks


def main() -> None:
    parser = argparse.ArgumentParser(description="Chimera v0.1 controlled coordination evolution")
    parser.add_argument("--tasks", type=Path, default=Path("benchmarks/tasks.json"))
    parser.add_argument("--ledger", type=Path, default=Path("experiments/ledger.jsonl"))
    parser.add_argument("--cloud", action="store_true", help="Enable paid/remote cloud calls")
    args = parser.parse_args()
    cloud = CloudAgent() if args.cloud else None
    print(json.dumps(evolve(load_tasks(args.tasks), LocalAgent(), cloud, args.ledger), indent=2))

if __name__ == "__main__":
    main()
