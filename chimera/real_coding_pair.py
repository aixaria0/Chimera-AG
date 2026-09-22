"""Real Git worktree coding agent benchmark, no mock executor or fixture result.

An operator supplies a clean, trusted Git task repo with prewritten tests and a
real jcode executable. Two separate clones share exactly the same source HEAD.
The baseline uses one jcode implementation call. Council uses the existing
specialist plan -> implementation -> review -> fixed-test workflow. Results
report tests, phase outcomes, runtime and failure modes, NOT model superiority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

from .agency_bridge import run_jcode
from .coding_comparison import prepare_clones
from .coding_workflow import git_fingerprint, git_snapshot, run_tests, execute_workflow


def run_real_coding_pair(*, source: Path, agency_checkout: Path, task: str,
                         destination: Path, test_suite: str = "pytest",
                         executable: str = "jcode", timeout: int = 300) -> dict:
    if not isinstance(task, str) or not task.strip() or len(task) > 6000:
        raise ValueError("Coding task must be 1–6000 characters")
    if not 1 <= timeout <= 900:
        raise ValueError("Timeout must be between 1 and 900 seconds")
    # Both environments are actual separate Git clones, never fixture-only
    # fake workspaces and never the operator's working source directory.
    baseline, council, revision = prepare_clones(source, destination)
    start = time.monotonic()
    initial = git_fingerprint(baseline)
    base = run_jcode(
        "Implement the following task in this Git project. Do not modify tests, "
        "commit, push or deploy. TASK:\n" + task,
        workspace=baseline, executable=executable, timeout=timeout,
    )
    baseline_modified = git_fingerprint(baseline) != initial
    base_test = (run_tests(baseline, test_suite)
                 if base.status == "completed" and baseline_modified else None)
    baseline_result = {
        "execution_status": base.status,
        "exit_code": base.returncode,
        "changed_workspace": baseline_modified,
        "tests_passed": base_test is not None and base_test.status == "completed",
        "test_status": base_test.status if base_test else "not_run",
        "duration_ms": round((time.monotonic() - start) * 1000),
        "model_output_sha256": hashlib.sha256(base.stdout.encode()).hexdigest(),
        "model_requests": 1,
    }
    start = time.monotonic()
    report = execute_workflow(
        checkout=agency_checkout, workspace=council, task=task,
        test_suite=test_suite, executable=executable, per_phase_timeout=timeout,
    )
    council_test = next((p for p in report["phases"] if p["name"] == "tests"), None)
    council_result = {
        "status": report["status"],
        "changed_workspace": report["workspace_changed"],
        "tests_passed": council_test is not None and council_test["status"] == "completed",
        "test_status": council_test["status"] if council_test else "not_run",
        "review_inconclusive": report.get("review_inconclusive", True),
        "duration_ms": round((time.monotonic() - start) * 1000),
        "model_requests": sum(p["name"] != "tests" for p in report["phases"]),
        "phase_statuses": [{ "name": p["name"], "status": p["status"],
                             "returncode": p["returncode"]} for p in report["phases"]],
    }
    return {
        "kind": "real_jcode_git_coding_pair",
        "source_commit": revision,
        "task_sha256": hashlib.sha256(task.encode()).hexdigest(),
        "test_suite": test_suite,
        "baseline": baseline_result,
        "council": council_result,
        "same_starting_commit": True,
        "human_approval_required": True,
        "model_superiority_proven": False,
        "source_modified": git_snapshot(source.resolve(strict=True)).strip() != "",
        "no_automatic_commit_or_deploy": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Paired real jcode Git coding benchmark")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--agency-checkout", type=Path, required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--test-suite", choices=("pytest", "cargo"), default="pytest")
    parser.add_argument("--jcode", default="jcode")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({"status": "dry_run", "jcode_calls": 0,
                          "requires": "real installed jcode, clean Git source and trusted tests"}))
        return
    if args.output.exists():
        parser.error("Output already exists; refusing to overwrite evidence")
    if args.destination.exists():
        parser.error("Destination already exists; refusing to overwrite workspaces")
    report = run_real_coding_pair(
        source=args.source, agency_checkout=args.agency_checkout,
        task=args.task, destination=args.destination, test_suite=args.test_suite,
        executable=args.jcode, timeout=args.timeout,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "recorded", "output": str(args.output),
                      "baseline_tests_passed": report["baseline"]["tests_passed"],
                      "council_tests_passed": report["council"]["tests_passed"],
                      "human_approval_required": True}))
if __name__ == "__main__":
    main()
