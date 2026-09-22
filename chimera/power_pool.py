"""Generate the broadest authorized Chimera council from live provider catalogs.

No credentials are embedded. Cloud agents activate only when --activate-cloud is
given AND the corresponding environment variable exists. max=0 means no Chimera
registration cap; provider/account/hardware limits still apply.
"""
from __future__ import annotations
import argparse
import json
import os
from urllib.request import Request, urlopen
from dataclasses import asdict, replace
from pathlib import Path

from .discovery import PROVIDERS, discover
from .fabric import AgentSpec, load_specs


DEFAULT_PROVIDERS = (
    "ollama", "vllm", "openrouter", "huggingface",
    "nvidia", "groq", "cerebras",
)
LOCAL = {"ollama", "vllm"}


def power_discover(provider_name: str) -> list[str]:
    """Prefer OpenRouter's live intelligence ordering; normal discovery elsewhere."""
    cfg = PROVIDERS[provider_name]
    if provider_name != "openrouter":
        return discover(cfg)
    key = os.environ.get(cfg.key_env, "")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")
    request = Request(
        cfg.models_url + "?sort=intelligence-high-to-low&output_modalities=text",
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json"})
    with urlopen(request, timeout=12) as response:
        body = json.load(response)
    rows = body.get("data") if isinstance(body, dict) else None
    if not isinstance(rows, list):
        raise ValueError("Unexpected OpenRouter model catalog")
    # Preserve provider ranking while deduplicating.
    return list(dict.fromkeys(
        row["id"] for row in rows
        if isinstance(row, dict) and isinstance(row.get("id"), str) and row["id"].strip()
    ))


def _enabled(provider: str, activate_cloud: bool) -> bool:
    cfg = PROVIDERS[provider]
    if provider in LOCAL:
        return True
    return bool(activate_cloud and cfg.key_env and os.environ.get(cfg.key_env))


def build_power_pool(*, providers=DEFAULT_PROVIDERS, activate_cloud=False,
                     max_per_provider=0, max_total=0, include_fusion=True,
                     discover_fn=None):
    if max_per_provider < 0 or max_total < 0:
        raise ValueError("limits must be >= 0; zero means no Chimera registration cap")
    specs, report = [], []
    for provider_name in dict.fromkeys(providers):
        if provider_name not in PROVIDERS:
            raise ValueError(f"Unknown provider: {provider_name}")
        cfg = PROVIDERS[provider_name]
        try:
            ids = (discover_fn(cfg) if discover_fn is not None else power_discover(provider_name))
            if max_per_provider:
                ids = ids[:max_per_provider]
            if max_total:
                ids = ids[:max(0, max_total - len(specs))]
            enabled = _enabled(provider_name, activate_cloud)
            for index, model in enumerate(ids):
                spec = AgentSpec(
                    name=f"{provider_name}-{index:05d}", provider=provider_name,
                    model=model, base_url=cfg.completions_url, key_env=cfg.key_env,
                    role="worker", enabled=enabled)
                spec.validate()
                specs.append(spec)
            report.append({"provider": provider_name, "discovered": len(ids),
                           "enabled": enabled, "credential_present":
                           bool(not cfg.key_env or os.environ.get(cfg.key_env))})
            if max_total and len(specs) >= max_total:
                break
        except (OSError, RuntimeError, ValueError, KeyError, json.JSONDecodeError) as exc:
            report.append({"provider": provider_name, "discovered": 0,
                           "status": "unavailable", "error_type": type(exc).__name__})

    # OpenRouter Fusion is a compound multi-model deliberation endpoint. It is
    # intentionally used only as a synthesizer and only when cloud activation is explicit.
    if (include_fusion and activate_cloud and os.environ.get("OPENROUTER_API_KEY")
            and (not max_total or len(specs) < max_total)):
        fusion = AgentSpec(
            name="openrouter-fusion-synthesizer", provider="openrouter",
            model="openrouter/fusion",
            base_url=PROVIDERS["openrouter"].completions_url,
            key_env="OPENROUTER_API_KEY", role="synthesizer", enabled=True)
        fusion.validate()
        specs.append(fusion)

    enabled_workers = [i for i, s in enumerate(specs) if s.enabled and s.role == "worker"]
    # If Fusion is unavailable, reserve a distinct enabled model as synthesizer.
    if not any(s.enabled and s.role == "synthesizer" for s in specs) and len(enabled_workers) >= 2:
        idx = enabled_workers.pop()
        specs[idx] = replace(specs[idx], role="synthesizer")

    # Reserve up to 3 verifier models, preferring provider diversity and never
    # reusing the synthesizer model. This is quality control, not a truth guarantee.
    synth_models = {s.model for s in specs if s.enabled and s.role == "synthesizer"}
    candidates = [(i, s) for i, s in enumerate(specs)
                  if s.enabled and s.role == "worker" and s.model not in synth_models]
    chosen, seen_providers = [], set()
    for i, s in reversed(candidates):
        if s.provider not in seen_providers:
            chosen.append(i)
            seen_providers.add(s.provider)
        if len(chosen) == 3:
            break
    for i in chosen:
        specs[i] = replace(specs[i], role="verifier")

    return specs, report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build maximum authorized Chimera council")
    parser.add_argument("--providers", nargs="+", choices=sorted(PROVIDERS),
                        default=list(DEFAULT_PROVIDERS))
    parser.add_argument("--activate-cloud", action="store_true")
    parser.add_argument("--max-per-provider", type=int, default=0,
                        help="0 = register every discovered model")
    parser.add_argument("--max-total", type=int, default=0,
                        help="0 = no Chimera registration cap")
    parser.add_argument("--no-fusion", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("configs/power_agents.json"))
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output exists; refusing to overwrite runtime configuration")
    specs, report = build_power_pool(
        providers=tuple(args.providers), activate_cloud=args.activate_cloud,
        max_per_provider=args.max_per_provider, max_total=args.max_total,
        include_fusion=not args.no_fusion)
    if not specs:
        print(json.dumps({"created": False, "providers": report}, indent=2))
        raise SystemExit(1)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"agents": [asdict(s) for s in specs]}, indent=2) + "\n")
    load_specs(args.output)
    print(json.dumps({
        "created": True, "path": str(args.output), "registered": len(specs),
        "enabled": sum(s.enabled for s in specs),
        "workers": sum(s.enabled and s.role == "worker" for s in specs),
        "verifiers": sum(s.enabled and s.role == "verifier" for s in specs),
        "synthesizers": sum(s.enabled and s.role == "synthesizer" for s in specs),
        "providers": report,
    }, indent=2))


if __name__ == "__main__":
    main()
