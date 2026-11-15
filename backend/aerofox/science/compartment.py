"""Well-mixed compartment transport of a passive tracer (e.g. a smoke surrogate).

For N fixed-volume compartments with volumes V_i (m^3), concentrations C_i
(arbitrary mass units per m^3), inter-compartment volumetric flows Q_ij (m^3/s,
from i to j), fresh-air supply S_i (m^3/s, concentration 0) and exhaust E_i (m^3/s):

    V_i dC_i/dt = sum_j Q_ji C_j - (sum_j Q_ij + E_i) C_i + G_i(t)        (1)

Volume conservation at fixed volume requires, for every i,

    S_i + sum_j Q_ji = E_i + sum_j Q_ij                                      (2)

G_i(t) is a tracer source (units/s). Tracer mass balance:

    d/dt sum_i V_i C_i = sum_i G_i - sum_i E_i C_i                           (3)

The system is linear, dC/dt = A C + b(t). It is integrated with the implicit
(backward) Euler method, which is unconditionally stable for this matrix, and
optionally with classical RK4 for comparison. A passive tracer says nothing
about flame spread, toxicity, detector alarm logic or suppression.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


class ModelError(ValueError):
    pass


@dataclass
class Compartment:
    name: str
    volume_m3: float
    supply_m3s: float = 0.0
    exhaust_m3s: float = 0.0
    source_rate: float = 0.0          # tracer units per second
    source_start_s: float = 0.0
    source_duration_s: float = 0.0    # 0 = no source
    c0: float = 0.0


def build(compartments: list[Compartment], flows: list[tuple[str, str, float]]):
    if not 1 <= len(compartments) <= 20:
        raise ModelError("between 1 and 20 compartments are supported")
    names = [c.name for c in compartments]
    if len(set(names)) != len(names):
        raise ModelError("compartment names must be unique")
    idx = {n: i for i, n in enumerate(names)}
    n = len(names)
    V = np.array([c.volume_m3 for c in compartments], float)
    if np.any(V <= 0) or np.any(V > 1e5):
        raise ModelError("volumes must be in (0, 1e5] m^3")
    Q = np.zeros((n, n))
    for a, b, q in flows:
        if a not in idx or b not in idx:
            raise ModelError(f"flow references unknown compartment: {a} -> {b}")
        if a == b or q < 0:
            raise ModelError("flows must connect two different compartments and be non-negative")
        Q[idx[a], idx[b]] += q
    S = np.array([c.supply_m3s for c in compartments], float)
    E = np.array([c.exhaust_m3s for c in compartments], float)
    if np.any(S < 0) or np.any(E < 0):
        raise ModelError("supply and exhaust must be non-negative")
    inflow = S + Q.sum(axis=0)
    outflow = E + Q.sum(axis=1)
    imbalance = inflow - outflow
    if np.any(np.abs(imbalance) > 1e-9 + 1e-6 * np.maximum(inflow, outflow)):
        bad = [f"{names[i]}: in {inflow[i]:.4g} vs out {outflow[i]:.4g} m3/s" for i in np.where(np.abs(imbalance) > 1e-9)[0]]
        raise ModelError("volume flow is not conserved (fixed-volume compartments): " + "; ".join(bad))
    A = (Q.T - np.diag(Q.sum(axis=1) + E)) / V[:, None]
    return names, V, Q, S, E, A


def source_vector(compartments: list[Compartment], V: np.ndarray, t: float) -> np.ndarray:
    g = np.array([c.source_rate if c.source_duration_s > 0 and c.source_start_s <= t < c.source_start_s + c.source_duration_s
                  else 0.0 for c in compartments])
    return g / V


def simulate(compartments: list[Compartment], flows: list[tuple[str, str, float]], t_end_s: float,
             dt_s: float | None = None, method: str = "implicit") -> dict:
    names, V, Q, S, E, A = build(compartments, flows)
    if not 0 < t_end_s <= 7 * 86400:
        raise ModelError("simulation time must be in (0, 7 days]")
    rates = np.abs(np.diag(A))
    tau_min = 1 / rates.max() if rates.max() > 0 else t_end_s
    if dt_s is None:
        dt_s = min(t_end_s / 400, max(tau_min / 5, t_end_s / 20000))
    if dt_s <= 0:
        raise ModelError("time step must be positive")
    steps = int(np.ceil(t_end_s / dt_s))
    if steps > 200000:
        raise ModelError("too many time steps; increase dt or shorten the simulation")
    C = np.array([c.c0 for c in compartments], float)
    out_t, out_C = [0.0], [C.copy()]
    mass_in, mass_out = 0.0, 0.0
    I = np.eye(len(V))
    M = np.linalg.inv(I - dt_s * A)
    t = 0.0
    for _ in range(steps):
        if method == "rk4":
            f = lambda tt, cc: A @ cc + source_vector(compartments, V, tt)
            k1 = f(t, C); k2 = f(t + dt_s / 2, C + dt_s / 2 * k1)
            k3 = f(t + dt_s / 2, C + dt_s / 2 * k2); k4 = f(t + dt_s, C + dt_s * k3)
            Cn = C + dt_s / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        else:
            Cn = M @ (C + dt_s * source_vector(compartments, V, t + dt_s))
        g = source_vector(compartments, V, t + dt_s) * V
        mass_in += g.sum() * dt_s
        mass_out += (E * (Cn if method == "implicit" else 0.5 * (C + Cn))).sum() * dt_s
        C, t = Cn, t + dt_s
        out_t.append(t)
        out_C.append(C.copy())
    out_C = np.array(out_C)
    m0 = float((V * out_C[0]).sum())
    m_end = float((V * out_C[-1]).sum())
    balance_err = (m_end - (m0 + mass_in - mass_out)) / max(m0 + mass_in, 1e-12)
    # thin output to <= 400 points for transport to the browser
    stride = max(1, len(out_t) // 400)
    sel = list(range(0, len(out_t), stride))
    if sel[-1] != len(out_t) - 1:
        sel.append(len(out_t) - 1)
    peaks = {n: {"peak": float(out_C[:, i].max()), "t_peak_s": float(out_t[int(out_C[:, i].argmax())])}
             for i, n in enumerate(names)}
    return {
        "names": names, "t_s": [round(out_t[i], 3) for i in sel],
        "C": {n: [float(out_C[i, j]) for i in sel] for j, n in enumerate(names)},
        "dt_s": dt_s, "steps": steps, "method": method, "peaks": peaks,
        "air_changes_per_hour": {n: float(3600 * (Q[j].sum() + E[j]) / V[j]) for j, n in enumerate(names)},
        "mass_balance_relative_error": float(balance_err),
        "fastest_time_constant_s": float(tau_min),
    }


def analytic_single_decay(c0: float, volume: float, flow: float, t: np.ndarray) -> np.ndarray:
    """C(t) = C0 exp(-Q t / V) for one compartment flushed with clean air (verification case)."""
    return c0 * np.exp(-flow * t / volume)


def time_to_fraction(t: list[float], c: list[float], level: float) -> float | None:
    for ti, ci in zip(t, c):
        if ci >= level:
            return ti
    return None
