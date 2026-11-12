"""Question → proposed Scenario (spec §11.2). The proposal is ALWAYS shown to the user to confirm.

Two paths with the same rules:
* ``llm``   the spec's system prompt through ``ember.llm.client.complete`` (cached).
* ``rules`` a deterministic regex parser, used when the LLM is unavailable and as a cross-check.

Grounding check (applies to the LLM path): every number the LLM returns must come from a number
in the question (after unit conversion) or from the Exploration-Atmosphere default rule. Ungrounded
numbers are dropped and reported, so the parser cannot invent conditions. Airflow is never guessed.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from pydantic import BaseModel, Field, ValidationError

from ember import config
from ember.schemas import FuelClass, Phenomenon
from ember.units import Q_

EXPLORATION_NOTE = "assumed NASA Exploration Atmosphere (TP-2010-216134)"
EXPLORATION_X_O2, EXPLORATION_P_KPA = 0.34, 56.5

SYSTEM_TEMPLATE = """Convert the user's fire-safety question into JSON matching this schema: {schema}
Rules:
- Convert units: % O2 -> fraction; psi/psia -> kPa (×6.89476); atm -> kPa (×101.325); bar -> kPa (×100).
- "Moon/lunar" -> gravity_g0 = 0.166; "Mars" -> 0.38; "ISS/orbit/spacecraft cabin" -> 0.0; "Earth/ground" -> 1.0.
- "Exploration atmosphere" or "lunar habitat atmosphere" with no numbers -> x_o2 = 0.34, p_kpa = 56.5, and set notes = "assumed NASA Exploration Atmosphere (TP-2010-216134)".
- Map fabric/paper/thin films -> thin_solid; PMMA blocks/thick plastics -> thick_solid; fuel droplets -> liquid_droplet.
- If something is not stated, use null. Never guess airflow.
Return ONLY JSON."""


class ParsedScenario(BaseModel):
    """Like ``Scenario`` but every field may be null (the user fills or confirms the rest)."""

    x_o2: float | None = Field(None, ge=0.0, le=1.0)
    p_kpa: float | None = Field(None, gt=0)
    u_cms: float | None = Field(None, ge=0)
    gravity_g0: float | None = Field(None, ge=0)
    phenomenon: Phenomenon | None = None
    fuel_class: FuelClass | None = None
    fuel_name: str | None = None
    flow_direction: str | None = None
    notes: str | None = None


def system_prompt() -> str:
    schema = json.dumps(ParsedScenario.model_json_schema(), separators=(",", ":"))
    return SYSTEM_TEMPLATE.format(schema=schema)


@dataclass
class ParseResult:
    fields: dict
    mode: str  # "llm" | "rules"
    notes: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)  # ungrounded LLM values removed
    error: str | None = None

    @property
    def unstated(self) -> list[str]:
        keys = ("x_o2", "p_kpa", "u_cms", "gravity_g0", "phenomenon", "fuel_class")
        return [k for k in keys if self.fields.get(k) is None]


# ------------------------------------------------------------------------------- number mining
_NUM = r"(\d+(?:\.\d+)?)"
_PCT = re.compile(_NUM + r"\s*(?:%|percent\b|mol\s*%)", re.I)
_FRAC = re.compile(
    r"(?:x_?o2|x_?o₂|oxygen\s+(?:mole\s+)?fraction|o2\s+fraction)\s*(?:=|of|:)?\s*(0?\.\d+)", re.I
)
_PRESSURE = re.compile(_NUM + r"\s*(psia|psi|kpa|atm|bar)\b", re.I)
_FLOW = re.compile(_NUM + r"\s*(cm/s|mm/s|m/s)", re.I)
PRESSURE_UNIT = {"psia": "psi", "psi": "psi", "kpa": "kPa", "atm": "atm", "bar": "bar"}


def question_numbers(q: str) -> dict[str, list[float]]:
    """Candidate canonical values for each quantity, mined from the question text."""
    o2 = [float(v) / 100 for v in _PCT.findall(q)] + [float(v) for v in _FRAC.findall(q)]
    p = [
        Q_(float(v), PRESSURE_UNIT[u.lower()]).to("kPa").magnitude for v, u in _PRESSURE.findall(q)
    ]
    u = [Q_(float(v), unit.lower()).to("cm/s").magnitude for v, unit in _FLOW.findall(q)]
    return {"x_o2": o2, "p_kpa": p, "u_cms": u}


def _exploration_phrase(q: str) -> bool:
    return bool(
        re.search(r"exploration atmosphere|lunar habitat atmosphere|habitat atmosphere", q, re.I)
    )


# ------------------------------------------------------------------------------- keyword maps
GRAVITY_WORDS: list[tuple[str, float]] = [
    (r"\b(moon|lunar)\b", config.G_MOON),
    (r"\b(mars|martian)\b", config.G_MARS),
    (r"\b(iss|orbit|orbital|spacecraft|space station|microgravity|cabin)\b", config.G_MICRO),
    (r"\b(earth|ground|1[\s-]?g|normal gravity)\b", config.G_EARTH),
]
FUEL_CLASS_WORDS: list[tuple[str, FuelClass]] = [
    (
        r"\b(pmma|acrylic|plexiglas)\s+(block|slab|rod|cylinder|sphere)s?\b|\bthick\b",
        FuelClass.thick_solid,
    ),
    (
        r"\b(fabric|cloth|textile|paper|thin film|thin sheet|cotton|nomex|sibal|kapton film)\b",
        FuelClass.thin_solid,
    ),
    (r"\bdroplets?\b", FuelClass.droplet),
    (r"\b(gas jet|gaseous jet|jet flame|burner flame)\b", FuelClass.gas_jet),
]
FUEL_NAMES = [
    "PMMA",
    "SIBAL",
    "Nomex",
    "Kapton",
    "Teflon",
    "cotton",
    "Delrin",
    "Ultem",
    "heptane",
    "n-heptane",
    "decane",
    "n-decane",
    "ethanol",
    "methanol",
    "ethylene",
]
PHENOMENON_WORDS: list[tuple[str, Phenomenon]] = [
    (r"cool flame", Phenomenon.cool_flame),
    (r"limiting oxygen|\bloc\b|lowest oxygen|minimum oxygen", Phenomenon.loc),
    (r"smoke point|soot", Phenomenon.soot_smoke_point),
    (r"smoke detect|detector", Phenomenon.detector_response),
    (r"smoke particle|particulate|particle size|smoke\b", Phenomenon.smoke_particles),
    (r"suppress|suppressant|extinguish|water[- ]mist", Phenomenon.suppression),
    (r"extinction|extinguishment|blow[- ]?off|quench", Phenomenon.extinction),
    (r"ignit", Phenomenon.ignition),
    (r"burning rate|burn rate", Phenomenon.burning_rate),
    (r"flame structure|flame shape", Phenomenon.flame_structure),
    (r"concurrent|wind[- ]aided|upward spread|co-current", Phenomenon.spread_concurrent),
    (r"opposed", Phenomenon.spread_opposed),
    (r"spread|flammab|burn", Phenomenon.spread_opposed),
]


def _first(patterns, q):
    for pat, val in patterns:
        if re.search(pat, q, re.I):
            return val
    return None


def rule_parse(q: str) -> ParseResult:
    nums = question_numbers(q)
    notes: list[str] = []
    f: dict = dict.fromkeys(ParsedScenario.model_fields)
    f["x_o2"] = nums["x_o2"][0] if nums["x_o2"] else None
    f["p_kpa"] = round(nums["p_kpa"][0], 2) if nums["p_kpa"] else None
    f["u_cms"] = round(nums["u_cms"][0], 3) if nums["u_cms"] else None  # only when stated
    if len(nums["x_o2"]) > 1 or len(nums["p_kpa"]) > 1:
        notes.append("Several values found in the question; the first of each was used.")
    if _exploration_phrase(q) and (f["x_o2"] is None or f["p_kpa"] is None):
        f["x_o2"] = EXPLORATION_X_O2 if f["x_o2"] is None else f["x_o2"]
        f["p_kpa"] = EXPLORATION_P_KPA if f["p_kpa"] is None else f["p_kpa"]
        f["notes"] = EXPLORATION_NOTE
    f["gravity_g0"] = _first(GRAVITY_WORDS, q)
    fc = _first(FUEL_CLASS_WORDS, q)
    f["fuel_class"] = fc.value if fc else None
    name = next((n for n in FUEL_NAMES if re.search(rf"\b{re.escape(n)}\b", q, re.I)), None)
    f["fuel_name"] = name
    ph = _first(PHENOMENON_WORDS, q)
    f["phenomenon"] = ph.value if ph else None
    if ph == Phenomenon.spread_opposed and not re.search(r"opposed", q, re.I):
        notes.append(
            "Flow direction not stated: opposed-flow spread chosen; change it in the sidebar if needed."
        )
    if name == "PMMA" and fc is None:
        notes.append("PMMA thickness not stated, so fuel class is left open.")
    return ParseResult(fields=f, mode="rules", notes=notes)


# ------------------------------------------------------------------------------- LLM path
def _extract_json(text: str) -> dict:
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        raise ValueError("no JSON object in response")
    return json.loads(text[a : b + 1])


def _grounded(value: float, candidates: list[float], rel: float = 0.01) -> bool:
    return any(abs(value - c) <= max(rel * abs(c), 1e-6) for c in candidates)


def ground(fields: dict, q: str) -> tuple[dict, list[str]]:
    """Drop numeric values that cannot be traced to the question or the Exploration-Atmosphere rule."""
    nums = question_numbers(q)
    expl = _exploration_phrase(q)
    out, dropped = dict(fields), []
    allowed_defaults = {
        "x_o2": [EXPLORATION_X_O2] if expl else [],
        "p_kpa": [EXPLORATION_P_KPA] if expl else [],
    }
    for k in ("x_o2", "p_kpa", "u_cms"):
        v = out.get(k)
        if v is None:
            continue
        if not _grounded(float(v), nums[k] + allowed_defaults.get(k, [])):
            dropped.append(f"{k}={v} (not stated in the question)")
            out[k] = None
    g = out.get("gravity_g0")
    if g is not None and _first(GRAVITY_WORDS, q) is None:
        dropped.append(f"gravity_g0={g} (no location or gravity named in the question)")
        out["gravity_g0"] = None
    return out, dropped


def llm_parse(q: str, complete=None) -> ParseResult:
    from ember.llm.client import complete as default_complete

    text = (complete or default_complete)(system_prompt(), q)
    try:
        parsed = ParsedScenario.model_validate(_extract_json(text))
    except (ValueError, ValidationError) as exc:
        raise ValueError(f"LLM output failed schema validation: {exc}") from exc
    fields = parsed.model_dump(mode="json")
    fields, dropped = ground(fields, q)
    return ParseResult(fields=fields, mode="llm", dropped=dropped)


def parse_question(q: str, *, use_llm: bool = True, complete=None) -> ParseResult:
    """LLM first (cached), rule parser on any failure. The result is a proposal for the user."""
    if use_llm:
        from ember.llm.client import LLMUnavailable

        try:
            return llm_parse(q, complete)
        except (LLMUnavailable, ValueError) as exc:
            r = rule_parse(q)
            r.error = str(exc)
            return r
    return rule_parse(q)
