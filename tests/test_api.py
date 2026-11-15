"""HTTP API: contracts, validation, exports, security headers and rate limiting."""
import pytest
from fastapi.testclient import TestClient

from aerofox.api import app as appmod

client = TestClient(appmod.app)


def test_health_and_frontend():
    h = client.get("/api/health").json()
    assert h["status"] == "ok" and h["evidence_items"] > 80
    r = client.get("/")
    assert r.status_code == 200 and "What would you like" in r.text
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
    assert r.headers["X-Request-ID"]


def test_chat_contract_and_csv_export():
    r = client.post("/api/chat", json={"message": "Compare Saffire-II runs 2-5 and 2-6"})
    assert r.status_code == 200
    body = r.json()
    for key in ("session_id", "answer", "blocks", "evidence", "warnings", "project", "mode", "request_id"):
        assert key in body
    chart = next(b for b in body["blocks"] if b["type"] == "chart")
    csv = client.get(chart["csv_url"])
    assert csv.status_code == 200 and "2-6" in csv.text and csv.headers["content-type"].startswith("text/csv")
    other = client.post("/api/sessions").json()["session_id"]
    assert client.get(chart["csv_url"].replace(body["session_id"], other)).status_code == 404


@pytest.mark.parametrize("payload,code", [
    ({"message": ""}, 422), ({"message": "x" * 5000}, 422), ({}, 422),
    ({"message": "hi", "session_id": "../../etc/passwd"}, 422),
])
def test_chat_validation(payload, code):
    assert client.post("/api/chat", json=payload).status_code == code


def test_project_patch_validation():
    sid = client.post("/api/sessions").json()["session_id"]
    assert client.patch(f"/api/sessions/{sid}/project", json={"o2_pct": 34, "pressure_kPa": 56.5}).status_code == 200
    assert client.patch(f"/api/sessions/{sid}/project", json={"o2_pct": 150}).status_code == 422
    assert client.patch(f"/api/sessions/{sid}/project", json={"__class__": 1}).status_code == 422
    assert client.patch("/api/sessions/deadbeef00/project", json={}).status_code == 404


def test_library_and_datasets():
    assert len(client.get("/api/library/investigations").json()) == 24
    assert len(client.get("/api/library/findings").json()) >= 12
    assert client.get("/api/library/provenance").json()["entries"] >= 600
    assert client.get("/api/datasets/flex_tests.csv").status_code == 200
    assert client.get("/api/datasets/..%2F..%2Fsecrets.csv").status_code == 404
    assert client.get("/figures/../../.env").status_code == 404
    assert client.get("/api/evidence/F04").json()["id"] == "F04"
    assert client.get("/api/evidence/NOPE").status_code == 404


def test_rate_limit(monkeypatch):
    monkeypatch.setattr(appmod, "LIMIT", appmod.RateLimiter(2))
    codes = [client.post("/api/chat", json={"message": "hello"}).status_code for _ in range(4)]
    assert codes[:2] == [200, 200] and 429 in codes[2:]


def test_browser_write_origin_and_csv_formula_safety():
    r = client.post("/api/sessions", headers={"Origin": "https://example.invalid"})
    assert r.status_code == 403
    r = client.post("/api/sessions", headers={"Origin": "http://testserver"})
    assert r.status_code == 200
    assert appmod._safe_csv_cell(" =1+1") == "' =1+1"
    assert appmod._safe_csv_cell(-1.5) == -1.5


def test_workflow_export_keeps_branches_and_session_scope():
    reply = client.post("/api/chat", json={"message": "Faça um fluxograma de segurança contra incêndio para um traje EVA."}).json()
    block = next(item for item in reply["blocks"] if item["type"] == "flowchart")
    assert sum(node["decision"] for node in block["nodes"]) == 3
    assert {"Sim", "Não"} <= {edge["label"] for edge in block["edges"]}
    response = client.get(block["mermaid_url"])
    assert response.status_code == 200 and "flowchart TD" in response.text and "-->|Não|" in response.text
    assert client.get(block["mermaid_url"].replace(reply["session_id"], "0" * 32)).status_code == 404
