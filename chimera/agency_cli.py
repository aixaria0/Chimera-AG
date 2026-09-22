"""Local Agency Agents + jcode workflow. No installation or execution by default."""
import argparse
import json
from pathlib import Path
from .agency_bridge import list_roles, load_role, compose_prompt, run_jcode


def main():
    parser = argparse.ArgumentParser(description="Agency role catalog and jcode coding workflow")
    parser.add_argument("--agency-checkout", type=Path, required=True,
                        help="Trusted local clone of msitarzewski/agency-agents")
    parser.add_argument("--list-roles", action="store_true")
    parser.add_argument("--role", help="Division/file.md path from --list-roles")
    parser.add_argument("--task", help="Task for the selected specialist")
    parser.add_argument("--workspace", type=Path,
                        help="Explicit, trusted local coding workspace")
    parser.add_argument("--jcode", default="jcode", help="Installed jcode executable")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--execute", action="store_true",
                        help="Opt in to running jcode; it may modify workspace files")
    args = parser.parse_args()
    if args.list_roles:
        print(json.dumps({"roles": list_roles(args.agency_checkout)}, indent=2))
        return
    if not args.role or not args.task:
        parser.error("Provide --role and --task or use --list-roles")
    role = load_role(args.agency_checkout, args.role)
    prompt = compose_prompt(role, args.task)
    if not args.execute:
        print(json.dumps({"status": "dry_run", "role": role.identifier,
                          "role_name": role.name, "prompt": prompt,
                          "jcode_invoked": False}, indent=2))
        return
    if args.workspace is None:
        parser.error("--execute requires --workspace")
    result = run_jcode(prompt, workspace=args.workspace,
                       executable=args.jcode, timeout=args.timeout)
    print(json.dumps({"role": role.identifier, "status": result.status,
                      "returncode": result.returncode,
                      "stdout": result.stdout, "stderr": result.stderr}, indent=2))
    if result.status != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
