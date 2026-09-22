# Chimera v0.9 — reproducible coding comparison

This milestone replaces a simulated-only orchestration claim with **real local subprocess + Git + pytest integration tests** and adds a **paired coding benchmark**: one specialist coding agent versus Chimera's plan → implement → review → test council on **two independent local clones of the identical clean Git commit**.

The GitHub CI integration test invokes a deliberately fake jcode executable. It exercises actual subprocesses, isolated temporary Git repositories and real pytest execution, but **no live language model**. Only a local operator with installed jcode and configured models can run the genuine comparison.

## Run a real paired comparison locally

Install jcode using its official project instructions and configure it with models you are authorized to use. Clone Agency Agents separately. Prepare a **trusted, clean Git repository with a fixed, independently written test suite**; neither arm can start from a dirty tree.

```bash
python -m pip install -e '.[test]'

# Preview does not start an agent.
chimera-code-compare \
  --source /path/to/trusted-clean-task-repo \
  --agency-checkout /path/to/agency-agents \
  --task 'Implement a specific small change described in the prewritten tests' \
  --output experiments/paired-code-report.json

# Deliberately opt into model requests and local code execution.
chimera-code-compare \
  --source /path/to/trusted-clean-task-repo \
  --agency-checkout /path/to/agency-agents \
  --task 'Implement a specific small change described in the prewritten tests' \
  --test-suite pytest \
  --output experiments/paired-code-report.json --execute
```

The command creates two local Git clones of the source at the same HEAD, runs the implementation specialist once in one clone, and runs the three specialist phases plus fixed tests in the other. It records per-arm process outcomes, tests passed, runtime, invocations, the common revision and a paired pass/fail difference. It does not alter the source repository, merge a PR, or deploy code. Temporary clones are removed when the command exits. A source repo with uncommitted/untracked files is rejected.

**A passing test suite is not a proof of code quality or general model superiority.** This runner does not yet measure token usage, actual billing, comparable provider latency, benchmark difficulty or stochastic variance. The report marks superiority and cost evidence as unproven. Repeat tasks and models using privately retained independent test cases before drawing comparative conclusions.

## Security and test integrity

Run against a project whose tests you trust, or inside an independently provisioned isolated execution environment. Tests are executable code; fixed command selection alone does not make untrusted tests safe. The jcode runtime may edit local workspaces and use your configured model credentials; do not run it against a sensitive source tree or send secrets as tasks. Rotate any credentials previously shared in chats.

The workflow now fingerprints actual tracked changes and untracked file content during read-only planning/review. The former Git-status-only check could miss a modified file changing again without changing its `M filename` status. The fingerprint check is a stronger guard but is not an OS sandbox or process isolation.

## Upstream

[Agency Agents](https://github.com/msitarzewski/agency-agents) provides local specialist role definitions; [jcode](https://github.com/1jehuang/jcode) supplies the separately installed coding runtime. Both are MIT-licensed upstream projects. The Chimera integration does not bundle them or bypass their own account and permission requirements.
