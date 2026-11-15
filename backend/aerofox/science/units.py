"""Unit conversion for the quantities AeroFox handles. Explicit tables, no magic."""
from __future__ import annotations

ATM_KPA = 101.325
TO_KPA = {"kpa": 1.0, "pa": 1e-3, "mpa": 1e3, "bar": 100.0, "mbar": 0.1, "atm": ATM_KPA, "psi": 6.894757,
          "psia": 6.894757, "mmhg": 0.133322368, "torr": 0.133322368, "inhg": 3.386389}
TO_M = {"m": 1.0, "cm": 1e-2, "mm": 1e-3, "um": 1e-6, "µm": 1e-6, "in": 0.0254, "ft": 0.3048}
TO_M3 = {"m3": 1.0, "l": 1e-3, "liter": 1e-3, "litre": 1e-3, "ft3": 0.0283168}
TO_M3S = {"m3/s": 1.0, "m3/h": 1 / 3600, "l/s": 1e-3, "l/min": 1e-3 / 60, "cfm": 0.000471947}
TO_MS = {"m/s": 1.0, "cm/s": 1e-2, "mm/s": 1e-3, "ft/min": 0.00508}
TO_C = {"c": lambda v: v, "k": lambda v: v - 273.15, "f": lambda v: (v - 32) * 5 / 9}
GRAVITY_MS2 = {"earth": 9.80665, "lunar": 1.62, "mars": 3.71, "micro": 0.0}

TABLES = {"pressure": (TO_KPA, "kPa"), "length": (TO_M, "m"), "volume": (TO_M3, "m3"),
          "volumetric_flow": (TO_M3S, "m3/s"), "velocity": (TO_MS, "m/s")}


class UnitError(ValueError):
    pass


def _norm(u: str) -> str:
    return u.strip().lower().replace(" ", "").replace("³", "3").replace("^3", "3")


def convert(value: float, from_unit: str, to_unit: str) -> dict:
    """Convert between units of the same dimension. Raises UnitError on mismatch."""
    fu, tu = _norm(from_unit), _norm(to_unit)
    if fu in TO_C or tu in TO_C:
        if fu not in TO_C or tu not in TO_C:
            raise UnitError(f"cannot convert {from_unit} to {to_unit}")
        c = TO_C[fu](value)
        out = {"c": c, "k": c + 273.15, "f": c * 9 / 5 + 32}[tu]
        return {"value": out, "unit": to_unit, "dimension": "temperature"}
    for dim, (table, base) in TABLES.items():
        if fu in table and tu in table:
            return {"value": value * table[fu] / table[tu], "unit": to_unit, "dimension": dim}
    raise UnitError(f"unknown or incompatible units: {from_unit} -> {to_unit}")


def to_kpa(value: float, unit: str) -> float:
    u = _norm(unit)
    if u not in TO_KPA:
        raise UnitError(f"unknown pressure unit {unit}")
    return value * TO_KPA[u]


def o2_fraction(value: float, unit: str = "%") -> float:
    """O2 given as percent ('%', 'vol%') or mole fraction ('fraction'). Validated to (0, 1]."""
    frac = value / 100.0 if unit.strip() in ("%", "vol%", "percent", "pct") else value
    if not 0 < frac <= 1:
        raise UnitError(f"O2 amount out of range: {value} {unit}")
    return frac


def atmosphere(p_kpa: float, x_o2: float) -> dict:
    if p_kpa <= 0:
        raise UnitError("pressure must be positive")
    if not 0 < x_o2 <= 1:
        raise UnitError("O2 mole fraction must be in (0, 1]")
    return {"pressure_kPa": round(p_kpa, 2), "pressure_psia": round(p_kpa / TO_KPA["psi"], 2),
            "pressure_atm": round(p_kpa / ATM_KPA, 3), "o2_mole_fraction": round(x_o2, 4),
            "o2_percent": round(100 * x_o2, 2), "pO2_kPa": round(p_kpa * x_o2, 2),
            "pO2_psia": round(p_kpa * x_o2 / TO_KPA["psi"], 2)}
