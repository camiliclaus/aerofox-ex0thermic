"""Read-only evidence store: processed NASA tables, findings, literature and metadata.

Loaded once at start-up and shared by all sessions (read-only, so no locking).
Retrieval combines an SQLite FTS5 (BM25) text index with an applicability score
that compares the experimental conditions of each item with the user's scenario.
"""
from __future__ import annotations

import json
import re
import sqlite3
import threading
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import pandas as pd

from ..config import settings

STATUS_LABEL = {
    "measured": "measured (PSI data, re-analysed by AeroFox)",
    "model_of_measurements": "statistical model of measured data",
    "published_statement": "published statement (NASA source)",
    "published_measurement": "published measurement",
    "published_interpretation": "published interpretation",
    "incident_record": "incident record",
    "metadata": "investigation metadata",
}


@dataclass
class Evidence:
    id: str
    kind: str                 # finding | literature | investigation | reference
    title: str
    text: str
    evidence_type: str
    source_title: str = ""
    url: str = ""
    locator: str = ""
    topics: list[str] = field(default_factory=list)
    conditions: dict = field(default_factory=dict)
    quote: str = ""
    accession: str = ""
    limitations: str = ""
    implication: str = ""
    uncertainty: str = ""

    def card(self) -> dict:
        return {"id": self.id, "kind": self.kind, "title": self.title, "text": self.text[:600],
                "quote": self.quote, "evidence_type": self.evidence_type,
                "status": STATUS_LABEL.get(self.evidence_type.split(" ")[0], self.evidence_type),
                "limitations": self.limitations, "uncertainty": self.uncertainty,
                "source": self.source_title, "url": self.url, "locator": self.locator}


# Words that map user vocabulary to topics used in the curated evidence.
SYNONYMS = {
    "moon": "lunar", "lua": "lunar", "lunar": "lunar", "mars": "mars", "marte": "mars", "martian": "mars",
    "droplet": "droplet", "gota": "droplet", "smoke": "smoke", "fumaça": "smoke", "fumaca": "smoke",
    "detector": "detection", "detecção": "detection", "deteccao": "detection", "oxygen": "oxygen", "oxigênio": "oxygen",
    "oxigenio": "oxygen", "ventilation": "ventilation", "ventilação": "ventilation", "ventilacao": "ventilation",
    "airflow": "flow", "fluxo": "flow", "suppression": "suppression", "supressão": "suppression", "extinguish": "suppression",
    "extinction": "extinction", "extinção": "extinction", "material": "materials", "materiais": "materials",
    "battery": "electrical", "bateria": "electrical", "wiring": "electrical", "electrical": "electrical",
    "atmosphere": "atmosphere", "atmosfera": "atmosphere", "pressure": "pressure",
    "pressão": "pressure", "pressao": "pressure", "egress": "egress", "evacuation": "egress", "evacuação": "egress",
}


class EvidenceStore:
    def __init__(self, data_dir: Path | None = None):
        self.data_dir = Path(data_dir or settings.data_dir)
        self.proc = self.data_dir / "processed"
        self.items: dict[str, Evidence] = {}
        self.sources: dict[str, dict] = {}
        self.tables: dict[str, pd.DataFrame] = {}
        self._lock = threading.Lock()
        self._load()
        self._index()

    # ------------------------------------------------------------------ loading
    def table(self, name: str) -> pd.DataFrame:
        if name not in self.tables:
            path = self.proc / f"{name}.csv"
            if not path.exists():
                raise KeyError(name)
            with self._lock:
                self.tables[name] = pd.read_csv(path, low_memory=False)
        return self.tables[name]

    def available_tables(self) -> list[str]:
        return sorted(p.stem for p in self.proc.glob("*.csv"))

    def _load(self) -> None:
        f = json.loads((self.data_dir / "findings" / "findings.json").read_text(encoding="utf-8"))
        self.figures = f.get("figures", [])
        for x in f["findings"]:
            self.items[x["id"]] = Evidence(
                id=x["id"], kind="finding", title=x["question"], text=x["result"],
                evidence_type=x.get("evidence_type", "measured"), source_title=x["dataset"],
                url="", locator=x["locator"],
                topics=[t.strip().lower() for t in re.split(r"[;,]", x.get("feature", "") + "," + x.get("applicability", ""))],
                conditions={"text": x.get("conditions", "")},
                limitations=x.get("limitations", ""), implication=x.get("implication", ""),
                uncertainty=x.get("uncertainty", ""),
            )
        lit = json.loads((self.data_dir / "curated" / "literature_evidence.json").read_text(encoding="utf-8"))
        self.sources = lit["sources"]
        for x in lit["evidence"]:
            src = self.sources[x["source"]]
            self.items[x["id"]] = Evidence(
                id=x["id"], kind="literature", title=src["title"], text=x["claim"], quote=x["quote"],
                evidence_type=x["evidence_type"], source_title=f'{src["authors"]} ({src["year"] or "n.d."}). {src["title"]}. {src["venue"]}.',
                url=src["url"], locator=x["locator"], topics=x["topics"], conditions=x.get("conditions", {}))
        inv = self.table("investigations")
        for r in inv.itertuples():
            text = " ".join(str(v) for v in [r.objective, r.hypothesis] if isinstance(v, str))
            self.items[r.accession] = Evidence(
                id=r.accession, kind="investigation", title=f"{r.accession} {r.acronym if isinstance(r.acronym, str) else ''} - {r.title}".replace("  ", " "),
                text=text[:1800], evidence_type="metadata",
                source_title=f"NASA Physical Sciences Informatics, {r.accession} (license {r.license}, PSI version {r.psi_version})",
                url=r.psi_url, locator="investigation metadata", accession=r.accession,
                topics=[str(r.sub_research_area or "").lower(), str(r.acronym or "").lower()],
                conditions={"gravity": "microgravity" if "Microgravity" in str(r.project_type) else "ground"})
        for p in sorted((self.data_dir / "raw" / "ntrs").glob("*.json")):
            d = json.loads(p.read_text(encoding="utf-8"))
            authors = ", ".join(a["meta"]["author"]["name"] for a in (d.get("authorAffiliations") or [])[:4])
            year = (d.get("distributionDate") or "")[:4]
            pubs = d.get("publications") or []
            if pubs and pubs[0].get("publicationDate"):
                year = pubs[0]["publicationDate"][:4]
            nid = f"NTRS-{d['id']}"
            self.items[nid] = Evidence(
                id=nid, kind="reference", title=d["title"], text=(d.get("abstract") or "")[:1800],
                evidence_type="published_statement", source_title=f"{authors} ({year}). {d['title']}. NTRS {d['id']}.",
                url=d["url"], locator="abstract", topics=[d.get("aerofox_reason", "").lower()])

    # ------------------------------------------------------------------ text index
    def _index(self) -> None:
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        self.db.execute("CREATE VIRTUAL TABLE ev USING fts5(id UNINDEXED, title, body, topics, tokenize='porter unicode61')")
        rows = [(e.id, e.title, f"{e.text} {e.quote} {e.locator}", " ".join(e.topics)) for e in self.items.values()]
        self.db.executemany("INSERT INTO ev VALUES (?,?,?,?)", rows)
        self.db.commit()

    @staticmethod
    def _fts_query(text: str) -> str:
        words = [w for w in re.findall(r"[A-Za-zÀ-ÿ0-9\-]{3,}", text.lower())]
        stop = {"the", "and", "what", "which", "how", "for", "with", "that", "this", "are", "does", "should", "about",
                "can", "you", "from", "into", "when", "would", "could", "have", "has", "was", "were", "show", "make",
                "uma", "que", "para", "com", "como", "qual", "quais", "sobre", "dos", "das", "por", "isso", "este", "esta"}
        terms = []
        for w in words:
            if w in stop:
                continue
            w = SYNONYMS.get(w, w)
            for t in w.split():
                terms.append('"' + t.replace('"', "") + '"')
        return " OR ".join(dict.fromkeys(terms)) or '"combustion"'

    def search(self, query: str, k: int = 6, scenario: dict | None = None, kinds: tuple[str, ...] | None = None) -> list[dict]:
        """Rank by BM25 then re-rank by condition applicability to the scenario."""
        q = self._fts_query(query)
        with self._lock:
            rows = self.db.execute("SELECT id, bm25(ev, 0.0, 2.0, 1.0, 1.5) FROM ev WHERE ev MATCH ? ORDER BY 2 LIMIT 60",
                                   (q,)).fetchall()
        out = []
        for rid, bm in rows:
            e = self.items[rid]
            if kinds and e.kind not in kinds:
                continue
            app, why = applicability(e, scenario or {})
            text_score = -bm
            kind_bonus = {"finding": 1.3, "literature": 1.2, "reference": 0.9, "investigation": 0.8}[e.kind]
            out.append((text_score * kind_bonus * (0.5 + app), e, app, why))
        out.sort(key=lambda t: -t[0])
        res = []
        for score, e, app, why in out[:k]:
            c = e.card()
            c.update(score=round(score, 3), applicability=round(app, 2), applicability_notes=why)
            res.append(c)
        return res

    def get(self, eid: str) -> Evidence | None:
        return self.items.get(eid)


def _gravity_class(text: str) -> str:
    t = (text or "").lower()
    if "lunar" in t or "moon" in t:
        return "lunar"
    if "mars" in t or "martian" in t:
        return "mars"
    if "micro" in t or "orbit" in t or "iss" in t or "cygnus" in t:
        return "micro"
    if "1 g" in t or "ground" in t or "earth" in t:
        return "earth"
    return ""


def applicability(e: Evidence, scenario: dict) -> tuple[float, list[str]]:
    """0..1 score: how well the evidence's regime matches the scenario. Explicit, rule-based."""
    if not scenario:
        return 0.5, []
    notes, score, n = [], 0.0, 0
    g_s = scenario.get("gravity")
    g_e = _gravity_class(str(e.conditions.get("gravity", "")) + " " + str(e.conditions.get("text", "")))
    if g_s and g_e:
        n += 1
        if g_s == g_e:
            score += 1
            notes.append(f"same gravity regime ({g_s})")
        elif {g_s, g_e} <= {"lunar", "mars"} or (g_s in ("lunar", "mars") and g_e in ("micro", "earth")):
            score += 0.3
            notes.append(f"evidence from {g_e} gravity; scenario is {g_s} (not directly transferable)")
        else:
            score += 0.4
            notes.append(f"evidence gravity {g_e} differs from scenario {g_s}")
    p_s, p_e = scenario.get("pressure_kPa"), e.conditions.get("pressure_kPa")
    if p_s and p_e:
        n += 1
        rel = abs(p_s - p_e) / max(p_s, 1)
        score += max(0.0, 1 - 2 * rel)
        notes.append(f"pressure {p_e:g} kPa vs scenario {p_s:g} kPa")
    o_s = scenario.get("o2_pct")
    o_e = e.conditions.get("o2_pct") or (e.conditions.get("o2_mole_fraction") or 0) * 100 or None
    if o_s and o_e:
        n += 1
        score += max(0.0, 1 - abs(o_s - o_e) / 10)
        notes.append(f"O2 {o_e:g}% vs scenario {o_s:g}%")
    if n == 0:
        return 0.5, notes
    return score / n, notes


@lru_cache(maxsize=1)
def get_store() -> EvidenceStore:
    return EvidenceStore()
