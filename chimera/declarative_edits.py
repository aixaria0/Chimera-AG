"""Apply a strictly bounded, operator-authorized file creation from real jcode output.

A local LLM may emit a JSON representation of a tool call rather than calling
jcode's tool. This opt-in compatibility adapter creates ONE preapproved file;
it cannot overwrite, remove, execute or choose new paths by itself.
"""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

NAME_RE = re.compile(r"^[a-zA-Z0-9_][a-zA-Z0-9_./-]{0,159}$")
FENCE_RE = re.compile(r"\x60\x60\x60(?:json)?\s*\n(.*?)\n\x60\x60\x60", re.DOTALL | re.IGNORECASE)
SUFFIXES = frozenset({".py", ".txt", ".md", ".json"})
MAX_CONTENT = 4096


def _read_write_intent(output: str) -> dict | None:
    """Only an explicit single JSON object with name=write qualifies."""
    fences = FENCE_RE.findall(output)
    if len(fences) > 1:
        return None
    raw = fences[0] if fences else output.strip()
    if len(raw) > MAX_CONTENT * 2:
        return None
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict) or value.get("name") != "write":
        return None
    args = value.get("arguments")
    if not isinstance(args, dict):
        return None
    if set(args) not in ({"file_path", "content"}, {"file_path", "content", "intent"}):
        return None
    return args


def apply_authorized_creation(
    root: Path, model_output: str, *, allowed_paths: frozenset[str],
) -> dict | None:
    """Create one NEW allowlisted relative file. Returns evidence or None.

    The parent folder must already exist. Reject symlinks, paths under hidden
    metadata directories, unapproved target names and any overwrite attempt.
    """
    args = _read_write_intent(model_output)
    if args is None:
        return None
    filename = args.get("file_path")
    content = args.get("content")
    if (not isinstance(filename, str) or filename not in allowed_paths
            or not NAME_RE.fullmatch(filename) or
            not isinstance(content, str) or not content
            or len(content.encode("utf-8")) > MAX_CONTENT or "\x00" in content):
        return None
    relative = PurePosixPath(filename)
    if (relative.is_absolute() or ".." in relative.parts or "." in relative.parts
            or any(part.startswith(".") for part in relative.parts)
            or relative.suffix not in SUFFIXES):
        return None
    workspace = root.resolve(strict=True)
    target = workspace.joinpath(*relative.parts)
    if target.exists() or target.is_symlink():
        return None
    try:
        parent = target.parent.resolve(strict=True)
    except (FileNotFoundError, OSError):
        return None
    if parent != workspace and workspace not in parent.parents:
        return None
    if not parent.is_dir():
        return None
    try:
        with target.open("x", encoding="utf-8") as output:
            output.write(content)
    except FileExistsError:
        return None
    return {"path": filename, "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "bytes": len(content.encode("utf-8")),
            "source": "actual_jcode_model_output",
            "operation": "operator_allowlisted_new_file_only",
            "human_approval_required": True}


def is_unexecuted_write_intent(output: str) -> bool:
    return _read_write_intent(output) is not None
