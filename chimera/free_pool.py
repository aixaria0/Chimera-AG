"""Conservative, credential-safe discovery of no-per-token-price model slots.

Local models are runnable only if an operator has started the local service.
OpenRouter models are considered free only if the provider's catalog explicitly
advertises zero prompt AND completion pricing and a :free model ID.
Provider free-tier quotas and eligibility are separate concerns.
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.error
from dataclasses import asdict
from pathlib import Path
from urllib.request import Request, urlopen

from .discovery import PROVIDERS
from .fabric import AgentSpec, load_specs


LOCAL_PROVIDERS = ("ollama", "vllm")


def _catalog(provider: str, *, timeout: float = 10) -> list[dict]:
    if provider not in ("openrouter", *LOCAL_PROVIDERS):
        raise ValueError("This catalog is not certified for free-only discovery")
    cfg = PROVIDERS[provider]
    key = os.environ.get(cfg.key_env, "") if cfg.key_env else ""
    if cfg.key_env and not key:
        raise RuntimeError(f"{cfg.key_env} is not configured")
    headers = {"Accept": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    with urlopen(Request(cfg.models_url, headers=headers), timeout=timeout) as response:
        result = json.load(response)
    if not isinstance(result, dict) or not isinstance(result.get("data"), list):
        raise ValueError("Unexpected provider model-list response")
    return [row for row in result["data"] if isinstance(row, dict)]


def _zero_price(value: object) -> bool:
    # Missing, malformed, negative or unknown pricing is NOT free.
    try:
        from decimal import Decimal, InvalidOperation
        parsed = Decimal(str(value))
        return parsed.is_finite() and parsed == 0
    except (ValueError, TypeError, InvalidOperation):
        return False


def is_free_openrouter_model(record: dict) -> bool:
    model = record.get("id")
    pricing = record.get("pricing")
    if not isinstance(model, str) or not (model.endswith(":free") or model == "openrouter/free"):
        return False
    if not isinstance(pricing, dict):
        return False
    return _zero_price(pricing.get("prompt")) and _zero_price(pricing.get("completion"))


def free_model_ids(provider: str, rows: list[dict]) -> list[str]:
    if provider not in ("openrouter", *LOCAL_PROVIDERS):
        raise ValueError("Unsupported provider")
    if provider == "openrouter":
        return sorted({row["id"] for row in rows if is_free_openrouter_model(row)})
    return sorted({row["id"] for row in rows
                   if isinstance(row.get("id"), str) and row["id"].strip()})


def make_pool(*, providers: tuple[str, ...] = ("ollama", "vllm", "openrouter"),
              max_per_provider: int = 128, max_total: int = 256,
              enable_local: bool = True, enable_cloud: bool = False,
              query=_catalog) -> tuple[list[AgentSpec], list[dict]]:
    if not (1 <= max_per_provider <= 512 and 1 <= max_total <= 1024):
        raise ValueError("Registration limits must be between 1 and 512/1024")
    specs: list[AgentSpec] = []
    report: list[dict] = []
    for name in providers:
        if name not in ("openrouter", *LOCAL_PROVIDERS):
            raise ValueError(f"Not a free-verified discovery provider: {name}")
        try:
            rows = query(name)
            ids = free_model_ids(name, rows)
            available = max(0, max_total - len(specs))
            selected = ids[:min(max_per_provider, available)]
            cfg = PROVIDERS[name]
            for index, model in enumerate(selected):
                spec = AgentSpec(
                    name=f"{name}-{index:04d}", provider=name, model=model,
                    base_url=cfg.completions_url, key_env=cfg.key_env,
                    role="worker",
                    enabled=(enable_local if name in LOCAL_PROVIDERS else enable_cloud),
                )
                spec.validate()
                specs.append(spec)
            report.append({"provider": name, "advertised": len(rows),
                           "eligible": len(ids), "registered": len(selected),
                           "enabled": bool(enable_local if name in LOCAL_PROVIDERS else enable_cloud)})
        except (OSError, RuntimeError, ValueError, KeyError, json.JSONDecodeError) as exc:
            # Never include exception body: urllib exceptions may contain remote content.
            report.append({"provider": name, "registered": 0,
                           "status": "unavailable", "error_type": type(exc).__name__})
    # Reserve one verifier using a distinct model; never count it as a worker.
    if len({s.model for s in specs}) >= 2:
        from dataclasses import replace
        for i in range(len(specs) - 1, -1, -1):
            chosen = specs[i]
            if chosen.enabled and any(s.enabled and s.model != chosen.model
                                      for j, s in enumerate(specs) if j != i):
                specs[i] = replace(chosen, role="verifier")
                break
    return specs, report


def run_cli() -> None:
    parser = argparse.ArgumentParser(description="Discover local and explicitly zero-priced model slots")
    parser.add_argument("--providers", nargs="+", choices=["ollama", "vllm", "openrouter"],
                        default=["ollama", "vllm", "openrouter"])
    parser.add_argument("--max-per-provider", type=int, default=128)
    parser.add_argument("--max-total", type=int, default=256)
    parser.add_argument("--output", type=Path, default=Path("configs/free_agents.json"))
    parser.add_argument("--enable-cloud", action="store_true",
                        help="Explicitly opt into provider-limited cloud requests")
    parser.add_argument("--disable-local", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output exists: refusing to replace an operator-managed manifest")
    specs, report = make_pool(
        providers=tuple(dict.fromkeys(args.providers)),
        max_per_provider=args.max_per_provider, max_total=args.max_total,
        enable_local=not args.disable_local, enable_cloud=args.enable_cloud)
    if not specs:
        print(json.dumps({"created": False, "providers": report}, indent=2))
        raise SystemExit(1)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"agents": [asdict(spec) for spec in specs]}, indent=2) + "\n",
        encoding="utf-8")
    load_specs(args.output)
    print(json.dumps({"created": True, "path": str(args.output),
                      "registered": len(specs), "enabled": sum(s.enabled for s in specs),
                      "providers": report}, indent=2))


if __name__ == "__main__":
    run_cli()
