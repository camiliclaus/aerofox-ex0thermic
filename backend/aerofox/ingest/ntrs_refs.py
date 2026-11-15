"""NASA Technical Reports Server references used by AeroFox.

    python -m aerofox.ingest.ntrs_refs

Downloads citation metadata (committed: data/raw/ntrs/<id>.json) and full text
(cache only: data/cache/ntrs/<id>.txt). Full texts are not redistributed because
some NTRS records flag third-party material; metadata and abstracts are.
Each reference carries the reason it was included.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .fetch import fetch

ROOT = Path(__file__).resolve().parents[3]
META = ROOT / "data" / "raw" / "ntrs"
CACHE = ROOT / "data" / "cache" / "ntrs"
API = "https://ntrs.nasa.gov/api/citations"

REFERENCES = {
    "20150023456": "FLEX detailed test-by-test results (NASA/TP-2015-216046); authoritative FLEX numbering and FLEX-035 description",
    "20090014812": "MDCA/FLEX hardware description",
    "20130014061": "Methanol droplet combustion in O2-inert environments (FLEX)",
    "20140006750": "Cool-flame extinction during n-alkane droplet combustion (FLEX)",
    "20160000344": "Cool-flame supported droplet combustion",
    "20205008449": "Inert-gas effects on cool-flame droplet combustion (CFI)",
    "20170008805": "Saffire-I/II large-scale flammability results; Saffire-II flow per sample",
    "20170000230": "Saffire programme objectives and status",
    "20170007283": "Spacecraft fire safety research at NASA GRC (overview)",
    "20210011385": "BASS-II summary report (NASA TM)",
    "20150019858": "BASS-II on-board CSA-CP / CDM sensor readings",
    "20130000422": "SAME-2 (SAME-R) smoke particle morphology and size",
    "20200000361": "SoFIE project on ISS",
    "20250010653": "Lunar Combustion Investigation (LUCI): flammability in simulated lunar gravity",
    "20210020446": "Impact of lunar gravity on material flammability",
    "20210020516": "Fire on the Moon: solid-fuel experiments",
    "20240008623": "Flammability of Materials on the Moon (planned lunar-surface experiment)",
    "20260002050": "Surface-vehicle atmosphere considerations for Moon-to-Mars exploration",
    "20040053567": "Upward/downward flame spread and extinction in partial gravity",
    "19980209743": "Fire safety in extraterrestrial environments",
    "20010074098": "Fire suppression in extraterrestrial environments",
    "20170006615": "Mixed-convection blowoff limits vs oxygen concentration",
    "20160012691": "Correlation of 1-g mixed-convection and microgravity forced-flow blowoff limits",
    "20150008961": "Microgravity flammability of PMMA rods in concurrent flow",
}


def run() -> dict:
    META.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    status = {}
    for rid, reason in REFERENCES.items():
        res, body = fetch(f"{API}/{rid}", expect=("application/json",))
        meta_path = META / f"{rid}.json"
        if res.ok:
            d = json.loads(body)
            keep = {k: d.get(k) for k in ("id", "title", "abstract", "stiType", "distributionDate", "publications",
                                          "authorAffiliations", "center", "subjectCategories", "keywords",
                                          "copyright", "downloads", "otherReportNumbers")}
            keep["aerofox_reason"] = reason
            keep["url"] = f"https://ntrs.nasa.gov/citations/{rid}"
            meta_path.write_text(json.dumps(keep, indent=1))
            dl = (d.get("downloads") or [{}])[0].get("links", {}).get("fulltext")
            if dl and not (CACHE / f"{rid}.txt").exists():
                fetch("https://ntrs.nasa.gov" + dl, CACHE / f"{rid}.txt", read_timeout=120)
            status[rid] = "verified_this_run"
        else:
            status[rid] = "snapshot" if meta_path.exists() else f"missing ({res.error})"
    return status


if __name__ == "__main__":
    s = run()
    print(json.dumps(s, indent=1))
    sys.exit(0 if all(not v.startswith("missing") for v in s.values()) else 1)
