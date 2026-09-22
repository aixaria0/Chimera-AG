"""Paired coding benchmark on two *separate* local Git clones of one clean HEAD.

An actual jcode installation is optional at import time, required only with
explicit --execute. A simulated executor may be injected for offline tests.
Tests are *proxy evidence* of behavior, not a proof of general code quality.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable

from .agency_bridge import compose_prompt, load_role, run_jcode, JcodeResult
from .coding_workflow import (
    DEFAULT_ROLES, execute_workflow, git_snapshot, git_fingerprint, run_tests,
)

MAX_OUTPUT = 12_000


def _git(argv: list[str], *, cwd: Path | None = None) -> str:
    process = subprocess.run(["git", *argv], cwd=str(cwd) if cwd else None,
                             capture_output=True, text=True, check=False, timeout=60)
    if process.returncode:
        raise RuntimeError("Local Git operation failed")
    return process.stdout.strip()


def prepare_clones(source: Path, destination: Path) -> tuple[Path, Path, str]:
    """Require clean source; clone the same commit into fresh isolated directories."""
    root = source.resolve(strict=True)
    if not root.is_dir() or git_snapshot(root).strip():
        raise ValueError("Source must be a clean Git working tree")
    revision = _git(["rev-parse", "HEAD"], cwd=root)
    if not _git(["rev-parse", "--show-toplevel"], cwd=root):
        raise ValueError("Source must be a Git working tree")
    destination.mkdir(parents=True, exist_ok=True)
    baseline = destination / "baseline"
    council = destination / "council"
    if baseline.exists() or council.exists():
        raise ValueError("Refusing to replace benchmark workspaces")
    try:
        for target in (baseline, council):
            _git(["clone", "--quiet", "--no-local", "--no-hardlinks", "--",
                  str(root), str(target)])
            # Source HEAD may be a detached commit; explicitly set both to the same SHA.
            _git(["checkout", "--quiet", "--detach", revision], cwd=target)
            if git_snapshot(target).strip():
                raise RuntimeError("Benchmark clone was not clean")
    except Exception:
        # The temporary output directory is owned by the caller, so do not
        # automatically delete its potentially valuable contents on failure.
        raise
    return baseline, council, revision


def _result(status: str, requests: int, answer: str, before: str, after: str,
            tests: JcodeResult | None, elapsed_ms: int) -> dict:
    return {
        "status": status, "jcode_invocations": requests,
        "output_sha256": hashlib.sha256(answer.encode("utf-8")).hexdigest(),
        "workspace_changed": before != after,
        "tests_passed": tests is not None and tests.status == "completed",
        "test_status": tests.status if tests else "not_run",
        "test_returncode": tests.returncode if tests else None,
        "elapsed_ms": elapsed_ms,
        "human_approval_required": True,
    }


def compare_code_task(*, source: Path, checkout: Path, task: str,
                      destination: Path, test_suite: str = "pytest",
                      executable: str = "jcode", timeout: int = 180,
                      agent_runner: Callable | None = None,
                      tests_runner: Callable | None = None) -> dict:
    """Run a single implementer then council on identical clean checkouts.

    Run only from explicit operator action. Actual provider usage and costs
    cannot be inferred from process exit status or test results.
    """
    if not task.strip() or len(task) > 20_000:
        raise ValueError("Invalid task")
    for role in DEFAULT_ROLES.values():
        load_role(checkout, role)
    baseline, council, revision = prepare_clones(source, destination)
    runner = agent_runner or (lambda prompt, workspace: run_jcode(
        prompt, workspace=workspace, executable=executable, timeout=timeout))
    tester = tests_runner or (lambda workspace: run_tests(workspace, test_suite))
    if test_suite not in ("pytest", "cargo"):
        raise ValueError("Unknown test suite")
    initial_baseline = git_fingerprint(baseline)
    initial_council = git_fingerprint(council)
    began = time.monotonic()
    prompt = compose_prompt(
        load_role(checkout, DEFAULT_ROLES["implementer"]),
        "Implement this bounded task in the given Git working tree. "
        "Do not commit, push or deploy. TASK:\n" + task,
    )
    base = runner(prompt, baseline)
    base_tests = tester(baseline) if base.status == "completed" and (
        git_fingerprint(baseline) != initial_baseline) else None
    baseline_result = _result(
        base.status, 1, base.stdout, initial_baseline, git_fingerprint(baseline),
        base_tests, int((time.monotonic() - began) * 1000),
    )

    began = time.monotonic()
    council_report = execute_workflow(
        checkout=checkout, workspace=council, task=task, test_suite=test_suite,
        run_agent=lambda prompt: runner(prompt, council),
        test_fn=lambda: tester(council),
    )
    council_result = {
        "status": council_report["status"],
        "jcode_invocations": sum(phase["name"] != "tests"
                                 for phase in council_report["phases"]),
        "workspace_changed": initial_council != git_fingerprint(council),
        "tests_passed": council_report["status"] == "candidate_for_human_review",
        "elapsed_ms": int((time.monotonic() - began) * 1000),
        "human_approval_required": True,
        "phases": [{"name": p["name"], "status": p["status"],
                    "returncode": p["returncode"],
                    "output_digest": p["output_digest"]}
                   for p in council_report["phases"]],
    }
    return {
        "kind": "paired_coding_workflow_experiment",
        "source_revision": revision,
        "task_sha256": hashlib.sha256(task.encode("utf-8")).hexdigest(),
        "task": task,
        "test_suite": test_suite,
        "baseline": baseline_result,
        "council": council_result,
        "baseline_workspace": str(baseline),
        "council_workspace": str(council),
        "comparison": {
            "same_starting_commit": True,
            "suite_pass_delta": int(council_result["tests_passed"]) -
                                int(baseline_result["tests_passed"]),
            "coding_quality_proven": False,
            "model_superiority_proven": False,
            "provider_costs_measured": False,
            "automatic_promotion": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Paired local coding benchmark")
    parser.add_argument("--source", type=Path, required=True,
                        help="Clean trusted Git repository containing fixed tests")
    parser.add_argument("--agency-checkout", type=Path, required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--test-suite", choices=("pytest", "cargo"), default="pytest")
    parser.add_argument("--jcode", default="jcode")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--output", type=Path, required=True,
                        help="New JSON report file, outside benchmark workspaces")
    parser.add_argument("--execute", action="store_true",
                        help="Explicitly invoke coding agents; may incur provider costs")
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({"status": "dry_run", "model_requests": 0,
                          "description": "Paired local clones; fixed tests; human review"}))
        return
    if args.output.exists():
        parser.error("Output exists; refusing to overwrite an experiment")
    with tempfile.TemporaryDirectory(prefix="chimera-paired-") as tmp:
        report = compare_code_task(
            source=args.source, checkout=args.agency_checkout, task=args.task,
            destination=Path(tmp), test_suite=args.test_suite,
            executable=args.jcode, timeout=args.timeout,
        )
        # Temporary benchmark clones disappear after this function. Don't put
        # their former paths in the durable report.
        report.pop("baseline_workspace")
        report.pop("council_workspace")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(args.output),
                      "baseline_tests_passed": report["baseline"]["tests_passed"],
                      "council_tests_passed": report["council"]["tests_passed"],
                      "quality_proven": False}, indent=2))


if __name__ == "__main__":
    main()
