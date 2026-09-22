"""Chimera Local: a real, self-hosted web product backed by installed Ollama models.

No mock model, hardcoded answer, cloud credential, or background mock executor.
The browser talks only to this same-origin server; this server talks to Ollama.
"""
from __future__ import annotations

import json
import mimetypes
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .product_integrations import coding_config, run_live_coding, run_live_council

STATIC = Path(__file__).resolve().parent.parent / "web"

def _static_root() -> Path:
    """The built Lovable UI is optional; existing bundled UI remains the default."""
    configured = os.environ.get("CHIMERA_WEB_DIST")
    if not configured:
        return STATIC
    root = Path(configured).resolve(strict=True)
    if not root.is_dir() or not (root / "index.html").is_file():
        raise ValueError("CHIMERA_WEB_DIST must contain a compiled index.html")
    return root


def _static_asset(root: Path, request_path: str) -> tuple[Path, str] | None:
    """Serve only the compiled SPA shell and /assets, never source or private files."""
    from urllib.parse import unquote
    if request_path in ("/", "/index.html"):
        return root / "index.html", "text/html; charset=utf-8"
    name = unquote(request_path.lstrip("/"))
    parts = Path(name).parts
    if (not name.startswith("assets/") or len(parts) < 2
            or any(part in (".", "..") or part.startswith(".") for part in parts)
            or chr(92) in name or chr(0) in name):
        return None
    candidate = (root / name).resolve()
    if not candidate.is_relative_to(root.resolve()) or not candidate.is_file():
        return None
    mime = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
    if mime in ("text/javascript", "application/javascript"):
        mime = "text/javascript"
    elif mime.startswith("text/"):
        mime += "; charset=utf-8"
    return candidate, mime

DEFAULT_MODEL = "qwen2.5:1.5b"
MAX_BODY = 64 * 1024
MAX_MESSAGES = 16
MAX_TEXT = 6000


class OllamaBackend:
    def __init__(self, endpoint: str = "http://127.0.0.1:11434",
                 model: str = DEFAULT_MODEL):
        parsed = urlparse(endpoint)
        if (parsed.scheme != "http" or not parsed.hostname
                or parsed.username or parsed.password or parsed.query
                or parsed.fragment or parsed.path not in ("", "/")):
            raise ValueError("Invalid Ollama endpoint")
        if not model or len(model) > 128 or any(ch in model for ch in "\r\n"):
            raise ValueError("Invalid model name")
        self.endpoint = endpoint.rstrip("/")
        self.model = model

    def request(self, method: str, path: str, body: dict | None = None,
                timeout: int = 45) -> dict:
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        request = Request(self.endpoint + path, data=payload, method=method,
                          headers={"Content-Type": "application/json",
                                   "Accept": "application/json"})
        with urlopen(request, timeout=timeout) as response:
            if int(response.headers.get("Content-Length") or "0") > 4_000_000:
                raise ValueError("Ollama returned an oversized response")
            data = response.read(4_000_001)
            if len(data) > 4_000_000:
                raise ValueError("Ollama returned an oversized response")
        result = json.loads(data)
        if not isinstance(result, dict):
            raise ValueError("Unexpected Ollama response")
        return result

    def installed(self) -> list[str]:
        body = self.request("GET", "/api/tags", timeout=5)
        models = body.get("models", [])
        if not isinstance(models, list):
            raise ValueError("Ollama model registry was invalid")
        return sorted({row["name"] for row in models
                       if isinstance(row, dict) and isinstance(row.get("name"), str)})

    def chat(self, messages: list[dict], *, model: str | None = None,
             max_predict: int = 256) -> dict:
        result = self.request("POST", "/api/chat",
                              {"model": model or self.model, "messages": messages,
                               "stream": False, "options": {"num_predict": max_predict}},
                              timeout=120)
        text = result.get("message", {}).get("content")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("The inference backend returned no text")
        return {"model": result.get("model", self.model),
                "reply": text.strip(), "done": result.get("done") is True,
                "total_duration_ns": result.get("total_duration"),
                "eval_count": result.get("eval_count")}


def _validate_messages(raw: object) -> list[dict]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_MESSAGES:
        raise ValueError("Provide 1–16 conversation messages")
    messages = []
    for item in raw:
        if not isinstance(item, dict) or item.get("role") not in ("user", "assistant"):
            raise ValueError("Only user and assistant messages are accepted")
        content = item.get("content")
        if not isinstance(content, str) or not content.strip() or len(content) > MAX_TEXT:
            raise ValueError("Each message must contain 1–6000 characters")
        messages.append({"role": item["role"], "content": content})
    if messages[-1]["role"] != "user":
        raise ValueError("The final message must come from the user")
    return messages


def make_handler(backend: OllamaBackend, *, code: dict | None = None,
                 agency_checkout: Path | None = None):
    # Backpressure prevents a browser refresh or accidental loop from launching
    # unbounded simultaneous model inference on a small CPU/GPU machine.
    slots = threading.BoundedSemaphore(2)
    coding_slot = threading.BoundedSemaphore(1)
    code = code or {"enabled": False}

    class Handler(BaseHTTPRequestHandler):
        server_version = "ChimeraLocal/1.1"

        def _headers(self, code: int, mime: str, length: int):
            self.send_response(code)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; script-src 'self'; style-src 'self'; "
                             "connect-src 'self'; img-src 'self'; object-src 'none'; "
                             "base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()

        def send_bytes(self, code: int, content: bytes, mime: str):
            self._headers(code, mime, len(content))
            self.wfile.write(content)

        def send_json(self, code: int, value: dict):
            data = json.dumps(value, ensure_ascii=False).encode("utf-8")
            self.send_bytes(code, data, "application/json; charset=utf-8")

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/api/health":
                try:
                    installed = backend.installed()
                    ready = backend.model in installed
                    self.send_json(200 if ready else 503,
                                   {"status": "ready" if ready else "model_missing",
                                    "model": backend.model, "installed": installed})
                except (OSError, ValueError, TimeoutError, URLError, HTTPError):
                    self.send_json(503, {"status": "ollama_unavailable",
                                         "model": backend.model})
                return
            if path == "/api/features":
                self.send_json(200, {
                    "single": True, "council": True,
                    "coding": bool(code.get("enabled")),
                    "agency_roles": agency_checkout is not None,
                    "coding_requires_human_review": True,
                })
                return
            if path == "/api/models":
                try:
                    self.send_json(200, {"models": backend.installed(),
                                         "active": backend.model})
                except (OSError, ValueError, TimeoutError, URLError, HTTPError):
                    self.send_json(503, {"error": "Ollama unavailable"})
                return
            root = _static_root()
            if root == STATIC:
                files = {"/": ("index.html", "text/html; charset=utf-8"),
                         "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                         "/style.css": ("style.css", "text/css; charset=utf-8")}
                if path not in files:
                    self.send_json(404, {"error": "Not found"})
                    return
                filename, mime = files[path]
                self.send_bytes(200, (STATIC / filename).read_bytes(), mime)
                return
            asset = _static_asset(root, path)
            if asset is None:
                self.send_json(404, {"error": "Not found"})
                return
            file_path, mime = asset
            self.send_bytes(200, file_path.read_bytes(), mime)

        def do_POST(self):
            if self.path not in ("/api/chat", "/api/council", "/api/code"):
                self.send_json(404, {"error": "Not found"})
                return
            # Only the operator can enable code. Explicit browser intent plus a
            # same-origin check prevent drive-by websites from invoking jcode.
            if self.path == "/api/code" and not code.get("enabled"):
                self.send_json(403, {"error": "Coding mode is disabled by the operator"})
                return
            origin = self.headers.get("Origin")
            expected = "http://" + self.headers.get("Host", "")
            if origin is not None and origin != expected:
                self.send_json(403, {"error": "Cross-site requests are not accepted"})
                return
            if self.path == "/api/code":
                host = self.headers.get("Host", "").split(":", 1)[0].lower()
                if (origin != expected or host not in ("localhost", "127.0.0.1")
                        or self.headers.get("X-Chimera-Intent") != "explicit-code-run"):
                    self.send_json(403, {"error": "Coding requires local same-origin explicit intent"})
                    return
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self.send_json(400, {"error": "Invalid request length"})
                return
            if not 0 < size <= MAX_BODY:
                self.send_json(413, {"error": "Request must be at most 64 KiB"})
                return
            if not self.headers.get("Content-Type", "").lower().startswith("application/json"):
                self.send_json(415, {"error": "Expected application/json"})
                return
            try:
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError("Request must be an object")
                if self.path == "/api/code":
                    task = body.get("task")
                    if not isinstance(task, str) or not task.strip() or len(task) > MAX_TEXT:
                        raise ValueError("Coding task must contain 1–6000 characters")
                    if body.get("confirm") is not True:
                        raise ValueError("Explicit coding confirmation is required")
                else:
                    messages = _validate_messages(body.get("messages"))
                    if self.path == "/api/council":
                        models = body.get("models")
                        if models is not None and (
                            not isinstance(models, list) or len(models) > 4
                            or any(not isinstance(item, str) for item in models)):
                            raise ValueError("Choose up to four installed model names")
            except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
                self.send_json(400, {"error": str(exc)})
                return
            slot = coding_slot if self.path == "/api/code" else slots
            if not slot.acquire(blocking=False):
                self.send_json(429, {"error": "The selected runtime is busy; retry shortly"})
                return
            try:
                if self.path == "/api/code":
                    self.send_json(200, run_live_coding(task, config=code))
                elif self.path == "/api/council":
                    # Preserve conversation context rather than discarding earlier turns.
                    context = "\\n".join(
                        f"{message['role']}: {message['content']}"
                        for message in messages)[-6000:]
                    result = run_live_council(
                        backend, context, checkout=agency_checkout,
                        requested_models=body.get("models"),
                    )
                    if result["status"] == "failed":
                        self.send_json(503, result)
                    else:
                        self.send_json(200, result)
                else:
                    self.send_json(200, backend.chat(messages))
            except HTTPError as exc:
                self.send_json(503, {"error": "Model inference failed",
                                     "upstream_status": exc.code})
            except (OSError, TimeoutError, ValueError, URLError, KeyError, TypeError):
                self.send_json(503, {"error": "Configured runtime is unavailable"})
            finally:
                slot.release()

        def log_message(self, format, *args):
            # Do not log chat messages or model outputs.
            return

    return Handler


def main() -> None:
    host = os.environ.get("CHIMERA_HOST", "127.0.0.1")
    port = int(os.environ.get("CHIMERA_PORT", "8080"))
    if not 1 <= port <= 65535:
        raise ValueError("Invalid port")
    backend = OllamaBackend(
        os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434"),
        os.environ.get("CHIMERA_MODEL", DEFAULT_MODEL))
    code = coding_config()
    agency_path = os.environ.get("CHIMERA_AGENCY_CHECKOUT")
    agency_checkout = Path(agency_path) if agency_path else None
    if code.get("enabled") and host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("jcode execution requires a loopback-only Chimera web server")
    server = ThreadingHTTPServer((host, port), make_handler(
        backend, code=code, agency_checkout=agency_checkout))
    print(f"Chimera Local listening on http://{host}:{port} with {backend.model}",
          flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
