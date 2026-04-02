import json
import signal
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import structlog

logger = structlog.get_logger()

_MIME_JSON = "application/json"


class _CandidatesHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler exposing candidate data as a local REST API."""

    candidates_file: str = "artifacts/candidate_sources.json"

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        logger.debug("http_request", msg=format % args, client=self.address_string())

    def _send_json(self, status: int, data: object) -> None:
        body = json.dumps(data, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", _MIME_JSON)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?")[0].rstrip("/") or "/"

        if path == "/health":
            self._send_json(200, {"status": "ok"})

        elif path == "/candidates":
            p = Path(self.candidates_file)
            if not p.exists():
                self._send_json(404, {"error": f"Candidates file not found: {self.candidates_file}"})
                return
            with open(p) as fh:
                candidates = json.load(fh)
            self._send_json(200, candidates)

        elif path == "/":
            self._send_json(200, {
                "name": "source-identifier-banking",
                "endpoints": ["/health", "/candidates"],
                "candidates_file": self.candidates_file,
            })

        else:
            self._send_json(404, {"error": f"Not found: {self.path}"})


def run_server(host: str, port: int, candidates_file: str) -> None:
    """
    Start the local HTTP server and block until interrupted.

    Args:
        host: Hostname or IP address to bind to (e.g. '127.0.0.1').
        port: TCP port to listen on.
        candidates_file: Path to the candidates JSON file to serve.
    """

    class _Handler(_CandidatesHandler):
        pass

    _Handler.candidates_file = candidates_file

    server = HTTPServer((host, port), _Handler)
    logger.info("server_start", host=host, port=port, candidates_file=candidates_file)

    stop_event = threading.Event()

    def _shutdown(signum: int, frame: object) -> None:
        logger.info("server_shutdown", signal=signum)
        stop_event.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        server.serve_forever()
    finally:
        server.server_close()
        logger.info("server_stopped")
