import json
import pytest
from chimera.experiment import read_suite, run_suite
from chimera.fabric import AgentSpec
from chimera.council import Council


def agent(name, role):
    return AgentSpec(name, "fake", name,
        "http://127.0.0.1:1/v1/chat/completions", role=role, enabled=True)


class Stub:
    def __init__(self, spec, budget):
        self.spec, self.budget = spec, budget

    def answer(self, prompt):
        assert self.budget.claim()
        if self.spec.name == "broken":
            raise RuntimeError("provider unavailable")
        if self.spec.role == "verifier":
            return "APPROVE"
        return "yes"


def test_paired_runner_uses_identical_task_ids():
    agents = [agent("base", "worker"), agent("synth", "synthesizer"),
              agent("verify", "verifier")]
    council = Council(agents, endpoint_factory=Stub)
    tasks = [{"id": "hold-1", "domain": "general", "prompt": "question",
              "expected": "yes"}]
    old, new, failures = run_suite(tasks, agents[0], council, baseline_factory=Stub)
    assert [r.task_id for r in old] == [r.task_id for r in new]
    assert old[0].answer == "yes"
    assert new[0].answer == "yes"
    assert old[0].requests == 1
    assert new[0].requests == 3
    assert failures == []


def test_missing_verifier_does_not_pass():
    agents = [agent("base", "worker"), agent("synth", "synthesizer"),
              agent("verify", "verifier"), agent("broken", "verifier")]
    result = Council(agents, endpoint_factory=Stub).run("question")
    assert result["status"] == "unverified"
    assert result["answer"] is None


def test_suite_checks_unique_ids_and_labels(tmp_path):
    path = tmp_path / "tasks.json"
    row = {"id": "1", "domain": "general", "prompt": "hello", "expected": "yes"}
    path.write_text(json.dumps([row, row]))
    with pytest.raises(ValueError, match="Duplicate"):
        read_suite(path)
    path.write_text(json.dumps([{"id": "1", "prompt": "hello"}]))
    with pytest.raises(ValueError, match="needs"):
        read_suite(path)
