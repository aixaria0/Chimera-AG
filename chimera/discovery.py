"""Opt-in provider model discovery and bounded worker manifest generation.

Discovery is not activation: a model listed by an API may still require access,
be unavailable, or have a charge. No credentials are stored in manifests.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .fabric import AgentSpec


@dataclass(frozen=True)
class Provider:
    name: str
    models_url: str
    completions_url: str
    key_env: str = ""


PROVIDERS = {
    "openrouter": Provider(
        "openrouter", "https://openrouter.ai/api/v1/models",
        "https://openrouter.ai/api/v1/chat/completions", "OPENROUTER_API_KEY"),
    "nvidia": Provider(
        "nvidia", "https://integrate.api.nvidia.com/v1/models",
        "https://integrate.api.nvidia.com/v1/chat/completions", "NVIDIA_API_KEY"),
    "ollama": Provider(
        "ollama", "http://127.0.0.1:11434/v1/models",
        "http://127.0.0.1:11434/v1/chat/completions"),
    "vllm": Provider(
        "vllm", "http://127.0.0.1:8000/v1/models",
        "http://127.0.0.1:8000/v1/chat/completions"),
}


def discover(provider: Provider, *, timeout: float = 12.0) -> list[str]:
    """Read only the provider's advertised model IDs; never infer entitlement."""
    url = urlparse(provider.models_url)
    if url.scheme != "https" and not (
        url.scheme == "http" and url.hostname in ("localhost", "127.0.0.1", "::1")
    ):
        raise ValueError("Discovery URL must use HTTPS or loopback HTTP")
    key = os.getenv(provider.key_env) if provider.key_env else None
    if provider.key_env and not key:
        raise RuntimeError(f"Missing {provider.key_env}; cannot discover {provider.name}")
    headers = {"Accept": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    with urlopen(Request(provider.models_url, headers=headers), timeout=timeout) as response:
        body = json.load(response)
    if not isinstance(body, dict) or not isinstance(body.get("data"), list):
        raise ValueError("Model discovery response must contain a data list")
    models = []
    for item in body["data"]:
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"].strip():
            models.append(item["id"])
    return sorted(set(models))


def build_agents(provider: Provider, models: list[str], *,
                 max_agents: int = 64, enabled: bool = False,
                 role: str = "worker", name_prefix: str | None = None) -> list[AgentSpec]:
    if not (1 <= max_agents <= 512):
        raise ValueError("max_agents must be between 1 and 512")
    if role not in ("worker", "verifier"):
        raise ValueError("Unsupported role")
    if enabled and provider.key_env and not os.getenv(provider.key_env):
        raise RuntimeError(f"Cannot enable {provider.name} without {provider.key_env}")
    prefix = name_prefix or provider.name
    agents = []
    for index, model in enumerate(sorted(set(models))[:max_agents]):
        if not model.strip():
            continue
        candidate = AgentSpec(
            name=f"{prefix}-{index:03d}", provider=provider.name,
            model=model, base_url=provider.completions_url,
            key_env=provider.key_env, role=role, enabled=enabled)
        candidate.validate()
        agents.append(candidate)
    return agents


def as_manifest(agents: list[AgentSpec]) -> str:
    if len({agent.name for agent in agents}) != len(agents):
        raise ValueError("Duplicate agent names")
    return json.dumps({"agents": [asdict(agent) for agent in agents]}, indent=2) + "\n"
