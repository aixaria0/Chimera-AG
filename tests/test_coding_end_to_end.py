"""Actual local subprocess + Git + pytest integration, with a clearly FAKE jcode.

The fixture verifies the orchestration wiring only. It does not call an LLM.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from chimera.agency_bridge import JcodeResult
from chimera.coding_workflow import (
    DEFAULT_ROLES, execute_workflow, git_fingerprint, run_tests,
)


def _run(*args, cwd):
    return subprocess.run(args, cwd=str(cwd), check=True, capture_output=True, text=True)


def _setup(tmp_path):
    roles = tmp_path / "agency"
    for identifier in DEFAULT_ROLES.values():
        destination = roles / identifier
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            "---\nname: Specialist\ndescription: Fixture agent\n---\n"
            "Act only on the explicit software task.\n", encoding="utf-8")
    root = tmp_path / "project"
    root.mkdir()
    (root / "test_calculator.py").write_text(
        "from calculator import add\n"
        "def test_add():\n"
        "    assert add(2, 3) == 5\n", encoding="utf-8")
    (root / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n")
    _run("git", "init", "-q", cwd=root)
    _run("git", "add", "test_calculator.py", ".gitignore", cwd=root)
    _run("git", "-c", "user.name=CI Fixture",
         "-c", "user.email=ci-fixture@example.invalid",
         "commit", "-qm", "initial test", cwd=root)
    return roles, root


def test_actual_subprocess_git_and_pytest_pipeline(tmp_path):
    roles, root = _setup(tmp_path)
    assert run_tests(root, "pytest").status == "failed"
    fake_jcode = tmp_path / "fixture-jcode"
    fake_jcode.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys\n"
        "assert sys.argv[1:3] == ['run', '--no-update']\n"
        "prompt = sys.argv[3]\n"
        "if 'READ-ONLY PLANNING ONLY' in prompt:\n"
        "    print('Create calculator.py with add(a, b).')\n"
        "elif 'Implement the following approved-scope task' in prompt:\n"
        "    pathlib.Path('calculator.py').write_text("
        "'def add(a, b):\\n    return a + b\\n')\n"
        "    print('Implemented calculator.add')\n"
        "elif 'READ-ONLY REVIEW' in prompt:\n"
        "    assert pathlib.Path('calculator.py').exists()\n"
        "    print('Review: inspect the changes and accept only after independent review')\n"
        "else:\n"
        "    raise SystemExit(2)\n", encoding="utf-8")
    fake_jcode.chmod(0o755)
    report = execute_workflow(
        checkout=roles, workspace=root, task="Implement add(a, b)",
        executable=str(fake_jcode), test_suite="pytest")
    assert report["status"] == "candidate_for_human_review"
    assert [phase["status"] for phase in report["phases"]] == ["completed"] * 4
    assert report["human_approval_required"] is True
    assert report["committed"] is False and report["deployed"] is False
    assert (root / "calculator.py").read_text() == "def add(a, b):\n    return a + b\n"
    assert run_tests(root, "pytest").status == "completed"


def test_reviewer_content_mutation_is_detected_even_if_git_status_same(tmp_path):
    roles, root = _setup(tmp_path)
    # Start with a clean checkout and perform real filesystem writes by stub agents.
    calls = 0

    def agent(prompt):
        nonlocal calls
        calls += 1
        if calls == 1:
            return JcodeResult("completed", "Create calculator", "", 0)
        if calls == 2:
            (root / "calculator.py").write_text("def add(a, b):\n    return a + b\n")
            return JcodeResult("completed", "implemented", "", 0)
        assert calls == 3
        (root / "calculator.py").write_text("def add(a, b):\n    return a - b\n")
        return JcodeResult("completed", "looks good", "", 0)

    report = execute_workflow(
        checkout=roles, workspace=root, task="Implement add(a,b)", run_agent=agent,
        test_fn=lambda: (_ for _ in ()).throw(AssertionError("tests must not run")))
    assert report["status"] == "halted_review"
    assert calls == 3


def test_content_fingerprint_changes_on_untracked_edit(tmp_path):
    _, root = _setup(tmp_path)
    initial = git_fingerprint(root)
    file = root / "new.py"
    file.write_text("first")
    first = git_fingerprint(root)
    file.write_text("second")
    second = git_fingerprint(root)
    assert initial != first and first != second
