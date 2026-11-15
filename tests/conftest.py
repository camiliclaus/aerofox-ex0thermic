import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
# Tests never call a real provider unless explicitly asked.
os.environ.setdefault("AEROFOX_LLM", "off")
os.environ.setdefault("AEROFOX_RATE_PER_MINUTE", "1000")
