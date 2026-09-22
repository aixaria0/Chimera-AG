import json
from pathlib import Path
from chimera.core import LocalAgent, Strategy, Task, eligible, evaluate, evolve, record_ledger

class FixedAgent:
    def __init__(self, output): self.output = output
    def answer(self, prompt): return self.output

def test_offline_fixture():
    tasks = [Task("1", "ANSWER: ok", "ok")]
    result = evaluate(tasks, Strategy("local"), LocalAgent(), None)
    assert result["accuracy"] == 1

def test_verifier_detects_disagreement():
    task = Task("1", "ANSWER: ok", "ok")
    result = evaluate([task], Strategy("hybrid", True, True), LocalAgent(), FixedAgent("wrong"))
    assert result["disagreements"] == 1

def test_gate_rejects_regression_and_ties():
    baseline = {"accuracy": 0.5, "disagreements": 0, "task_count": 2}
    assert not eligible({"accuracy": 0.5, "disagreements": 0, "task_count": 2}, baseline)
    assert not eligible({"accuracy": 1, "disagreements": 1, "task_count": 2}, baseline)
    assert eligible({"accuracy": 1, "disagreements": 0, "task_count": 2}, baseline)

def test_evolve_offline_does_not_claim_improvement(tmp_path):
    report = evolve([Task("1", "ANSWER: ok", "ok")], LocalAgent(), None, tmp_path / "ledger.jsonl")
    assert report["selected"] == "local_only"
    assert any(item["status"] == "skipped_no_cloud" for item in report["candidates"])

def test_ledger_chain(tmp_path):
    path = tmp_path / "ledger.jsonl"
    record_ledger(path, {"x": 1})
    record_ledger(path, {"x": 2})
    first, second = [json.loads(line) for line in path.read_text().splitlines()]
    assert first["previous"] == "0" * 64
    assert second["previous"] == first["hash"]
