import json
import threading
import time
import urllib.request
from pathlib import Path

import pytest

from source_identifier_banking.server import _CandidatesHandler
from http.server import HTTPServer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _start_server(tmp_path: Path, candidates: list | None = None, *, port: int) -> threading.Thread:
    """Spin up a test server in a daemon thread and return the thread."""
    candidates_file = str(tmp_path / "candidates.json")
    if candidates is not None:
        with open(candidates_file, "w") as fh:
            json.dump(candidates, fh)

    class _Handler(_CandidatesHandler):
        pass

    _Handler.candidates_file = candidates_file

    server = HTTPServer(("127.0.0.1", port), _Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    # give the server a moment to bind
    time.sleep(0.05)
    return server


def _get(port: int, path: str) -> tuple[int, dict]:
    url = f"http://127.0.0.1:{port}{path}"
    with urllib.request.urlopen(url) as resp:
        return resp.status, json.loads(resp.read())


def _get_error(port: int, path: str) -> tuple[int, dict]:
    """Fetch a URL expected to return a non-2xx status."""
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}{path}")
        raise AssertionError("Expected an HTTP error")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_returns_200(self, tmp_path):
        server = _start_server(tmp_path, [], port=18101)
        try:
            status, body = _get(18101, "/health")
            assert status == 200
            assert body == {"status": "ok"}
        finally:
            server.shutdown()

    def test_trailing_slash_ignored(self, tmp_path):
        server = _start_server(tmp_path, [], port=18102)
        try:
            status, body = _get(18102, "/health/")
            assert status == 200
        finally:
            server.shutdown()


class TestRootEndpoint:
    def test_returns_200_with_metadata(self, tmp_path):
        server = _start_server(tmp_path, [], port=18103)
        try:
            status, body = _get(18103, "/")
            assert status == 200
            assert body["name"] == "source-identifier-banking"
            assert "/health" in body["endpoints"]
            assert "/candidates" in body["endpoints"]
        finally:
            server.shutdown()

    def test_candidates_file_path_in_response(self, tmp_path):
        server = _start_server(tmp_path, [], port=18104)
        try:
            _, body = _get(18104, "/")
            assert "candidates_file" in body
        finally:
            server.shutdown()


class TestCandidatesEndpoint:
    def test_returns_candidates_list(self, tmp_path):
        data = [{"candidate_id": "abc", "source_name": "Test"}]
        server = _start_server(tmp_path, data, port=18105)
        try:
            status, body = _get(18105, "/candidates")
            assert status == 200
            assert body == data
        finally:
            server.shutdown()

    def test_returns_empty_list(self, tmp_path):
        server = _start_server(tmp_path, [], port=18106)
        try:
            status, body = _get(18106, "/candidates")
            assert status == 200
            assert body == []
        finally:
            server.shutdown()

    def test_404_when_file_missing(self, tmp_path):
        server = _start_server(tmp_path, candidates=None, port=18107)
        try:
            status, body = _get_error(18107, "/candidates")
            assert status == 404
            assert "error" in body
        finally:
            server.shutdown()

    def test_query_string_stripped(self, tmp_path):
        data = [{"candidate_id": "x"}]
        server = _start_server(tmp_path, data, port=18108)
        try:
            status, body = _get(18108, "/candidates?foo=bar")
            assert status == 200
            assert body == data
        finally:
            server.shutdown()


class TestUnknownEndpoint:
    def test_returns_404(self, tmp_path):
        server = _start_server(tmp_path, [], port=18109)
        try:
            status, body = _get_error(18109, "/nonexistent")
            assert status == 404
            assert "error" in body
        finally:
            server.shutdown()



