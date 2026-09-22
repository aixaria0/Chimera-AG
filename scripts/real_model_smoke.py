"""Real-model smoke check: fails unless an installed model generates an answer.

No mocks, prerecorded answers, API keys or expected fixed completion text.
"""
from __future__ import annotations

import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = os.environ.get("CHIMERA_URL", "http://127.0.0.1:8080").rstrip("/")
MODEL = os.environ.get("CHIMERA_MODEL", "smollm2:135m")


def request(path: str, body: dict | None = None) -> dict:
    payload = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if payload else {}
    req = Request(BASE + path, data=payload, headers=headers,
                  method="POST" if payload is not None else "GET")
    with urlopen(req, timeout=150) as response:
        if response.status != 200:
            raise RuntimeError("Unexpected service status")
        return json.load(response)


def main():
    deadline = time.monotonic() + 90
    while True:
        try:
            health = request("/api/health")
            if health.get("status") == "ready":
                break
        except (OSError, ValueError, HTTPError, URLError):
            pass
        if time.monotonic() >= deadline:
            raise RuntimeError("Real inference service never became ready")
        time.sleep(2)
    if health["model"] != MODEL or MODEL not in health["installed"]:
        raise RuntimeError("Expected model is not installed and active")
    prompt = ("In one short sentence, say what an AI language model does. "
              "Respond in English.")
    answer = request("/api/chat", {"messages": [{"role": "user", "content": prompt}]})
    if (answer.get("model") != MODEL or not isinstance(answer.get("reply"), str)
            or not answer["reply"].strip() or answer.get("done") is not True):
        raise RuntimeError("Model did not generate a valid completed answer")
    if not isinstance(answer.get("eval_count"), int) or answer["eval_count"] < 1:
        raise RuntimeError("No real generated model tokens were reported")
    print(json.dumps({
        "real_model_inference": True,
        "model": answer["model"],
        "generated_tokens": answer["eval_count"],
        "answer": answer["reply"],
        "backend": "Ollama",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
