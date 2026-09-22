"""Real jcode artifact workflow: generate content first, then validate actual files."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .jcode_artifacts import generate_and_test


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Real jcode model content -> one operator-chosen new file -> actual tests")
    parser.add_argument("--agency-checkout", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--role", default="engineering/engineering-senior-developer.md")
    parser.add_argument("--jcode", default="jcode")
    parser.add_argument("--test-suite", choices=("pytest", "cargo"), default="pytest")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--execute", action="store_true",
                        help="Explicitly call real installed jcode and modify local workspace")
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({"status": "dry_run", "target": args.target,
            "real_model_requests": 0, "files_modified": False,
            "approach": "Real jcode generates content in separate scratch directory; "
                        "Chimera writes only the operator-selected new file and runs tests"}))
        return
    report = generate_and_test(
        checkout=args.agency_checkout, workspace=args.workspace, task=args.task,
        target=args.target, role=args.role, executable=args.jcode,
        test_suite=args.test_suite, timeout=args.timeout)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if report["status"] != "candidate_for_human_review":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
