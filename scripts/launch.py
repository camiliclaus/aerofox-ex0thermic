"""One-command local launcher (Windows, macOS, Linux).

    python scripts/launch.py            # create .venv if needed, install, start, open browser
    python scripts/launch.py --no-browser --port 8010

Uses only the Python standard library until the virtual environment exists.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import json
import socket
import subprocess
import sys
import time
import urllib.request
import venv
import webbrowser
from pathlib import Path
from local_model import start_default

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def say(msg: str) -> None:
    print(f"[AeroFox] {msg}", flush=True)


def fail(msg: str, hint: str = "") -> None:
    say("ERROR: " + msg)
    if hint:
        say("How to fix: " + hint)
    sys.exit(1)


def port_free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--offline", action="store_true", help="deliberately disable model inference")
    ap.add_argument("--external-local-model", action="store_true", help="use an already running local model")
    ap.add_argument("--model-profile", choices=("auto", "gpu", "cpu"), default="auto")
    ap.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 to let teammates on your network connect")
    a = ap.parse_args()

    if sys.version_info < (3, 10):
        fail(f"Python {sys.version.split()[0]} is too old.", "install Python 3.10 or newer from https://www.python.org/downloads/ "
             "(tick 'Add python.exe to PATH' on Windows), then run START_AEROFOX.bat again.")
    for p in ("data/processed/flex_tests.csv", "data/findings/findings.json", "frontend/index.html"):
        if not (ROOT / p).exists():
            fail(f"missing {p}", "re-extract the AeroFox ZIP or re-clone the repository; the data snapshot is part of it.")

    if not PY.exists():
        say("Creating a private Python environment in .venv (first run only)...")
        venv.EnvBuilder(with_pip=True).create(VENV)
    req = ROOT / "requirements.txt"
    stamp = VENV / ".req-hash"
    h = hashlib.sha256(req.read_bytes()).hexdigest()
    if not stamp.exists() or stamp.read_text() != h:
        say("Installing dependencies (first run takes 1-3 minutes)...")
        r = subprocess.run([str(PY), "-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", str(req)])
        if r.returncode != 0:
            fail("dependency installation failed.", "check your internet connection (needed once), or a corporate proxy; then retry.")
        stamp.write_text(h)

    port = a.port
    while not port_free(port) and port < a.port + 20:
        port += 1
    if port != a.port:
        say(f"Port {a.port} is busy; using {port}.")
    env = dict(os.environ)
    env.setdefault("PYTHONUTF8", "1")
    model_process = None
    offline = a.offline or env.get("AEROFOX_LLM", "").lower() == "off"
    if offline:
        env["AEROFOX_LLM"] = "off"
    elif not a.external_local_model:
        try:
            say("Preparing the open-weight local model...")
            model_process, env["AEROFOX_MODEL"], env["AEROFOX_LLM_URL"] = start_default(a.model_profile)
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            fail(str(exc), "check docs/MODEL_RUNTIME.md or launch with --offline for the evidence engine.")
    cmd = [str(PY), "-m", "uvicorn", "aerofox.api.app:app", "--host", a.host, "--port", str(port), "--no-access-log"]
    say("Starting server: " + " ".join(cmd[2:]))
    proc = subprocess.Popen(cmd, cwd=ROOT / "backend", env=env)
    url = f"http://127.0.0.1:{port}"
    for _ in range(60):
        if proc.poll() is not None:
            fail("the server stopped during start-up (see messages above).")
        try:
            with urllib.request.urlopen(url + "/api/health", timeout=2) as r:
                if r.status == 200:
                    health = json.load(r)
                    break
        except OSError:
            time.sleep(0.5)
    else:
        proc.terminate()
        fail("the server did not answer within 30 s.")
    say(f"AeroFox is running at {url}")
    say("Language model: " + (health["llm"]["model"] if health["llm"]["ready"] else "unavailable; offline evidence"))
    if a.host == "0.0.0.0":
        say("Teammates on the same network can open http://<this-computer's-IP>:%d" % port)
    say("Press Ctrl+C in this window to stop.")
    if not a.no_browser:
        webbrowser.open(url)
    try:
        proc.wait()
    except KeyboardInterrupt:
        say("Stopping...")
        proc.terminate()
    finally:
        if model_process and model_process.poll() is None:
            model_process.terminate()


if __name__ == "__main__":
    main()
