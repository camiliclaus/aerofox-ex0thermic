"""Concurrent-user load test against a running AeroFox server.

    python scripts/load_test.py --base http://127.0.0.1:8000 --users 40 --turns 3

Each simulated user runs its own multi-turn conversation with a distinct O2 level and
checks that the server returns *its* value on every turn (session isolation).
Start the server with a high AEROFOX_RATE_PER_MINUTE for this test, since all users share one address.
"""
import argparse
import concurrent.futures as cf
import json
import statistics
import time
import urllib.request


def post(base, path, body):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())
    return data, time.perf_counter() - t0


def user(base, i, turns):
    o2 = 21 + (i % 15)
    msgs = [f"Lunar habitat at 70 kPa and {o2}% oxygen: assess the atmosphere",
            "What is the strongest uncertainty?", "Can you export the data behind that graph?",
            "Explain that chart in simpler terms."][:turns]
    sid, lat, ok = None, [], True
    try:
        for m in msgs:
            d, dt = post(base, "/api/chat", {"message": m, "session_id": sid})
            sid = d["session_id"]
            lat.append(dt)
            ok &= d["project"].get("o2_pct") == o2
        return {"ok": ok, "lat": lat, "error": None}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "lat": lat, "error": str(e)[:120]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--users", type=int, default=40)
    ap.add_argument("--turns", type=int, default=3)
    a = ap.parse_args()
    t0 = time.perf_counter()
    with cf.ThreadPoolExecutor(a.users) as ex:
        res = list(ex.map(lambda i: user(a.base, i, a.turns), range(a.users)))
    wall = time.perf_counter() - t0
    lat = sorted(x for r in res for x in r["lat"])
    out = {"users": a.users, "turns_per_user": a.turns, "requests": len(lat), "wall_s": round(wall, 2),
           "throughput_rps": round(len(lat) / wall, 1), "isolation_ok": sum(r["ok"] for r in res),
           "errors": [r["error"] for r in res if r["error"]][:5],
           "latency_s": {"p50": round(statistics.median(lat), 3), "p95": round(lat[int(0.95 * len(lat)) - 1], 3),
                         "max": round(lat[-1], 3)} if lat else None}
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    main()
