"""Robust fetching: retries, validation, atomic writes and last-known-good behaviour."""
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from aerofox.ingest import fetch as F


class Handler(BaseHTTPRequestHandler):
    plan: list = []

    def do_GET(self):
        code, body, ctype = Handler.plan.pop(0) if Handler.plan else (200, b"ok", "text/plain")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture()
def server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    F._limiter.min_interval_s = 0
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_retries_then_succeeds(server, tmp_path):
    Handler.plan = [(503, b"down", "text/plain"), (502, b"bad", "text/plain"), (200, b"a,b\n1,2\n", "text/csv")]
    res, body = F.fetch(server + "/x.csv", tmp_path / "x.csv", backoff_base=0.01, backoff_cap=0.02)
    assert res.ok and res.attempts == 3 and body == b"a,b\n1,2\n"
    assert (tmp_path / "x.csv").read_bytes() == body
    assert res.sha256 == F.sha256_file(tmp_path / "x.csv")


def test_failure_keeps_last_known_good(server, tmp_path):
    good = tmp_path / "keep.csv"
    good.write_bytes(b"verified")
    Handler.plan = [(503, b"", "text/plain")] * 3
    res, body = F.fetch(server + "/keep.csv", good, retries=2, backoff_base=0.01, backoff_cap=0.02)
    assert not res.ok and body is None and "retries exhausted" in res.error
    assert good.read_bytes() == b"verified"


def test_content_type_and_status_validation(server, tmp_path):
    Handler.plan = [(200, b"<html>error page</html>", "text/html")]
    res, _ = F.fetch(server + "/api", expect=("application/json",))
    assert not res.ok and "content-type" in res.error
    Handler.plan = [(404, b"no", "text/plain")]
    res, _ = F.fetch(server + "/missing", retries=3)
    assert not res.ok and res.attempts == 1 and res.error == "HTTP 404"


def test_size_limit(server):
    Handler.plan = [(200, b"x" * 5000, "text/plain")]
    res, _ = F.fetch(server + "/big", max_bytes=1000)
    assert not res.ok and "exceeds" in res.error


def test_unreachable_host_is_reported():
    res, _ = F.fetch("http://127.0.0.1:9/never", retries=1, connect_timeout=0.5, backoff_base=0.01)
    assert not res.ok and res.attempts == 2
