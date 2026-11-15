"""Deterministic scientific analyses over the evidence store.

Every function returns a plain dict:
    summary   short factual text built from computed values
    blocks    list of chart / table / matrix specs rendered by the frontend
    evidence  ids of evidence items supporting the result
    warnings  applicability limits that must be shown with the result
    data      machine-readable values (used by the language model and tests)
No function invents data: if a request cannot be answered from the snapshot,
it says so in `warnings` and returns no chart.
"""
from __future__ import annotations

import json
import math
import re
from functools import lru_cache

import numpy as np
import pandas as pd

from ..config import settings
from ..evidence.store import get_store
from . import compartment as cm
from .units import ATM_KPA, atmosphere, o2_fraction, to_kpa

REF_ATMOSPHERES = [
    {"name": "ISS cabin (nominal)", "pressure_kPa": 101.3, "o2_pct": 21.0, "evidence": []},
    {"name": "Artemis sustained target", "pressure_kPa": 56.5, "o2_pct": 34.0, "evidence": ["LIT-ATM-ARTEMIS"]},
    {"name": "Alternative vehicle atmosphere", "pressure_kPa": 66.2, "o2_pct": 28.5, "evidence": ["LIT-ATM-ALT"]},
]
LEVEL_ORDER = {"direct": 2, "partial": 1, "none": 0}


class AnalysisError(ValueError):
    """Raised for invalid inputs; message is safe to show to the user."""


def _r(x, n=3):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), n)


@lru_cache(maxsize=1)
def factors_kb() -> dict:
    return json.loads((settings.data_dir / "curated" / "fire_factors.json").read_text(encoding="utf-8"))


EXPERIMENTS = {
    "flex": "PSI-69", "flex-2": "PSI-68", "flex2": "PSI-68", "saffire-i": "PSI-98", "saffire-1": "PSI-98",
    "saffire-ii": "PSI-99", "saffire-2": "PSI-99", "saffire-iii": "PSI-100", "saffire-3": "PSI-100",
    "saffire": "PSI-99", "bass": "PSI-26", "bass-ii": "PSI-25", "bass-2": "PSI-25", "same": "PSI-102",
    "same-r": "PSI-101", "daft": "PSI-47", "cfi": "PSI-39", "cool flames": "PSI-39", "cfi-g": "PSI-159",
    "acme": "PSI-21", "spice": "PSI-107", "slice": "PSI-106", "sofie": None,
    "flame extinguishment": "PSI-69", "burning and suppression of solids": "PSI-26", "smoke aerosol measurement experiment-reflight": "PSI-101", "smoke aerosol measurement": "PSI-102",
    "smoke and aerosol measurement": "PSI-102", "dust and aerosol": "PSI-47", "cool flames investigation": "PSI-39",
    "advanced combustion via microgravity": "PSI-21", "smoke point in co-flow": "PSI-107", "structure and liftoff": "PSI-106",
    "spacecraft fire experiment": "PSI-99", "solid fuel ignition and extinction": None,
}
KEY_FINDINGS = {"PSI-69": ["F01", "F02", "F03", "F04", "F11"], "PSI-99": ["F05", "F06"], "PSI-101": ["F07", "F08"],
                "PSI-102": ["F07"], "PSI-25": ["F09"], "PSI-98": ["F09"], "PSI-39": ["F04"]}


def resolve_experiment(name: str) -> str | None:
    n = name.strip().lower()
    if re.fullmatch(r"psi-\d+", n):
        return n.upper()
    n = n.replace("saffire ii", "saffire-ii").replace("saffire iii", "saffire-iii").replace("saffire i", "saffire-i")
    n = n.replace("bass ii", "bass-ii").replace("same r", "same-r").replace("flex 2", "flex-2")
    for k in sorted(EXPERIMENTS, key=len, reverse=True):
        if k in n:
            return EXPERIMENTS[k]
    return None


# ---------------------------------------------------------------------------- experiments
def experiment_overview(name: str) -> dict:
    s = get_store()
    acc = resolve_experiment(name)
    if acc is None:
        if "sofie" in name.lower() or "solid fuel ignition" in name.lower():
            return {"summary": "SoFIE (Solid Fuel Ignition and Extinction) is not in the PSI combustion repository snapshot; "
                               "AeroFox only has its NTRS project description.", "blocks": [],
                    "evidence": ["LIT-SOFIE", "NTRS-20200000361"], "warnings": ["No SoFIE measurements are available."], "data": {}}
        raise AnalysisError(f"Unknown experiment '{name}'. Known: FLEX, FLEX-2, Saffire I/II/III, BASS, BASS-II, SAME, SAME-R, DAFT, CFI, CFI-G, ACME, SPICE, SLICE.")
    inv = s.table("investigations").set_index("accession")
    if acc not in inv.index:
        raise AnalysisError(f"{acc} is not a combustion investigation in the snapshot")
    r = inv.loc[acc]
    cat = s.table("catalog_summary")
    cats = cat[cat.accession == acc].sort_values("files", ascending=False)
    rows = [[c.category, int(c.files), _r(c.bytes / 1e9, 2)] for c in cats.itertuples()]
    table = {"type": "table", "id": f"files_{acc}", "title": f"{acc} {r.acronym}: PSI file catalog by category",
             "columns": ["category", "files", "GB"], "rows": rows,
             "caption": "Counts from the PSI /files/v2 catalog (entries referenced, not downloaded).",
             "source": f"NASA PSI {acc}"}
    data = {"accession": acc, "acronym": r.acronym, "title": r.title, "platform": r.flight_program,
            "project_type": r.project_type, "hardware": r.hardware, "dates": f"{r.start} to {r.end}",
            "objective": r.objective[:900], "license": r.license, "catalog_files": int(r.catalog_files or 0),
            "n_publications": int(r.n_publications), "url": r.psi_url}
    ev = [acc] + KEY_FINDINGS.get(acc, [])
    summary = (f"{r.acronym} ({acc}): {r.title}. Platform: {r.flight_program}; hardware: {r.hardware}. "
               f"Objective (PSI): {r.objective[:400].strip()}")
    return {"summary": summary, "blocks": [table], "evidence": ev, "warnings": [], "data": data}


def flex_query(fuel: str | None = None, diluent: str | None = None, o2_min: float | None = None,
               o2_max: float | None = None, p_min_kpa: float | None = None, p_max_kpa: float | None = None) -> dict:
    f = get_store().table("flex_tests")
    f = f[~f.flag_zero_pressure.astype(bool)]
    if fuel:
        f = f[f.fuel.str.lower() == fuel.lower()]
    if diluent:
        f = f[f.diluent.str.upper() == diluent.upper()]
    for col, lo, hi in [("x_o2", o2_min, o2_max), ("p_kPa", p_min_kpa, p_max_kpa)]:
        if lo is not None:
            f = f[f[col] >= lo]
        if hi is not None:
            f = f[f[col] <= hi]
    if f.empty:
        return {"summary": "No FLEX tests match these conditions.", "blocks": [], "evidence": ["PSI-69"],
                "warnings": ["The FLEX test matrix does not cover the requested conditions."], "data": {"n": 0}}
    g = f.groupby(["fuel", "diluent"]).agg(n=("flex_number", "size"), K_median=("K_mm2s", "median"),
                                          K_q1=("K_mm2s", lambda x: x.quantile(.25)), K_q3=("K_mm2s", lambda x: x.quantile(.75)),
                                          p_min=("p_kPa", "min"), p_max=("p_kPa", "max"), o2_min=("x_o2", "min"),
                                          o2_max=("x_o2", "max")).reset_index()
    rows = [[x.fuel, x.diluent, int(x.n), _r(x.K_median), f"{_r(x.K_q1)}-{_r(x.K_q3)}", f"{_r(x.p_min,1)}-{_r(x.p_max,1)}",
             f"{_r(x.o2_min,2)}-{_r(x.o2_max,2)}"] for x in g.itertuples()]
    table = {"type": "table", "id": "flex_query", "title": "FLEX tests matching the query",
             "columns": ["fuel", "diluent", "tests", "K median (mm²/s)", "K IQR", "p range (kPa)", "X_O2 range"],
             "rows": rows, "caption": "One row per fuel/diluent group; unit of analysis is the droplet test.",
             "source": "PSI-69 experiment table re-keyed to official FLEX numbers (NASA/TP-2015-216046)"}
    outcomes = f.test_end.value_counts().to_dict()
    return {"summary": f"{len(f)} FLEX tests match; outcomes: " + ", ".join(f"{k} {v}" for k, v in outcomes.items()) + ".",
            "blocks": [table], "evidence": ["PSI-69", "F02", "F03"], "warnings": [],
            "data": {"n": int(len(f)), "groups": g.round(4).to_dict("records"), "outcomes": outcomes}}


def flex_run(number: int) -> dict:
    label = f"FLEX-{number:03d}"
    records = get_store().table("flex_tests")
    matched = records.loc[records.flex_number.eq(number)]
    if len(matched) != 1:
        message = (f"{label} is absent from this snapshot." if matched.empty
                   else f"{label} has conflicting rows in this snapshot.")
        return {"summary": message, "blocks": [], "evidence": ["PSI-69"],
                "warnings": ["The exact identifier could not be resolved. No other run was substituted."],
                "data": {"run_id": label, "matches": len(matched)}}
    row = matched.iloc[0]
    fields = [label, row.cir_id, row.fuel, row.diluent, _r(row.p_kPa), _r(row.x_o2), _r(row.K_mm2s)]
    block = {"type": "table", "id": "flex_run", "title": label,
             "columns": ["official run ID", "CIR ID", "fuel", "diluent", "pressure (kPa)", "X_O₂", "reported K (mm²/s)"],
             "rows": [fields], "caption": "The official run number is linked by CIR identifier.",
             "source": "NASA PSI-69 and NASA/TP-2015-216046"}
    return {"summary": f"{label} is linked to CIR record {row.cir_id} in the NASA snapshot.", "blocks": [block],
            "evidence": ["PSI-69", "F02"], "warnings": [], "data": dict(zip(block["columns"], fields))}


def flex_k_vs_o2(fuel: str | None = None) -> dict:
    f = get_store().table("flex_tests")
    f = f[~f.flag_zero_pressure.astype(bool) & f.K_mm2s.notna()]
    if fuel:
        f = f[f.fuel.str.lower() == fuel.lower()]
    series = []
    for (fu, dil), g in f.groupby(["fuel", "diluent"]):
        series.append({"name": f"{fu} / {dil} (n={len(g)})", "x": g.x_o2.round(4).tolist(), "y": g.K_mm2s.round(4).tolist(),
                       "mode": "markers", "text": [f"FLEX-{int(n):03d}, {p:.0f} kPa" for n, p in zip(g.flex_number, g.p_kPa)]})
    reg = {}
    for fu, g in f.groupby("fuel"):
        X = np.column_stack([np.ones(len(g)), g.x_o2, np.log(g.p_kPa / ATM_KPA), (g.diluent == "CO2") * 1.0, (g.diluent == "He") * 1.0])
        b, *_ = np.linalg.lstsq(X, g.K_mm2s.values, rcond=None)
        reg[fu] = {"per_0.1_xo2": _r(0.1 * b[1], 3), "He_vs_N2": _r(b[4], 3), "CO2_vs_N2": _r(b[3], 3), "n": int(len(g))}
    chart = {"type": "chart", "id": "flex_k_vs_o2", "kind": "scatter", "title": "FLEX burning-rate constant vs ambient O2",
             "x_label": "O2 mole fraction X_O2 (-)", "y_label": "burning-rate constant K (mm²/s)", "series": series,
             "caption": "Each point is one droplet test (PSI-69). Pressure varies between tests (0.5-3 atm).",
             "source": "NASA PSI-69 FLEX experiment table, re-keyed by AeroFox"}
    parts = [f"{k}: +{v['per_0.1_xo2']} mm²/s per +0.1 X_O2 (He vs N2 {v['He_vs_N2']:+}, n={v['n']})" for k, v in reg.items()]
    return {"summary": "Burning rate rises with oxygen for both fuels, controlling for pressure and diluent. " + "; ".join(parts) + ".",
            "blocks": [chart], "evidence": ["F03", "F02", "PSI-69"],
            "warnings": ["Liquid-droplet burning rates do not transfer directly to solid cabin materials.",
                         "Descriptive regression on a non-factorial test matrix; not a predictive model."],
            "data": {"regression": reg}}


def flex035_case() -> dict:
    s = get_store()
    ts = s.table("flex035_timeseries")
    ts = ts[ts.t_s < 38.0]
    row = s.table("flex_tests").query("flex_number == 35").iloc[0]
    tb = float(row.burn_time_s)
    fit = lambda d: np.polyfit(d.t_s, d.d2_mm2, 1)
    burn = ts[(ts.t_s >= 0.2 * tb) & (ts.t_s <= 0.9 * tb)]
    post = ts[(ts.t_s >= tb + 0.5) & (ts.t_s <= tb + 0.5 + 0.5 * tb)]
    kb, kp = -fit(burn)[0], -fit(post)[0]
    lu = ts.dropna(subset=["lluv"])
    chart = {"type": "chart", "id": "flex035", "kind": "line", "title": "FLEX-035: droplet regression before and after visible flame-out",
             "x_label": "time from ignition (s)", "y_label": "droplet diameter squared d² (mm²)",
             "series": [{"name": "measured d²", "x": ts.t_s.round(3).tolist()[::2], "y": ts.d2_mm2.round(4).tolist()[::2], "mode": "markers"},
                        {"name": "UV flame signal (LLUV, scaled ×0.4)", "x": lu.t_s.round(3).tolist(), "y": (lu.lluv * 0.4).round(3).tolist(),
                         "mode": "lines", "y2": False}],
             "shapes": [{"type": "vline", "x": tb, "label": f"visible extinction {tb:.1f} s"}],
             "caption": f"Heptane droplet in air at 102.4 kPa. K while burning {kb:.3f} mm²/s; after visible extinction {kp:.3f} mm²/s. "
                        "Samples after 38 s (vapor-cloud imaging artifact) omitted.",
             "source": "NASA PSI-69 FLEX-035 DropletData and LLUVData; interpretation NASA/TP-2015-216046 Fig. 39"}
    return {"summary": (f"FLEX-035 (heptane, air, 1 atm): the visible flame went out at {tb:.1f} s, but the droplet kept shrinking at "
                        f"{kp:.3f} mm²/s versus {kb:.3f} mm²/s while burning - essentially the same rate - for about 25 s. "
                        "NASA's FLEX report attributes this to a cool flame that persisted after the hot flame extinguished."),
            "blocks": [chart], "evidence": ["F04", "LIT-FLEX035", "LIT-FLEX035-PLATEAU"],
            "warnings": ["One test; the cool flame is a published interpretation, not directly measured in these files."],
            "data": {"K_burn": _r(kb), "K_post": _r(kp), "t_visible_extinction_s": tb}}


def saffire2_flow_case() -> dict:
    s = get_store()
    sf = s.table("saffire2_flow").merge(s.table("saffire_samples").query("experiment == 'Saffire-II'"), on="sample")
    rows = [[r.sample, r.material, r.flow_nominal_cm_s, _r(r.anem1_mean_cm_s, 1), _r(r.anem2_mean_cm_s, 1),
             r.ug_spread_rate_mm_s if not pd.isna(r.ug_spread_rate_mm_s) else "-"] for r in sf.itertuples()]
    table = {"type": "table", "id": "saffire2_flow", "title": "Saffire-II: tabulated vs measured duct flow",
             "columns": ["sample", "material", "PSI table (cm/s)", "anemometer 1 (cm/s)", "anemometer 2 (cm/s)", "spread rate (mm/s)"],
             "rows": rows, "caption": "Measured values: mean over 120 s after ignition from the PSI-99 telemetry workbook.",
             "source": "NASA PSI-99 table and telemetry; NTRS 20170008805"}
    chart = {"type": "chart", "id": "saffire2_flow_bar", "kind": "bar", "title": "Saffire-II duct flow per sample",
             "x_label": "sample", "y_label": "air speed (cm/s)",
             "series": [{"name": "PSI table", "x": sf["sample"].tolist(), "y": sf.flow_nominal_cm_s.tolist()},
                        {"name": "measured (mean of 2 anemometers)", "x": sf["sample"].tolist(), "y": sf.anem_mean_cm_s.round(2).tolist()}],
             "caption": "Sample 2-6 ran at ~25 cm/s although the PSI table lists 20 cm/s.", "source": "NASA PSI-99"}
    r5, r6 = sf.set_index("sample").loc["2-5"], sf.set_index("sample").loc["2-6"]
    return {"summary": (f"The PSI table lists 20 cm/s for every Saffire-II sample. Telemetry confirms ~20 cm/s except sample 2-6, "
                        f"which ran at {r6.anem_mean_cm_s:.1f} cm/s (as NTRS 20170008805 states). Samples 2-5 and 2-6 are the same "
                        f"cotton-fiberglass fabric: spread {r5.ug_spread_rate_mm_s} vs {r6.ug_spread_rate_mm_s} mm/s at "
                        f"{r5.anem_mean_cm_s:.1f} vs {r6.anem_mean_cm_s:.1f} cm/s."),
            "blocks": [chart, table], "evidence": ["F05", "LIT-SAF2-FLOW", "PSI-99"],
            "warnings": ["One sample per flow speed: the flow effect cannot be separated from run-to-run variability."],
            "data": {"flow_2_5": _r(r5.anem_mean_cm_s, 2), "flow_2_6": _r(r6.anem_mean_cm_s, 2),
                     "spread_2_5": r5.ug_spread_rate_mm_s, "spread_2_6": r6.ug_spread_rate_mm_s}}


def smoke_particles() -> dict:
    sr = get_store().table("same_reduced")
    d = sr[(sr.flight == "SAME-R")].dropna(subset=["amd_um"])
    g = d.groupby("material").amd_um.agg(["count", "median", lambda x: x.quantile(.25), lambda x: x.quantile(.75)]).reset_index()
    g.columns = ["material", "n", "median", "q1", "q3"]
    chart = {"type": "chart", "id": "same_amd", "kind": "bar", "title": "SAME-R smoke particle size by material",
             "x_label": "material", "y_label": "median arithmetic mean diameter (µm)",
             "series": [{"name": "median AMD", "x": g.material.tolist(), "y": g["median"].round(3).tolist(),
                         "error_minus": (g["median"] - g.q1).round(3).tolist(), "error_plus": (g.q3 - g["median"]).round(3).tolist()}],
             "caption": "Bars: median per material; whiskers: interquartile range across tests. Smoke from heated, non-flaming samples.",
             "source": "NASA PSI-101 SAME/SAME-R results workbook (reduced data sheet)"}
    return {"summary": "Smoke from overheated spacecraft materials is sub-micrometre: " +
                       ", ".join(f"{r.material} {r['median']:.2f} µm (n={r.n})" for _, r in g.iterrows()) + ".",
            "blocks": [chart], "evidence": ["F07", "F08", "LIT-SAME2"],
            "warnings": ["Detector alarm times or thresholds cannot be derived from these data (F08)."],
            "data": {"by_material": g.round(4).to_dict("records")}}


# ---------------------------------------------------------------------------- atmosphere
def assess_atmosphere(pressure: float, pressure_unit: str, o2: float, o2_unit: str = "%", gravity: str | None = None) -> dict:
    try:
        p = to_kpa(pressure, pressure_unit)
        x = o2_fraction(o2, o2_unit)
        atm = atmosphere(p, x)
    except ValueError as e:
        raise AnalysisError(str(e))
    if not 5 <= p <= 1000:
        raise AnalysisError(f"pressure {p:.1f} kPa is outside the range AeroFox can assess (5-1000 kPa)")
    s = get_store()
    pts = _tested_conditions()
    near = pts[((pts.p_kPa - p).abs() <= 10) & ((pts.x_o2 - x).abs() <= 0.03)]
    counts = near.family.value_counts().to_dict()
    solid = sum(v for k, v in counts.items() if "solid" in k)
    warnings = []
    if solid == 0:
        warnings.append("No PSI solid-material flight test lies within 10 kPa and 3 points of O2 of this atmosphere (F09).")
    if x > 0.30:
        warnings.append("Above 30% O2 materials qualified for ISS (MOC 30% at sea level) may not pass; test at the design atmosphere (LIT-ATM-MOC).")
    if gravity in ("lunar", "mars"):
        warnings.append(f"No {gravity}-gravity fire data at this atmosphere; do not interpolate between 1 g and microgravity (F10).")
    series = [{"name": fam, "x": g.p_kPa.round(1).tolist(), "y": g.x_o2.round(3).tolist(), "mode": "markers"}
              for fam, g in pts.groupby("family")]
    series.append({"name": "reference atmospheres", "x": [a["pressure_kPa"] for a in REF_ATMOSPHERES],
                   "y": [a["o2_pct"] / 100 for a in REF_ATMOSPHERES], "mode": "markers", "marker": "star",
                   "text": [a["name"] for a in REF_ATMOSPHERES]})
    series.append({"name": "your scenario", "x": [round(p, 1)], "y": [round(x, 3)], "mode": "markers", "marker": "diamond",
                   "text": ["scenario"]})
    chart = {"type": "chart", "id": "atm_coverage", "kind": "scatter", "title": "Your atmosphere vs conditions tested in NASA PSI experiments",
             "x_label": "total pressure (kPa)", "y_label": "O2 mole fraction (-)", "series": series, "x_range": [0, 330], "y_range": [0.05, 0.6],
             "caption": "Each grey/coloured point is one test. Stars: ISS cabin and Artemis atmosphere options (NTRS 20260002050).",
             "source": "NASA PSI-69, -39, -159, -10, -25, -98, -99 tables; NTRS 20260002050"}
    comp = [[a["name"], a["pressure_kPa"], a["o2_pct"], round(a["pressure_kPa"] * a["o2_pct"] / 100, 1)] for a in REF_ATMOSPHERES]
    comp.append(["your scenario", round(p, 1), round(100 * x, 1), round(p * x, 1)])
    table = {"type": "table", "id": "atm_compare", "title": "Atmosphere comparison", "columns": ["atmosphere", "total p (kPa)", "O2 (%)", "pO2 (kPa)"],
             "rows": comp, "caption": "pO2 = O2 mole fraction × total pressure.", "source": "NTRS 20260002050; AeroFox calculation"}
    return {"summary": (f"{atm['pressure_kPa']} kPa ({atm['pressure_psia']} psia) at {atm['o2_percent']}% O2 gives an O2 partial pressure of "
                        f"{atm['pO2_kPa']} kPa. Tests within ±10 kPa and ±3 points O2 in the snapshot: "
                        + (", ".join(f"{k} {v}" for k, v in counts.items()) if counts else "none") + "."),
            "blocks": [chart, table], "evidence": ["F09", "LIT-ATM-GENERAL", "LIT-ATM-MOC", "LIT-ATM-ARTEMIS"],
            "warnings": warnings, "data": {**atm, "nearby_tests": counts}}


@lru_cache(maxsize=1)
def _tested_conditions() -> pd.DataFrame:
    s = get_store()
    pts = []
    f = s.table("flex_tests")
    f = f[~f.flag_zero_pressure.astype(bool)]
    pts += [("FLEX droplets", p, x) for p, x in zip(f.p_kPa, f.x_o2)]
    c = s.table("cfi_tests").dropna(subset=["p_atm", "x_o2"])
    pts += [("CFI droplets", p * ATM_KPA, x) for p, x in zip(c.p_atm, c.x_o2)]
    for nm, xc, pc, fac in [("table_PSI-159_cfi_g_normal_flames", "XO2 before test", "approx p (bar)", 100),
                            ("table_PSI-159_cfi_g_inverse_flames", "XO2", "approx p (bar)", 100),
                            ("table_PSI-10_flame_design_normal_flame", "XO2 (init)", "pmean (atm)", ATM_KPA),
                            ("table_PSI-10_flame_design_inverse_flame", "XO2", "pmean (atm)", ATM_KPA)]:
        d = s.table(nm)
        x = pd.to_numeric(d[xc], errors="coerce")
        p = pd.to_numeric(d[pc], errors="coerce") * fac
        pts += [("ACME gaseous flames", pi, xi) for pi, xi in zip(p, x) if np.isfinite(pi) and np.isfinite(xi)]
    b = s.table("bass2_tests")
    b = b[~b.flag_o2_increase.astype(bool)].dropna(subset=["o2_init_pct"])
    pts += [("BASS-II solids", 101.3, v / 100) for v in b.o2_init_pct]
    sa = s.table("saffire_samples").dropna(subset=["o2_pct"])
    pts += [("Saffire solids", 101.3, v / 100) for v in sa.o2_pct]
    P = pd.DataFrame(pts, columns=["family", "p_kPa", "x_o2"])
    return P[(P.x_o2 > 0) & (P.x_o2 < 1) & (P.p_kPa > 0)].reset_index(drop=True)


# ---------------------------------------------------------------------------- design review
SYSTEM_ALIASES = {
    "lunar_habitat": ["lunar habitat", "lunar base", "moon base", "base lunar", "habitat lunar", "lunar outpost", "moon habitat", "base na lua"],
    "mars_habitat": ["mars habitat", "martian habitat", "mars base", "habitat em marte", "base em marte", "base marciana"],
    "space_station": ["space station", "iss", "estacao espacial", "estacao orbital", "orbital station", "station module"],
    "crew_vehicle": ["capsule", "crew vehicle", "spacecraft", "lander", "capsula", "nave"],
    "pressurized_rover": ["rover", "pressurized rover", "veiculo pressurizado"],
    "eva_suit": ["eva suit", "spacesuit", "space suit", "suit", "traje"],
    "battery_system": ["battery", "batteries", "bateria", "baterias"],
}


def resolve_system(text: str | None) -> str | None:
    if not text:
        return None
    t = text.lower().replace("-", " ").replace("_", " ")
    for key, al in SYSTEM_ALIASES.items():
        if key.replace("_", " ") in t or any(a in t for a in al):
            return key
    return None


def fire_safety_factors(system: str, gravity: str | None = None, pressure_kPa: float | None = None,
                        o2_pct: float | None = None) -> dict:
    kb = factors_kb()
    sysk = resolve_system(system) or system
    if sysk not in kb["systems"]:
        raise AnalysisError(f"Unknown system '{system}'. Supported: " + ", ".join(kb["systems"]))
    spec = kb["systems"][sysk]
    g = gravity or spec["gravity"]
    elevated = o2_pct is not None and o2_pct > 23.5
    untested_atm = (pressure_kPa is not None and abs(pressure_kPa - 101.3) > 10) or elevated or g in ("lunar", "mars")
    fac = {f["id"]: f for f in kb["factors"]}
    rows = []
    for fid in spec["factors"]:
        f = fac[fid]
        tier = f.get("tier_default", 2)
        if fid == "atmosphere":
            tier = 1 if untested_atm else 2
        if fid == "gravity" and g in ("lunar", "mars"):
            tier = 2
        cov = f["coverage"].get(g, "none")
        rows.append({"id": fid, "name": f["name"], "short": f["short"], "tier": tier, "coverage": cov,
                     "incident": f["incident"], "why": f["why"], "evidence": f["evidence"],
                     "questions": f["questions"], "verification": f["verification"]})
    rows.sort(key=lambda r: (r["tier"], LEVEL_ORDER[r["coverage"]], 0 if r["incident"] else 1))
    tier_name = {1: "Tier 1 - decisive", 2: "Tier 2 - major", 3: "Tier 3 - supporting"}
    matrix = {"type": "matrix", "id": "factor_matrix", "title": f"Fire-safety factors: {sysk.replace('_', ' ').replace('eva', 'EVA')} ({g} gravity)",
              "columns": ["priority tier", "evidence in this regime", "implicated in a NASA incident", "key verification"],
              "rows": [{"label": r["short"], "cells": [tier_name[r["tier"]], r["coverage"], "yes" if r["incident"] else "no",
                                                       r["verification"][0]],
                        "levels": [f"tier{r['tier']}", r["coverage"], "yes" if r["incident"] else "no", ""]} for r in rows],
              "caption": "Qualitative decision matrix. Order follows the explicit rules in fire_factors.json "
                         "(incident history and whether the design condition lies outside tested conditions); "
                         "it is not a calibrated risk ranking.",
              "source": "AeroFox fire_factors.json; NASA PSI findings; NTRS and NASA SMA lessons learned"}
    ev = list(dict.fromkeys(e for r in rows for e in r["evidence"]))
    top = rows[0]
    warnings = ["This is a preliminary, evidence-weighted prioritisation, not a certified hazard analysis."]
    if not gravity and sysk == "eva_suit":
        warnings.append("The matrix uses lunar gravity as a reference scenario. The suit's mission environment remains unspecified.")
    if g in ("lunar", "mars"):
        warnings.append(f"Most measured fire data are from orbital microgravity or 1 g; {g} gravity is covered only by "
                        + ("literature from simulated lunar gravity (LUCI)." if g == "lunar" else "no measurements in this snapshot."))
    if sysk == "eva_suit":
        warnings.append("The suit's internal atmosphere is a separate, low-pressure domain from the cabin (4.3 or 5.2 psi suit "
                        "pressure in early Artemis architectures, LIT-ATM-SUIT); cabin-air test data do not describe it.")
        ev[:0] = ["LIT-EVA-WIRE", "LIT-ATM-SUIT"]
    elif g in ("lunar", "mars"):
        ev.insert(0, "LIT-MOON-EXTERIOR" if g == "lunar" else "LIT-MARS-EXTERIOR")
    tier1 = [r["short"] for r in rows if r["tier"] == 1]
    label = sysk.replace("_", " ").replace("eva", "EVA")
    article = "an" if label[0].lower() in "aeiou" else "a"
    if sysk == "eva_suit":
        for r in rows:
            if r["id"] == "atmosphere":
                r["name"] = "Suit atmosphere (O2 fraction and pressure) and cabin atmosphere at suit interfaces"
    return {"summary": (f"For {article} {label} in {g} gravity, the decisive factor in this review is "
                        f"{top['name'].lower()}. Tier-1 factors: {', '.join(tier1)}. The order follows NASA incident history "
                        f"and whether your design condition lies outside what has been tested; it is not a numeric risk score."),
            "blocks": [matrix], "evidence": ev, "warnings": warnings,
            "data": {"system": sysk, "gravity": g, "factors": rows}}


def gravity_comparison() -> dict:
    """Published LUCI spread rates (simulated lunar g vs 1 g) plus the regime facts used for transfer decisions."""
    chart = {"type": "chart", "id": "luci_rates", "kind": "bar", "title": "Downward flame spread over SIBAL: simulated lunar gravity vs 1 g",
             "x_label": "flame feature", "y_label": "spread rate (mm/s)",
             "series": [{"name": "1 g", "x": ["flame base", "flame tip"], "y": [1.5, 2.8]},
                        {"name": "simulated lunar g (LUCI)", "x": ["flame base", "flame tip"], "y": [0.9, 1.1]}],
             "caption": "Published values (NTRS 20250010653, combined results slide); no uncertainty reported. Orbital microgravity "
                        "has no buoyant flow at all, so it is not a point on this axis.",
             "source": "NASA GRC, Lunar Combustion Investigation (2025)"}
    table = {"type": "table", "id": "gravity_regimes", "title": "Gravity regimes and what the evidence covers",
             "columns": ["regime", "g (m/s²)", "buoyant flow", "fire data in AeroFox"],
             "rows": [["Earth", 9.81, "strong", "ground tests (literature)"], ["Mars", 3.71, "weak", "none"],
                      ["Moon", 1.62, "weak", "LUCI: simulated lunar g, SIBAL and PMMA, air, 1 atm"],
                      ["Orbit (ISS, Cygnus)", "~0", "none; forced flow only", "PSI: FLEX, Saffire, BASS, SAME, CFI, ACME"]],
             "caption": "Gravity values are standard surface gravities.", "source": "AeroFox; NTRS 20250010653"}
    return {"summary": ("Orbital microgravity removes buoyancy; flames there are fed only by ventilation flow or diffusion. Lunar "
                        "gravity keeps a weak buoyant flow. In LUCI, downward spread over SIBAL was slower in simulated lunar gravity "
                        "than in 1 g (0.9 vs 1.5 mm/s at the flame base), while other work reports materials that are more flammable "
                        "at lunar gravity. Flame behaviour is therefore not monotonic in gravity."),
            "blocks": [chart, table], "evidence": ["F10", "LIT-LUCI-RATES", "LIT-LUCI-SETUP", "LIT-FM2-GOLDILOCKS", "LIT-GUIDE"],
            "warnings": ["Do not interpolate lunar or Mars fire behaviour between 1 g and orbital microgravity.",
                         "LUCI used a rotating sounding rocket (Coriolis effects, ~2.5 min burns)."],
            "data": {"luci_1g": {"base": 1.5, "tip": 2.8}, "luci_lunar": {"base": 0.9, "tip": 1.1}}}


def evidence_coverage_matrix() -> dict:
    t = get_store().table  # noqa: F841  (kept for symmetry)
    domains = ["Cabin solids (ISS air)", "Fire growth, ventilated", "Elevated O2 / reduced p", "Smoke detection",
               "Suppression", "Liquid fuels", "Gaseous leaks", "Lunar gravity", "Mars gravity"]
    E = {"Saffire I-III": [2, 2, 0, 1, 0, 0, 0, 0, 0], "BASS / BASS-II": [2, 1, 0, 0, 1, 0, 0, 0, 0],
         "FLEX / FLEX-2": [0, 0, 1, 0, 2, 2, 0, 0, 0], "CFI": [0, 0, 1, 0, 1, 2, 0, 0, 0], "SAME / SAME-R": [1, 0, 0, 2, 0, 0, 0, 0, 0],
         "DAFT": [0, 0, 0, 1, 0, 0, 0, 0, 0], "ACME, SPICE, SLICE": [0, 0, 1, 1, 0, 0, 2, 0, 0], "LUCI (literature)": [1, 0, 0, 0, 0, 0, 0, 1, 0]}
    names = {0: "none", 1: "partial", 2: "direct"}
    matrix = {"type": "matrix", "id": "evidence_matrix", "title": "Which evidence supports which engineering decision",
              "columns": domains, "rows": [{"label": k, "cells": [names[v] for v in vals], "levels": [names[v] for v in vals]}
                                           for k, vals in E.items()],
              "caption": "direct = measured in the regime of the decision; partial = different regime, conditions only, or literature; none = no data.",
              "source": "AeroFox analysis notebook, Section 9.1"}
    return {"summary": "Evidence is strong for cabin solids in ISS air, droplet suppression and smoke particle sizes; weak for "
                       "elevated-O2/reduced-pressure atmospheres and lunar gravity; absent for Mars gravity.",
            "blocks": [matrix], "evidence": ["F09", "F10"], "warnings": [], "data": {"matrix": E, "domains": domains}}


def materials_evidence(materials: list[str]) -> dict:
    if not 1 <= len(materials) <= 12 or any(not 1 <= len(name.strip()) <= 80 for name in materials):
        raise AnalysisError("Provide one to twelve material names of up to eighty characters.")
    s = get_store()
    sa, b2, sr = s.table("saffire_samples"), s.table("bass2_tests"), s.table("same_reduced")
    rows, found = [], set()
    aliases = {"sibal": ["sibal", "cotton", "fiberglass"], "pmma": ["pmma", "acrylic", "plexiglass"], "silicone": ["silicone", "silicon"],
               "nomex": ["nomex"], "kapton": ["kapton"], "teflon": ["teflon", "ptfe"], "pyrell": ["pyrell", "foam"],
               "lampwick": ["lampwick", "cotton wick"], "delrin": ["delrin"], "cellulose": ["cellulose", "paper", "kimwipe"]}
    for m in materials:
        key = next((k for k, al in aliases.items() if any(a in m.lower() for a in al)), m.lower())
        al = aliases.get(key, [key])
        pat = "|".join(map(re.escape, al))
        a = sa[sa.material.fillna("").str.lower().str.contains(pat)]
        for r in a.itertuples():
            outcome = (f"spread {r.ug_spread_rate_mm_s} mm/s" if not pd.isna(getattr(r, "ug_spread_rate_mm_s", np.nan))
                       else f"burn time {r.burn_time_s:g} s" if not pd.isna(r.burn_time_s) else "see PSI")
            if str(getattr(r, "burn_time_raw", "")).strip().lower() == "insignificant":
                outcome = "no sustained burning"
            rows.append([key, f"{r.experiment} {r.sample}", f"{r.thickness_mm:g} mm, {r.direction}, {r.flow_nominal_cm_s:g} cm/s", outcome])
            found.add(key)
        b = b2[b2.material_raw.fillna("").str.lower().str.contains(pat)]
        if len(b):
            rows.append([key, f"BASS-II ({len(b)} test points)", f"O2 {b.o2_init_pct.min():.1f}-{b.o2_init_pct.max():.1f} vol%",
                         "conditions only (outcomes in NASA TM 20210011385)"])
            found.add(key)
        c = sr[(sr.flight == "SAME-R") & sr.material.str.lower().str.contains(pat)].dropna(subset=["amd_um"])
        if len(c):
            rows.append([key, f"SAME-R ({len(c)} smoke tests)", "heated, non-flaming", f"median smoke AMD {c.amd_um.median():.2f} µm"])
            found.add(key)
    missing = [m for m in materials if not any(m.lower() in f or f in m.lower() for f in found)]
    table = {"type": "table", "id": "materials", "title": "Microgravity evidence by material", "columns": ["material", "test", "conditions", "outcome"],
             "rows": rows, "caption": "Only materials tested in the PSI snapshot appear; absence means no data, not low flammability.",
             "source": "NASA PSI-98/99/100 (Saffire), PSI-25 (BASS-II), PSI-101 (SAME-R)"}
    w = [f"No PSI data for: {', '.join(missing)}." for _ in [0] if missing]
    w.append("Flammability depends on thickness, orientation, flow and atmosphere; compare only like-for-like conditions.")
    return {"summary": f"Found microgravity evidence for {', '.join(sorted(found)) or 'none of the requested materials'}.",
            "blocks": [table] if rows else [], "evidence": ["F06", "F07", "PSI-99", "PSI-25", "PSI-101"], "warnings": w,
            "data": {"rows": rows, "missing": missing}}


# ---------------------------------------------------------------------------- calculations
def droplet_burn(d0_mm: float, K_mm2s: float | None = None, fuel: str | None = None, x_o2: float | None = None) -> dict:
    if not 0.05 <= d0_mm <= 50:
        raise AnalysisError("initial diameter must be 0.05-50 mm")
    source = "user-supplied K"
    if K_mm2s is None:
        if not fuel:
            raise AnalysisError("give either K (mm²/s) or a fuel (methanol or heptane) to look up FLEX data")
        f = get_store().table("flex_tests")
        f = f[(f.fuel.str.lower() == fuel.lower()) & f.K_mm2s.notna() & (f.diluent == "N2")]
        if x_o2 is not None:
            f = f[(f.x_o2 - x_o2).abs() <= 0.02]
        if f.empty:
            raise AnalysisError("no FLEX N2-diluted tests near that O2 level for this fuel")
        K_mm2s = float(f.K_mm2s.median())
        source = f"median of {len(f)} FLEX {fuel} tests in N2" + (f" at X_O2 {x_o2}±0.02" if x_o2 else "")
    if not 0.01 <= K_mm2s <= 5:
        raise AnalysisError("K must be 0.01-5 mm²/s")
    tb = d0_mm ** 2 / K_mm2s
    t = np.linspace(0, tb, 60)
    chart = {"type": "chart", "id": "d2law", "kind": "line", "title": "d²-law droplet regression (idealised)",
             "x_label": "time (s)", "y_label": "d² (mm²)", "series": [{"name": f"K = {K_mm2s:.3f} mm²/s", "x": t.round(3).tolist(),
                                                                       "y": (d0_mm ** 2 - K_mm2s * t).round(4).tolist(), "mode": "lines"}],
             "caption": "Model: d² = d0² - K t. Ignores ignition transient, extinction and cool-flame stages.", "source": source}
    return {"summary": f"With d0 = {d0_mm} mm and K = {K_mm2s:.3f} mm²/s ({source}), the d²-law burnout time is {tb:.1f} s.",
            "blocks": [chart], "evidence": ["F02", "F03"],
            "warnings": ["Real droplets in low O2 may extinguish before burnout (F11), and cool flames can continue after flame-out (F04)."],
            "data": {"burnout_time_s": _r(tb, 2), "K_mm2s": _r(K_mm2s, 4), "K_source": source}}


def ventilation_sim(compartments: list[dict], flows: list[dict], t_end_s: float = 1800, method: str = "implicit") -> dict:
    try:
        comps = [cm.Compartment(name=str(c["name"])[:40], volume_m3=float(c["volume_m3"]), supply_m3s=float(c.get("supply_m3s", 0)),
                                exhaust_m3s=float(c.get("exhaust_m3s", 0)), source_rate=float(c.get("source_rate", 0)),
                                source_start_s=float(c.get("source_start_s", 0)), source_duration_s=float(c.get("source_duration_s", 0)),
                                c0=float(c.get("c0", 0))) for c in compartments]
        fl = [(str(f["from"]), str(f["to"]), float(f["m3s"])) for f in flows]
        res = cm.simulate(comps, fl, t_end_s, method=method)
    except (KeyError, TypeError) as e:
        raise AnalysisError(f"invalid ventilation scenario: missing or malformed field {e}")
    except cm.ModelError as e:
        raise AnalysisError(str(e))
    series = [{"name": n, "x": res["t_s"], "y": [round(v, 6) for v in res["C"][n]], "mode": "lines"} for n in res["names"]]
    chart = {"type": "chart", "id": "tracer", "kind": "line", "title": "Passive tracer concentration by compartment",
             "x_label": "time (s)", "y_label": "tracer concentration (source units per m³)", "series": series,
             "caption": f"Well-mixed compartments, {res['method']} integration, dt = {res['dt_s']:.2f} s, "
                        f"mass-balance error {res['mass_balance_relative_error']:.1e}. SYNTHETIC scenario inputs.",
             "source": "AeroFox compartment model (Eq. 1 in SCIENTIFIC_METHODS.md)"}
    peaks = "; ".join(f"{n}: peak {v['peak']:.3g} at {v['t_peak_s']:.0f} s" for n, v in res["peaks"].items())
    return {"summary": f"Simulated {len(comps)} compartment(s) for {t_end_s:.0f} s. {peaks}.",
            "blocks": [chart], "evidence": [],
            "warnings": ["Passive-tracer model: it does not predict flame spread, toxicity, detector alarm timing or suppression.",
                         "Scenario values are user or example inputs (synthetic), not NASA measurements."],
            "data": {k: res[k] for k in ("peaks", "air_changes_per_hour", "mass_balance_relative_error", "dt_s", "fastest_time_constant_s")}}


EXAMPLE_VENT = {
    "connected": {"compartments": [{"name": "battery bay", "volume_m3": 8, "exhaust_m3s": 0.0, "source_rate": 1.0, "source_duration_s": 300},
                                   {"name": "crew module", "volume_m3": 40, "supply_m3s": 0.10},
                                   {"name": "airlock", "volume_m3": 6, "exhaust_m3s": 0.10}],
                  # recirculation: crew->bay 0.10, bay->crew 0.05, bay->airlock 0.05, crew->airlock 0.05 (volume-balanced)
                  "flows": [{"from": "crew module", "to": "battery bay", "m3s": 0.10}, {"from": "battery bay", "to": "crew module", "m3s": 0.05},
                            {"from": "battery bay", "to": "airlock", "m3s": 0.05}, {"from": "crew module", "to": "airlock", "m3s": 0.05}]},
    "isolated": {"compartments": [{"name": "battery bay", "volume_m3": 8, "supply_m3s": 0.02, "exhaust_m3s": 0.02, "source_rate": 1.0,
                                   "source_duration_s": 300},
                                  {"name": "crew module", "volume_m3": 40, "supply_m3s": 0.10, "exhaust_m3s": 0.10},
                                  {"name": "airlock", "volume_m3": 6}],
                 "flows": []},
}


def compare_ventilation_designs(t_end_s: float = 1800) -> dict:
    out = {k: ventilation_sim(v["compartments"], v["flows"], t_end_s) for k, v in EXAMPLE_VENT.items()}
    series = []
    for k, r in out.items():
        for s in r["blocks"][0]["series"]:
            if s["name"] == "crew module":
                series.append({**s, "name": f"crew module - {k} bays"})
    chart = {"type": "chart", "id": "vent_compare", "kind": "line", "title": "Smoke surrogate reaching the crew module: connected vs isolated bays",
             "x_label": "time (s)", "y_label": "tracer concentration (units per m³)", "series": series,
             "caption": "SYNTHETIC example: 300 s tracer release in an 8 m³ battery bay. Connected: the bay exchanges air with the crew "
                        "module (0.10 m³/s in, 0.05 m³/s back). Isolated: the bay has its own 0.02 m³/s supply and extract.", "source": "AeroFox compartment model"}
    pc = {k: r["data"]["peaks"]["crew module"]["peak"] for k, r in out.items()}
    return {"summary": (f"In this synthetic layout the crew module sees a peak tracer level of {pc['connected']:.3g} with connected bays "
                        f"and {pc['isolated']:.3g} with an isolated, separately exhausted battery bay."),
            "blocks": [chart] + [out["connected"]["blocks"][0]], "evidence": [],
            "warnings": out["connected"]["warnings"], "data": {"crew_module_peaks": pc}}
