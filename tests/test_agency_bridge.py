import subprocess
from pathlib import Path
import pytest
from chimera.agency_bridge import load_role, list_roles, compose_prompt, run_jcode


def sample(tmp_path):
    root = tmp_path / "agency"
    (root / "engineering").mkdir(parents=True)
    (root / "engineering" / "engineering-code-reviewer.md").write_text(
        "---\nname: Code Reviewer\ndescription: Reviews code\n---\n"
        "Check correctness, security and tests.\n", encoding="utf-8")
    return root


def test_role_discovery_and_prompt(tmp_path):
    root = sample(tmp_path)
    assert list_roles(root) == ["engineering/engineering-code-reviewer.md"]
    role = load_role(root, "engineering/engineering-code-reviewer.md")
    assert role.name == "Code Reviewer"
    assert "Check correctness" in compose_prompt(role, "Review the diff")


def test_reject_escape_and_symlink(tmp_path):
    root = sample(tmp_path)
    with pytest.raises(ValueError):
        load_role(root, "../secret.md")
    external = tmp_path / "outside.md"
    external.write_text("---\nname: X\ndescription: X\n---\nHello")
    (root / "engineering" / "engineering-escape.md").symlink_to(external)
    with pytest.raises(ValueError):
        load_role(root, "engineering/engineering-escape.md")


def test_jcode_invocation_is_explicit_and_shell_free(tmp_path):
    captured = {}
    def fake_runner(args, **kwargs):
        captured["args"], captured["kwargs"] = args, kwargs
        return subprocess.CompletedProcess(args, 0, stdout="OK", stderr="")
    result = run_jcode("Audit this", workspace=tmp_path, runner=fake_runner)
    assert result.status == "completed"
    assert captured["args"] == ["jcode", "run", "--no-update", "Audit this"]
    assert captured["kwargs"]["cwd"] == str(tmp_path.resolve())
    assert "shell" not in captured["kwargs"]


def test_jcode_missing_and_timeout(tmp_path):
    def missing(*args, **kwargs):
        raise FileNotFoundError("missing")
    def timed(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="jcode", timeout=1)
    assert run_jcode("Task", workspace=tmp_path, runner=missing).status == "missing_executable"
    assert run_jcode("Task", workspace=tmp_path, runner=timed).status == "timeout"


def test_invalid_task_and_role(tmp_path):
    root = sample(tmp_path)
    with pytest.raises(ValueError):
        load_role(root, "engineering/../../LICENSE")
    role = load_role(root, "engineering/engineering-code-reviewer.md")
    with pytest.raises(ValueError):
        compose_prompt(role, "")
