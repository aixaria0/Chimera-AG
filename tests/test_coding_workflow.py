"""Offline integration tests: no real jcode, cloud provider or repository writes."""
import subprocess

import pytest

from chimera.agency_bridge import JcodeResult
from chimera.coding_workflow import (
    DEFAULT_ROLES, execute_workflow, git_snapshot, run_tests,
)


def roles(tmp_path):
    root = tmp_path / "agency"
    for identifier in DEFAULT_ROLES.values():
        file = root / identifier
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(
            "---\nname: Specialist\ndescription: Specialist guidance\n---\n"
            "Keep the task within the local workspace.\n", encoding="utf-8")
    return root


def success(text="ok"):
    return JcodeResult("completed", text, "", 0)


def test_successful_flow_requires_review_after_tests(tmp_path):
    checkout = roles(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = {"files": "", "calls": []}

    def agent(prompt):
        state["calls"].append(prompt)
        if len(state["calls"]) == 1:
            return success("PLAN")
        if len(state["calls"]) == 2:
            assert "PLAN" in prompt
            state["files"] = " M example.py"
            return success("IMPLEMENTED")
        assert "READ-ONLY REVIEW" in prompt
        return success("Some concerns to inspect")

    report = execute_workflow(checkout=checkout, workspace=workspace, task="Fix bug",
                              run_agent=agent, status_fn=lambda: state["files"],
                              test_fn=lambda: success("3 passed"))
    assert report["status"] == "candidate_for_human_review"
    assert [p["name"] for p in report["phases"]] == [
        "planner", "implementer", "reviewer", "tests"]
    assert report["human_approval_required"]
    assert not report["committed"]
    assert len(state["calls"]) == 3


def test_dirty_workspace_never_starts_agent(tmp_path):
    checkout = roles(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    with pytest.raises(ValueError, match="clean Git"):
        execute_workflow(checkout=checkout, workspace=workspace, task="Fix bug",
                         run_agent=lambda prompt: pytest.fail("must not invoke"),
                         status_fn=lambda: "?? secret.txt")


def test_planner_edits_halt_before_implementation(tmp_path):
    checkout = roles(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = {"status": "", "calls": 0}

    def agent(prompt):
        state["calls"] += 1
        state["status"] = " M modified.py"
        return success("PLAN")

    report = execute_workflow(checkout=checkout, workspace=workspace, task="Fix bug",
                              run_agent=agent, status_fn=lambda: state["status"])
    assert report["status"] == "halted_planning"
    assert state["calls"] == 1


def test_reviewer_edit_halts_before_tests(tmp_path):
    checkout = roles(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = {"status": "", "calls": 0}

    def agent(prompt):
        state["calls"] += 1
        if state["calls"] == 2:
            state["status"] = " M change.py"
        if state["calls"] == 3:
            state["status"] += "\n?? extra.py"
        return success("PLAN")

    report = execute_workflow(checkout=checkout, workspace=workspace, task="Fix bug",
                              run_agent=agent, status_fn=lambda: state["status"],
                              test_fn=lambda: pytest.fail("must not test"))
    assert report["status"] == "halted_review"


def test_failed_tests_do_not_promote(tmp_path):
    checkout = roles(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = {"status": "", "calls": 0}

    def agent(prompt):
        state["calls"] += 1
        if state["calls"] == 2:
            state["status"] = " M change.py"
        return success("PLAN")

    report = execute_workflow(checkout=checkout, workspace=workspace, task="Fix bug",
                              run_agent=agent, status_fn=lambda: state["status"],
                              test_fn=lambda: JcodeResult("failed", "", "failed", 1))
    assert report["status"] == "failed_tests"
    assert report["human_approval_required"]
    assert not report["deployed"]


def test_tests_use_fixed_argv_and_no_shell(tmp_path):
    captured = {}

    def runner(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(args, 0, stdout="5 passed", stderr="")

    assert run_tests(tmp_path, "pytest", runner=runner).status == "completed"
    assert captured["args"] == ["python", "-m", "pytest", "-q"]
    assert "shell" not in captured["kwargs"]
    with pytest.raises(ValueError):
        run_tests(tmp_path, "sh -c something", runner=runner)


def test_git_snapshot_tracks_untracked_files(tmp_path):
    def runner(args, **kwargs):
        assert "--untracked-files=all" in args
        return subprocess.CompletedProcess(args, 0, stdout="?? new_file.py\n", stderr="")
    assert git_snapshot(tmp_path, runner=runner) == "?? new_file.py\n"
