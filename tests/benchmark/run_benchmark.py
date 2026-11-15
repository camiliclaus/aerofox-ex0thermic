"""Run the AeroFox scenario benchmark against the agent and write reports/benchmark_*.{json,md}.

    python tests/benchmark/run_benchmark.py            # whichever engine is configured
    AEROFOX_LLM=off python tests/benchmark/run_benchmark.py   # offline engine only

Scoring (automated, no human grading):
  tool_ok    at least one expected tool was called successfully (if any are expected)
  blocks_ok  every expected block type was returned with non-empty content
  no_error   no tool failed and the answer is non-empty
  state_ok   (multi-turn) project state holds the expected values after the turn
A case passes when all applicable checks hold.
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).parent))

from aerofox.agent.orchestrator import handle_turn  # noqa: E402
from cases import HOLDOUT, multi_turn, single_turn  # noqa: E402


def blocks_ok(r: dict, want: list[str]) -> bool:
    got = defaultdict(int)
    for b in r["blocks"]:
        nonempty = bool(b.get("series") or b.get("rows") or b.get("links") is not None)
        if nonempty:
            got[b["type"]] += 1
    return all(got[w] for w in want)


def check(r: dict, tools: list[str], blocks: list[str]) -> dict:
    called = [t["name"] for t in r["tools"] if t["ok"]]
    res = {"tool_ok": (not tools) or any(t in called for t in tools), "blocks_ok": blocks_ok(r, blocks),
           "no_error": bool(r["answer"].strip()) and all(t["ok"] for t in r["tools"]), "called": called,
           "latency_s": r["elapsed_s"], "mode": r["mode"]}
    res["pass"] = res["tool_ok"] and res["blocks_ok"] and res["no_error"]
    return res


def run() -> dict:
    t0 = time.time()
    single = []
    for c in single_turn():
        r = handle_turn(None, c["text"], "bench")
        single.append({**c, **check(r, c["tools"], c["blocks"])})
    multi = []
    for conv in multi_turn():
        sid, turns_ok, state_ok = None, [], []
        for t in conv["turns"]:
            r = handle_turn(sid, t["text"], "bench")
            sid = r["session_id"]
            ck = check(r, t.get("tools", []), t.get("blocks", []))
            exp = t.get("project", {})
            st = all((abs(r["project"].get(k, -1) - v) < 0.05 if isinstance(v, float) else r["project"].get(k) == v)
                     for k, v in exp.items())
            turns_ok.append(ck["pass"] and st)
            state_ok.append(st)
        multi.append({"id": conv["id"], "turns": len(conv["turns"]), "turns_passed": sum(turns_ok), "pass": all(turns_ok),
                      "state_retained": all(state_ok)})
    hold = []
    for text, tools in HOLDOUT:
        r = handle_turn(None, text, "bench")
        ck = check(r, tools, [])
        hold.append({"text": text, "expected_any": tools, **ck})
    lat = [c["latency_s"] for c in single] + [h["latency_s"] for h in hold]
    fam = defaultdict(list)
    for c in single:
        fam[c["family"]].append(c["pass"])
    by_topic = defaultdict(list)
    for c in single:
        by_topic[c["topic"]].append(c["pass"])
    summary = {
        "engine": single[0]["mode"] if single else None,
        "single_turn": {"cases": len(single), "passed": sum(c["pass"] for c in single),
                        "tool_selection_accuracy": round(sum(c["tool_ok"] for c in single) / len(single), 4),
                        "block_success": round(sum(c["blocks_ok"] for c in single) / len(single), 4),
                        "error_free": round(sum(c["no_error"] for c in single) / len(single), 4),
                        "families": len(fam), "families_all_passed": sum(all(v) for v in fam.values())},
        "by_style": {s: f"{sum(c['pass'] for c in single if c['style'] == s)}/{sum(1 for c in single if c['style'] == s)}" for s in ("en", "enx", "pt")},
        "multi_turn": {"conversations": len(multi), "passed": sum(m["pass"] for m in multi),
                       "turns": sum(m["turns"] for m in multi), "turns_passed": sum(m["turns_passed"] for m in multi),
                       "state_retained": sum(m["state_retained"] for m in multi)},
        "holdout": {"cases": len(hold), "passed": sum(h["pass"] for h in hold)},
        "latency_s": {"p50": round(statistics.median(lat), 3), "p95": round(sorted(lat)[int(0.95 * len(lat)) - 1], 3), "max": round(max(lat), 3)},
        "runtime_s": round(time.time() - t0, 1),
    }
    failures = {"single": [c for c in single if not c["pass"]], "multi": [m for m in multi if not m["pass"]],
                "holdout": [h for h in hold if not h["pass"]], "topics": {k: f"{sum(v)}/{len(v)}" for k, v in by_topic.items()}}
    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    (out / "benchmark_results.json").write_text(json.dumps({"summary": summary, "failures": failures,
                                                            "single": single, "multi": multi, "holdout": hold}, indent=1, default=str))
    return {"summary": summary, "failures": failures}


if __name__ == "__main__":
    res = run()
    print(json.dumps(res["summary"], indent=1))
    for k in ("single", "holdout"):
        for f in res["failures"][k][:40]:
            print("FAIL", k, f.get("id", ""), "|", f["text"][:80], "| called", f["called"], "| tool_ok", f["tool_ok"], "blocks_ok", f["blocks_ok"], "no_err", f["no_error"])
    for m in res["failures"]["multi"][:10]:
        print("FAIL multi", m)
