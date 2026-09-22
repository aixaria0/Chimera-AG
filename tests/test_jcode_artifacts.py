import json
import subprocess
from pathlib import Path

import pytest

from chimera.jcode_artifacts import extract_artifact, generate_and_test


def _setup(tmp_path):
    checkout = tmp_path / "agency"
    role = checkout / "engineering" / "engineering-senior-developer.md"
    role.parent.mkdir(parents=True)
    role.write_text("---\nname: Developer\ndescription: Implement a task\n---\n"
                    "Write useful source code.\n", encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    (project / "test_output.py").write_text(
        "from pathlib import Path\n"
        "def test_output():\n"
        "    assert Path('a.txt').read_text().strip() == 'ok'\n")
    (project / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n")
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(["git", "add", "."], cwd=project, check=True)
    subprocess.run(["git", "-c", "user.name=CI", "-c", "user.email=ci@example.invalid",
                    "commit", "-qm", "initial"], cwd=project, check=True)
    return project, checkout


def test_real_format_artifact_extraction():
    output = ("```json\n" + json.dumps({
        "name": "write", "arguments": {"file_path": "todo.txt", "content": "ok",
                                       "intent": "create", "format": "markdown"}}) +
              "\n```\n[Tokens] upload: 2050 download: 38")
    assert extract_artifact(output) == "ok"
    assert extract_artifact("```text\nok\n```") == "ok"


def test_generated_output_never_controls_target_name(tmp_path, monkeypatch):
    project, checkout = _setup(tmp_path)
    def run_real_interface(prompt, *, workspace, executable, timeout):
        # This test exercises the artifact contract only. Live model evidence
        # comes from the separate real-jcode GitHub workflow.
        from chimera.agency_bridge import JcodeResult
        assert workspace != project
        return JcodeResult("completed", "```json\n" + json.dumps({
            "name": "write", "arguments": {"file_path": "../../escape.txt",
                                           "content": "ok"}}) + "\n```", "", 0)
    monkeypatch.setattr("chimera.jcode_artifacts.run_jcode", run_real_interface)
    report = generate_and_test(workspace=project, checkout=checkout,
                               target="a.txt", task="Create a.txt")
    assert report["status"] == "candidate_for_human_review"
    assert report["tests_passed"]
    assert (project / "a.txt").read_text() == "ok"
    assert not (tmp_path / "escape.txt").exists()
    assert report["human_approval_required"] and not report["committed"]


def test_reject_invalid_or_existing_target(tmp_path):
    project, checkout = _setup(tmp_path)
    for target in ("../escape.txt", "test_output.py", ".git/config", "/tmp/escape.txt"):
        with pytest.raises(ValueError):
            generate_and_test(workspace=project, checkout=checkout,
                              target=target, task="Test")


def test_dirty_target_rejected_before_running_model(tmp_path):
    project, checkout = _setup(tmp_path)
    (project / "dirty.txt").write_text("dirty")
    with pytest.raises(ValueError, match="clean"):
        generate_and_test(workspace=project, checkout=checkout,
                          target="a.txt", task="Test")


def test_empty_and_multiple_outputs_rejected():
    for text in ("", "```json\n{}\n```",
                 "```text\none\n```\n```text\ntwo\n```"):
        with pytest.raises(ValueError):
            extract_artifact(text)
