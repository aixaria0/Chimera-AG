# Chimera v0.8 — End-to-end specialist coding

Chimera now composes the external [Agency Agents](https://github.com/msitarzewski/agency-agents) specialist prompts with the independently installed [jcode](https://github.com/1jehuang/jcode) coding runtime into a four-phase workflow: **plan → implement → review → test**. The bridge uses upstream content from an explicitly provided local checkout; it does not vendor either MIT-licensed upstream project, replace jcode's permission controls, or silently install binaries.

## Setup

On a machine where jcode is installed and configured for models you are authorized to use, clone Agency Agents and Chimera, then install Chimera:

```bash
git clone https://github.com/msitarzewski/agency-agents.git
git clone https://github.com/aixaria0/Chimera-AG.git
cd Chimera-AG
python -m pip install -e '.[test]'
pytest -q
```

Use a **clean, disposable, reviewed Git worktree** as the coding workspace. The command refuses a workspace with tracked modifications or untracked files. Keep the Agency Agents checkout separate from the target worktree.

Preview role selection without invoking jcode:

```bash
chimera-code --agency-checkout ../agency-agents \
  --workspace . --task 'Implement a small, independently testable improvement.'
```

After reviewing the task, chosen role files, model credentials and jcode permissions, explicitly execute:

```bash
chimera-code --agency-checkout ../agency-agents \
  --workspace . --task 'Implement a small, independently testable improvement.' \
  --test-suite pytest --execute
```

For a Rust target repository choose `--test-suite cargo`, which uses `cargo test --locked --offline`. The Python test option invokes `python -m pytest -q`. Tests run as local processes; a malicious or untrusted test suite can execute code, so run this workflow only in a trusted or independently isolated workspace.

The default specialist assignments are **Software Architect** (plan), **Senior Developer** (implement), and **Code Reviewer** (review), all from Agency Agents. Each can be replaced using `--planner`, `--implementer`, or `--reviewer` with a valid relative role file, such as `engineering/engineering-multi-agent-systems-architect.md`. The agency catalog does not need to be copied into Chimera and can be upgraded independently.

## Failure gates and evidence

The planner and reviewer phases are expected to be read-only: changes after either cause an immediate halt. The implementation phase must produce a Git working-tree change. Each stage must finish successfully. If the reviewer step fails, alters files, or the test suite fails, the workflow stops and reports the outcome. A successful review *process exit* is not proof that a review found no defects. The operator must inspect the review text and Git diff and approve the change; Chimera does not commit, push, deploy or merge on its own.

The workflow reports per-stage status, runtime and output digests. It includes bounded output previews, which may contain task/model text; avoid passing secrets as tasks and avoid publishing raw reports from sensitive environments. This is an integration foundation, not a measured claim of superior coding performance or a fully isolated sandbox.

## Reproducibility

For meaningful comparisons, record the Agency Agents commit, installed jcode version, Chimera commit, model/provider ID, task specification, fixed test suite and initial Git tree. Compare with the existing `chimera-experiment` and `chimera-benchmark` tooling only after capturing independently labeled held-out results and actual provider costs.
