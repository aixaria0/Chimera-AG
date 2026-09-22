"""Repeat real Ollama comparisons with an external, independently labeled suite.

This evaluator measures paired exact-match success, abstention, latency and
generated token usage. It never routes results into automatic model promotion.
The caller provides a separate held-out suite; the bundled smoke is NOT evidence
of general intelligence gains.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

from .live_benchmark import measure, read_suite
from .product import OllamaBackend


def summarize(runs: list[dict]) -> dict:
    if not runs:
        raise ValueError("At least one genuine run is required")
    rows = [row for report in runs for row in report["results"]]
    n = len(rows)
    return {
        "pairs": n,
        "runs": len(runs),
        "single_exact_match": sum(bool(row["single"]["exact_match"]) for row in rows),
        "council_candidate_exact_match": sum(bool(row["council"]["exact_match"]) for row in rows),
        "council_accepted_exact_match": sum(bool(row["council"]["accepted_exact_match"]) for row in rows),
        "council_abstentions": sum(row["council"]["status"] != "accepted" for row in rows),
        "paired_single_only": sum(bool(row["single"]["exact_match"]) and
                                  not bool(row["council"]["exact_match"]) for row in rows),
        "paired_council_only": sum(not bool(row["single"]["exact_match"]) and
                                  bool(row["council"]["exact_match"]) for row in rows),
        "single_latency_median_ms": statistics.median(
            row["single"]["latency_ms"] for row in rows),
        "council_latency_median_ms": statistics.median(
            row["council"]["latency_ms"] for row in rows),
        "single_generated_tokens": sum(
            row["single"]["generated_tokens"] or 0 for row in rows),
        "council_generated_tokens": sum(
            row["council"]["generated_tokens"] or 0 for row in rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Repeated real Ollama paired comparisons")
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--ollama-host", default="http://127.0.0.1:11434")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.repeats <= 20:
        parser.error("Repeats must be between 1 and 20")
    if not args.execute:
        print(json.dumps({"status": "dry_run", "repeats": args.repeats,
                          "model_requests": 0}))
        return
    if args.output.exists():
        parser.error("Refusing to overwrite an existing evaluation report")
    if args.suite.resolve() == args.output.resolve():
        parser.error("Suite cannot be the report output")
    tasks = read_suite(args.suite)
    raw = args.suite.read_bytes()
    backend = OllamaBackend(args.ollama_host, args.model)
    reports = [measure(backend, tasks) for _ in range(args.repeats)]
    result = {
        "kind": "repeated_real_paired_evaluation",
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "suite_sha256": hashlib.sha256(raw).hexdigest(),
        "suite_size": len(tasks),
        "model": args.model,
        "repeats": args.repeats,
        "summary": summarize(reports),
        "runs": reports,
        "limitations": [
            "Exact-match labels can reject correct paraphrases and reward accidental matches.",
            "Repeated calls to one model are not independent cross-model validation.",
            "No inference about general performance from a tiny smoke suite.",
            "Latency depends on machine load, cached model weights, and scheduling.",
            "Token usage is not billed cost; there is no automatic model promotion.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({"status": "recorded", "report": str(args.output),
                      "summary": result["summary"]}))


if __name__ == "__main__":
    main()
