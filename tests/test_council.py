from chimera.council import Council
from chimera.fabric import AgentSpec


def spec(name, role):
    return AgentSpec(name, "mock", name,
        "http://127.0.0.1:1/v1/chat/completions", role=role, enabled=True)


class Stub:
    answers = {}
    def __init__(self, spec, budget):
        self.spec, self.budget = spec, budget
    def answer(self, prompt):
        assert self.budget.claim()
        if self.spec.role == "synthesizer":
            return "synthesized answer"
        if self.spec.role == "verifier":
            return self.answers.get(self.spec.name, "APPROVE")
        return self.answers.get(self.spec.name, self.spec.name + " view")


def test_council_uses_all_workers_and_verifiers():
    specs = [spec("w1", "worker"), spec("w2", "worker"),
             spec("s", "synthesizer"), spec("v1", "verifier"),
             spec("v2", "verifier")]
    result = Council(specs, endpoint_factory=Stub).run("question")
    assert result["status"] == "accepted"
    assert len(result["worker_responses"]) == 2
    assert len(result["verifier_agreement"]) == 2
    assert result["requests_used"] == 5


def test_one_rejecting_verifier_blocks_acceptance():
    Stub.answers = {"v2": "REJECT"}
    specs = [spec("w", "worker"), spec("s", "synthesizer"),
             spec("v1", "verifier"), spec("v2", "verifier")]
    result = Council(specs, endpoint_factory=Stub).run("question")
    assert result["status"] == "unverified"
    assert result["answer"] is None
    assert result["candidate"] == "synthesized answer"
    Stub.answers = {}


def test_requires_synthesizer():
    try:
        Council([spec("w", "worker")], endpoint_factory=Stub)
        assert False
    except ValueError as exc:
        assert "synthesizer" in str(exc)
