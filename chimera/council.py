"""Parallel council: diverse workers -> synthesizer -> independent verifiers.

This is a coordination mechanism, not a truth oracle. It uses every enabled worker
once, then synthesizes their outputs and asks all enabled verifiers to review it.
"""
from __future__ import annotations
import concurrent.futures
import json
import time
from .fabric import AgentSpec, ChatEndpoint, RequestBudget


class Council:
    def __init__(self, specs: list[AgentSpec], *, max_workers: int | None = None,
                 endpoint_factory=None):
        enabled = [s for s in specs if s.enabled]
        self.workers = [s for s in enabled if s.role == "worker"]
        self.synthesizers = [s for s in enabled if s.role == "synthesizer"]
        self.verifiers = [s for s in enabled if s.role == "verifier"]
        if not self.workers:
            raise ValueError("Council requires at least one enabled worker")
        if not self.synthesizers:
            raise ValueError("Council requires an enabled synthesizer")
        if max_workers is not None and max_workers < 1:
            raise ValueError("max_workers must be positive")
        # One request per enabled role. No arbitrary registration/concurrency ceiling;
        # actual provider and machine capacity still applies.
        self.concurrency = max_workers or len(self.workers)
        self.budget = RequestBudget(len(self.workers) + 1 + len(self.verifiers))
        self.endpoint_factory = endpoint_factory or (lambda s, b: ChatEndpoint(s, b))

    def _call(self, spec: AgentSpec, prompt: str):
        try:
            return spec.name, self.endpoint_factory(spec, self.budget).answer(prompt), None
        except Exception as exc:
            return spec.name, None, type(exc).__name__ + ": " + str(exc)

    def run(self, task: str) -> dict:
        if not task.strip():
            raise ValueError("Task must be nonempty")
        start = time.monotonic()
        responses, errors = {}, {}
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=min(self.concurrency, len(self.workers))) as pool:
            futures = [pool.submit(self._call, spec, task) for spec in self.workers]
            for future in concurrent.futures.as_completed(futures):
                name, answer, error = future.result()
                (errors if error else responses)[name] = error or answer
        if not responses:
            return {"status": "failed", "answer": None, "errors": errors,
                    "requests_used": self.budget.used}

        evidence = json.dumps(
            [{"agent": name, "answer": answer} for name, answer in sorted(responses.items())],
            ensure_ascii=False)
        synthesis_prompt = (
            "Solve the TASK using the candidate analyses as fallible evidence. "
            "Resolve conflicts, do not blindly vote, and return the best concise final answer.\n"
            f"TASK:\n{task}\nCANDIDATES_JSON:\n{evidence}"
        )
        synth = self.synthesizers[0]
        synth_name, candidate, error = self._call(synth, synthesis_prompt)
        if error:
            errors[synth_name] = error
            return {"status": "failed", "answer": None, "worker_responses": responses,
                    "errors": errors, "requests_used": self.budget.used}

        verdicts = {}
        if self.verifiers:
            verify_prompt = (
                "Independently check whether CANDIDATE adequately answers TASK. "
                "Reply exactly APPROVE if it is correct and supported; otherwise REJECT.\n"
                f"TASK:\n{task}\nCANDIDATE:\n{candidate}"
            )
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.verifiers)) as pool:
                futures = [pool.submit(self._call, spec, verify_prompt) for spec in self.verifiers]
                for future in concurrent.futures.as_completed(futures):
                    name, verdict, verr = future.result()
                    if verr:
                        errors[name] = verr
                    else:
                        verdicts[name] = verdict.strip().upper() == "APPROVE"
        accepted = bool(verdicts) and all(verdicts.values())
        return {
            "status": "accepted" if accepted else "unverified",
            "answer": candidate if accepted else None,
            "candidate": candidate,
            "worker_responses": responses,
            "synthesizer": synth_name,
            "verifier_agreement": verdicts,
            "errors": errors,
            "requests_used": self.budget.used,
            "elapsed_seconds": round(time.monotonic() - start, 4),
        }
