import io
import json
import pytest
from chimera.discovery import PROVIDERS, Provider, as_manifest, build_agents, discover
from chimera.fabric import Fabric, load_specs

class FakeResponse:
    def __init__(self, data): self.data = data
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def read(self, *_): return json.dumps(self.data).encode("utf-8")

def test_discovery_deduplicates_and_sorts(monkeypatch):
    monkeypatch.setattr("chimera.discovery.urlopen", lambda request, timeout: FakeResponse(
        {"data": [{"id": "z"}, {"id": "a"}, {"id": "z"}, {}, {"id": 1}]}))
    assert discover(PROVIDERS["ollama"]) == ["a", "z"]

def test_cloud_discovery_requires_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        discover(PROVIDERS["openrouter"])

def test_generation_is_bounded_and_opt_in(tmp_path):
    agents = build_agents(PROVIDERS["ollama"], [str(i) for i in range(100)], max_agents=5)
    assert len(agents) == 5
    assert all(not agent.enabled for agent in agents)
    p = tmp_path / "agents.json"
    p.write_text(as_manifest(agents), encoding="utf-8")
    assert len(load_specs(p)) == 5

def test_remote_plaintext_discovery_is_refused():
    unsafe = Provider("unsafe", "http://example.com/v1/models",
                      "https://example.com/v1/chat/completions")
    with pytest.raises(ValueError, match="HTTPS"):
        discover(unsafe)

def test_invalid_registration_limits():
    with pytest.raises(ValueError, match="between"):
        build_agents(PROVIDERS["ollama"], ["test"], max_agents=10000)

def test_enabled_workers_need_verifier_to_accept():
    agents = build_agents(PROVIDERS["ollama"], ["model-a", "model-b"], enabled=True)
    class Stub:
        def __init__(self, spec, budget): self.budget = budget
        def answer(self, task):
            assert self.budget.claim()
            return "ok"
    result = Fabric(agents, endpoint_factory=Stub).run("hello")
    assert result["status"] == "unverified"
