"""Run every enabled council worker, then synthesize and verify."""
import argparse
import json
from .council import Council
from .fabric import load_specs


def main() -> None:
    parser = argparse.ArgumentParser(description="Chimera full-pool council")
    parser.add_argument("--config", default="configs/power_agents.json")
    parser.add_argument("--task", required=True)
    parser.add_argument("--workers", type=int, default=0,
                        help="Concurrent workers; 0 uses all enabled worker agents")
    args = parser.parse_args()
    council = Council(load_specs(args.config),
                      max_workers=None if args.workers == 0 else args.workers)
    print(json.dumps(council.run(args.task), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
