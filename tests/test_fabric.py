import json
import threading
from pathlib import Path
import pytest
from chimera.fabric import AgentSpec, RequestBudget, Fabric, ChatEndpoint, load_specs

def spec(name, role="worker"):
    return AgentSpec(name, "mock", "mock-model", "http://127.0.0.1:1234/v1/chat/completions", role=role, enabled=True)

class Stub:
    def __init__(self, spec, budget, answers):
        self.spec, self.budget, self.answers = spec, budget, answers
    def answer(self, prompt):
        if not self.budget.claim():
            raise RuntimeError("budget exceeded")
        return self.answers[self.spec.name]

def make(answers, specs, cap=10):
    return Fabric(specs, max_workers=2, max_requests=cap,
                  endpoint_factory=lambda s, b: Stub(s, b, answers))

def test_majority_and_separate_verifier():
    result = make({"a": "YES", "b": "yes", "c": "no", "v": "Yes"},
                  [spec("a"), spec("b"), spec("c"), spec("v", "verifier")]).run("question")
    assert result["status"] == "accepted"
    assert result["answer"] == "yes"
    assert result["requests_used"] == 4

def test_tie_never_accepted():
    result = make({"a": "yes", "b": "no", "v": "yes"},
                  [spec("a"), spec("b"), spec("v", "verifier")]).run("question")
    assert result["status"] == "unverified"
    assert result["answer"] is None

def test_without_independent_verifier_is_unverified():
    result = make({"a": "ok"}, [spec("a")]).run("question")
    assert result["status"] == "unverified"

def test_verifier_can_reject_majority():
    result = make({"a": "ok", "v": "bad"},
                  [spec("a"), spec("v", "verifier")]).run("question")
    assert result["status"] == "unverified"

def test_budget_hard_cap():
    result = make({"a": "ok", "b": "ok", "v": "ok"},
                  [spec("a"), spec("b"), spec("v", "verifier")], cap=1).run("question")
    assert result["requests_used"] == 1
    assert result["status"] == "unverified"

def test_manifest_rejects_duplicate_names(tmp_path):
    p = tmp_path / "agents.json"
    p.write_text(json.dumps({"agents": [dict(name="x", provider="local", model="x",
                   base_url="http://127.0.0.1:1/v1/chat/completions", enabled=True)] * 2}))
    with pytest.raises(ValueError, match="unique"):
        load_specs(p)

def test_remote_http_rejected():
    with pytest.raises(ValueError, match="Plain HTTP"):
        spec("a").__class__("x", "remote", "model",
            "http://api.example.com/v1/chat/completions", enabled=True).validate()


def test_fusion_uses_general_high_and_required_tool(monkeypatch):
    captured = {}
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, *args): return b'{"choices":[{"message":{"content":"ok"}}]}'
    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data.decode())
        return Response()
    monkeypatch.setattr("chimera.fabric.urlopen", fake_urlopen)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-placeholder")
    s = AgentSpec("fusion", "openrouter", "openrouter/fusion",
        "https://openrouter.ai/api/v1/chat/completions",
        key_env="OPENROUTER_API_KEY", role="synthesizer", enabled=True)
    assert ChatEndpoint(s, RequestBudget(1)).answer("question") == "ok"
    assert captured["body"]["plugins"] == [{"id": "fusion", "preset": "general-high"}]
    assert captured["body"]["tool_choice"] == "required"
