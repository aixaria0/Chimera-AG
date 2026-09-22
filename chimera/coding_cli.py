"""CLI for a scoped, reviewable Agency Agents + jcode coding workflow."""
import argparse
import json
from pathlib import Path

from .coding_workflow import DEFAULT_ROLES, TEST_COMMANDS, execute_workflow


def main() -> None:
    parser = argparse.ArgumentParser(description="Chimera coding workflow: plan, implement, review, test")
    parser.add_argument("--agency-checkout", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--task", required=True)
    parser.add_argument("--planner", default=DEFAULT_ROLES["planner"])
    parser.add_argument("--implementer", default=DEFAULT_ROLES["implementer"])
    parser.add_argument("--reviewer", default=DEFAULT_ROLES["reviewer"])
    parser.add_argument("--test-suite", choices=sorted(TEST_COMMANDS), default="pytest")
    parser.add_argument("--jcode", default="jcode")
    parser.add_argument("--phase-timeout", type=int, default=180)
    parser.add_argument("--test-timeout", type=int, default=300)
    parser.add_argument("--execute", action="store_true",
                        help="Opt in to jcode execution and local file modification")
    args = parser.parse_args()
    roles = {key: getattr(args, key) for key in DEFAULT_ROLES}
    if not args.execute:
        print(json.dumps({"status": "dry_run", "roles": roles,
            "workspace": str(args.workspace), "test_suite": args.test_suite,
            "jcode_invoked": False, "files_modified": False,
            "human_approval_required": True}, indent=2))
        return
    result = execute_workflow(
        checkout=args.agency_checkout, workspace=args.workspace, task=args.task,
        roles=roles, test_suite=args.test_suite, executable=args.jcode,
        per_phase_timeout=args.phase_timeout, test_timeout=args.test_timeout)
    print(json.dumps(result, indent=2))
    if result["status"] != "candidate_for_human_review":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
