"""Build or refresh the local NASA PSI combustion snapshot.

Usage (from repo root):
    python -m aerofox.ingest.psi_snapshot            # refresh, keep last-known-good on failure
    python -m aerofox.ingest.psi_snapshot --offline  # only re-verify checksums of files on disk

The PSI web app is an Angular front end over a JSON API (`/geode-py/ws`).
Investigation metadata comes from `/repo/investigations/<accession>`; table files
are served through presigned S3 URLs returned by `/studies/<acc>/download`.

Every file lands in data/raw/psi/ and is listed in data/raw/psi/manifest.json
with its URL, SHA-256, size, retrieval time and verification status:
  verified_this_run   downloaded and checksummed during this execution
  snapshot            download failed now, previous verified copy kept
  missing             never obtained
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from .fetch import fetch, sha256_file

import csv
import gzip
import re

API = "https://psi.nasa.gov/geode-py/ws"

# Curated raw/analyzed files: (accession, regex on file name, committed_to_git).
# Large telemetry workbooks go to data/cache (gitignored) and only their extracted
# derivatives are committed. Everything is re-downloadable from the manifest URLs.
CURATED = [
    ("PSI-69", r"_(DropletData|TestSheet)\.txt$", True),
    ("PSI-69", r"FLEX-035_(LLUVData|ColorCamData)\.txt$", True),
    ("PSI-39", r"_(DropletData|TestSheet)\.txt$", True),
    ("PSI-117", r"_Analyzed Data_.*\.(csv|xlsx)$", True),
    ("PSI-25", r"(Fan calibration data|Test\.Matrices)\.xlsx$", True),
    ("PSI-26", r"Test Matrix\.xlsx$", True),
    ("PSI-47", r"(DAFT Retrieved Data Summary\.xls|_Raw Data_[DP]Trk\d+\.txt)$", True),
    ("PSI-101", r"SAME, SAME-R_Results\.xlsx$", True),
    ("PSI-142", r"\.xlsx$", True),
    ("PSI-98", r"Telemetry Data Good Process Version\.xlsx$", False),
    ("PSI-99", r"Saffire-II Telemetry Data\.xlsx$", False),
    ("PSI-100", r"Raw telemetry file\.csv$", False),
]
ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw" / "psi"
MANIFEST = RAW / "manifest.json"
CACHE = ROOT / "data" / "cache" / "psi"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {"files": {}, "runs": []}


def _record(manifest: dict, key: str, res, path: Path, kind: str, extra: dict | None = None) -> None:
    prev = manifest["files"].get(key)
    entry = {
        "kind": kind,
        "path": str(path.relative_to(ROOT)),
        "source_url": res.url.split("?")[0],
        "last_attempt": _now(),
        "attempts": res.attempts,
    }
    if extra:
        entry.update(extra)
    if res.ok:
        entry.update(status="verified_this_run", sha256=res.sha256, size=res.size, retrieved_at=_now())
    elif prev and path.exists() and sha256_file(path) == prev.get("sha256"):
        entry.update(status="snapshot", sha256=prev["sha256"], size=prev["size"],
                     retrieved_at=prev.get("retrieved_at"), last_error=res.error)
    else:
        entry.update(status="missing", last_error=res.error)
    manifest["files"][key] = entry


def search_combustion() -> tuple[list[dict], object]:
    q = urllib.parse.urlencode({"size": 500, "ffield": "Research Area", "fvalue": "combustion science"})
    res, body = fetch(f"{API}/repo/search?{q}", RAW / "search_combustion.json", expect=("application/json",))
    if not res.ok:
        cached = RAW / "search_combustion.json"
        if cached.exists():
            body = cached.read_bytes()
        else:
            return [], res
    hits = json.loads(body)["hits"]["hits"]
    return [h["_source"] for h in hits], res


def download_file(acc: str, name: str, dest: Path):
    q = urllib.parse.urlencode({"file": name, "redirect": "false"})
    ures, ubody = fetch(f"{API}/studies/{acc}/download?{q}", expect=("text/", "application/json"), max_bytes=8192)
    if ures.ok and ubody and ubody.startswith(b"https://"):
        fres, _ = fetch(ubody.decode().strip(), dest, max_bytes=150 * 1024 * 1024, read_timeout=180)
        fres.url = f"{API}/studies/{acc}/download?file={urllib.parse.quote(name)}"
        return fres
    ures.error = ures.error or "presign endpoint did not return a URL"
    return ures


def fetch_catalog(manifest: dict, acc: str, version: int) -> list[tuple[str, int]]:
    """File catalog for one investigation, stored as gzipped CSV (key, bytes)."""
    import requests
    from .fetch import FetchResult
    dest = RAW / "catalog" / f"{acc}.csv.gz"
    res = FetchResult(url=f"{API}/files/v2#{acc}", ok=False)
    rows: list[tuple[str, int]] = []
    for attempt in range(4):
        res.attempts = attempt + 1
        try:
            r = requests.post(f"{API}/files/v2", json={"folder": "", "fileType": "study", "studyId": acc,
                                                       "version": version}, timeout=(10, 180))
            if r.status_code != 200:
                res.error = f"HTTP {r.status_code}"
                continue
            tree = r.json()

            def walk(node):
                for f in node.get("files", []):
                    if f.get("directory") or f.get("files"):
                        walk(f)
                    else:
                        rows.append((f["key"], int(f.get("bytes_size") or 0)))
            walk(tree)
            buf = "key,bytes\n" + "".join(f'"{k}",{b}\n' for k, b in rows)
            data = gzip.compress(buf.encode(), mtime=0)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            import hashlib
            res.ok, res.size, res.sha256, res.error = True, len(data), hashlib.sha256(data).hexdigest(), None
            break
        except (requests.RequestException, ValueError) as exc:
            res.error = type(exc).__name__
    _record(manifest, f"catalog/{acc}", res, dest, "file_catalog", {"entries": len(rows) if res.ok else None})
    if not res.ok and dest.exists():
        with gzip.open(dest, "rt") as fh:
            rows = [(r["key"], int(r["bytes"])) for r in csv.DictReader(fh)]
    return rows


def run(offline: bool = False) -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    run_log = {"started": _now(), "offline": offline, "ok": 0, "snapshot": 0, "missing": 0, "errors": []}

    if offline:
        for key, entry in manifest["files"].items():
            p = ROOT / entry["path"]
            good = p.exists() and entry.get("sha256") and sha256_file(p) == entry["sha256"]
            entry["offline_check"] = "checksum_ok" if good else "checksum_failed"
            run_log["ok" if good else "missing"] += 1
        manifest["runs"].append(run_log)
        MANIFEST.write_text(json.dumps(manifest, indent=1))
        return run_log

    investigations, sres = search_combustion()
    _record(manifest, "search/combustion", sres, RAW / "search_combustion.json", "search_index")
    for inv in investigations:
        acc = inv["Accession"]
        ipath = RAW / "investigations" / f"{acc}.json"
        res, body = fetch(f"{API}/repo/investigations/{acc}", ipath, expect=("application/json",))
        _record(manifest, f"investigation/{acc}", res, ipath, "investigation_metadata")
        if body is None and ipath.exists():
            body = ipath.read_bytes()
        if body is None:
            run_log["errors"].append(f"{acc}: {res.error}")
            continue
        meta = json.loads(body)
        for table_kind in ("experimentalTable", "modelingTable"):
            for tf in meta.get(table_kind) or []:
                if tf.get("restricted") or not tf.get("visible", True):
                    continue
                name = tf["file_name"]
                tpath = RAW / "tables" / acc / name
                q = urllib.parse.urlencode({"file": name, "redirect": "false"})
                ures, ubody = fetch(f"{API}/studies/{acc}/download?{q}", expect=("text/", "application/json"),
                                    max_bytes=8192)
                if ures.ok and ubody and ubody.startswith(b"https://"):
                    fres, _ = fetch(ubody.decode().strip(), tpath, max_bytes=100 * 1024 * 1024)
                    fres.url = f"{API}/studies/{acc}/download?file={urllib.parse.quote(name)}"
                else:
                    fres = ures
                    fres.error = fres.error or "presign endpoint did not return a URL"
                _record(manifest, f"table/{acc}/{name}", fres, tpath, table_kind,
                        {"psi_s3_version": tf.get("s3_version_id"), "declared_size": tf.get("file_size")})

    for inv in investigations:
        acc = inv["Accession"]
        ipath = RAW / "investigations" / f"{acc}.json"
        version = json.loads(ipath.read_text()).get("version") or 1 if ipath.exists() else 1
        files = fetch_catalog(manifest, acc, version)
        for cacc, pattern, committed in CURATED:
            if cacc != acc:
                continue
            for key, size in files:
                name = key.rsplit("/", 1)[-1]
                if not re.search(pattern, name):
                    continue
                dest = (RAW / "files" if committed else CACHE) / acc / name
                mkey = f"file/{acc}/{name}"
                prev = manifest["files"].get(mkey)
                if prev and prev.get("status") in ("verified_this_run", "snapshot") and dest.exists() \
                        and prev.get("sha256") == sha256_file(dest):
                    prev["last_attempt"] = _now()
                    prev["status"] = "snapshot"
                    continue  # immutable PSI versioned object already verified locally
                fres = download_file(acc, name, dest)
                _record(manifest, mkey, fres, dest, "raw_file" if committed else "raw_file_cached",
                        {"committed": committed, "catalog_size": size})

    for e in manifest["files"].values():
        if e["last_attempt"] >= run_log["started"]:
            key = {"verified_this_run": "ok", "snapshot": "snapshot", "missing": "missing"}[e["status"]]
            run_log[key] += 1
    run_log["finished"] = _now()
    manifest["runs"].append(run_log)
    manifest["runs"] = manifest["runs"][-20:]
    tmp = MANIFEST.with_suffix(".json.part")
    tmp.write_text(json.dumps(manifest, indent=1))
    tmp.replace(MANIFEST)
    return run_log


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    log = run(offline=ap.parse_args().offline)
    print(json.dumps(log, indent=1))
    sys.exit(0 if log["missing"] == 0 else 1)
