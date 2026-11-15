"""Per-session state: typed project parameters plus a compact conversation record."""
from __future__ import annotations

import threading
import time
import uuid
from collections import OrderedDict
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Gravity = Literal["micro", "lunar", "mars", "earth"]


class ProjectState(BaseModel):
    """Engineering scenario the user is working on. Every field optional; nothing is invented."""
    system: str | None = Field(None, description="lunar_habitat, mars_habitat, space_station, crew_vehicle, pressurized_rover, eva_suit, battery_system")
    mission_phase: str | None = None
    gravity: Gravity | None = None
    pressure_kPa: float | None = Field(None, ge=5, le=1000)
    o2_pct: float | None = Field(None, gt=0, le=100)
    balance_gas: str | None = None
    materials: list[str] = Field(default_factory=list)
    ignition_sources: list[str] = Field(default_factory=list)
    ventilation: str | None = None
    detectors: str | None = None
    suppression: str | None = None
    crew_size: int | None = Field(None, ge=0, le=100)
    compartments: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @field_validator("materials", "ignition_sources", "compartments", "notes")
    @classmethod
    def _limit(cls, v: list[str]) -> list[str]:
        return [str(x)[:80] for x in v][:20]

    def scenario(self) -> dict:
        return {k: v for k, v in {"gravity": self.gravity, "pressure_kPa": self.pressure_kPa, "o2_pct": self.o2_pct}.items() if v}

    def known(self) -> dict:
        return {k: v for k, v in self.model_dump().items() if v not in (None, [], "")}

    def missing_for_design_review(self) -> list[str]:
        miss = []
        if not self.system:
            miss.append("system type")
        if self.pressure_kPa is None or self.o2_pct is None:
            miss.append("cabin pressure and O2 fraction")
        if not self.materials:
            miss.append("main interior materials")
        return miss


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    text: str
    t: float = Field(default_factory=time.time)


class Session(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    created: float = Field(default_factory=time.time)
    last_used: float = Field(default_factory=time.time)
    language: Literal["en", "pt"] = "en"
    preferred_language: Literal["en", "pt"] | None = None
    project: ProjectState = Field(default_factory=ProjectState)
    turns: list[Turn] = Field(default_factory=list)
    artifacts: dict[str, dict] = Field(default_factory=dict)   # artifact id -> block (for export)
    artifact_sequence: int = 0
    last_blocks: list[str] = Field(default_factory=list)      # ids of blocks in the previous answer
    last_topic: str | None = None                             # last analysis performed (for follow-ups)
    last_args: dict = Field(default_factory=dict)

    def remember(self, role: str, text: str) -> None:
        self.turns.append(Turn(role=role, text=text[:6000]))
        self.turns = self.turns[-30:]

    def add_artifact(self, block: dict) -> str:
        self.artifact_sequence += 1
        aid = f"{block.get('id', 'a')}-{self.artifact_sequence}"
        block["artifact_id"] = aid
        self.artifacts[aid] = block
        if len(self.artifacts) > 60:
            self.artifacts.pop(next(iter(self.artifacts)))
        return aid


class SessionStore:
    """Thread-safe in-memory sessions with TTL and LRU eviction. Each session is isolated."""

    def __init__(self, max_sessions: int, ttl_s: int):
        self.max, self.ttl = max_sessions, ttl_s
        self._d: OrderedDict[str, Session] = OrderedDict()
        self._locks: dict[str, threading.Lock] = {}
        self._g = threading.Lock()

    def get_or_create(self, sid: str | None) -> Session:
        now = time.time()
        with self._g:
            self._evict(now)
            if sid and sid in self._d:
                s = self._d.pop(sid)
                s.last_used = now
                self._d[sid] = s
                return s
            if len(self._d) >= self.max:
                old, _ = self._d.popitem(last=False)
                self._locks.pop(old, None)
            s = Session()
            self._d[s.id] = s
            self._locks[s.id] = threading.Lock()
            return s

    def lock(self, sid: str) -> threading.Lock:
        with self._g:
            return self._locks.setdefault(sid, threading.Lock())

    def get(self, sid: str) -> Session | None:
        with self._g:
            self._evict(time.time())
            return self._d.get(sid)

    def reset(self, sid: str) -> Session:
        with self._g:
            self._d.pop(sid, None)
        return self.get_or_create(None)

    def _evict(self, now: float) -> None:
        for k in [k for k, s in self._d.items() if now - s.last_used > self.ttl]:
            self._d.pop(k, None)
            self._locks.pop(k, None)

    def __len__(self) -> int:
        return len(self._d)
