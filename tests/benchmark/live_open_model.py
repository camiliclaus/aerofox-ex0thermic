"""Exercise actual AeroFox inference via the browser-facing HTTP API."""
from __future__ import annotations

import argparse
import json
import statistics
import urllib.request
from pathlib import Path

CASES = [
    ("flex035", [("Why does the curve keep descending after visible extinction in FLEX-035?", "flex035_case_study", "chart")]),
    ("habitat-transfer", [
        ("We are planning a surface outpost on the Moon. Chart which fire barrier needs verification first.", "fire_safety_factors", "matrix"),
        ("And on Mars?", "fire_safety_factors", "matrix")]),
    ("oxygen-pt", [("Mostre um gráfico de como o oxigênio se relaciona com a taxa de queima de gotas no FLEX.", "chart_flex_burning_rate_vs_oxygen", "chart")]),
    ("isolation", [("How could shared return air move contamination from a battery bay? Model the difference if I isolate it.", "compare_ventilation_designs", "chart")]),
    ("saffire", [("Show the independent measurements for Saffire-II flow, especially sample 2-6.", "saffire2_flow_case_study", "chart")]),
    ("new-engineering", [("What should a verification plan measure for wiring faults near the breathing circuit in an EVA suit?", "fire_safety_factors", "matrix")]),
]


def run(url):
    results = []
    for label, turns in CASES:
        sid = None
        for text, tool, visual in turns:
            request = urllib.request.Request(url + "/api/chat", data=json.dumps({"message": text, "session_id": sid}).encode(),
                                             headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=110) as response:
                item = json.load(response)
            sid = item["session_id"]
            good_tool = any(x["name"] == tool and x["ok"] for x in item["tools"])
            blocks = [b["title"] for b in item["blocks"] if b["type"] == visual and (b.get("rows") or b.get("series"))]
            ground = bool(item["evidence"]) and "[" in item["answer"]
            transfer = label != "habitat-transfer" or text != "And on Mars?" or (
                item["project"].get("system") == "mars_habitat" and any("mars" in b.casefold() for b in blocks))
            actual = item["mode"] == "llm" and (item["usage"] or {}).get("output", 0) > 0
            row = {"case": label, "question": text, "mode": item["mode"], "model": item["model"],
                   "latency_s": item["elapsed_s"], "usage": item["usage"], "tools": item["tools"], "blocks": blocks,
                   "source_ids": [x["id"] for x in item["evidence"]], "notice": item["notice"],
                   "warnings": item["warnings"], "answer": item["answer"],
                   "pass": bool(actual and good_tool and blocks and ground and transfer)}
            results.append(row)
            print(f'{label} {row["mode"]} {row["pass"]} {row["latency_s"]:.2f}s {blocks}', flush=True)
    return {"total":len(results), "passed":sum(r["pass"] for r in results),
            "median_s":statistics.median(r["latency_s"] for r in results), "turns":results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.url.rstrip("/"))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    raise SystemExit(0 if result["total"] == result["passed"] else 1)

