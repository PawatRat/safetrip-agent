from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .env import load_env_file
from .orchestrator import SafeTripOrchestrator


ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = ROOT / "frontend"
FRONTEND_DIST_DIR = FRONTEND_DIR / "dist"


class DemoState:
    def __init__(self, offline: bool) -> None:
        self.offline = offline
        self.sessions: dict[str, SafeTripOrchestrator] = {}

    def orchestrator_for(self, session_id: str, offline: bool | None = None) -> SafeTripOrchestrator:
        use_model = not (self.offline if offline is None else offline)
        existing = self.sessions.get(session_id)
        if existing and existing.use_model == use_model:
            return existing
        orchestrator = SafeTripOrchestrator(verbose=False, use_model=use_model)
        self.sessions[session_id] = orchestrator
        return orchestrator

    def reset(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)


class SafeTripDemoHandler(BaseHTTPRequestHandler):
    server_version = "SafeTripDemo/0.1"

    def do_GET(self) -> None:
        if self.path == "/api/health":
            self._handle_health()
            return
        if self.path == "/api/status":
            self._handle_status()
            return
        self._serve_frontend()

    def do_POST(self) -> None:
        if self.path == "/api/chat":
            self._handle_chat()
            return
        if self.path == "/api/chat/stream":
            self._handle_chat_stream()
            return
        if self.path == "/api/reset":
            self._handle_reset()
            return
        self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write("SafeTrip demo: " + format % args + "\n")

    def _handle_chat(self) -> None:
        try:
            payload = self._read_json()
            message = str(payload.get("message", "")).strip()
            session_id = str(payload.get("session_id") or "default")
            offline = payload.get("offline")
            requested_offline = offline if isinstance(offline, bool) else None
            if not message:
                self._send_json({"error": "Message is required"}, HTTPStatus.BAD_REQUEST)
                return
            state: DemoState = self.server.demo_state  # type: ignore[attr-defined]
            orchestrator = state.orchestrator_for(session_id, requested_offline)
            result = orchestrator.process(message)
            self._send_json(result_to_payload(result))
        except Exception as exc:
            status = HTTPStatus.BAD_REQUEST if is_model_configuration_error(exc) else HTTPStatus.INTERNAL_SERVER_ERROR
            self._send_json(
                {
                    "error": f"{exc.__class__.__name__}: {exc}",
                    "hint": format_runtime_hint(exc),
                },
                status,
            )

    def _handle_chat_stream(self) -> None:
        try:
            payload = self._read_json()
            message = str(payload.get("message", "")).strip()
            session_id = str(payload.get("session_id") or "default")
            offline = payload.get("offline")
            requested_offline = offline if isinstance(offline, bool) else None
            if not message:
                self._send_json({"error": "Message is required"}, HTTPStatus.BAD_REQUEST)
                return
            state: DemoState = self.server.demo_state  # type: ignore[attr-defined]
            orchestrator = state.orchestrator_for(session_id, requested_offline)
        except Exception as exc:
            status = (
                HTTPStatus.BAD_REQUEST
                if is_model_configuration_error(exc)
                else HTTPStatus.INTERNAL_SERVER_ERROR
            )
            self._send_json(
                {
                    "error": f"{exc.__class__.__name__}: {exc}",
                    "hint": format_runtime_hint(exc),
                },
                status,
            )
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        try:
            result = orchestrator.process(message, on_progress=self._write_sse)
            self._write_sse({"type": "final", **result_to_payload(result)})
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as exc:
            self._write_sse(
                {
                    "type": "error",
                    "error": f"{exc.__class__.__name__}: {exc}",
                    "hint": format_runtime_hint(exc),
                }
            )

    def _write_sse(self, event: dict) -> None:
        data = json.dumps(event)
        self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
        self.wfile.flush()

    def _handle_status(self) -> None:
        state: DemoState = self.server.demo_state  # type: ignore[attr-defined]
        provider = os.getenv("SAFETRIP_MODEL_PROVIDER", "gemini").lower()
        live_available = has_live_model_credentials(provider)
        self._send_json(
            {
                "provider": provider,
                "live_model_available": live_available,
                "default_mode": "offline" if state.offline else "live",
                "model_hint": model_status_hint(provider, live_available),
            }
        )

    def _handle_health(self) -> None:
        self._send_json({"ok": True})

    def _handle_reset(self) -> None:
        payload = self._read_json()
        session_id = str(payload.get("session_id") or "default")
        state: DemoState = self.server.demo_state  # type: ignore[attr-defined]
        state.reset(session_id)
        self._send_json({"ok": True})

    def _read_json(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length) if content_length else b"{}"
        return json.loads(body.decode("utf-8") or "{}")

    def _serve_frontend(self) -> None:
        if not FRONTEND_DIST_DIR.exists():
            self._send_json(
                {
                    "error": "Frontend bundle not found",
                    "hint": "Run `npm install` and `npm run build` in frontend/, then restart the web demo.",
                },
                HTTPStatus.NOT_FOUND,
            )
            return

        parsed_path = unquote(urlparse(self.path).path)
        relative_path = parsed_path.lstrip("/") or "index.html"
        candidate = (FRONTEND_DIST_DIR / relative_path).resolve()
        dist_root = FRONTEND_DIST_DIR.resolve()
        try:
            candidate.relative_to(dist_root)
        except ValueError:
            candidate = FRONTEND_DIST_DIR / "index.html"
        if not candidate.exists() or candidate.is_dir():
            candidate = FRONTEND_DIST_DIR / "index.html"

        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if candidate.suffix == ".js":
            content_type = "text/javascript"
        if candidate.suffix == ".css":
            content_type = "text/css"
        self._serve_file(candidate, f"{content_type}; charset=utf-8")

    def _serve_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self._send_json({"error": "Static file not found"}, HTTPStatus.NOT_FOUND)
            return
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def result_to_payload(result) -> dict:
    raw_result = result.raw_result
    return {
        "final_text": result.final_text,
        "workflow_steps": raw_result.get("workflow_steps", []),
        "agent_traces": raw_result.get("agent_traces", []),
        "case_state": raw_result.get("case_state", result.case_state.model_dump(mode="json")),
    }


def has_live_model_credentials(provider: str) -> bool:
    if provider == "gemini":
        return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    if provider == "azure":
        return bool(os.getenv("AZURE_OPENAI_ENDPOINT") and os.getenv("AZURE_OPENAI_API_KEY"))
    if provider == "openai":
        return bool(os.getenv("OPENAI_API_KEY"))
    return False


def model_status_hint(provider: str, live_available: bool) -> str:
    if live_available:
        return "Live model credentials are configured."
    if provider == "gemini":
        return "Missing GEMINI_API_KEY or GOOGLE_API_KEY. Add it to .env for live LLM mode."
    if provider == "azure":
        return "Missing AZURE_OPENAI_ENDPOINT or AZURE_OPENAI_API_KEY. Add them to .env for live LLM mode."
    if provider == "openai":
        return "Missing OPENAI_API_KEY. Add it to .env for live LLM mode."
    return "Unsupported SAFETRIP_MODEL_PROVIDER. Use gemini, azure, or openai."


def is_model_configuration_error(exc: Exception) -> bool:
    message = str(exc)
    return (
        "Missing GEMINI_API_KEY" in message
        or "Missing AZURE_OPENAI_ENDPOINT" in message
        or "Missing OPENAI_API_KEY" in message
        or "Unsupported SAFETRIP_MODEL_PROVIDER" in message
        or "API key not valid" in message
        or "API_KEY_INVALID" in message
    )


def format_runtime_hint(exc: Exception) -> str:
    message = str(exc)
    if "API_KEY_INVALID" in message or "API key not valid" in message:
        return "Gemini rejected the API key. Update GEMINI_API_KEY in .env or switch to offline mode."
    if (
        "Missing GEMINI_API_KEY" in message
        or "Missing AZURE_OPENAI_ENDPOINT" in message
        or "Missing OPENAI_API_KEY" in message
    ):
        return f"{message} Switch to offline mode for deterministic demo fallback."
    if "Unsupported SAFETRIP_MODEL_PROVIDER" in message:
        return message
    return f"{exc.__class__.__name__}: {message}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the SafeTrip web demo.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Default new sessions to offline deterministic mode.",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Load environment variables before starting the demo.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_env_file(args.env_file)
    server = ThreadingHTTPServer((args.host, args.port), SafeTripDemoHandler)
    server.demo_state = DemoState(offline=args.offline)  # type: ignore[attr-defined]
    print(f"SafeTrip web demo running at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping SafeTrip web demo.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
