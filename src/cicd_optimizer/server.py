"""Tiny local web server that serves the live HTML dashboard.

We use only the stdlib ``http.server`` so we don't add another runtime dependency. On every
request the dashboard is re-rendered against the current state of the workflows on disk.
"""

from __future__ import annotations

import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .analyzer import AnalysisConfig, analyze
from .report import render_html


def serve(
    targets: list[Path],
    config: AnalysisConfig,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
) -> None:
    """Run the dashboard server until interrupted."""

    class Handler(BaseHTTPRequestHandler):
        # Silence default per-request logging.
        def log_message(self, fmt: str, *args) -> None:  # noqa: A003
            return

        def do_GET(self) -> None:  # noqa: N802
            if self.path in ("/healthz", "/health"):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")
                return
            result = analyze(targets, config=config)
            body = render_html(result).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}"
    print(f"cicd-optimizer dashboard live at {url}")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()
