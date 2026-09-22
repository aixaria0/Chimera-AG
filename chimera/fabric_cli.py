"""Run the bounded hybrid fabric using an explicitly enabled agent manifest."""
import argparse
import json
from .fabric import Fabric, load_specs

def main():
    parser = argparse.ArgumentParser(description="Chimera hybrid agent fabric")
    parser.add_argument("--config", default="configs/agents.json")
    parser.add_argument("--task", required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--max-requests", type=int, default=16)
    args = parser.parse_args()
    result = Fabric(load_specs(args.config), max_workers=args.workers,
                    max_requests=args.max_requests).run(args.task)
    print(json.dumps(result, indent=2))
if __name__ == "__main__":
    main()
