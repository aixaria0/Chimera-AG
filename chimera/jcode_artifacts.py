"""Real jcode as a code generator; Chimera is the constrained file writer.

This bridge does not rely on the LLM successfully invoking native jcode tools.
It requests content from a real jcode/model session in a SEPARATE ephemeral
workspace, extracts only the proposed bytes, and writes them to the exact
operator-selected NEW path inside a clean Git project. Real pytest/cargo tests
then decide if the artifact is a reviewable candidate.
"""
from __future__ import annotations

import hashlib
import json
import re
import tempfile
import time
from pathlib import Path, PurePosixPath

from .agency_bridge import compose_prompt, load_role, run_jcode
from .coding_workflow import git_fingerprint, git_snapshot, run_tests

FENCE = re.compile(r"```(?:json|python|text|markdown|md)?\s*\n(.*?)\n```", re.I | re.S)
RESULT_LIMIT = 32_768
CONTENT_LIMIT = 16_384
ALLOWED_EXTENSIONS = frozenset({".py", ".txt", ".md", ".json", ".rs"})


def extract_artifact(stdout: str) -> str:
    """Extract a single file's content; never obey the model's suggested path."""
    if not isinstance(stdout, str) or len(stdout) > RESULT_LIMIT * 2:
        raise ValueError("Output missing or too large")
    blocks = FENCE.findall(stdout)
    if len(blocks) > 1:
        raise ValueError("Ambiguous multi-block model output")
    candidate = blocks[0] if blocks else re.split(
        r"\n\[Tokens\]\s+upload:", stdout.strip(), maxsplit=1)[0].strip()
    try:
        instruction = json.loads(candidate)
    except (ValueError, TypeError):
        instruction = None
    if isinstance(instruction, dict):
        if instruction.get("name", instruction.get("function")) not in ("write", "create_file"):
            raise ValueError("Unsupported model instruction")
        arguments = instruction.get("arguments")
        if not isinstance(arguments, dict):
            raise ValueError("Missing content arguments")
        candidate = arguments.get("content")
        if not isinstance(candidate, str):
            raise ValueError("Model did not provide file content")
    if not isinstance(candidate, str) or not candidate or len(candidate.encode("utf-8")) > CONTENT_LIMIT:
        raise ValueError("Missing or oversized artifact content")
    if "\x00" in candidate:
        raise ValueError("Binary output is unsupported")
    return candidate


def _target_path(workspace: Path, requested: str) -> Path:
    if not isinstance(requested, str) or len(requested) > 160 or "\\" in requested:
        raise ValueError("Invalid target")
    relative = PurePosixPath(requested)
    if (relative.is_absolute() or not relative.parts or
            any(p in ("", ".", "..") or p.startswith(".") for p in relative.parts) or
            relative.suffix not in ALLOWED_EXTENSIONS):
        raise ValueError("Only new, operator-chosen relative source files are allowed")
    root = workspace.resolve(strict=True)
    target = root.joinpath(*relative.parts)
    if target.exists() or target.is_symlink():
        raise ValueError("Target already exists or is a symlink")
    parent = target.parent.resolve(strict=True)
    if not parent.is_dir() or (parent != root and root not in parent.parents):
        raise ValueError("Target parent must exist inside workspace")
    return target


def generate_and_test(*, workspace: Path, checkout: Path, task: str,
                      target: str, role: str = "engineering/engineering-senior-developer.md",
                      executable: str = "jcode", test_suite: str = "pytest",
                      timeout: int = 300) -> dict:
    """One real jcode generation; one exact new target; fixed real test command."""
    if not isinstance(task, str) or not task.strip() or len(task) > 6000:
        raise ValueError("Task must be 1–6000 characters")
    if not isinstance(timeout, int) or not 1 <= timeout <= 900:
        raise ValueError("Invalid jcode timeout")
    root = workspace.resolve(strict=True)
    if git_snapshot(root).strip():
        raise ValueError("The target Git workspace must be clean")
    target_path = _target_path(root, target)
    role_data = load_role(checkout, role)
    initial = git_fingerprint(root)
    # Distinct scratch space: jcode may decide to call tools there, but it
    # never receives the path to the operator's actual project workspace.
    with tempfile.TemporaryDirectory(prefix="chimera-jcode-content-") as scratch:
        scratch_root = Path(scratch)
        prompt = compose_prompt(
            role_data,
            "Generate the COMPLETE UTF-8 CONTENT of ONE file for this task. "
            "No shell command, no interactive operations, no placeholders. "
            "Return only the file content or one JSON write instruction with a "
            "content string. The file name is controlled by the operator and "
            "any file_path in your response will be ignored.\n"
            "FILE TYPE: " + target_path.suffix + "\nTASK: " + task,
        )
        started = time.monotonic()
        outcome = run_jcode(prompt, workspace=scratch_root, executable=executable,
                            timeout=timeout)
        elapsed_ms = round((time.monotonic() - started) * 1000)
    base = {"generator": "real_upstream_jcode", "status": outcome.status,
            "generation_ms": elapsed_ms, "target": target,
            "content_sha256": None, "tests_passed": False,
            "human_approval_required": True, "committed": False, "deployed": False}
    if outcome.status != "completed":
        return base
    try:
        content = extract_artifact(outcome.stdout)
    except ValueError:
        return {**base, "status": "invalid_model_artifact"}
    # Stop on unexpected concurrent workspace edits; do not let model output
    # choose filenames or overwrite anything, even if it resembles a tool call.
    if git_fingerprint(root) != initial:
        return {**base, "status": "workspace_changed_during_generation"}
    try:
        with target_path.open("x", encoding="utf-8") as file:
            file.write(content)
    except FileExistsError:
        return {**base, "status": "target_was_created_concurrently"}
    evidence = hashlib.sha256(content.encode("utf-8")).hexdigest()
    tested = run_tests(root, test_suite, timeout=300)
    # If it fails, do NOT auto-delete the actual model artifact; the user may
    # inspect the failure and choose to retry from a new clean worktree.
    return {**base,
            "status": ("candidate_for_human_review" if tested.status == "completed"
                       else "failed_tests"),
            "content_sha256": evidence, "bytes": len(content.encode("utf-8")),
            "tests_passed": tested.status == "completed",
            "test_status": tested.status, "test_returncode": tested.returncode,
            "test_output_preview": tested.stdout[-4000:],
            "original_model_output_sha256": hashlib.sha256(
                outcome.stdout.encode("utf-8")).hexdigest()}
