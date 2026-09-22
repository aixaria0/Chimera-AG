import json
from pathlib import Path

from chimera.declarative_edits import apply_authorized_creation, is_unexecuted_write_intent


def tool_intent(name, content="approved"):
    return "```json\n" + json.dumps({
        "name": "write", "arguments": {"file_path": name, "content": content,
                                      "intent": "new file"}
    }) + "\n```\n[Tokens] upload: 100 download: 40"


def test_only_preapproved_new_file_is_created(tmp_path):
    evidence = apply_authorized_creation(
        tmp_path, tool_intent("ANSWER.txt", "real contents\n"),
        allowed_paths=frozenset({"ANSWER.txt"}))
    assert evidence["path"] == "ANSWER.txt"
    assert evidence["source"] == "actual_jcode_model_output"
    assert (tmp_path / "ANSWER.txt").read_text() == "real contents\n"
    assert apply_authorized_creation(
        tmp_path, tool_intent("ANSWER.txt", "overwrite"),
        allowed_paths=frozenset({"ANSWER.txt"})) is None
    assert (tmp_path / "ANSWER.txt").read_text() == "real contents\n"


def test_never_apply_unapproved_or_traversing_write(tmp_path):
    for path in ("../elsewhere.txt", ".git/config", "other.txt", "/tmp/elsewhere.txt"):
        assert apply_authorized_creation(
            tmp_path, tool_intent(path),
            allowed_paths=frozenset({path})) is None
    assert not (tmp_path / "other.txt").exists()


def test_no_shell_calls_multiple_objects_or_oversized_content(tmp_path):
    assert not is_unexecuted_write_intent('{"name":"shell","arguments":{"command":"pwd"}}')
    assert apply_authorized_creation(
        tmp_path, '{"name":"shell","arguments":{"command":"pwd"}}',
        allowed_paths=frozenset({"ANSWER.txt"})) is None
    assert apply_authorized_creation(
        tmp_path, tool_intent("ANSWER.txt", "x" * 4200),
        allowed_paths=frozenset({"ANSWER.txt"})) is None
    assert apply_authorized_creation(
        tmp_path, tool_intent("ANSWER.txt") + "\n" + tool_intent("ANSWER.txt"),
        allowed_paths=frozenset({"ANSWER.txt"})) is None


def test_symlink_parent_cannot_escape_allowlisted_workspace(tmp_path):
    outside = tmp_path.parent / "elsewhere"
    outside.mkdir(exist_ok=True)
    (tmp_path / "linked").symlink_to(outside, target_is_directory=True)
    assert apply_authorized_creation(
        tmp_path, tool_intent("linked/new.txt"),
        allowed_paths=frozenset({"linked/new.txt"})) is None
    assert not (outside / "new.txt").exists()
