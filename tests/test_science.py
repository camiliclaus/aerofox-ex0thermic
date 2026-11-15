"""Units, compartment model verification and droplet calculations."""
import numpy as np
import pytest

from aerofox.science import analyses as A
from aerofox.science import compartment as cm
from aerofox.science.units import UnitError, atmosphere, convert, o2_fraction, to_kpa


def test_pressure_conversions():
    assert to_kpa(1, "atm") == pytest.approx(101.325)
    assert to_kpa(14.696, "psi") == pytest.approx(101.325, rel=1e-4)
    assert to_kpa(760, "mmHg") == pytest.approx(101.325, rel=1e-5)
    assert convert(8.2, "psi", "kPa")["value"] == pytest.approx(56.54, abs=0.01)
    assert convert(25, "C", "K")["value"] == pytest.approx(298.15)


def test_o2_percent_vs_fraction():
    assert o2_fraction(34, "%") == pytest.approx(0.34)
    assert o2_fraction(0.34, "fraction") == pytest.approx(0.34)
    with pytest.raises(UnitError):
        o2_fraction(120, "%")
    with pytest.raises(UnitError):
        convert(1, "psi", "m")


def test_partial_pressure():
    a = atmosphere(56.5, 0.34)
    assert a["pO2_kPa"] == pytest.approx(19.21, abs=0.01)
    with pytest.raises(UnitError):
        atmosphere(-1, 0.2)


def test_single_compartment_matches_analytic_decay():
    V, Q, c0 = 20.0, 0.05, 1.0
    comps = [cm.Compartment("a", V, supply_m3s=Q, exhaust_m3s=Q, c0=c0)]
    for method, tol in (("implicit", 5e-3), ("rk4", 1e-6)):
        r = cm.simulate(comps, [], t_end_s=1200, dt_s=1.0, method=method)
        t = np.array(r["t_s"])
        exact = cm.analytic_single_decay(c0, V, Q, t)
        assert np.max(np.abs(np.array(r["C"]["a"]) - exact)) < tol


def test_implicit_converges_first_order():
    comps = [cm.Compartment("a", 10, supply_m3s=0.1, exhaust_m3s=0.1, c0=1.0)]
    errs = []
    for dt in (4.0, 2.0, 1.0):
        r = cm.simulate(comps, [], t_end_s=200, dt_s=dt)
        errs.append(abs(r["C"]["a"][-1] - cm.analytic_single_decay(1.0, 10, 0.1, np.array([200.0]))[0]))
    assert errs[0] / errs[1] == pytest.approx(2, rel=0.15)
    assert errs[1] / errs[2] == pytest.approx(2, rel=0.15)


def test_mass_conservation_with_source_and_network():
    ex = A.EXAMPLE_VENT["connected"]
    r = A.ventilation_sim(ex["compartments"], ex["flows"], 1800)
    assert abs(r["data"]["mass_balance_relative_error"]) < 1e-9


def test_steady_state_source():
    # constant source G in a flushed room: C_ss = G / Q
    comps = [cm.Compartment("a", 30, supply_m3s=0.1, exhaust_m3s=0.1, source_rate=0.5, source_duration_s=1e6)]
    r = cm.simulate(comps, [], t_end_s=6000, dt_s=2)
    assert r["C"]["a"][-1] == pytest.approx(0.5 / 0.1, rel=1e-3)


@pytest.mark.parametrize("bad", [
    ([cm.Compartment("a", -1)], []),
    ([cm.Compartment("a", 10, supply_m3s=0.1)], []),                     # supply without exhaust
    ([cm.Compartment("a", 10), cm.Compartment("a", 5)], []),             # duplicate names
    ([cm.Compartment("a", 10)], [("a", "b", 0.1)]),                      # unknown compartment
])
def test_invalid_models_rejected(bad):
    with pytest.raises(cm.ModelError):
        cm.simulate(*bad, t_end_s=100)


def test_droplet_burnout_time():
    r = A.droplet_burn(2.0, K_mm2s=0.5)
    assert r["data"]["burnout_time_s"] == pytest.approx(8.0)
    with pytest.raises(A.AnalysisError):
        A.droplet_burn(-1, 0.5)


def test_atmosphere_assessment_flags_gaps():
    r = A.assess_atmosphere(8.2, "psi", 34, "%", "lunar")
    assert r["data"]["pO2_kPa"] == pytest.approx(19.22, abs=0.02)
    joined = " ".join(r["warnings"])
    assert "No PSI solid-material" in joined and "lunar" in joined
    with pytest.raises(A.AnalysisError):
        A.assess_atmosphere(2, "kPa", 21)
