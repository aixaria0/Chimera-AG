"""Offline, credential-free free-pool tests. No provider network calls."""
import json
from dataclasses import replace
from chimera.free_pool import free_model_ids, is_free_openrouter_model, make_pool, _zero_price
from chimera.fabric import load_specs


def test_price_requires_both_zero_and_free_id():
    assert is_free_openrouter_model({"id": "vendor/model:free",
        "pricing": {"prompt": "0", "completion": "0"}})
    assert not is_free_openrouter_model({"id": "vendor/model:free",
        "pricing": {"prompt": "0", "completion": "0.00001"}})
    assert not is_free_openrouter_model({"id": "vendor/model:free", "pricing": {}})
    assert not is_free_openrouter_model({"id": "vendor/model",
        "pricing": {"prompt": "0", "completion": "0"}})
    assert is_free_openrouter_model({"id": "openrouter/free",
        "pricing": {"prompt": "0", "completion": "0"}})
    assert not _zero_price(None)
    assert not _zero_price("NaN")
    assert not _zero_price("-0.01")


def test_filters_cloud_catalog_conservatively():
    records = [
        {"id": "vendor/paid", "pricing": {"prompt": "1", "completion": "1"}},
        {"id": "vendor/free:free", "pricing": {"prompt": "0", "completion": "0"}},
        {"id": "vendor/unknown:free"},
    ]
    assert free_model_ids("openrouter", records) == ["vendor/free:free"]


def test_local_models_opt_in_and_verifier(tmp_path):
    def catalog(provider):
        if provider == "ollama":
            return [{"id": "model-a"}, {"id": "model-b"}, {"id": "model-c"}]
        return []
    specs, report = make_pool(
        providers=("ollama",), max_per_provider=2, max_total=2, query=catalog)
    assert len(specs) == 2
    assert {s.role for s in specs} == {"worker", "verifier"}
    assert all(s.enabled for s in specs)
    manifest = tmp_path / "agents.json"
    manifest.write_text(json.dumps({"agents": [vars(s) for s in specs]}))
    assert len(load_specs(manifest)) == 2


def test_cloud_is_disabled_by_default(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-only-placeholder")
    def catalog(provider):
        return [{"id": "a:free", "pricing": {"prompt": "0", "completion": "0"}},
                {"id": "b:free", "pricing": {"prompt": "0", "completion": "0"}}]
    specs, report = make_pool(providers=("openrouter",), query=catalog)
    assert len(specs) == 2
    assert not any(s.enabled for s in specs)
    assert not any(s.role == "verifier" for s in specs)


def test_never_calls_unavailable_cloud_and_reports_status():
    def catalog(provider):
        raise RuntimeError("no provider connection")
    specs, report = make_pool(providers=("openrouter",), query=catalog)
    assert specs == []
    assert report[0]["status"] == "unavailable"
    assert "no provider connection" not in json.dumps(report)


def test_pool_has_hard_registration_cap():
    def catalog(provider):
        return [{"id": f"local-{i}"} for i in range(100)]
    specs, report = make_pool(providers=("ollama",), max_per_provider=50,
                              max_total=7, query=catalog)
    assert len(specs) == 7
