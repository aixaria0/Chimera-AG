import json
import pytest
from chimera.discovery import PROVIDERS
from chimera.power_pool import build_power_pool
from chimera.fabric import load_specs


def fake_discover(provider):
    return [f"{provider.name}/model-a", f"{provider.name}/model-b",
            f"{provider.name}/model-c"]


def test_all_local_models_enabled_without_artificial_registration_cap():
    specs, report = build_power_pool(
        providers=("ollama", "vllm"), discover_fn=fake_discover)
    assert len(specs) == 6
    assert all(s.enabled for s in specs)
    assert sum(s.role == "synthesizer" for s in specs) == 1
    assert sum(s.role == "verifier" for s in specs) >= 1


def test_cloud_never_activates_without_explicit_flag(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-placeholder")
    specs, _ = build_power_pool(
        providers=("openrouter",), activate_cloud=False, discover_fn=fake_discover)
    assert specs
    assert not any(s.enabled for s in specs)


def test_cloud_activation_requires_runtime_credential(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    specs, report = build_power_pool(
        providers=("groq",), activate_cloud=True, discover_fn=fake_discover)
    assert specs
    assert not any(s.enabled for s in specs)


def test_openrouter_fusion_reserved_for_synthesis(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-placeholder")
    specs, _ = build_power_pool(
        providers=("openrouter",), activate_cloud=True, discover_fn=fake_discover)
    fusion = [s for s in specs if s.model == "openrouter/fusion"]
    assert len(fusion) == 1
    assert fusion[0].role == "synthesizer"
    assert fusion[0].enabled


def test_zero_limit_means_uncapped_registration():
    def many(provider):
        return [f"{provider.name}/{i}" for i in range(700)]
    specs, _ = build_power_pool(
        providers=("ollama",), max_per_provider=0, max_total=0, discover_fn=many)
    assert len(specs) == 700


def test_explicit_caps_still_work():
    specs, _ = build_power_pool(
        providers=("ollama", "vllm"), max_per_provider=2,
        max_total=3, discover_fn=fake_discover)
    assert len(specs) == 3


def test_new_provider_registry():
    for name in ("huggingface", "groq", "cerebras", "nvidia", "openrouter"):
        assert name in PROVIDERS
    assert PROVIDERS["cerebras"].discovery_requires_key is False
