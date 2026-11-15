"""Derive analysis tables from the raw PSI snapshot.

    python -m aerofox.ingest.derive

Reads data/raw/psi (and data/cache/psi for large telemetry, if present) and
writes data/processed/*.csv plus data/processed/derivation_log.json. Raw values
are kept next to cleaned values; every non-trivial transformation is logged.

Unit of analysis per table:
  flex_tests / cfi_tests       one row = one droplet test (one ignition)
  flex_droplet_fits            one row = one droplet test with a usable diameter history
  saffire_samples              one row = one burned sample
  saffire2_flow                one row = one Saffire-II sample, telemetry window statistics
  bass2_tests                  one row = one BASS-II test point (several per sample possible)
"""
from __future__ import annotations

import gzip
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw" / "psi"
CACHE = ROOT / "data" / "cache" / "psi"
OUT = ROOT / "data" / "processed"
ATM_KPA = 101.325
MMHG_KPA = 0.133322368

LOG: list[dict] = []


def log(table: str, action: str, detail: str, n: int | None = None) -> None:
    LOG.append({"table": table, "action": action, "detail": detail, "rows_affected": n})


def read_csv_any(path: Path) -> pd.DataFrame:
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(path, encoding=enc, dtype=str, keep_default_na=False)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"cannot decode {path}")


def first_number(s) -> float:
    """First numeric token in a cell ('~ 22.1' -> 22.1, '20 cm/s' -> 20). NaN if none."""
    if s is None:
        return np.nan
    m = re.search(r"-?\d+(?:\.\d+)?", str(s).replace(",", ""))
    return float(m.group()) if m else np.nan


def table_path(acc: str) -> list[Path]:
    return sorted((RAW / "tables" / acc).glob("*.csv"))


# ---------------------------------------------------------------- investigations
def build_investigations() -> pd.DataFrame:
    rows = []
    for p in sorted((RAW / "investigations").glob("*.json")):
        d = json.loads(p.read_text())
        cat = RAW / "catalog" / f"{d['accession']}.csv.gz"
        n_files = n_bytes = None
        if cat.exists():
            c = pd.read_csv(cat)
            n_files, n_bytes = len(c), int(c["bytes"].sum())
        rows.append({
            "accession": d["accession"],
            "acronym": d.get("investigationAcronym") or "",
            "title": d.get("title"),
            "project_type": d.get("projectType"),
            "flight_program": d.get("flightProgram"),
            "sub_research_area": d.get("subResearchArea"),
            "hardware": d.get("experimentHardware"),
            "managing_center": d.get("managingNasaCenter"),
            "start": d.get("investigationStartDate"),
            "end": d.get("investigationEndDate"),
            "release_date": d.get("releaseDate"),
            "license": d.get("licenseIdentifier") or "unspecified",
            "doi": d.get("doi"),
            "psi_version": d.get("version"),
            "n_publications": len(d.get("publications") or []),
            "n_experiment_tables": len(d.get("experimentalTable") or []),
            "catalog_files": n_files,
            "catalog_bytes": n_bytes,
            "declared_total_bytes": d.get("totalFileSize"),
            "objective": (d.get("objective") or "").strip(),
            "hypothesis": (d.get("hypothesis") or "").strip(),
            "approach": (d.get("approach") or "").strip(),
            "impacts": (d.get("researchImpacts") or "").strip(),
        })
    df = pd.DataFrame(rows)
    df["psi_url"] = "https://psi.nasa.gov/physci/repo/data/investigations/" + df["accession"]
    return df


def build_catalog_summary() -> pd.DataFrame:
    parts = []
    for p in sorted((RAW / "catalog").glob("*.csv.gz")):
        acc = p.name.split(".")[0]
        c = pd.read_csv(p)
        c["category"] = c["key"].str.split("/").str[2].fillna("?")
        c["ext"] = c["key"].str.extract(r"(\.[A-Za-z0-9]+)$")[0].str.lower().fillna("")
        g = c.groupby("category").agg(files=("key", "size"), bytes=("bytes", "sum")).reset_index()
        g.insert(0, "accession", acc)
        parts.append(g)
    return pd.concat(parts, ignore_index=True)


def catalog_duplicates() -> dict:
    keys = []
    for p in sorted((RAW / "catalog").glob("*.csv.gz")):
        c = pd.read_csv(p)
        c["accession"] = p.name.split(".")[0]
        keys.append(c)
    allc = pd.concat(keys, ignore_index=True)
    allc["name"] = allc["key"].str.rsplit("/", n=1).str[-1]
    return {
        "entries": int(len(allc)),
        "unique_keys": int(allc["key"].nunique()),
        "unique_name_size_pairs": int(allc.drop_duplicates(["name", "bytes"]).shape[0]),
        "referenced_bytes": int(allc["bytes"].sum()),
        "referenced_bytes_dedup_name_size": int(allc.drop_duplicates(["name", "bytes"])["bytes"].sum()),
    }


# ---------------------------------------------------------------- FLEX / CFI droplets
def parse_test_sheet(path: Path) -> dict:
    txt = path.read_text(encoding="latin-1")
    def grab(label, cast=float):
        m = re.search(label + r"\s*[:=]?\s*\t?\s*([^\t\r\n]+)", txt)
        if not m:
            return None
        v = m.group(1).strip()
        try:
            return cast(v)
        except ValueError:
            return v
    return {
        "sheet_test": re.search(r"FLEX-(\d+)", txt).group(1) if re.search(r"FLEX-(\d+)", txt) else None,
        "sheet_date": grab(r"Test Date:", str),
        "sheet_cir_id": grab(r"CIR Test Number:", str),
        "sheet_p_atm": grab(r"Pressure \(atm\) ="),
        "sheet_x_o2": grab(r"O2 Mole Fraction ="),
        "sheet_x_n2": grab(r"N2 Mole Fraction ="),
        "sheet_x_co2": grab(r"CO2 Mole Fraction ="),
        "sheet_x_he": grab(r"He Mole Fraction ="),
        "sheet_T_K": grab(r"Temperature \(K\) ="),
        "sheet_fuel": grab(r"Fuel:", str),
        "sheet_d0_mm": grab(r"D0\s+\(mm\) ="),
        "sheet_kavg_mm2s": grab(r"kavg\s+\(mm2/s\) ="),
        "sheet_fiber": grab(r"Fiber:", str),
        "sheet_dext_mm": grab(r"Dext\s+\(mm\) ="),
        "sheet_comment": txt.split("COMMENTS:", 1)[1].strip() if "COMMENTS:" in txt else "",
    }


def read_droplet_history(path: Path) -> pd.DataFrame:
    """DropletData files are tab separated with classic-Mac CR line endings."""
    lines = [l for l in path.read_text(encoding="latin-1").splitlines() if l.strip()]
    rows = []
    for l in lines[1:]:
        parts = l.split("\t")
        try:
            rows.append([float(x) for x in parts[:2]])
        except ValueError:
            continue
    df = pd.DataFrame(rows, columns=["t_s", "d_mm"], dtype=float)
    df = df[np.isfinite(df.d_mm) & (df.d_mm > 0)].sort_values("t_s")
    df["d2_mm2"] = df.d_mm ** 2
    return df.reset_index(drop=True)


def linfit(t: np.ndarray, y: np.ndarray) -> dict:
    """OLS fit y = a + b t, returning slope, its standard error and R^2."""
    n = len(t)
    if n < 5:
        return {"slope": np.nan, "slope_se": np.nan, "r2": np.nan, "n": n}
    A = np.vstack([np.ones(n), t]).T
    coef, res, *_ = np.linalg.lstsq(A, y, rcond=None)
    yhat = A @ coef
    ss_res = float(((y - yhat) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    s2 = ss_res / (n - 2)
    se = float(np.sqrt(s2 / ((t - t.mean()) ** 2).sum()))
    return {"intercept": float(coef[0]), "slope": float(coef[1]), "slope_se": se,
            "r2": 1 - ss_res / ss_tot if ss_tot > 0 else np.nan, "n": n}


def fit_droplet(h: pd.DataFrame, burn_time: float | None) -> dict:
    """Burning-rate constant K = -d(d^2)/dt over the quasi-steady burning window.

    Window: 0.2*tb <= t <= 0.9*tb, where tb is the tabulated visible-flame
    duration. The early transient (ignition, droplet heating) and the last
    portion near extinction are excluded. If tb is unknown, no fit is made.
    The post-extinction vaporization rate is fitted on tb+0.5 s .. tb+0.5 s+W
    where W = min(0.5*tb, available data), only when >= 10 samples exist.
    """
    out = {"n_samples": len(h), "t_first": h.t_s.min() if len(h) else np.nan,
           "t_last": h.t_s.max() if len(h) else np.nan,
           "d0_hist_mm": float(h[h.t_s <= 0].d_mm.iloc[-1]) if (h.t_s <= 0).any() else np.nan}
    if burn_time is None or not np.isfinite(burn_time) or burn_time <= 0.5:
        return out
    w = h[(h.t_s >= 0.2 * burn_time) & (h.t_s <= 0.9 * burn_time)]
    f = linfit(w.t_s.values, w.d2_mm2.values)
    out.update(K_fit_mm2s=-f["slope"], K_fit_se=f["slope_se"], K_fit_r2=f["r2"], K_fit_n=f["n"])
    post = h[(h.t_s >= burn_time + 0.5) & (h.t_s <= burn_time + 0.5 + max(1.0, 0.5 * burn_time))]
    if len(post) >= 10:
        g = linfit(post.t_s.values, post.d2_mm2.values)
        out.update(K_post_mm2s=-g["slope"], K_post_se=g["slope_se"], K_post_r2=g["r2"], K_post_n=g["n"])
    return out


def flex_tp_index() -> dict[str, list[int]]:
    """CIR id -> official FLEX number(s), parsed from NASA/TP-2015-216046 full text.

    The full text lives in the cache (not redistributed); the parsed index is
    committed as data/processed/flex_tp_cir_index.json so the build works offline.
    """
    committed = OUT / "flex_tp_cir_index.json"
    txt_path = ROOT / "data" / "cache" / "ntrs" / "20150023456.txt"
    if txt_path.exists():
        txt = txt_path.read_text(encoding="utf-8", errors="ignore")
        idx: dict[str, set] = {}
        for n, c in re.findall(r"FLEX[\u2013-](\d{3})\s+([0-9A-Z]{6,8})\b", txt):
            if not c.isdigit():
                idx.setdefault(c, set()).add(int(n))
        out = {c: sorted(v) for c, v in sorted(idx.items())}
        committed.write_text(json.dumps(out, indent=0))
        return out
    return json.loads(committed.read_text())


def build_flex() -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = read_csv_any(table_path("PSI-69")[0])
    cols = {
        "FLEX Test #": "test", "FLEX Identifier": "table_identifier", "Test Date": "date", "Test GMT": "gmt",
        "Fuel": "fuel", "Ambient pressure; mmHg": "p_mmHg_raw",
        "O initial ambient composition; mole fraction": "x_o2_raw",
        "N initial ambient composition; mole fraction": "x_n2_raw",
        "CO initial ambient composition; mole fraction": "x_co2_raw",
        "He initial ambient composition; mole fraction": "x_he_raw",
        "Droplet initial diameter; mm": "d0_mm_raw",
        "Visible flame extinction diameter; mm": "dext_mm_raw",
        "Burning rate; mm": "K_mm2s_raw", "Burn time; s": "burn_time_s_raw", "Test end": "test_end",
    }
    df = raw.rename(columns=cols)
    log("flex_tests", "rename", "column 'Burning rate; mm' interpreted as K in mm^2/s (test sheets state kavg (mm2/s))")
    log("flex_tests", "rename", "columns 'O/N/CO initial ambient composition' interpreted as O2/N2/CO2 mole fractions")
    for c in ["p_mmHg_raw", "x_o2_raw", "x_n2_raw", "x_co2_raw", "x_he_raw", "d0_mm_raw", "dext_mm_raw",
              "K_mm2s_raw", "burn_time_s_raw"]:
        df[c.replace("_raw", "")] = pd.to_numeric(df[c].str.strip(), errors="coerce")
    df["test"] = pd.to_numeric(df["test"], errors="coerce").astype("Int64")
    df["p_kPa"] = df.p_mmHg * MMHG_KPA
    df["p_atm"] = df.p_kPa / ATM_KPA
    df["pO2_kPa"] = df.x_o2 * df.p_kPa
    df["x_sum"] = df[["x_o2", "x_n2", "x_co2", "x_he"]].sum(axis=1, min_count=1)
    df["diluent"] = np.select(
        [df.x_he > 0.05, df.x_co2 > 0.05, df.x_n2 > 0.05], ["He", "CO2", "N2"], default="other")
    df["fuel"] = df.fuel.str.strip()
    df["test_end"] = df.test_end.str.strip()

    # Canonical FLEX number. The PSI table's "FLEX Test #" is a sequential row number that
    # drifts from the official FLEX numbering after test 155 (tests omitted from the table).
    # NASA/TP-2015-216046 (NTRS 20150023456) lists every test with its CIR identifier, and
    # the per-test PSI files (TestSheet/DropletData) follow that official numbering.
    tp_index = flex_tp_index()
    df["cir_id"] = df.table_identifier.astype(str).str.strip().str.upper()
    df["flex_number"] = df.cir_id.map(lambda c: tp_index[c][0] if len(tp_index.get(c, [])) == 1 else np.nan)
    df["flex_number_source"] = np.where(df.flex_number.notna(), "NASA/TP-2015-216046 via CIR id", "")
    amb = df.flex_number.isna()
    df.loc[amb, "flex_number"] = df.loc[amb, "test"].astype(float)
    df.loc[amb, "flex_number_source"] = "PSI table row number (CIR id absent or ambiguous in TP)"
    df["table_number_offset"] = df.flex_number - df.test.astype(float)
    log("flex_tests", "rekey", "official FLEX number assigned from CIR identifier using NASA/TP-2015-216046 test list",
        int((df.table_number_offset != 0).sum()))

    sheets = []
    for p in sorted((RAW / "files" / "PSI-69").glob("*_TestSheet.txt")):
        s = parse_test_sheet(p)
        s["flex_number"] = int(re.search(r"FLEX-(\d+)_TestSheet", p.name).group(1))
        s["sheet_file"] = p.name
        sheets.append(s)
    sh = pd.DataFrame(sheets)
    sh["sheet_cir_upper"] = sh.sheet_cir_id.astype(str).str.strip().str.upper()
    # join on CIR identifier (robust to numbering drift); keep the sheet's own number for audit
    df = df.merge(sh.rename(columns={"flex_number": "sheet_number"}), left_on="cir_id", right_on="sheet_cir_upper",
                  how="left")
    df = df.drop_duplicates(subset=["test"]).reset_index(drop=True)
    df["has_sheet"] = df.sheet_file.notna()
    for a, b, tol in [("d0_mm", "sheet_d0_mm", 0.011), ("K_mm2s", "sheet_kavg_mm2s", 0.011),
                      ("x_o2", "sheet_x_o2", 0.0051), ("p_atm", "sheet_p_atm", 0.02)]:
        bnum = pd.to_numeric(df[b], errors="coerce")
        df[f"agree_{a}"] = np.where(df[a].notna() & bnum.notna(), (df[a] - bnum).abs() <= tol, pd.NA)
    df["flag_zero_pressure"] = df.p_mmHg <= 0
    log("flex_tests", "flag", "ambient pressure <= 0 mmHg flagged (physically impossible for a burning test)",
        int(df.flag_zero_pressure.sum()))

    # Droplet-history fits: file numbers follow official FLEX numbering
    fits = []
    by_num = df.set_index("flex_number")
    for p in sorted((RAW / "files" / "PSI-69").glob("*_DropletData.txt")):
        num = int(re.search(r"FLEX-(\d+)_DropletData", p.name).group(1))
        tb = None
        if num in by_num.index:
            v = by_num.loc[num, "burn_time_s"]
            v = v.iloc[0] if isinstance(v, pd.Series) else v
            tb = float(v) if pd.notna(v) else None
        h = read_droplet_history(p)
        f = fit_droplet(h, tb)
        f.update(flex_number=num, file=p.name, burn_time_s=tb)
        fits.append(f)
    fits = pd.DataFrame(fits)
    log("flex_droplet_fits", "fit", "K from OLS of d^2 vs t on 0.2*tb..0.9*tb (tb = tabulated burn time)", len(fits))
    df = df.merge(fits[["flex_number", "K_fit_mm2s", "K_fit_se", "K_fit_r2", "K_fit_n", "K_post_mm2s"]],
                  on="flex_number", how="left")
    return df, fits


def flex035_series() -> pd.DataFrame:
    p = RAW / "files" / "PSI-69" / "PSI-69_Raw Data_FLEX-035_DropletData.txt"
    h = read_droplet_history(p)
    h["test"] = 35
    lluv = RAW / "files" / "PSI-69" / "PSI-69_Raw Data_FLEX-035_LLUVData.txt"
    if lluv.exists():
        rows = []
        for l in lluv.read_text(encoding="latin-1").splitlines()[1:]:
            parts = l.split("\t")
            try:
                rows.append([float(parts[0]), float(parts[1])])
            except (ValueError, IndexError):
                continue
        lu = pd.DataFrame(rows, columns=["t_s", "lluv"])
        h = pd.merge_asof(h.sort_values("t_s"), lu.sort_values("t_s"), on="t_s", direction="nearest",
                          tolerance=0.05)
    return h


def build_cfi() -> pd.DataFrame:
    raw = read_csv_any(table_path("PSI-39")[0])
    df = raw.rename(columns={"Flex Number": "test", "Test Date": "date", "Local Time": "local_time",
                             "CIR ": "cir_id", "Pressure": "pressure_raw", "Oxygen": "x_o2_raw",
                             "Nitrogen": "x_n2_raw", "Helium": "x_he_raw", "Fiber": "fiber", "Fuel ": "fuel"})
    df["test"] = pd.to_numeric(df.test, errors="coerce").astype("Int64")
    df["p_atm"] = df.pressure_raw.map(first_number)
    for c in ["x_o2", "x_n2", "x_he"]:
        df[c] = pd.to_numeric(df[c + "_raw"], errors="coerce")
    df["pO2_kPa"] = df.x_o2 * df.p_atm * ATM_KPA
    df["fuel"] = df.fuel.str.strip()
    sheets = []
    for p in sorted((RAW / "files" / "PSI-39").glob("*_TestSheet.txt")):
        s = parse_test_sheet(p)
        s["test"] = int(re.search(r"FLEX-(\d+)_TestSheet", p.name).group(1))
        sheets.append(s)
    if sheets:
        df = df.merge(pd.DataFrame(sheets), on="test", how="left")
        df["cir_match"] = np.where(df.sheet_cir_id.notna(),
                                   df.cir_id.str.strip().str.lower() == df.sheet_cir_id.astype(str).str.strip().str.lower(),
                                   pd.NA)
    fits = []
    for p in sorted((RAW / "files" / "PSI-39").glob("*_DropletData.txt")):
        test = int(re.search(r"FLEX-(\d+)_DropletData", p.name).group(1))
        h = read_droplet_history(p)
        # CFI table has no burn time; fit the steepest sustained linear segment is not attempted.
        fits.append({"test": test, "n_samples": len(h), "t_last": h.t_s.max() if len(h) else np.nan,
                     "d0_hist_mm": float(h[h.t_s <= 0].d_mm.iloc[-1]) if (h.t_s <= 0).any() else np.nan})
    if fits:
        df = df.merge(pd.DataFrame(fits), on="test", how="left")
    return df


# ---------------------------------------------------------------- Saffire
def build_saffire() -> pd.DataFrame:
    rows = []
    s1 = read_csv_any(table_path("PSI-98")[0])
    for _, r in s1.iterrows():
        sid = r["Sample Number "].strip()
        if not re.match(r"^S\d$", sid):
            continue
        rows.append(dict(experiment="Saffire-I", accession="PSI-98", sample=sid, material=r["Material"].strip(),
                         thickness_mm=first_number(r["Sample Thickness (cm)"]) * 10,
                         length_cm=first_number(r["Sample Length (cm)"]), width_cm=first_number(r["Sample Width (cm)"]),
                         flow_nominal_cm_s=first_number(r["Air Flow (cm/s)"]), o2_pct_raw=r["Percent O2"],
                         o2_pct=first_number(r["Percent O2"]), ignition_power_W=first_number(r["Ignition Power (W)"]),
                         ignition_time_s=first_number(r["Ignition Time (s)"]), burn_time_s=first_number(r["Burn Time (s)"]),
                         direction=r["Flow Direction "].strip()))
    log("saffire_samples", "units", "Saffire-I table: length 40.6 cm and width 94 cm appear transposed relative to NTRS 20170008805 (94 x 40.6 cm sample, flow along 94 cm); stored as tabulated")
    s2 = read_csv_any(table_path("PSI-99")[0])
    for _, r in s2.iterrows():
        sid = r["Sample Number"].strip()
        if not re.match(r"^2-\d$", sid):
            continue
        thick_raw = r["Samle Thickness "].strip()
        thick = first_number(thick_raw)
        if thick_raw.startswith("037"):
            thick = 0.37
            log("saffire_samples", "correct", f"Saffire-II {sid}: thickness '037 mm' read as 0.37 mm (NTRS 20170008805 lists 0.37 mm)", 1)
        material = r["Material"].strip()
        mat_source = "psi_table"
        if not material and sid == "2-6":
            material, mat_source = "Cotton-Fiberglass (SIBAL)", "NTRS 20170008805 (samples 2-5 and 2-6 identical fabric)"
            log("saffire_samples", "fill", "Saffire-II 2-6 material blank in PSI table; filled from NTRS 20170008805", 1)
        if not material and sid == "2-9":
            material, mat_source = "PMMA", "NTRS 20170008805 (samples 2-8 and 2-9 PMMA slabs)"
            log("saffire_samples", "fill", "Saffire-II 2-9 material blank in PSI table; filled from NTRS 20170008805", 1)
        spread = r["?-g Spread Length"].strip()
        rows.append(dict(experiment="Saffire-II", accession="PSI-99", sample=sid, material=material,
                         material_source=mat_source, thickness_mm=thick if "cm" not in thick_raw else thick * 10,
                         thickness_raw=thick_raw, length_cm=first_number(r["Sample Length "]),
                         width_cm=first_number(r["Sample Width (cm)"]),
                         flow_nominal_cm_s=first_number(r["Air Flow (cm/s)"]), o2_pct_raw=r["Percent O2 (Note 1)"],
                         o2_pct=first_number(r["Percent O2 (Note 1)"]),
                         o2_basis="derived from measured CO2 production, referenced to ISS initial O2 (table note 1)",
                         ignition_power_W=first_number(r["Ignition Power (W)"]),
                         ignition_time_s=first_number(r["Ignition Time (s)"]),
                         burn_time_s=first_number(r["Burn Time (s)"]), burn_time_raw=r["Burn Time (s)"],
                         direction=r["Flow Direction"].strip(), ug_burn_length_raw=r["?-g Burn Length"],
                         ug_spread_rate_mm_s=first_number(spread) if "mm/s" in spread else np.nan,
                         onegee_burn_length_raw=r["1-g Burn Length"], onegee_spread_raw=r["1-g Spread Rate"]))
    s3 = read_csv_any(table_path("PSI-100")[0])
    for _, r in s3.iterrows():
        sid = r["Sample Number "].strip()
        if not re.match(r"^S\d$", sid):
            continue
        rows.append(dict(experiment="Saffire-III", accession="PSI-100", sample=sid, material=r["Material"].strip(),
                         thickness_mm=first_number(r["Sample Thickness"]) * 10,
                         length_cm=first_number(r["Sample Length"]), width_cm=first_number(r["Sample Width"]),
                         flow_nominal_cm_s=first_number(r["Air Flow "]), direction=r["Direction"].strip()))
    df = pd.DataFrame(rows)
    df["ignition_energy_J"] = df.ignition_power_W * df.ignition_time_s
    return df


def saffire2_flow() -> pd.DataFrame | None:
    """Measured duct flow per Saffire-II sample from the telemetry workbook (cache)."""
    p = CACHE / "PSI-99" / "PSI-99_Raw Data_Saffire-II Telemetry Data.xlsx"
    if not p.exists():
        return None
    import openpyxl
    wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
    rows = list(wb["RawData"].iter_rows(values_only=True))
    hdr = [c if c else f"c{i}" for i, c in enumerate(rows[0])]
    df = pd.DataFrame(rows[1:], columns=hdr).apply(pd.to_numeric, errors="coerce")
    # 'RelativeSeconds' holds milliseconds (values step by 1000 per 1 s row).
    df["t_s"] = df["RelativeSeconds"] / 1000.0
    df = df[(df.t_s > -20000) & (df.t_s < 1000)]
    log("saffire2_flow", "units", "RelativeSeconds column contains milliseconds; divided by 1000")
    keep = ["t_s", "Anemometer1", "Anemometer2", "FanTachometer", "Radiometer1Value", "Radiometer2Value",
            "Radiometer3Value", "Radiometer4Value"] + [f"Sample{i}IgniterI" for i in range(1, 10)]
    ts = df[keep].reset_index(drop=True)
    out = []
    for s in range(1, 10):
        active = ts[f"Sample{s}IgniterI"] > -1.0   # state-coded channel: ~0.03 when the igniter is energised
        if not active.any():
            continue
        ti = float(ts.t_s[active].min())
        win = ts[(ts.t_s >= ti) & (ts.t_s < ti + 120)]
        pre = ts[(ts.t_s >= ti - 60) & (ts.t_s < ti - 2)]
        out.append({
            "sample": f"2-{s}", "ignition_t_s": ti, "igniter_active_samples": int(active.sum()),
            "anem1_mean_cm_s": win.Anemometer1.mean(), "anem1_sd": win.Anemometer1.std(),
            "anem2_mean_cm_s": win.Anemometer2.mean(), "anem2_sd": win.Anemometer2.std(),
            "anem_mean_cm_s": (win.Anemometer1.mean() + win.Anemometer2.mean()) / 2,
            "anem_diff_cm_s": win.Anemometer1.mean() - win.Anemometer2.mean(),
            "fan_tach_mean": win.FanTachometer.mean(), "n_window": len(win),
            "anem1_pre_mean": pre.Anemometer1.mean(),
        })
    flow = pd.DataFrame(out)
    # 1 Hz telemetry export for the window -60..+300 s around each ignition (compact, committed)
    parts = []
    for r in out:
        w = ts[(ts.t_s >= r["ignition_t_s"] - 60) & (ts.t_s <= r["ignition_t_s"] + 300)].copy()
        w.insert(0, "sample", r["sample"])
        w["t_rel_s"] = w.t_s - r["ignition_t_s"]
        parts.append(w[["sample", "t_rel_s", "Anemometer1", "Anemometer2", "FanTachometer",
                        "Radiometer1Value", "Radiometer2Value", "Radiometer3Value", "Radiometer4Value"]])
    pd.concat(parts).to_csv(OUT / "saffire2_telemetry_windows.csv", index=False, float_format="%.4g")
    return flow


# ---------------------------------------------------------------- BASS, SAME, DAFT, others
def build_bass2() -> pd.DataFrame:
    raw = read_csv_any(table_path("PSI-25")[0])
    raw.columns = [re.sub(r"\s+", " ", c).strip() for c in raw.columns]
    df = pd.DataFrame({
        "pi": raw["PI"].str.strip(), "test": raw["Test #"].str.strip(), "date": raw["Date"],
        "sample": raw["Sample #"].str.strip(), "material_raw": raw["Fuel Sample Material"].str.strip(),
        "flow_restrictor_raw": raw["Flow restrictor"], "fan_display_raw": raw["Fan display"],
        "o2_init_pct_raw": raw["Calibrated initial O2 % by vol"], "o2_final_pct_raw": raw["Calibrated final O2 % by vol"],
        "co2_init_pct_raw": raw["Initial CO2 % by vol"], "co2_final_pct_raw": raw["Final CO2 % by vol"],
        "co_init_ppm_raw": raw["Initial CO (ppm)"], "co_final_ppm_raw": raw["Final CO (ppm)"],
    })
    for c in ["o2_init_pct", "o2_final_pct", "co2_init_pct", "co2_final_pct", "co_init_ppm", "co_final_ppm",
              "fan_display"]:
        df[c] = df[c + "_raw"].map(lambda s: first_number(s) if re.fullmatch(r"\s*-?\d+(\.\d+)?\s*", str(s)) else np.nan)
    df["multi_valued_fan"] = df.fan_display_raw.str.contains(r"\d\s+\d", regex=True)
    m = df.material_raw.str.lower()
    df["material_class"] = np.select(
        [m.str.contains("pmma"), m.str.contains("sibal|cotton"), m.str.contains("acrylic"), m.str.contains("delrin"),
         m.str.contains("cellulose|kimwipe|paper"), m.str.contains("film")],
        ["PMMA", "SIBAL", "acrylic", "Delrin", "cellulose", "film (unspecified)"], default="other")
    df["thickness_um"] = df.material_raw.str.extract(r"(\d+)\s*micron")[0].astype(float)
    df["o2_drop_pct"] = df.o2_init_pct - df.o2_final_pct
    df["flag_o2_increase"] = df.o2_final_pct > df.o2_init_pct + 1.0
    log("bass2_tests", "flag", "o2_final > o2_init + 1 vol% flagged as implausible (no O2 source in MSG work volume)",
        int(df.flag_o2_increase.sum()))
    return df


def build_same_r() -> pd.DataFrame:
    raw = read_csv_any(table_path("PSI-101")[0])
    df = raw.rename(columns={"Sample Type": "material", "SAME Test #": "test", "Description": "description",
                             "Date": "date", "Inlet velocity (cm/s)": "inlet_velocity_cm_s_raw", "Rt/R0": "rt_r0_raw",
                             "Duration (sec)": "duration_s_raw", "Primary aging time (sec)": "primary_aging_s_raw",
                             "Primary mixing time (sec)": "primary_mixing_s_raw", "Net aging time (sec)": "net_aging_s_raw"})
    for c in ["inlet_velocity_cm_s", "rt_r0", "duration_s", "primary_aging_s", "primary_mixing_s", "net_aging_s"]:
        df[c] = pd.to_numeric(df[c + "_raw"].str.strip(), errors="coerce")
    df["material"] = df.material.str.strip()
    df["is_aged_segment"] = df.test.str.strip().str.match(r"^\d+[a-z]$")
    return df


def build_same_reduced() -> tuple[pd.DataFrame, pd.DataFrame]:
    """SAME/SAME-R per-test particle statistics and smoke-detector responses.

    Source: PSI-101 'SAME, SAME-R_Results.xlsx' (sheet 'Reduced data sheet' for particle
    moments of both flights; sheet 'SAME R Results' for ISS/STS detector voltages, SAME-R only).
    """
    import warnings
    p = RAW / "files" / "PSI-101" / "PSI-101_Analyzed Data_SAME, SAME-R_Results.xlsx"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        red = pd.read_excel(p, sheet_name="Reduced data sheet", header=1)
        det = pd.read_excel(p, sheet_name="SAME R Results", header=1)
    red.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in red.columns]
    red = red.rename(columns={
        red.columns[0]: "flight", "Sample Type": "material", "SAME #": "same_test", "Description": "description",
        "Inlet Velocity (cm/sec)": "inlet_velocity_cm_s", "Rt/R0": "rt_r0", "Net Aging Duration": "net_aging_s",
        "M0 best Diameter": "M0_per_cm3", "M1 (mm/cm^3)": "M1_mm_per_cm3",
        "M1/M0 (micro-m)--AMD": "amd_um", "Hatch Choate Sigma g": "sigma_g", "Hatch Choate Dg": "dg_um",
        "Sample Temperature C": "sample_T_C", "Mass Loss (mg)": "mass_loss_mg"})
    keep = ["flight", "material", "same_test", "description", "inlet_velocity_cm_s", "rt_r0", "net_aging_s",
            "M0_per_cm3", "M1_mm_per_cm3", "amd_um", "sigma_g", "dg_um", "sample_T_C", "mass_loss_mg"]
    dam = [c for c in red.columns if c.startswith("Diameter of Average mass")]
    if dam:
        red = red.rename(columns={dam[0]: "d_avg_mass_um"})
        keep.insert(10, "d_avg_mass_um")
    red = red[keep]
    red = red[red.material.notna() & red.flight.notna()].copy()
    red["flight"] = red.flight.astype(str).str.strip().map({"1": "SAME", "2": "SAME-R", "g": "ground"}).fillna(red.flight.astype(str))
    for c in keep[4:]:
        red[c] = pd.to_numeric(red[c], errors="coerce")
    red["material"] = red.material.astype(str).str.strip()
    # zero moments mean 'not measured' in this workbook (e.g. DBP rows), not zero particles
    for c in ["M0_per_cm3", "M1_mm_per_cm3", "amd_um", "sigma_g", "dg_um"]:
        red.loc[red[c] == 0, c] = np.nan
    log("same_reduced", "nullify", "zero particle moments treated as not measured", None)

    det.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in det.columns]
    dcols = {"Sample Type": "material", "SAME #": "same_test", "Description": "description",
             "Inlet Velocity (cm/sec)": "inlet_velocity_cm_s", "Rt/R0": "rt_r0", "Net Aging Duration": "net_aging_s",
             "ISS Obscuration (volts)": "iss_obscuration_V", "ISS Detector Scatter (volts)": "iss_scatter_V",
             "STS Detector (volts)": "sts_detector_V", "STS Detector offset (volts)": "sts_offset_V",
             "M1/M0 (micro-m)--AMD": "amd_um", "Mass Loss (mg)": "mass_loss_mg"}
    det = det.rename(columns=dcols)
    det = det.loc[:, ~det.columns.duplicated()]
    det = det[[c for c in dcols.values() if c in det.columns]]
    det = det[det.material.notna() & det.same_test.notna()].copy()
    for c in det.columns[3:]:
        det[c] = pd.to_numeric(det[c], errors="coerce")
    det["material"] = det.material.astype(str).str.strip()
    det["same_test"] = det.same_test.astype(str).str.strip()
    return red, det


def build_generic(acc: str) -> list[tuple[str, pd.DataFrame]]:
    out = []
    for p in table_path(acc):
        df = read_csv_any(p)
        df.columns = [re.sub(r"\s+", " ", c).strip() for c in df.columns]
        df = df.loc[:, [c for c in df.columns if c]]
        df = df[~(df == "").all(axis=1)]
        name = re.sub(r"[^a-z0-9]+", "_", p.stem.split("Experimental table_", 1)[-1].lower()).strip("_")
        out.append((f"{acc}_{name}", df))
    return out


def quality_audit(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for name, df in tables.items():
        for c in df.columns:
            s = df[c]
            blank = s.isna() | (s.astype(str).str.strip().isin(["", "none", "n/a", "N/A", "nan"]))
            rows.append({"table": name, "column": c, "rows": len(df), "missing_or_blank": int(blank.sum()),
                         "missing_pct": round(100 * blank.mean(), 1) if len(df) else 0,
                         "n_unique": int(s.nunique(dropna=True)), "dtype": str(s.dtype)})
    return pd.DataFrame(rows)


def run() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    LOG.clear()
    written = {}

    def save(name: str, df: pd.DataFrame):
        df.to_csv(OUT / f"{name}.csv", index=False)
        written[name] = df

    save("investigations", build_investigations())
    save("catalog_summary", build_catalog_summary())
    flex, fits = build_flex()
    save("flex_tests", flex)
    save("flex_droplet_fits", fits)
    save("flex035_timeseries", flex035_series())
    save("cfi_tests", build_cfi())
    save("saffire_samples", build_saffire())
    flow = saffire2_flow()
    if flow is not None:
        save("saffire2_flow", flow)
    elif (OUT / "saffire2_flow.csv").exists():
        log("saffire2_flow", "reuse", "telemetry workbook not in cache; kept previously derived saffire2_flow.csv")
    save("bass2_tests", build_bass2())
    save("same_r_tests", build_same_r())
    red, det = build_same_reduced()
    save("same_reduced", red)
    save("same_r_detectors", det)
    for acc in ["PSI-10", "PSI-102", "PSI-106", "PSI-107", "PSI-142", "PSI-159", "PSI-20", "PSI-21", "PSI-22",
                "PSI-23", "PSI-26", "PSI-47", "PSI-68"]:
        for name, df in build_generic(acc):
            save(f"table_{name}", df)
    for p in sorted((RAW / "files" / "PSI-117").glob("*.csv")):
        nm = re.sub(r"[^a-z0-9]+", "_", p.stem.split("Analyzed Data_", 1)[-1].lower()).strip("_")
        save(f"psi117_{nm}", read_csv_any(p))
    save("quality_audit_columns", quality_audit({k: v for k, v in written.items() if not k.startswith("quality")}))
    dup = catalog_duplicates()
    meta = {"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tables": {k: int(len(v)) for k, v in written.items()}, "catalog": dup, "log": LOG}
    (OUT / "derivation_log.json").write_text(json.dumps(meta, indent=1, default=str))
    return meta


if __name__ == "__main__":
    m = run()
    print(json.dumps({"tables": m["tables"], "catalog": m["catalog"]}, indent=1))
