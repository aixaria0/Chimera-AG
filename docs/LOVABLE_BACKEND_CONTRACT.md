# Chimera v0.13 — Backend contract for the future Lovable UI

The current browser is a replaceable client. The existing Python service remains
the backend, so a future Lovable frontend can connect **without reimplementing
model inference or jcode**.

## Existing endpoints

The local server exposes `GET /api/health`, `GET /api/models`, and
`GET /api/features`. `POST /api/chat` takes `{"messages":[{"role":"user","content":"..."}]}`.
`POST /api/council` accepts the same message structure and optional
`"models":["installed-model-name"]`. These perform genuine Ollama inference
when installed models are ready.

`POST /api/code` is disabled unless the machine operator explicitly enables
coding mode and provides the local trusted source worktree and actual jcode
binary. Its request is `{"task":"bounded task","confirm":true}`; the server
requires the explicit browser-intent header and local same-origin access. This
endpoint is **not a public remote-execution API**. Never embed a jcode tool,
file-path control, provider secret, or arbitrary shell command in the frontend.

## Lovable integration boundary

Build a frontend that calls these endpoints only through an authenticated,
operator-managed same-origin gateway. Keep inference, model credentials, local
file access, Git permissions, and all agent execution on the backend. Do not
publish the local jcode host to the internet. A Lovable-hosted interface can be
connected after its concrete project URL and hosting arrangement are provided
and an authenticated proxy is configured. A third-party hosted frontend alone
does not authorize cross-origin coding execution.

Display each actual agent role, selected installed model, generated-token
count, verifier result, and explicit unverified/error state from the Council
response. Distinguish a genuine local coding task from a plan or model-produced
unexecuted tool text. Display the actual Git diff and independent test results
before any human decision to commit. Never render a green badge from the model
statement 'success' alone.

## Real comparison instruments

`chimera-repeat-eval` repeatedly compares the single-model and Council
endpoints on a fixed user-provided labeled suite, recording per-task real
responses, paired disagreements, abstentions, token totals and latency. It is
NOT an intelligence leaderboard; the two-question smoke suite is only a wiring
check. Broader performance claims require separately curated, held-out,
domain-diverse tasks, repeated runs, and analysis of paired measurements.

`chimera-real-code-pair` invokes an actual installed jcode on independent
same-commit Git worktrees for the baseline and the specialist Council workflow.
`chimera-code-eval` compares direct jcode repository editing against the
separate real-jcode constrained-artifact path. Those arms have different
permissions, so record that difference when interpreting their test results.
The operator chooses clean source repos, prewritten acceptance tests, and an
isolated host. No generated changes are auto-committed or deployed.

The existing green GitHub real-model and real-jcode smoke tests prove that
local model generation and a bounded file-generation acceptance test run.
They do not establish general software-development competence or model
superiority. Use stronger independently written tasks and a larger model
when the compute is available.
