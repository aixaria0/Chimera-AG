import pytest
from chimera.router import Observation, select_committee, model_stats
from chimera.fabric import AgentSpec
from chimera.evaluation import Outcome, score_outcomes, compare_heldout


def agent(name, provider="a", role="worker"):
    return AgentSpec(name=name, provider=provider, model=name,
        base_url="http://127.0.0.1:1/v1/chat/completions",
        role=role, enabled=True)


def observations(agent_name, domain, successes, total, latency=10, cost=0):
    return [Observation(agent_name, domain, i < successes, latency, cost)
            for i in range(total)]


def roster():
    return [agent("coder", "p1"), agent("researcher", "p2"),
            agent("unknown", "p3"), agent("synth", "p4", "synthesizer"),
            agent("verify", "p5", "verifier")]


def training():
    return (observations("coder", "coding", 5, 5)
            + observations("researcher", "coding", 1, 5)
            + observations("coder", "research", 0, 5)
            + observations("researcher", "research", 5, 5))


def test_domain_aware_selection_and_unknown_not_promoted():
    specs = roster()
    coding = select_committee(specs, training(), "coding", max_workers=1)
    research = select_committee(specs, training(), "research", max_workers=1)
    assert coding[0].name == "coder"
    assert research[0].name == "researcher"
    assert "unknown" not in {s.name for s in coding}


def test_unmeasured_domain_fails_closed():
    with pytest.raises(ValueError, match="No eligible"):
        select_committee(roster(), training(), "multilingual")


def test_cost_constraint_is_observation_based():
    records = (observations("coder", "coding", 5, 5, cost=1.0)
               + observations("researcher", "coding", 4, 5, cost=0.0))
    chosen = select_committee(roster(), records, "coding",
                              max_workers=1, max_estimated_cost_usd=0)
    assert chosen[0].name == "researcher"


def test_minimum_sample_count():
    with pytest.raises(ValueError, match="No eligible"):
        select_committee(roster(), observations("coder", "coding", 1, 1),
                         "coding", min_trials=3)


def test_heldout_gate_requires_strict_improvement_and_no_cost_regression():
    baseline = [Outcome("h1", "coding", "yes", "no", 1, 0, 20),
                Outcome("h2", "coding", "yes", "yes", 1, 0, 20)]
    candidate = [Outcome("h1", "coding", "yes", "yes", 2, 0, 30),
                 Outcome("h2", "coding", "yes", "yes", 2, 0, 30)]
    report = compare_heldout(baseline, candidate, {"training1"})
    assert report["eligible_for_review"]
    assert report["automatic_deployment"] is False
    assert not compare_heldout(baseline, [
        Outcome("h1", "coding", "yes", "yes", 2, 1, 30), candidate[1]
    ], {"training1"})["eligible_for_review"]


def test_pairing_and_leakage_guards():
    base = [Outcome("train", "reasoning", "x", "x", 1, 0, 10)]
    with pytest.raises(ValueError, match="overlap"):
        compare_heldout(base, base, {"train"})
    with pytest.raises(ValueError, match="same unique"):
        compare_heldout(base, [Outcome("different", "reasoning", "x", "x", 1, 0, 10)], set())


def test_empty_and_duplicate_outcomes_rejected():
    with pytest.raises(ValueError, match="Empty"):
        score_outcomes([])
    row = Outcome("same", "general", "x", "x", 1, 0, 1)
    with pytest.raises(ValueError, match="Duplicate"):
        score_outcomes([row, row])


def test_no_false_improvement_on_tie():
    row = Outcome("h", "general", "ok", "ok", 1, 0, 2)
    assert not compare_heldout([row], [row], set())["eligible_for_review"]
