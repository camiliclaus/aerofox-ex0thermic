"""Prepare a portable release from tracked and unignored project files."""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
SECRET = re.compile(rb"(?:sk-(?:ant-|proj-)?[A-Za-z0-9_-]{26,}|gh[pousr]_[A-Za-z0-9]{28,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)")
TEXT = {".env", ".py", ".ps1", ".bat", ".sh", ".txt", ".md", ".json", ".yaml", ".yml", ".html", ".js", ".ipynb"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    names = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT
    ).decode("utf-8").split("\0")
    files = []
    for name in sorted(set(names) - {""}):
        path = ROOT / name
        if not path.is_file() or path.is_symlink():
            continue
        if path.suffix in {".gguf", ".safetensors", ".log", ".part", ".pem", ".key"}:
            continue
        if name.startswith(".env") and name != ".env.example":
            continue
        if (path.suffix in TEXT or name == ".env.example") and SECRET.search(path.read_bytes()):
            raise RuntimeError(f"Possible secret in {name}")
        files.append((path, name))
    with ZipFile(args.output, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for path, name in files:
            archive.write(path, "aerofox/" + name)
    with ZipFile(args.output) as archive:
        if corrupt := archive.testzip():
            raise RuntimeError(f"Corrupt ZIP entry {corrupt}")
    with args.output.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    args.output.with_suffix(".zip.sha256").write_text(f"{digest}  {args.output.name}\n", encoding="ascii")
    print(f"{len(files)} files, {args.output.stat().st_size:,} bytes, SHA-256 {digest}")


if __name__ == "__main__":
    main()

