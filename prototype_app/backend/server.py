#!/usr/bin/env python3
from __future__ import annotations

import json
import mimetypes
import os
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from repository import DemoRepository


ROOT_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = ROOT_DIR / "prototype_app" / "frontend"
REPOSITORY = DemoRepository.load()


class DemoRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self._handle_api(parsed)
            return
        if parsed.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _handle_api(self, parsed: Any) -> None:
        if parsed.path == "/api/summary":
            self._send_json(REPOSITORY.summary)
            return
        if parsed.path == "/api/companies":
            self._send_json(REPOSITORY.list_companies(parse_qs(parsed.query)))
            return
        if parsed.path.startswith("/api/company/"):
            company_id = unquote(parsed.path.rsplit("/", 1)[-1])
            payload = REPOSITORY.get_company_detail(company_id)
            if payload is None:
                self._send_json({"error": "company not found"}, status=HTTPStatus.NOT_FOUND)
            else:
                self._send_json(payload)
            return
        self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def guess_type(self, path: str) -> str:
        guessed = mimetypes.guess_type(path)[0]
        return guessed or "application/octet-stream"


def main() -> None:
    host = os.environ.get("FINCHAIN_HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", os.environ.get("FINCHAIN_PORT", "8765")))
    server = ThreadingHTTPServer((host, port), DemoRequestHandler)
    print(f"FinChain-Agent demo is running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
