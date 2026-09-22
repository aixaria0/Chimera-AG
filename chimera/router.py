"""Task-aware committee selection from *training-only* agent observations.

This router is a deterministic policy over explicitly measured outcomes, not a
language-model capability predictor. Unknown agents receive no fabricated score.
"""
from __future__ import annotations
import json
import math
from dataclasses import dataclass
from pathlib import Path
from .fabric import AgentSpec

DOMAINS = frozenset({"coding", "reasoning", "research", "multilingual", "long_context", "general"})


@dataclass(frozen=True)
class Observation:
    agent: str
    domain: str
    correct: bool
    latency_ms: float
    cost_usd: float = 0.0

    def validate(self):
        if not self.agent or self.domain not in DOMAINS:
            raise ValueError("Unknown agent or task domain")
        if not isinstance(self.correct, bool):
            raise ValueError("correct must be a boolean")
        if not all(math.isfinite(x) and x >= 0 for x in (self.latency_ms, self.cost_usd)):
            raise ValueError("Invalid latency/cost")


def load_observations(path: Path) -> list[Observation]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Expected a list of observations")
    result = [Observation(**row) for row in data]
    for item in result:
        item.validate()
    return result


def model_stats(observations: list[Observation], domain: str) -> dict[str, dict]:
    """Training data only. Domain-specific Laplace-smoothed correctness estimates."""
    if domain not in DOMAINS:
        raise ValueError("Unknown domain")
    grouped: dict[str, list[Observation]] = {}
    for observation in observations:
        observation.validate()
        if observation.domain == domain:
            grouped.setdefault(observation.agent, []).append(observation)
    return {
        name: {"trials": len(rows),
               "successes": sum(r.correct for r in rows),
               "estimated_accuracy": (sum(r.correct for r in rows) + 1) / (len(rows) + 2),
               "mean_latency_ms": sum(r.latency_ms for r in rows) / len(rows),
               "mean_cost_usd": sum(r.cost_usd for r in rows) / len(rows)}
        for name, rows in grouped.items()
    }


def select_committee(specs: list[AgentSpec], observations: list[Observation],
                     domain: str, *, max_workers: int = 3,
                     latency_weight: float = 0.0, cost_weight: float = 0.0,
                     min_trials: int = 3, max_estimated_cost_usd: float | None = None) -> list[AgentSpec]:
    """Pick measured worker models; preserve existing synthesizer/verifier assignments.

    Unknown or under-sampled workers never displace a measured candidate.
    The cost cap is an *estimate* from training observations, not a spend guard.
    """
    if domain not in DOMAINS or max_workers < 1 or min_trials < 1:
        raise ValueError("Invalid routing options")
    if not all(math.isfinite(v) and v >= 0 for v in (latency_weight, cost_weight)):
        raise ValueError("Weights must be nonnegative and finite")
    if max_estimated_cost_usd is not None and (not math.isfinite(max_estimated_cost_usd)
                                             or max_estimated_cost_usd < 0):
        raise ValueError("Invalid estimated-cost cap")
    stats = model_stats(observations, domain)
    enabled = [s for s in specs if s.enabled]
    workers = [s for s in enabled if s.role == "worker"]
    others = [s for s in enabled if s.role != "worker"]
    if not any(s.role == "synthesizer" for s in others) or not any(s.role == "verifier" for s in others):
        raise ValueError("Routing requires an enabled synthesizer and verifier")
    candidates = []
    for s in workers:
        entry = stats.get(s.name)
        if entry is None or entry["trials"] < min_trials:
            continue
        score = (entry["estimated_accuracy"]
                 - latency_weight * entry["mean_latency_ms"]
                 - cost_weight * entry["mean_cost_usd"])
        candidates.append((score, s, entry))
    # Deterministic across manifest order. Prefer provider/model diversity when
    # scores are equal; never count cloned deployments of the same model twice.
    candidates.sort(key=lambda item: (-item[0], item[1].provider, item[1].model, item[1].name))
    chosen = []
    distinct_models = set()
    spent = 0.0
    for _, s, entry in candidates:
        if (s.provider, s.model) in distinct_models:
            continue
        projected = spent + entry["mean_cost_usd"]
        if max_estimated_cost_usd is not None and projected > max_estimated_cost_usd:
            continue
        chosen.append(s)
        distinct_models.add((s.provider, s.model))
        spent = projected
        if len(chosen) == max_workers:
            break
    if not chosen:
        raise ValueError("No eligible measured workers: collect training observations first")
    return chosen + others
