"""Real, model-backed code-generation evaluation on independently tested tasks.

The suite contains Git repositories with prewritten tests, an exact new-file
target and task text. The baseline is the real upstream jcode binary. The
specialist arm uses the real Agency Agents role plus the existing verified
artifact generator. No mock agents, synthetic success or automatic promotion.
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
from .coding_workflow import git_fingerprint, run_tests
from .jcode_artifacts import generate_and_test


def _test(workspace: Path, suite: str) -> dict:
    result = run_tests(workspace, suite)
    return {"status": result.status, "passed": result.status == "completed",
            "exit_code": result.returncode}


def evaluate_task(*, source: Path, checkout: Path, destination: Path,
                  task: str, target: str, suite: str = "pytest",
                  jcode: str = "jcode", timeout: int = 300) -> dict:
    """Report what actually happened in independent, same-commit worktrees."""
    baseline, specialist, commit = prepare_clones(source, destination)
    baseline_initial = git_fingerprint(baseline)
    started = time.monotonic()
    first = run_jcode(
        "Implement this bounded task in the working tree. Preserve existing tests, "
        "do not commit or deploy. TASK:\n" + task,
        workspace=baseline, executable=jcode, timeout=timeout)
    baseline_changed = baseline_initial != git_fingerprint(baseline)
    baseline_test = (_test(baseline, suite)
                     if first.status == "completed" and baseline_changed
                     else {"status": "not_run", "passed": False, "exit_code": None})
    baseline_result = {
        "status": first.status, "changed_workspace": baseline_changed,
        "test": baseline_test, "elapsed_ms": round((time.monotonic()-started)*1000),
        "output_sha256": hashlib.sha256(first.stdout.encode()).hexdigest(),
    }
    started = time.monotonic()
    specialist_result = generate_and_test(
        workspace=specialist, checkout=checkout, task=task, target=target,
        executable=jcode, test_suite=suite, timeout=timeout)
    specialist_result = {
        "status": specialist_result["status"],
        "generator": specialist_result["generator"],
        "tests_passed": specialist_result.get("tests_passed", False),
        "content_sha256": specialist_result.get("content_sha256"),
        "elapsed_ms": round((time.monotonic()-started)*1000),
    }
    return {"starting_commit": commit, "task_sha256": hashlib.sha256(task.encode()).hexdigest(),
            "baseline": baseline_result, "specialist": specialist_result,
            "same_starting_commit": True, "independent_test_suite": suite,
            "human_approval_required": True, "model_superiority_proven": False}


def main() -> None:
    parser = argparse.ArgumentParser(description="Paired genuine jcode artifact evaluation")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--agency-checkout", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jcode", default="jcode")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({"status": "dry_run", "model_calls": 0}))
        return
    if args.output.exists() or args.work_root.exists():
        parser.error("Evidence file or benchmark workspace already exists")
    tasks = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not isinstance(tasks, list) or not tasks or len(tasks) > 100:
        parser.error("Manifest must include 1-100 tasks")
    ids = set()
    for item in tasks:
        if not isinstance(item, dict) or set(item) != {"id", "source", "task", "target", "suite"}:
            parser.error("Tasks must contain id, source, task, target and suite")
        if not isinstance(item["id"], str) or not item["id"].strip() or item["id"] in ids:
            parser.error("Task IDs must be nonempty and unique")
        if not isinstance(item["task"], str) or not item["task"].strip():
            parser.error("Task must be a nonempty string")
        if item["suite"] not in ("pytest", "cargo"):
            parser.error("Unsupported fixed test suite")
        if not isinstance(item["target"], str) or not item["target"].strip():
            parser.error("Operator must specify a target filename")
        ids.add(item["id"])
    args.work_root.mkdir(parents=True)
    results = []
    for index, item in enumerate(tasks):
        if not isinstance(item, dict) or set(item) != {"id", "source", "task", "target", "suite"}:
            parser.error("Tasks must contain id, source, task, target and suite")
        root = Path(item["source"]).resolve(strict=True)
        results.append({
            "id": item["id"],
            **evaluate_task(source=root, checkout=args.agency_checkout,
                            destination=args.work_root / f"task-{index:03d}",
                            task=item["task"], target=item["target"],
                            suite=item["suite"], jcode=args.jcode),
        })
    payload = {"kind": "real_jcode_artifact_evaluation",
               "tasks": len(results), "results": results,
               "baseline_passes": sum(x["baseline"]["test"]["passed"] for x in results),
               "specialist_passes": sum(x["specialist"]["tests_passed"] for x in results),
               "limits": ["No mocks", "Prewritten tests measure task-specific behavior only",
                          "Specialist is a bounded artifact workflow, not a complete general coding agent",
                          "Different execution contracts: direct repo editing vs one constrained file",
                          "Do not use these scores to declare model superiority"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(args.output), "tasks": payload["tasks"],
                      "baseline_passes": payload["baseline_passes"],
                      "specialist_passes": payload["specialist_passes"]}))


if __name__ == "__main__":
    main()
