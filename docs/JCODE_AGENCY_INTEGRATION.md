# Chimera v0.7 — Agency Agents × jcode

This is a **working, opt-in integration bridge**, not a claim that Chimera bundles jcode or that every Agency Agents role has been trained or evaluated. The upstream repositories remain independent.

**Sources and attribution:** [1jehuang/jcode](https://github.com/1jehuang/jcode), copyright 2025 Jeremy Huang (MIT); [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents), copyright 2025 AgentLand Contributors (MIT). Chimera does not copy either codebase or its prompt library into this repository. The bridge reads their role files at runtime from a separately obtained, trusted local Agency Agents checkout and invokes an installed jcode binary. Retain upstream licenses when redistributing either project.

## Capability

Agency Agents supplies Markdown-based specialist prompts grouped by division. The bridge scans every one-level `division/agent.md` file matching the upstream naming convention, parses the role name/description/body, and makes it selectable. It does **not** limit you to a hard-coded list of roles; roles added upstream become available when you update the local checkout. The prompt is assembled for an explicitly selected specialist.

jcode supplies an independent coding-agent runtime with `jcode run --no-update <prompt>`. This bridge uses it as an external coding executor in an explicitly specified local workspace. It does not vendor or reimplement jcode's Rust code, terminals, tools, provider integrations, or UI.

## Setup

Install jcode and configure its model providers according to its own documentation. Clone Agency Agents and Chimera to your local machine, respecting their licenses:

```bash
git clone https://github.com/msitarzewski/agency-agents.git
git clone https://github.com/aixaria0/Chimera-AG.git
cd Chimera-AG
python -m pip install -e '.[test]'
pytest -q
chimera-agency --agency-checkout ../agency-agents --list-roles
```

Preview one specialist task without running any coding agent or making provider calls:

```bash
chimera-agency --agency-checkout ../agency-agents \
  --role engineering/engineering-code-reviewer.md \
  --task 'Review this project for correctness and test gaps.'
```

Run only after reviewing your jcode permissions, provider configuration, workspace and the role's contents:

```bash
chimera-agency --agency-checkout ../agency-agents \
  --role engineering/engineering-code-reviewer.md \
  --task 'Review this repository and propose a minimal patch.' \
  --workspace . --execute
```

This command can invoke jcode tools and modify workspace files, depending on its own configuration. Run in a disposable clone or reviewed worktree; inspect the diff, execute tests, and approve commits yourself. The bridge does not grant jcode repository credentials, disable upstream protections, execute model-produced shell commands, or start background autonomous processes. `--execute` is required and missing jcode is reported explicitly. Run the command on your authorized local machine; the GitHub connector does not install or run jcode for you.

## Suggested structured workflow

Choose **Backend Architect** or **Multi-Agent Systems Architect** to plan the change, **Senior Developer** for implementation, and **Code Reviewer** for verification. Re-run the command for each selected role; no unattended multi-agent loop or real code-quality gain is claimed. Chimera's existing measured routing and paired benchmark modules can be used independently to assess changes, but are **not yet wired into this jcode bridge**.

## Security and reproducibility

Only choose roles from a trusted checkout. Role text is instructions to an AI model, **not an authorization grant**. Do not put API tokens, credentials or sensitive benchmark labels in role files or task prompts. Keep jcode's native permissions and provider usage limits enabled. Record the upstream commit of both repos for reproducible experiments. No remote download, silent auto-update, role execution, GitHub push, or automated PR merge is performed by the bridge.
