"""Connect the existing Council and coding workflow to live product backends.

Council worker/synthesis/verifier calls are actual Ollama inference requests, not
fabricated agent strings. Reusing one model does NOT constitute independent
verification; the API reports that limitation explicitly.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path
from urllib.parse import urlparse

from .agency_bridge import load_role
from .council import Council
from .fabric import AgentSpec, RequestBudget

# Role names and task framing are local defaults, not falsely attributed verbatim
# quotations from Agency Agents. If its checkout is mounted, use actual role text.
LOCAL_ROLES = {
    "planner": "Decompose the task, identify assumptions, and present a reasoned solution.",
    "engineer": "Solve the task using concrete technical reasoning; identify edge cases.",
    "critic": "Independently question unsupported assumptions and propose corrections.",
    "synthesizer": "Reconcile candidate responses; produce one useful answer with uncertainty.",
    "verifier": "Check the candidate against the task. Return only APPROVE or REJECT.",
}
AGENCY_ROLE_IDS = {
    "planner": "engineering/engineering-software-architect.md",
    "engineer": "engineering/engineering-ai-engineer.md",
    "critic": "engineering/engineering-code-reviewer.md",
    "synthesizer": "engineering/engineering-multi-agent-systems-architect.md",
    "verifier": "engineering/engineering-code-reviewer.md",
}


def _instruction(role: str, checkout: Path | None) -> str:
    if checkout is None:
        return LOCAL_ROLES[role]
    guidance = load_role(checkout, AGENCY_ROLE_IDS[role]).instructions
    # A role prompt is a guiding persona, not permission to use tools or exfiltrate.
    tail = (" Return only APPROVE or REJECT; give no explanation." if role == "verifier" else "")
    return guidance[:6000] + "\nDo not execute code, tools or external actions." + tail


class OllamaCouncilEndpoint:
    """Adapter implementing Council's ChatEndpoint contract via Ollama /api/chat."""
    def __init__(self, spec: AgentSpec, budget: RequestBudget, *,
                 backend, instruction: str, trace: list, trace_lock):
        self.spec = spec
        self.budget = budget
        self.backend = backend
        self.instruction = instruction
        self.trace = trace
        self.trace_lock = trace_lock

    def answer(self, prompt: str) -> str:
        if not self.budget.claim():
            raise RuntimeError("Council request budget exhausted")
        result = self.backend.chat([
            {"role": "system", "content": self.instruction},
            {"role": "user", "content": prompt},
        ], model=self.spec.model, max_predict=96)
        with self.trace_lock:
            self.trace.append({"agent": self.spec.name, "model": self.spec.model,
                               "generated_tokens": result.get("eval_count"),
                               "done": result.get("done")})
        return result["reply"]


def run_live_council(backend, task: str, *, checkout: Path | None = None,
                     requested_models: list[str] | None = None) -> dict:
    """Make four live calls (two workers, synthesizer, verifier) to real Ollama.

    Optional selected model list must be installed. A user with three or more
    distinct installed models gets real cross-model synthesis/verification.
    """
    if not isinstance(task, str) or not task.strip() or len(task) > 6000:
        raise ValueError("Council task must contain 1–6000 characters")
    installed = backend.installed()
    if backend.model not in installed:
        raise ValueError("Default Ollama model is not installed")
    models = requested_models or [backend.model]
    if not isinstance(models, list) or not 1 <= len(models) <= 4:
        raise ValueError("Choose between 1 and 4 installed models")
    if any(not isinstance(name, str) or name not in installed for name in models):
        raise ValueError("Council models must be installed in Ollama")
    # Prefer distinct model identities when enough distinct local weights exist.
    worker_one = models[0]
    worker_two = models[1] if len(models) > 1 else models[0]
    synthesis_model = models[2] if len(models) > 2 else models[0]
    verifier_model = models[3] if len(models) > 3 else (models[-1] if len(models) > 1 else models[0])
    roles = (
        ("planner", "worker", worker_one),
        ("engineer", "worker", worker_two),
        ("synthesizer", "synthesizer", synthesis_model),
        ("verifier", "verifier", verifier_model),
    )
    specs = [AgentSpec(
        name=name, provider="ollama", model=model,
        base_url=backend.endpoint + "/api/chat", role=role, enabled=True,
    ) for name, role, model in roles]
    instructions = {name: _instruction(name, checkout) for name, _, _ in roles}
    trace = []
    trace_lock = threading.Lock()
    council = Council(
        specs, max_workers=2,
        endpoint_factory=lambda spec, budget: OllamaCouncilEndpoint(
            spec, budget, backend=backend, instruction=instructions[spec.name],
            trace=trace, trace_lock=trace_lock),
    )
    report = council.run(task)
    # Model agreement only; never call a reused model an independent verifier.
    independent = verifier_model not in {worker_one, worker_two, synthesis_model}
    candidate = report.get("candidate")
    if report["status"] == "failed":
        return {"status": "failed", "reply": None, "candidate": None,
                "error_types": sorted({str(v).split(":", 1)[0]
                                       for v in report.get("errors", {}).values()}),
                "requests_used": report["requests_used"], "trace": trace}
    return {
        "status": report["status"],
        "reply": candidate,  # Expose unverified candidates, visibly tagged as such.
        "verified_by_independent_model": independent and report["status"] == "accepted",
        "candidate": candidate,
        "model": synthesis_model,
        "models": {name: model for name, _, model in roles},
        "worker_responses": report["worker_responses"],
        "verifier_agreement": report["verifier_agreement"],
        "requests_used": report["requests_used"],
        "trace": sorted(trace, key=lambda item: item["agent"]),
        "elapsed_seconds": report["elapsed_seconds"],
        "agency_role_source": "agency-agents" if checkout else "chimera-local",
    }


def coding_config() -> dict:
    """Only operators can enable jcode. No client-supplied paths or executable."""
    enabled = os.environ.get("CHIMERA_ENABLE_CODE", "0") == "1"
    checkout = os.environ.get("CHIMERA_AGENCY_CHECKOUT")
    workspace = os.environ.get("CHIMERA_CODE_WORKSPACE")
    executable = os.environ.get("CHIMERA_JCODE", "jcode")
    if not enabled or not checkout or not workspace:
        return {"enabled": False, "reason": "Operator has not configured coding mode"}
    root = Path(workspace).resolve(strict=True)
    roles = Path(checkout).resolve(strict=True)
    if not root.is_dir() or not roles.is_dir():
        raise ValueError("Coding paths must be existing directories")
    if root == roles or root in roles.parents or roles in root.parents:
        raise ValueError("Coding workspace and Agency checkout must be separate")
    for role in ("planner", "engineer", "critic"):
        load_role(roles, AGENCY_ROLE_IDS[role])
    load_role(roles, "engineering/engineering-senior-developer.md")
    return {"enabled": True, "checkout": roles, "workspace": root,
            "executable": executable}


def run_live_coding(task: str, *, config: dict) -> dict:
    """Execute the *existing* gated Agency Agents + jcode workflow, not a mock."""
    from .coding_workflow import execute_workflow
    if not config.get("enabled"):
        raise ValueError("Coding mode is disabled")
    if not isinstance(task, str) or not task.strip() or len(task) > 6000:
        raise ValueError("Coding task must contain 1–6000 characters")
    report = execute_workflow(
        checkout=config["checkout"], workspace=config["workspace"], task=task,
        roles={"planner": AGENCY_ROLE_IDS["planner"],
               "implementer": "engineering/engineering-senior-developer.md",
               "reviewer": AGENCY_ROLE_IDS["critic"]},
        executable=config["executable"], per_phase_timeout=180, test_timeout=300,
    )
    return {
        "status": report["status"], "phases": report["phases"],
        "workspace_changed": report["workspace_changed"],
        "human_approval_required": True, "committed": False, "deployed": False,
    }
