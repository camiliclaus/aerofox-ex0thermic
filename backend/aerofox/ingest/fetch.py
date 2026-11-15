"""Defensive HTTP fetching for NASA sources.

PSI and NTRS are intermittently unavailable, so every download goes through
`fetch()`: bounded retries with exponential backoff and jitter, separate
connect/read timeouts, status and content-type validation, a size ceiling,
SHA-256 checksums and atomic writes. A failed fetch never overwrites a file
that is already on disk; the caller gets a `FetchResult` describing what
happened and keeps the last-known-good copy.
"""
from __future__ import annotations

import hashlib
import os
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests

USER_AGENT = "AeroFox-research-ingest/1.0 (NASA Space Apps 2026; scientific data snapshot)"
RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


@dataclass
class FetchResult:
    url: str
    ok: bool
    status: int | None = None
    content_type: str | None = None
    size: int = 0
    sha256: str | None = None
    attempts: int = 0
    error: str | None = None
    path: str | None = None
    elapsed_s: float = 0.0
    history: list[str] = field(default_factory=list)


class RateLimiter:
    """Minimum interval between requests to the same host (polite access)."""

    def __init__(self, min_interval_s: float = 0.5):
        self.min_interval_s = min_interval_s
        self._last: dict[str, float] = {}

    def wait(self, host: str) -> None:
        last = self._last.get(host, 0.0)
        delay = self.min_interval_s - (time.monotonic() - last)
        if delay > 0:
            time.sleep(delay)
        self._last[host] = time.monotonic()


_limiter = RateLimiter()
_session = requests.Session()
_session.headers["User-Agent"] = USER_AGENT


def _backoff(attempt: int, base: float, cap: float) -> float:
    # "full jitter": uniform(0, min(cap, base * 2**attempt))
    return random.uniform(0, min(cap, base * (2 ** attempt)))


def fetch(
    url: str,
    dest: Path | None = None,
    *,
    expect: tuple[str, ...] = (),
    max_bytes: int = 200 * 1024 * 1024,
    retries: int = 4,
    connect_timeout: float = 10.0,
    read_timeout: float = 60.0,
    backoff_base: float = 1.0,
    backoff_cap: float = 20.0,
    session: requests.Session | None = None,
) -> tuple[FetchResult, bytes | None]:
    """Download `url`. If `dest` is given, write atomically (tmp file + rename).

    `expect` lists acceptable content-type prefixes; an empty tuple accepts any.
    Returns the result record and the payload (None on failure).
    """
    sess = session or _session
    host = requests.utils.urlparse(url).netloc
    res = FetchResult(url=url, ok=False)
    t0 = time.monotonic()
    for attempt in range(retries + 1):
        res.attempts = attempt + 1
        _limiter.wait(host)
        try:
            with sess.get(url, timeout=(connect_timeout, read_timeout), stream=True) as r:
                res.status = r.status_code
                res.content_type = r.headers.get("Content-Type", "")
                if r.status_code in RETRYABLE_STATUS:
                    res.history.append(f"attempt {attempt + 1}: HTTP {r.status_code}")
                    raise _Retry()
                if r.status_code != 200:
                    res.error = f"HTTP {r.status_code}"
                    break
                if expect and not any(res.content_type.startswith(e) for e in expect):
                    res.error = f"unexpected content-type {res.content_type!r}"
                    break
                declared = int(r.headers.get("Content-Length") or 0)
                if declared > max_bytes:
                    res.error = f"declared size {declared} exceeds limit {max_bytes}"
                    break
                chunks, total = [], 0
                for chunk in r.iter_content(64 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError(f"payload exceeds limit {max_bytes}")
                    chunks.append(chunk)
                body = b"".join(chunks)
                if declared and len(body) != declared:
                    res.history.append(f"attempt {attempt + 1}: truncated {len(body)}/{declared}")
                    raise _Retry()
                if not body:
                    res.error = "empty payload"
                    break
                res.size = len(body)
                res.sha256 = hashlib.sha256(body).hexdigest()
                if dest is not None:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    tmp = dest.with_suffix(dest.suffix + ".part")
                    tmp.write_bytes(body)
                    os.replace(tmp, dest)
                    res.path = str(dest)
                res.ok = True
                res.error = None
                res.elapsed_s = round(time.monotonic() - t0, 3)
                return res, body
        except _Retry:
            pass
        except (requests.ConnectionError, requests.Timeout, requests.exceptions.ChunkedEncodingError) as exc:
            res.history.append(f"attempt {attempt + 1}: {type(exc).__name__}")
        except ValueError as exc:
            res.error = str(exc)
            break
        if attempt < retries:
            time.sleep(_backoff(attempt, backoff_base, backoff_cap))
    else:
        res.error = res.error or "retries exhausted: " + "; ".join(res.history[-2:])
    res.elapsed_s = round(time.monotonic() - t0, 3)
    return res, None


class _Retry(Exception):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()
