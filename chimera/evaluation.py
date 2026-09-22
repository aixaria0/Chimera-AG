"""Leakage-aware evaluation of recorded baseline and routed-council outcomes.

All inputs must be obtained on the same held-out task IDs. No live API calls are
made here. Gate promotion only on measured accuracy without cost regression.
"""
from __future__ import annotations
import json
import math
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Outcome:
    task_id: str
    domain: str
    expected: str
    answer: str | None
    requests: int
    cost_usd: float
    latency_ms: float

    def validate(self):
        if not self.task_id or not self.domain or not isinstance(self.expected, str):
            raise ValueError("Outcome requires a task ID, domain and reference answer")
        if type(self.requests) is not int or self.requests < 0:
            raise ValueError("Invalid request count")
        if not all(math.isfinite(v) and v >= 0 for v in (self.cost_usd, self.latency_ms)):
            raise ValueError("Invalid cost/latency")


def score_outcomes(rows: list[Outcome]) -> dict:
    if not rows:
        raise ValueError("Empty held-out outcomes")
    for row in rows:
        row.validate()
    if len({row.task_id for row in rows}) != len(rows):
        raise ValueError("Duplicate held-out task IDs")
    correct = sum(row.answer is not None
                  and row.answer.strip() == row.expected.strip() for row in rows)
    return {
        "tasks": len(rows), "correct": correct,
        "accuracy": correct / len(rows),
        "requests": sum(row.requests for row in rows),
        "cost_usd": sum(row.cost_usd for row in rows),
        "mean_latency_ms": sum(row.latency_ms for row in rows) / len(rows),
    }


def compare_heldout(baseline: list[Outcome], candidate: list[Outcome],
                    training_task_ids: set[str], *, max_cost_increase_usd: float = 0.0,
                    min_accuracy_gain: float = 0.0) -> dict:
    if not baseline or not candidate:
        raise ValueError("Both evaluation arms are required")
    if max_cost_increase_usd < 0 or min_accuracy_gain < 0:
        raise ValueError("Thresholds must be nonnegative")
    left = {row.task_id: row for row in baseline}
    right = {row.task_id: row for row in candidate}
    if len(left) != len(baseline) or len(right) != len(candidate) or left.keys() != right.keys():
        raise ValueError("Both arms must have exactly the same unique held-out task IDs")
    if left.keys() & training_task_ids:
        raise ValueError("Held-out task IDs overlap with routing training tasks")
    for task_id, original in left.items():
        revised = right[task_id]
        if (original.domain, original.expected) != (revised.domain, revised.expected):
            raise ValueError("Evaluation arms have different task labels")
    old = score_outcomes(baseline)
    new = score_outcomes(candidate)
    # Accuracy must improve strictly, even when min_accuracy_gain is zero.
    promoted = (new["accuracy"] > old["accuracy"]
                and new["accuracy"] - old["accuracy"] >= min_accuracy_gain
                and new["cost_usd"] <= old["cost_usd"] + max_cost_increase_usd)
    return {"baseline": old, "candidate": new, "eligible_for_review": promoted,
            "automatic_deployment": False,
            "note": "Descriptive paired benchmark only; human approval required."}


def load_outcomes(path: Path) -> list[Outcome]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Expected outcome list")
    return [Outcome(**item) for item in data]
