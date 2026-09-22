"""Offline paired comparison through real Git clones and real pytest tests.

The executor is a deterministic fixture, NOT a live language model.
"""
import subprocess
import pytest
from chimera.agency_bridge import JcodeResult
from chimera.coding_comparison import compare_code_task, prepare_clones
from chimera.coding_workflow import DEFAULT_ROLES


def _run(*args, cwd):
    return subprocess.run(args, cwd=str(cwd), capture_output=True,
                          text=True, check=True)


def setup_project(tmp_path):
    checkout = tmp_path / "agency"
    for identifier in DEFAULT_ROLES.values():
        role = checkout / identifier
        role.parent.mkdir(parents=True, exist_ok=True)
        role.write_text("---\nname: Specialist\ndescription: A coding agent\n---\n"
                        "Act on the specific software task.\n", encoding="utf-8")
    source = tmp_path / "source"
    source.mkdir()
    (source / "test_math.py").write_text(
        "from math_patch import add\n"
        "def test_add():\n"
        "    assert add(2, 3) == 5\n", encoding="utf-8")
    (source / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n",
                                       encoding="utf-8")
    _run("git", "init", "-q", cwd=source)
    _run("git", "add", ".", cwd=source)
    _run("git", "-c", "user.name=CI Fixture",
         "-c", "user.email=ci-fixture@example.invalid",
         "commit", "-qm", "initial", cwd=source)
    return source, checkout


def fake_agent(prompt, workspace):
    if "READ-ONLY PLANNING ONLY" in prompt:
        return JcodeResult("completed", "Create math_patch.add", "", 0)
    if "READ-ONLY REVIEW" in prompt:
        return JcodeResult("completed", "Check the diff manually", "", 0)
    (workspace / "math_patch.py").write_text(
        "def add(a, b):\n    return a + b\n", encoding="utf-8")
    return JcodeResult("completed", "Created math_patch", "", 0)


def test_paired_runs_use_same_clean_starting_commit(tmp_path):
    source, checkout = setup_project(tmp_path)
    result = compare_code_task(
        source=source, checkout=checkout, task="Implement integer addition",
        destination=tmp_path / "paired", agent_runner=fake_agent)
    assert result["comparison"]["same_starting_commit"] is True
    assert result["baseline"]["tests_passed"] is True
    assert result["council"]["tests_passed"] is True
    assert result["baseline"]["jcode_invocations"] == 1
    assert result["council"]["jcode_invocations"] == 3
    assert result["comparison"]["suite_pass_delta"] == 0
    assert result["comparison"]["coding_quality_proven"] is False
    assert result["comparison"]["model_superiority_proven"] is False
    assert result["baseline_workspace"] != result["council_workspace"]
    assert (source / "math_patch.py").exists() is False
    assert result["baseline"]["workspace_changed"]
    assert result["council"]["workspace_changed"]


def test_source_must_be_clean(tmp_path):
    source, checkout = setup_project(tmp_path)
    (source / "untracked.txt").write_text("dirty")
    with pytest.raises(ValueError, match="clean Git"):
        prepare_clones(source, tmp_path / "paired")


def test_baseline_failure_recorded_without_overclaiming(tmp_path):
    source, checkout = setup_project(tmp_path)
    def no_baseline_change(prompt, workspace):
        if workspace.name == "baseline":
            return JcodeResult("completed", "No modifications", "", 0)
        return fake_agent(prompt, workspace)
    result = compare_code_task(
        source=source, checkout=checkout, task="Implement integer addition",
        destination=tmp_path / "paired", agent_runner=no_baseline_change)
    assert result["baseline"]["tests_passed"] is False
    assert result["baseline"]["test_status"] == "not_run"
    assert result["council"]["tests_passed"] is True
    assert result["comparison"]["suite_pass_delta"] == 1
    assert result["comparison"]["model_superiority_proven"] is False
