"""Pins the scientific results the application relies on to the processed snapshot."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from aerofox.ingest.fetch import sha256_file

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"


def t(name):
    return pd.read_csv(PROC / f"{name}.csv", low_memory=False)


def test_manifest_checksums_for_committed_files():
    m = json.loads((ROOT / "data/raw/psi/manifest.json").read_text())
    committed = [e for e in m["files"].values() if e.get("committed") is not False]
    assert len(committed) >= 600
    bad = [e["path"] for e in committed if sha256_file(ROOT / e["path"]) != e["sha256"]]
    assert not bad


def test_catalog_counts_match_audit():
    d = json.loads((PROC / "derivation_log.json").read_text())["catalog"]
    assert d["entries"] == 66567
    assert d["referenced_bytes_dedup_name_size"] / 1e12 == pytest.approx(13.47, abs=0.01)
    assert len(t("investigations")) == 24


def test_flex_rekey_restores_agreement():
    f = t("flex_tests")
    assert len(f) == 274
    assert (f.table_number_offset != 0).sum() == 119
    v = f[(f.K_fit_r2 > 0.95) & f.K_mm2s.notna()]
    r = np.corrcoef(v.K_fit_mm2s, v.K_mm2s)[0, 1]
    assert r > 0.98
    assert (v.K_fit_mm2s - v.K_mm2s).abs().median() < 0.01


def test_flex035_reference_values():
    f = t("flex_tests").set_index("flex_number").loc[35]
    assert f.cir_id == "181F001" and f.fuel == "Heptane"
    assert f.K_mm2s == pytest.approx(0.43)
    assert f.K_fit_mm2s == pytest.approx(0.412, abs=0.005)
    assert f.K_post_mm2s == pytest.approx(0.419, abs=0.005)


def test_saffire2_sample_6_flow():
    s = t("saffire2_flow").set_index("sample")
    assert s.loc["2-6", "anem_mean_cm_s"] == pytest.approx(25.0, abs=0.3)
    for smp in ["2-1", "2-2", "2-3", "2-4", "2-5"]:
        assert s.loc[smp, "anem_mean_cm_s"] == pytest.approx(20.0, abs=0.3)
    sa = t("saffire_samples").set_index("sample")
    assert sa.loc["2-6", "material"].startswith("Cotton-Fiberglass")
    assert sa.loc["2-4", "thickness_mm"] == pytest.approx(0.37)


def test_units_and_ranges_are_physical():
    f = t("flex_tests")
    ok = f[~f.flag_zero_pressure]
    assert ok.x_o2.between(0.1, 0.4).all()
    assert ok.p_kPa.between(40, 320).all()
    # FLEX-129 (very short burn) reports d_ext 0.01 mm above d0: within imaging resolution / initial swelling
    assert (ok.dext_mm.dropna() <= ok.loc[ok.dext_mm.notna(), "d0_mm"] + 0.02).all()
    s = t("same_reduced")
    assert s.amd_um.dropna().between(0.01, 2).all()


def test_findings_catalog_complete():
    f = json.loads((ROOT / "data/findings/findings.json").read_text())["findings"]
    assert len(f) >= 12
    for x in f:
        for k in ("id", "question", "result", "dataset", "locator", "method", "uncertainty", "limitations", "implication"):
            assert x.get(k), (x["id"], k)
