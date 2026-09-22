"""Paired live single-model versus Council measurements using the product backend.

No mocks or fixed model outputs: each arm calls actual installed Ollama weights.
Only directly measured facts (answer, abstention, latency, token totals) are
reported; a tiny fixture is not a claim of intelligence superiority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from .product import OllamaBackend
from .product_integrations import run_live_council


def read_suite(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("Benchmark must be a nonempty JSON task list")
    ids = set()
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"id", "prompt", "expected"}:
            raise ValueError("Every task must contain exactly id, prompt and expected")
        if any(not isinstance(item[k], str) or not item[k].strip()
               for k in ("id", "prompt", "expected")):
            raise ValueError("Task values must be nonempty strings")
        if item["id"] in ids or len(item["prompt"]) > 2000:
            raise ValueError("Duplicate ID or oversized prompt")
        ids.add(item["id"])
    return raw


def _answer_text(text: str) -> str:
    return " ".join(text.casefold().strip().split())


def measure(backend: OllamaBackend, tasks: list[dict], *,
            models: list[str] | None = None) -> dict:
    """Run a paired suite without changing prompts, reference labels or weights."""
    installed = backend.installed()
    if backend.model not in installed:
        raise ValueError("Benchmark model not installed")
    if not tasks:
        raise ValueError("Empty benchmark suite")
    results = []
    for row in tasks:
        if set(row) != {"id", "prompt", "expected"}:
            raise ValueError("Invalid task")
        start = time.monotonic()
        try:
            single = backend.chat([{"role": "user", "content": row["prompt"]}])
            single_record = {
                "status": "completed", "answer": single["reply"],
                "generated_tokens": single.get("eval_count"),
                "exact_match": _answer_text(single["reply"]) == _answer_text(row["expected"]),
                "model": single["model"],
            }
        except Exception as exc:
            single_record = {"status": "failed", "error_type": type(exc).__name__,
                             "answer": None, "exact_match": False,
                             "generated_tokens": None}
        single_record["latency_ms"] = round((time.monotonic() - start) * 1000)
        start = time.monotonic()
        try:
            council = run_live_council(backend, row["prompt"], requested_models=models)
            candidate = council.get("reply")
            council_record = {
                "status": council["status"],
                "answer": candidate,
                "exact_match": (isinstance(candidate, str) and
                                _answer_text(candidate) == _answer_text(row["expected"])),
                "accepted_exact_match": (
                    council["status"] == "accepted" and isinstance(candidate, str) and
                    _answer_text(candidate) == _answer_text(row["expected"])),
                "verified_by_independent_model": council.get(
                    "verified_by_independent_model", False),
                "generated_tokens": sum(x["generated_tokens"]
                                        for x in council.get("trace", [])
                                        if isinstance(x.get("generated_tokens"), int)),
                "requests_used": council["requests_used"],
                "models": council.get("models"),
            }
        except Exception as exc:
            council_record = {"status": "failed", "error_type": type(exc).__name__,
                              "answer": None, "exact_match": False,
                              "accepted_exact_match": False,
                              "generated_tokens": None}
        council_record["latency_ms"] = round((time.monotonic() - start) * 1000)
        results.append({"task_id": row["id"], "expected": row["expected"],
                        "single": single_record, "council": council_record})
    n = len(results)
    return {
        "kind": "paired_real_model_inference", "tasks": n,
        "model": backend.model,
        "single_exact_matches": sum(bool(x["single"]["exact_match"]) for x in results),
        "council_candidate_exact_matches": sum(bool(x["council"]["exact_match"]) for x in results),
        "council_accepted_exact_matches": sum(bool(x["council"]["accepted_exact_match"]) for x in results),
        "council_abstentions": sum(x["council"]["status"] != "accepted" for x in results),
        "note": ("A descriptive benchmark of these specific tasks and weights only. "
                 "Model agreement is not proof of correctness; token counts are not billed cost. "
                 "No automatic model promotion."),
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Paired real-model Chimera evaluation")
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ollama-host", default="http://127.0.0.1:11434")
    parser.add_argument("--model", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({"status": "dry_run", "real_inference_calls": 0}))
        return
    if args.output.exists():
        parser.error("Refusing to overwrite an existing benchmark report")
    tasks = read_suite(args.suite)
    backend = OllamaBackend(args.ollama_host, args.model)
    report = measure(backend, tasks)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(json.dumps({"report": str(args.output), "tasks": report["tasks"],
                      "single_exact_matches": report["single_exact_matches"],
                      "council_candidate_exact_matches": report["council_candidate_exact_matches"],
                      "council_accepted_exact_matches": report["council_accepted_exact_matches"],
                      "council_abstentions": report["council_abstentions"]}))


if __name__ == "__main__":
    main()
