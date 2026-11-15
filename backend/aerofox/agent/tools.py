"""Tool registry: typed, validated wrappers around the deterministic analyses.

Each tool has a JSON schema (strict, additionalProperties false) used for the
language model and a Python function. `run_tool` validates inputs, enforces a
time limit, and converts failures into explicit error results so the model can
never 'invent' a value after a tool failed.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import time
from dataclasses import dataclass
from typing import Any, Callable

from ..evidence.store import get_store
from ..science import analyses as A
from ..science.units import UnitError, convert
from ..science.workflows import fire_safety_workflow
from .state import ProjectState, Session

TOOL_TIMEOUT_S = 20
_pool = cf.ThreadPoolExecutor(max_workers=8, thread_name_prefix="tool")


@dataclass
class Tool:
    name: str
    description: str
    schema: dict
    fn: Callable[..., dict]
    needs_session: bool = False

    def spec(self) -> dict:
        return {"name": self.name, "description": self.description, "input_schema": self.schema, "strict": True}


def _obj(props: dict, required: list[str] | None = None) -> dict:
    # strict mode: every property must be listed in required; optional ones accept null
    props = {k: dict(v) for k, v in props.items()}
    for k, v in props.items():
        if k not in (required or []):
            t = v.get("type")
            v["type"] = [t, "null"] if isinstance(t, str) else t
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


NUM, STR = {"type": "number"}, {"type": "string"}


def _search(session: Session, query: str, k: int | None = None) -> dict:
    res = get_store().search(query, k=min(k or 6, 10), scenario=session.project.scenario())
    return {"summary": f"{len(res)} evidence items retrieved.", "blocks": [], "evidence": [r["id"] for r in res],
            "warnings": [], "data": {"results": [{x: r[x] for x in ("id", "title", "text", "quote", "status", "source", "locator",
                                                                  "applicability", "applicability_notes")} for r in res]}}


def _get_evidence(session: Session, ids: list[str]) -> dict:
    s = get_store()
    out, missing = [], []
    for i in ids[:10]:
        e = s.get(i)
        (out.append(e.card()) if e else missing.append(i))
    return {"summary": f"{len(out)} items.", "blocks": [], "evidence": [o["id"] for o in out],
            "warnings": [f"Unknown evidence id(s): {', '.join(missing)}"] if missing else [], "data": {"items": out}}


def _update_project(session: Session, **fields) -> dict:
    changes = {}
    current = session.project.model_dump()
    for k, v in fields.items():
        if v is None:
            continue
        if k in ("materials", "ignition_sources", "compartments", "notes") and isinstance(v, list):
            v = list(dict.fromkeys(current.get(k, []) + v))
        current[k] = v
        changes[k] = v
    try:
        session.project = ProjectState(**current)
    except Exception as e:  # pydantic validation error -> explicit tool error
        raise A.AnalysisError(f"invalid project values: {e}")
    return {"summary": "Project updated: " + ", ".join(f"{k}={v}" for k, v in changes.items()) if changes else "No changes.",
            "blocks": [], "evidence": [], "warnings": [], "data": {"project": session.project.known(), "changed": list(changes)}}


def _export(session: Session, artifact_id: str | None = None) -> dict:
    arts = list(session.artifacts.values())
    if artifact_id:
        arts = [a for a in arts if a["artifact_id"] == artifact_id]
    else:
        arts = [session.artifacts[a] for a in session.last_blocks if a in session.artifacts] or arts[-1:]
    if not arts:
        return {"summary": "There is no visual in this conversation yet to export.", "blocks": [], "evidence": [],
                "warnings": [], "data": {"links": []}}
    links = []
    for artifact in arts:
        extension = "mmd" if artifact["type"] == "flowchart" else "csv"
        aid = artifact["artifact_id"]
        links.append({"artifact_id": aid, "title": artifact.get("title", ""),
                      "url": f"/api/sessions/{session.id}/artifacts/{aid}.{extension}",
                      "format": "Mermaid" if extension == "mmd" else "CSV"})
    return {"summary": "Export ready for " + ", ".join(l["title"] for l in links), "blocks": [{"type": "downloads", "id": "downloads", "links": links}],
            "evidence": [], "warnings": [], "data": {"links": links}}


def _convert(session: Session, value: float, from_unit: str, to_unit: str) -> dict:
    try:
        r = convert(value, from_unit, to_unit)
    except UnitError as e:
        raise A.AnalysisError(str(e))
    return {"summary": f"{value:g} {from_unit} = {r['value']:.6g} {to_unit}", "blocks": [], "evidence": [], "warnings": [], "data": r}


TOOLS: list[Tool] = [
    Tool("search_evidence", "Search the AeroFox evidence store (NASA PSI findings, curated NASA literature quotes, investigation "
         "metadata, NTRS abstracts). Results are ranked by text relevance and by how well each item's test conditions match the "
         "current project (gravity, pressure, O2). Use before making any factual claim you have not already retrieved.",
         _obj({"query": STR, "k": {"type": "integer"}}, ["query"]), _search, True),
    Tool("get_evidence", "Fetch full evidence cards by id (e.g. F04, LIT-ATM-ARTEMIS, PSI-69, NTRS-20150023456).",
         _obj({"ids": {"type": "array", "items": STR}}, ["ids"]), _get_evidence, True),
    Tool("update_project", "Record project parameters the USER explicitly stated (never guess). Lists are merged. system is one of "
         "lunar_habitat, mars_habitat, space_station, crew_vehicle, pressurized_rover, eva_suit, battery_system; gravity one of "
         "micro, lunar, mars, earth; pressure in kPa; o2_pct in percent.",
         _obj({"system": STR, "gravity": STR, "pressure_kPa": NUM, "o2_pct": NUM, "materials": {"type": "array", "items": STR},
               "ignition_sources": {"type": "array", "items": STR}, "ventilation": STR, "detectors": STR, "suppression": STR,
               "crew_size": {"type": "integer"}, "notes": {"type": "array", "items": STR}}), _update_project, True),
    Tool("experiment_overview", "Describe a NASA combustion investigation from PSI metadata (objective, platform, hardware, file "
         "catalog). Names: FLEX, FLEX-2, Saffire-I/II/III, BASS, BASS-II, SAME, SAME-R, DAFT, CFI, CFI-G, ACME, SPICE, SLICE, SoFIE, or PSI-nn.",
         _obj({"name": STR}, ["name"]), lambda name: A.experiment_overview(name)),
    Tool("flex_query", "Filter FLEX droplet tests (PSI-69) by fuel (methanol/heptane), diluent (N2/CO2/He), O2 mole fraction and pressure "
         "(kPa) and summarise burning-rate constants and outcomes.",
         _obj({"fuel": STR, "diluent": STR, "o2_min": NUM, "o2_max": NUM, "p_min_kpa": NUM, "p_max_kpa": NUM}),
         lambda **k: A.flex_query(**k)),
    Tool("flex_run", "Look up a single official FLEX run number. Never substitute another run.",
         _obj({"number": {"type": "integer", "minimum": 1, "maximum": 999}}, ["number"]), A.flex_run),
    Tool("chart_flex_burning_rate_vs_oxygen", "Scatter chart of FLEX burning-rate constant K versus O2 mole fraction by diluent, with "
         "regression of K on O2, pressure and diluent.", _obj({"fuel": STR}), lambda fuel=None: A.flex_k_vs_o2(fuel)),
    Tool("flex035_case_study", "FLEX-035 case: droplet keeps regressing after visible flame extinction (cool flame). Returns chart and fitted rates.",
         _obj({}), lambda: A.flex035_case()),
    Tool("saffire2_flow_case_study", "Saffire-II tabulated vs telemetry-measured duct flow per sample (sample 2-6 at 25 cm/s), with spread rates.",
         _obj({}), lambda: A.saffire2_flow_case()),
    Tool("smoke_particle_sizes", "SAME-R smoke particle size (arithmetic mean diameter) by material, with detector-data limitations.",
         _obj({}), lambda: A.smoke_particles()),
    Tool("assess_atmosphere", "Compute O2 partial pressure for a cabin atmosphere, compare with ISS and Artemis atmospheres, and count "
         "NASA PSI tests near those conditions; returns a coverage chart. o2_unit is '%' or 'fraction'.",
         _obj({"pressure": NUM, "pressure_unit": STR, "o2": NUM, "o2_unit": STR, "gravity": STR}, ["pressure", "pressure_unit", "o2"]),
         lambda pressure, pressure_unit, o2, o2_unit=None, gravity=None: A.assess_atmosphere(pressure, pressure_unit, o2, o2_unit or "%", gravity)),
    Tool("fire_safety_factors", "Evidence-weighted, qualitative prioritisation of fire-safety factors for a system (lunar_habitat, "
         "mars_habitat, space_station, crew_vehicle, pressurized_rover, eva_suit, battery_system). Returns a decision matrix; "
         "never numeric risk scores.", _obj({"system": STR, "gravity": STR, "pressure_kPa": NUM, "o2_pct": NUM}, ["system"]),
         lambda system, gravity=None, pressure_kPa=None, o2_pct=None: A.fire_safety_factors(system, gravity, pressure_kPa, o2_pct)),
    Tool("fire_safety_workflow", "Draw a conceptual verification flowchart with decision branches for an EVA suit, lunar or Mars habitat, or pressurized rover.",
         _obj({"system": {"type": "string", "enum": ["eva_suit", "lunar_habitat", "mars_habitat", "pressurized_rover"]},
               "language": {"type": "string", "enum": ["en", "pt"]}}, ["system"]), fire_safety_workflow),
    Tool("compare_gravity_regimes", "Compare orbital microgravity, lunar, Mars and Earth gravity for fire behaviour; returns the "
         "published LUCI lunar-gravity spread rates and a regime/evidence table.", _obj({}), lambda: A.gravity_comparison()),
    Tool("evidence_coverage_matrix", "Matrix of which NASA experiments support which engineering decisions (direct/partial/none).",
         _obj({}), lambda: A.evidence_coverage_matrix()),
    Tool("materials_evidence", "Microgravity flammability and smoke evidence for named materials from Saffire, BASS-II and SAME-R.",
         _obj({"materials": {"type": "array", "items": STR}}, ["materials"]), lambda materials: A.materials_evidence(materials)),
    Tool("droplet_burn_time", "d²-law burnout time for a droplet; K given directly or looked up from FLEX data for a fuel and O2 fraction.",
         _obj({"d0_mm": NUM, "K_mm2s": NUM, "fuel": STR, "x_o2": NUM}, ["d0_mm"]),
         lambda d0_mm, K_mm2s=None, fuel=None, x_o2=None: A.droplet_burn(d0_mm, K_mm2s, fuel, x_o2)),
    Tool("simulate_ventilation", "Well-mixed compartment model of a passive smoke surrogate. compartments: list of {name, volume_m3, "
         "supply_m3s, exhaust_m3s, source_rate, source_start_s, source_duration_s, c0}; flows: list of {from, to, m3s}. Volume flow "
         "must balance in every compartment. Inputs are synthetic unless the user gives real values.",
         _obj({"compartments": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": [
             "name", "volume_m3", "supply_m3s", "exhaust_m3s", "source_rate", "source_start_s", "source_duration_s", "c0"],
             "properties": {"name": STR, "volume_m3": NUM, "supply_m3s": NUM, "exhaust_m3s": NUM, "source_rate": NUM,
                            "source_start_s": NUM, "source_duration_s": NUM, "c0": NUM}}},
               "flows": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["from", "to", "m3s"],
                                                    "properties": {"from": STR, "to": STR, "m3s": NUM}}},
               "t_end_s": NUM}, ["compartments", "flows"]),
         lambda compartments, flows, t_end_s=None: A.ventilation_sim(compartments, flows, t_end_s or 1800)),
    Tool("compare_ventilation_designs", "Synthetic example comparing a battery bay connected to the crew module with an isolated, "
         "separately exhausted bay.", _obj({}), lambda: A.compare_ventilation_designs()),
    Tool("export_data", "Give CSV or Mermaid download links for visuals shown in this conversation (latest answer if no id).",
         _obj({"artifact_id": STR}), _export, True),
    Tool("convert_units", "Convert pressure, length, volume, flow, velocity or temperature units.",
         _obj({"value": NUM, "from_unit": STR, "to_unit": STR}, ["value", "from_unit", "to_unit"]), _convert, True),
]
REGISTRY = {t.name: t for t in TOOLS}


def run_tool(session: Session, name: str, args: dict[str, Any]) -> dict:
    """Execute a tool with a time limit. Always returns a dict with ok/error."""
    t0 = time.monotonic()
    tool = REGISTRY.get(name)
    if tool is None:
        return {"ok": False, "error": f"unknown tool {name}"}
    if not isinstance(args, dict):
        return {"ok": False, "error": "tool input must be an object"}
    allowed = set(tool.schema["properties"])
    extra = set(args) - allowed
    if extra:
        return {"ok": False, "error": f"unexpected argument(s): {sorted(extra)}"}
    clean = {k: v for k, v in args.items() if v is not None}
    try:
        call = (lambda: tool.fn(session, **clean)) if tool.needs_session else (lambda: tool.fn(**clean))
        res = _pool.submit(call).result(timeout=TOOL_TIMEOUT_S)
        res["ok"] = True
    except cf.TimeoutError:
        res = {"ok": False, "error": f"{name} timed out after {TOOL_TIMEOUT_S} s"}
    except (A.AnalysisError, ValueError, TypeError, KeyError) as e:
        res = {"ok": False, "error": str(e)[:400]}
    res["tool"], res["elapsed_s"] = name, round(time.monotonic() - t0, 3)
    return res


def result_for_model(res: dict) -> str:
    """Compact JSON for the language model: no chart series (token economy), but all numbers it may quote."""
    if not res.get("ok"):
        return json.dumps({"error": res.get("error"), "instruction": "Report this failure; do not substitute values."})
    blocks = [{"type": b.get("type"), "title": b.get("title"), "artifact_id": b.get("artifact_id")} for b in res.get("blocks", [])]
    data = json.dumps(res.get("data", {}), default=str)
    if len(data) > 6000:
        data = data[:6000] + "...(truncated)"
    return json.dumps({"summary": res.get("summary"), "evidence_ids": res.get("evidence", []), "warnings": res.get("warnings", []),
                       "shown_to_user": blocks, "data": json.loads(data) if not data.endswith("(truncated)") else data}, default=str)
