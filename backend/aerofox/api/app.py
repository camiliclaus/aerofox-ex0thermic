"""AeroFox HTTP API and static frontend.

    uvicorn aerofox.api.app:app --host 127.0.0.1 --port 8000      (from backend/)
"""
from __future__ import annotations

import csv
import io
import json
import logging
import os
import threading
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..agent import llm
from ..agent.orchestrator import BUDGET, SESSIONS, handle_turn
from ..agent.state import ProjectState
from ..config import settings
from ..evidence.store import get_store
from ..science.workflows import mermaid_source

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("aerofox.api")

@asynccontextmanager
async def lifespan(_app):
    s = get_store()
    for t in ("flex_tests", "saffire_samples", "same_reduced"):
        s.table(t)
    log.info("AeroFox ready: %d evidence items, llm=%s", len(s.items), llm.available())
    yield


app = FastAPI(title="AeroFox", version=settings.app_version, docs_url="/api/docs", openapi_url="/api/openapi.json",
              lifespan=lifespan)
PUBLIC_DEMO = os.environ.get("AEROFOX_PUBLIC_DEMO") == "1"
if settings.cors_origins:
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["GET", "POST", "PATCH"],
                       allow_headers=["Content-Type"])


class RateLimiter:
    """Sliding-window limit per client address for the expensive endpoints."""

    def __init__(self, per_minute: int):
        self.n = per_minute
        self.hits: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= self.n:
                return False
            q.append(now)
            if len(self.hits) > 50000:
                self.hits.clear()
            return True


LIMIT = RateLimiter(settings.rate_per_minute)


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = uuid.uuid4().hex[:12]
    request.state.rid = rid
    if PUBLIC_DEMO and (request.url.path.startswith("/api/sessions/") and request.method == "GET"
                       and not request.url.path.endswith((".csv", ".mmd")) or request.url.path in {"/api/docs", "/api/openapi.json"}):
        return JSONResponse({"error": "route unavailable in the public demo"}, status_code=404)
    if request.method in {"POST", "PATCH"}:
        origin = request.headers.get("origin")
        if origin and origin not in settings.cors_origins:
            try:
                source = urlsplit(origin)
                local_origin = source.scheme in {"http", "https"} and source.netloc.lower() == request.url.netloc.lower()
            except ValueError:
                local_origin = False
            if not local_origin:
                return JSONResponse({"error": "cross-origin writes are disabled", "request_id": rid}, status_code=403)
    if request.method in {"POST", "PATCH"} and request.url.path != "/api/sessions":
        try:
            length = int(request.headers["content-length"])
        except (KeyError, ValueError):
            return JSONResponse({"error": "valid content length required", "request_id": rid}, status_code=411)
        if not 0 <= length <= 64_000:
            return JSONResponse({"error": "request too large", "request_id": rid}, status_code=413)
    t0 = time.monotonic()
    try:
        resp = await call_next(request)
    except Exception:  # never leak stack traces to users
        log.error("rid=%s unhandled request failure", rid)
        return JSONResponse({"error": "internal error - the team can trace it with this id", "request_id": rid}, status_code=500)
    resp.headers["X-Request-ID"] = rid
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Content-Security-Policy"] = ("default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
                                               "script-src 'self'; connect-src 'self'; font-src 'self'; frame-ancestors 'none'")
    if request.url.path.startswith("/api/"):
        route = request.scope.get("route")
        log.info("rid=%s %s %s %d %.3fs", rid, request.method, getattr(route, "path", "/api/other"),
                 resp.status_code, time.monotonic() - t0)
    return resp


TRUST_PROXY = os.environ.get("AEROFOX_TRUST_PROXY", "0") == "1"


def client_key(request: Request) -> str:
    """Client address for rate limiting. X-Forwarded-For is only trusted behind a known proxy (AEROFOX_TRUST_PROXY=1),
    otherwise a client could spoof it to escape the limit."""
    if TRUST_PROXY:
        fwd = request.headers.get("x-forwarded-for", "")
        if fwd:
            return fwd.split(",")[-1].strip()   # address appended by our own proxy
    return request.client.host if request.client else "unknown"


class ChatIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=settings.max_message_chars)
    session_id: str | None = Field(None, max_length=64, pattern=r"^[a-f0-9]{8,64}$")


@app.post("/api/chat")
def chat(body: ChatIn, request: Request):
    if not LIMIT.allow(client_key(request)):
        raise HTTPException(429, "Too many requests - please wait a minute.")
    out = handle_turn(body.session_id, body.message, request.state.rid)
    if out.get("error"):
        raise HTTPException(400, out["error"])
    return out


@app.get("/api/health")
def health():
    s = get_store()
    return {"status": "ok", "version": settings.app_version, "snapshot": settings.snapshot_version,
            "public_demo": PUBLIC_DEMO,
            "evidence_items": len(s.items), "tables": len(s.available_tables()),
            "llm": {"configured": llm.available(), "ready": llm.ready(),
                    "model": settings.model if llm.available() else None,
                    "runtime": "llama.cpp", "daily_budget_left": max(0, BUDGET.limit - BUDGET.used)},
            "sessions": len(SESSIONS)}


@app.post("/api/sessions")
def new_session(request: Request):
    if not LIMIT.allow(client_key(request)):
        raise HTTPException(429, "Too many requests - please wait a minute.")
    s = SESSIONS.get_or_create(None)
    return {"session_id": s.id, "project": s.project.known()}


@app.get("/api/sessions/{sid}")
def get_session(sid: str):
    s = SESSIONS.get(sid)
    if not s:
        raise HTTPException(404, "session expired or unknown")
    return {"session_id": s.id, "project": s.project.model_dump(), "language": s.language,
            "turns": [t.model_dump() for t in s.turns], "artifacts": list(s.artifacts)}


@app.patch("/api/sessions/{sid}/project")
def patch_project(sid: str, body: dict, request: Request):
    if not LIMIT.allow(client_key(request)):
        raise HTTPException(429, "Too many requests - please wait a minute.")
    s = SESSIONS.get(sid)
    if not s:
        raise HTTPException(404, "session expired or unknown")
    allowed = set(ProjectState.model_fields)
    bad = set(body) - allowed
    if bad:
        raise HTTPException(422, f"unknown fields: {sorted(bad)}")
    with SESSIONS.lock(s.id):
        data = s.project.model_dump()
        data.update(body)
        try:
            s.project = ProjectState(**data)
        except ValueError:
            raise HTTPException(422, "Invalid project values.")
        return {"project": s.project.model_dump()}


def _block_to_rows(b: dict) -> tuple[list[str], list[list]]:
    if b["type"] == "table":
        return b["columns"], b["rows"]
    if b["type"] == "matrix":
        return ["row"] + b["columns"], [[r["label"]] + r["cells"] for r in b["rows"]]
    if b["type"] == "chart":
        rows = []
        for s in b["series"]:
            for i, (x, y) in enumerate(zip(s["x"], s["y"])):
                rows.append([s["name"], x, y] + ([s["text"][i]] if s.get("text") and i < len(s["text"]) else []))
        return ["series", b.get("x_label", "x"), b.get("y_label", "y"), "label"], rows
    return [], []


def _safe_csv_cell(value):
    if isinstance(value, str) and (value.startswith(("\t", "\r", "\n"))
                                   or value.lstrip().startswith(("=", "+", "-", "@"))):
        return "'" + value
    return value


@app.get("/api/sessions/{sid}/artifacts/{aid}.csv")
def artifact_csv(sid: str, aid: str):
    s = SESSIONS.get(sid)
    if not s or aid not in s.artifacts or s.artifacts[aid].get("type") not in {"chart", "table", "matrix"}:
        raise HTTPException(404, "artifact not found (sessions expire after inactivity)")
    b = s.artifacts[aid]
    cols, rows = _block_to_rows(b)
    buf = io.StringIO()
    for key in ("title", "source", "caption"):
        value = " ".join(str(b.get(key, "")).splitlines())
        buf.write(f"# {key}: {value}\n")
    w = csv.writer(buf)
    w.writerow(map(_safe_csv_cell, cols))
    w.writerows(map(_safe_csv_cell, row) for row in rows)
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="aerofox_{aid}.csv"'})


@app.get("/api/sessions/{sid}/artifacts/{aid}.mmd")
def artifact_mermaid(sid: str, aid: str):
    s = SESSIONS.get(sid)
    block = s.artifacts.get(aid) if s else None
    if not block or block.get("type") != "flowchart":
        raise HTTPException(404, "Workflow not found in this conversation.")
    return Response(mermaid_source(block), media_type="text/plain",
                    headers={"Content-Disposition": f'attachment; filename="aerofox_{aid}.mmd"'})


@app.get("/api/library/investigations")
def investigations():
    inv = get_store().table("investigations")
    cols = ["accession", "acronym", "title", "project_type", "flight_program", "sub_research_area", "hardware", "start", "end",
            "license", "doi", "catalog_files", "catalog_bytes", "n_experiment_tables", "n_publications", "psi_url"]
    return json.loads(inv[cols].to_json(orient="records"))


@app.get("/api/library/references")
def references():
    s = get_store()
    out = [{"id": k, **v} for k, v in s.sources.items()]
    out += [{"id": e.id, "title": e.title, "authors": e.source_title.split(" (")[0], "year": None, "venue": "NASA NTRS",
             "url": e.url} for e in s.items.values() if e.kind == "reference"]
    return out


@app.get("/api/library/findings")
def findings():
    return [e.card() for e in get_store().items.values() if e.kind == "finding"]


@app.get("/api/library/fields")
def fields():
    return json.loads((settings.data_dir / "curated" / "data_dictionary.json").read_text(encoding="utf-8"))


@app.get("/api/library/provenance")
def provenance():
    m = json.loads((settings.data_dir / "raw" / "psi" / "manifest.json").read_text(encoding="utf-8"))
    files = m["files"].values()
    from collections import Counter
    return {"snapshot": settings.snapshot_version, "entries": len(m["files"]),
            "by_status": dict(Counter(f["status"] for f in files)), "by_kind": dict(Counter(f["kind"] for f in files)),
            "last_run": m["runs"][-1] if m["runs"] else None,
            "derivation": json.loads((settings.data_dir / "processed" / "derivation_log.json").read_text())["catalog"]}


@app.get("/api/datasets/{name}.csv")
def dataset(name: str):
    s = get_store()
    if name not in s.available_tables():
        raise HTTPException(404, "unknown dataset")
    return FileResponse(settings.data_dir / "processed" / f"{name}.csv", media_type="text/csv", filename=f"{name}.csv")


@app.get("/api/evidence/search")
def evidence_search(q: str, k: int = 6):
    if not q.strip() or len(q) > 500:
        raise HTTPException(400, "query must be 1-500 characters")
    return get_store().search(q, k=min(max(k, 1), 20))


@app.get("/api/evidence/{eid}")
def evidence_item(eid: str):
    e = get_store().get(eid)
    if not e:
        raise HTTPException(404, "unknown evidence id")
    return e.card()


@app.get("/figures/{name}")
def figure(name: str):
    path = (settings.root / "outputs" / "figures" / name).resolve()
    if path.parent != (settings.root / "outputs" / "figures").resolve() or not path.exists() or path.suffix != ".png":
        raise HTTPException(404, "figure not found")
    return FileResponse(path, media_type="image/png")


app.mount("/", StaticFiles(directory=str(settings.frontend_dir), html=True), name="frontend")
