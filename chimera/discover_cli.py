"""Discover a provider's current catalog and generate opt-in agent configuration."""
import argparse
import json
from pathlib import Path
from .discovery import PROVIDERS, discover, build_agents, as_manifest
from .fabric import load_specs


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover models; create bounded Chimera manifest")
    parser.add_argument("--providers", nargs="+", choices=sorted(PROVIDERS), default=["ollama"])
    parser.add_argument("--output", type=Path, default=Path("configs/agents.json"))
    parser.add_argument("--max-agents-per-provider", type=int, default=32)
    parser.add_argument("--activate", action="store_true",
                        help="Explicitly enable discovered models; cloud calls can cost money")
    parser.add_argument("--model-contains", default="",
                        help="Filter IDs (case-insensitive); empty means all returned models")
    parser.add_argument("--verifier-provider", choices=sorted(PROVIDERS),
                        help="Reserve one discovered model from this provider as verifier")
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"Output already exists: {args.output}; refusing to overwrite configured models")
    entries, summaries, errors = [], [], {}
    for name in args.providers:
        provider = PROVIDERS[name]
        try:
            advertised = discover(provider)
            matches = [model for model in advertised if args.model_contains.lower() in model.lower()]
            workers = build_agents(provider, matches, max_agents=args.max_agents_per_provider,
                                   enabled=args.activate, name_prefix=name)
            if args.verifier_provider == name and len(workers) > 1:
                verifier = workers.pop()
                workers.append(type(verifier)(name=verifier.name, provider=verifier.provider,
                    model=verifier.model, base_url=verifier.base_url,
                    key_env=verifier.key_env, role="verifier", enabled=verifier.enabled))
            entries.extend(workers)
            summaries.append({"provider": name, "advertised": len(advertised),
                              "matched": len(matches), "registered": len(workers)})
        except (RuntimeError, ValueError, OSError, KeyError) as exc:
            # Do not print raw provider HTTP errors: URLs may carry account-specific context.
            errors[name] = type(exc).__name__
    if not entries:
        print(json.dumps({"created": False, "providers": summaries, "errors": errors}, indent=2))
        raise SystemExit(1)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(as_manifest(entries), encoding="utf-8")
    load_specs(args.output)
    print(json.dumps({"created": True, "path": str(args.output),
        "agents": len(entries), "enabled": args.activate,
        "providers": summaries, "errors": errors}, indent=2))


if __name__ == "__main__":
    main()
