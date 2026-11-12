"""Unit handling. Every conversion goes through ``pint`` (spec §0.6, §9.6).

Canonical internal units:
    O₂            mole fraction (0–1)
    pressure      kPa
    flow velocity cm/s
    gravity       multiples of g₀
    length        cm
    time          s

Unknown or unparsable units never raise inside ``normalize``; they return
``status="unknown"`` so the registry can store the raw string beside a null value.
"""

from __future__ import annotations

from dataclasses import dataclass

import pint

ureg = pint.UnitRegistry()
ureg.define("g0 = 9.80665 m/s**2 = gravity_multiple")
Q_ = ureg.Quantity

# Quantity name -> canonical pint unit string
CANONICAL: dict[str, str] = {
    "x_o2": "dimensionless",
    "p_kpa": "kPa",
    "u_cms": "cm/s",
    "gravity_g0": "g0",
    "size_cm": "cm",
    "time_s": "s",
}

# Spellings seen in NASA tables/papers mapped to pint-parsable units.
UNIT_ALIASES: dict[str, str] = {
    "%": "percent",
    "% o2": "percent",
    "%o2": "percent",
    "percent": "percent",
    "pct": "percent",
    "vol%": "percent",
    "mol%": "percent",
    "mol %": "percent",
    "% by vol": "percent",
    "vol %": "percent",
    "fraction": "dimensionless",
    "mole fraction": "dimensionless",
    "psia": "psi",
    "psi": "psi",
    "psig": "psi",  # gauge: caller must add atmospheric offset before normalizing
    "kpa": "kPa",
    "pa": "Pa",
    "atm": "atm",
    "bar": "bar",
    "mbar": "mbar",
    "torr": "torr",
    "mmhg": "mmHg",
    "cm/s": "cm/s",
    "cm s-1": "cm/s",
    "mm/s": "mm/s",
    "m/s": "m/s",
    "cm": "cm",
    "mm": "mm",
    "m": "m",
    "in": "inch",
    "inch": "inch",
    "s": "s",
    "sec": "s",
    "min": "min",
    "g": "g0",
    "g0": "g0",
    "ge": "g0",
}


@dataclass(frozen=True)
class Normalized:
    value: float | None
    unit: str  # canonical unit string
    status: str  # "known" | "unknown"
    unit_as_written: str | None = None
    note: str | None = None


def _resolve_unit(unit: str) -> str | None:
    key = unit.strip().lower()
    return UNIT_ALIASES.get(key, unit.strip() if unit.strip() else None)


def convert(value: float, from_unit: str, to_unit: str) -> float:
    """Convert ``value`` between units via pint. Raises on incompatible/unknown units."""
    src = _resolve_unit(from_unit)
    if src is None:
        raise ValueError("empty unit")
    if src == "percent":
        q = Q_(value / 100.0, "dimensionless")
    else:
        q = Q_(value, src)
    if to_unit == "dimensionless":
        return float(q.to("dimensionless").magnitude)
    return float(q.to(to_unit).magnitude)


def normalize(value: float | None, unit_as_written: str | None, quantity: str) -> Normalized:
    """Normalize a raw (value, unit) pair into the canonical unit for ``quantity``.

    Never raises for bad units: returns ``status="unknown"`` with a note instead.
    """
    if quantity not in CANONICAL:
        raise KeyError(f"unknown quantity {quantity!r}; expected one of {list(CANONICAL)}")
    target = CANONICAL[quantity]
    if value is None:
        return Normalized(None, target, "unknown", unit_as_written, "no value")
    if unit_as_written is None or not unit_as_written.strip():
        # Only O2 may be given unitless, and only when it already looks like a fraction.
        if quantity == "x_o2" and 0.0 <= value <= 1.0:
            return Normalized(float(value), target, "known", unit_as_written, "assumed fraction")
        return Normalized(None, target, "unknown", unit_as_written, "unit not stated")
    try:
        out = convert(float(value), unit_as_written, target)
    except (pint.errors.UndefinedUnitError, pint.errors.DimensionalityError, ValueError) as exc:
        return Normalized(None, target, "unknown", unit_as_written, f"unconvertible: {exc}")
    return Normalized(out, target, "known", unit_as_written)


# Convenience wrappers used throughout the engine and the UI.
def o2_to_fraction(value: float, unit: str = "%") -> float:
    return convert(value, unit, "dimensionless")


def to_kpa(value: float, unit: str) -> float:
    return convert(value, unit, "kPa")


def to_cms(value: float, unit: str) -> float:
    return convert(value, unit, "cm/s")


def to_cm(value: float, unit: str) -> float:
    return convert(value, unit, "cm")


def psi_to_kpa(psi: float) -> float:
    return to_kpa(psi, "psi")


def kpa_to_psi(kpa: float) -> float:
    return convert(kpa, "kPa", "psi")


def ppo2_kpa(x_o2: float, p_kpa: float) -> float:
    """Oxygen partial pressure, ppO₂ = X_O₂ · P (spec Appendix C)."""
    return x_o2 * p_kpa
