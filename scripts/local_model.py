"""Install and supervise the pinned CPU inference model on Windows."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import time
from pathlib import Path
from urllib.request import ProxyHandler, build_opener
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path(os.environ.get("AEROFOX_MODEL_DIR", ROOT / ".models"))
RUNTIME = "llama-b8230-bin-win-cpu-x64.zip"
WEIGHTS = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
GPU_RUNTIME = "llama-b8230-bin-win-vulkan-x64.zip"
GPU_WEIGHTS = "Qwen3-4B-Q4_K_M.gguf"
FILES = {
    RUNTIME: (
        "https://github.com/ggml-org/llama.cpp/releases/download/b8230/" + RUNTIME,
        "431419c8e0f41602797397b0e53e3a6755d8312fc9815b02490c22551f0cfb30",
    ),
    WEIGHTS: (
        "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/91cad51170dc346986eccefdc2dd33a9da36ead9/" + WEIGHTS,
        "6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e",
    ),
    GPU_RUNTIME: (
        "https://github.com/ggml-org/llama.cpp/releases/download/b8230/" + GPU_RUNTIME,
        "4dd4e492d8c03ec34b1cf3e2b2817e2af1f45700f57450456fb6787f63eddf78",
    ),
    GPU_WEIGHTS: (
        "https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/bc640142c66e1fdd12af0bd68f40445458f3869b/" + GPU_WEIGHTS,
        "7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5",
    ),
}
ENDPOINT = "http://127.0.0.1:8793"
GPU_ENDPOINT = "http://127.0.0.1:8796"
MODEL = "aerofox-qwen-1.5b"
GPU_MODEL = "aerofox-qwen3-4b"


def _sha(path):
    with path.open("rb") as stream:
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _verified(path, expected):
    return path.is_file() and _sha(path) == expected


def _download(name):
    target = CACHE / name
    url, expected = FILES[name]
    if _verified(target, expected):
        return target
    curl = shutil.which("curl.exe")
    if not curl:
        raise RuntimeError("Windows curl.exe is required for the first model download")
    partial = target.with_suffix(target.suffix + ".part")
    print(f"[AeroFox] Downloading {name} from its publisher", flush=True)
    if not _verified(partial, expected):
        subprocess.run([curl, "--fail", "--location", "--retry", "2", "--connect-timeout", "15",
                        "--max-time", "900", "--continue-at", "-", "--output", str(partial), url], check=True)
    if not _verified(partial, expected):
        raise RuntimeError(f"SHA-256 mismatch. Remove {partial} and retry.")
    partial.replace(target)
    return target


def _runtime(filename):
    runtime = CACHE / ("vulkan" if filename == GPU_RUNTIME else "runtime")
    zip_path = _download(filename)
    stamp = runtime / ".verified"
    digest = FILES[filename][1]
    candidates = list(runtime.rglob("llama-server.exe")) if stamp.is_file() and stamp.read_text().strip() == digest else []
    if not candidates:
        with ZipFile(zip_path) as archive:
            archive.extractall(runtime)
        candidates = list(runtime.rglob("llama-server.exe"))
        if not candidates:
            raise RuntimeError("The pinned archive did not contain llama-server.exe")
        stamp.write_text(digest, encoding="ascii")
    return candidates[0]


def ready(endpoint=ENDPOINT, model=MODEL):
    try:
        opener = build_opener(ProxyHandler({}))
        with opener.open(endpoint + "/v1/models", timeout=1) as stream:
            return any(item.get("id") == model for item in json.load(stream)["data"])
    except (OSError, ValueError, KeyError, TypeError):
        return False


def _has_discrete_gpu():
    executable = shutil.which("nvidia-smi")
    if executable:
        try:
            response = subprocess.check_output([executable, "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                                               text=True, timeout=4)
            return any(int(line) >= 5800 for line in response.splitlines() if line.strip().isdigit())
        except (OSError, subprocess.SubprocessError):
            return False
    return False


def _vulkan_device(runtime):
    result = subprocess.run([str(runtime), "--list-devices"], capture_output=True, text=True, timeout=20, check=True)
    for match in re.finditer(r"(Vulkan\d+): NVIDIA[^\n]*\((\d+) MiB, (\d+) MiB free\)", result.stdout + result.stderr):
        if int(match[3]) >= 4200:
            return match[1]
    raise RuntimeError("Vulkan did not find an NVIDIA GPU with enough free memory")


def start_default(profile="auto"):
    gpu = profile == "gpu" or profile == "auto" and _has_discrete_gpu()
    alias, endpoint, port = (GPU_MODEL, GPU_ENDPOINT, 8796) if gpu else (MODEL, ENDPOINT, 8793)
    if ready(endpoint, alias):
        return None, alias, endpoint
    if platform.system() != "Windows" or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise RuntimeError("Use the documented self-hosted llama.cpp instructions on this OS")
    CACHE.mkdir(parents=True, exist_ok=True)
    runtime = _runtime(GPU_RUNTIME if gpu else RUNTIME)
    model = _download(GPU_WEIGHTS if gpu else WEIGHTS)
    threads = str(min(6, max(2, (os.cpu_count() or 4) // 2)))
    cmd = [str(runtime), "--model", str(model), "--host", "127.0.0.1", "--port", str(port),
           "--alias", alias, "-c", "8192", "-np", "1", "-t", threads, "--log-disable", "--cache-ram", "0"]
    if gpu:
        cmd += ["--reasoning-budget", "0", "--device", _vulkan_device(runtime), "--n-gpu-layers", "99"]
    process = subprocess.Popen(cmd, cwd=runtime.parent, creationflags=subprocess.CREATE_NO_WINDOW)
    for _ in range(150):
        if process.poll() is not None:
            raise RuntimeError("llama.cpp stopped while loading its weights")
        if ready(endpoint, alias):
            return process, alias, endpoint
        time.sleep(.4)
    process.terminate()
    raise RuntimeError("llama.cpp did not become ready")


if __name__ == "__main__":
    proc, _, _ = start_default()
    print("[AeroFox] Local inference ready", flush=True)
    if proc:
        try:
            proc.wait()
        finally:
            proc.terminate()

