"""Cite-or-drop verifier (spec §11.3). A failing statement is DROPPED, never rewritten (except rule 5,
which the spec says to replace), and every drop is counted with its reason.

Unit of verification: one statement per line. The narrator is told to write one cited sentence
per line; the template narration writes one cited statement per record.

Rules:
1. ≥1 citation ``[id]``; every cited id exists in the payload.
2. Every number matches a number in a cited record or the user's scenario (after unit
   normalization; tolerance ±1 in the last stated digit).
3. "85" in a sentence mentioning CFI-G needs "burner" or "oxidizer".
4. Partial-g disclaimer when the scenario gravity ∉ {0, 1} or the text mentions Moon/lunar/Mars;
   "measured/tested/observed … lunar/moon/mars/partial" is rejected unless it cites LUCI/FM2 and
   says non-PSI.
5. Units outside the controlled list are replaced with "unit not stated".
6. "Beyond tested envelope" banner when any top-k record has D > 1.
7. Each kept sentence carries a claim-type badge.
8. "safe", "proves", "guarantees" are rejected.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ember import config
from ember.llm.templates import partial_g_disclaimer
from ember.units import Q_

CITATION = re.compile(r"\[([^\[\]]+)\]")
# A number not glued to a letter, underscore, digit, dot or hyphen (so O2, CO2, PSI-69, T001 are skipped).
NUMBER = re.compile(
    r"(?<![A-Za-z_\d.\-])(\d+(?:\.\d+)?)(?![\d])\s*([A-Za-z%µ°/²³·]+(?:/[A-Za-z²³]+)?)?"
)
FORBIDDEN = re.compile(r"\b(safe|safely|proves?|proven|guarantee[sd]?)\b", re.I)
MEASURED_PARTIAL_G = re.compile(r"(measured|tested|observed).{0,30}(lunar|moon|mars|partial)", re.I)
PARTIAL_G_WORDS = re.compile(r"\b(moon|lunar|mars|martian)\b", re.I)
PARTIAL_G_SOURCES = ("LUCI", "FM2", "NTRS-20240015307", "NTRS-20250010653")

CONTROLLED_UNITS = {
    "%",
    "kPa",
    "psi",
    "psia",
    "atm",
    "bar",
    "cm/s",
    "mm/s",
    "m/s",
    "g",
    "g0",
    "s",
    "ms",
    "min",
    "mm",
    "cm",
    "m",
    "nm",
    "µm",
    "um",
    "K",
    "°C",
    "kW/m²",
    "kW/m2",
    "mg/m³",
    "mg/m3",
    "V",
    "mm²/s",
    "mm2/s",
    "cc",
    "×",
    "x",
}
# Words that pint would read as units but are ordinary English after a number.
NOT_UNITS = {
    "at",
    "in",
    "to",
    "a",
    "and",
    "or",
    "of",
    "for",
    "with",
    "the",
    "by",
    "from",
    "mol",
    "is",
    "are",
    "was",
    "on",
    "as",
    "per",
    "h",
    "t",
    "d",
    "y",
}
CONVERT = {
    "%": (0.01, "fraction"),
    "psi": (6.89476, "kPa"),
    "psia": (6.89476, "kPa"),
    "atm": (101.325, "kPa"),
    "bar": (100.0, "kPa"),
    "mm/s": (0.1, "cm/s"),
    "m/s": (100.0, "cm/s"),
}

BANNER_ENVELOPE = (
    "Beyond tested envelope: at least one record shown implies a response factor above 2.7× "
    "(D > 1). Treat it as a distant bracket, not a match."
)


@dataclass
class Statement:
    text: str
    citations: list[str]
    badge: str


@dataclass
class Verified:
    kept: list[Statement] = field(default_factory=list)
    dropped: list[tuple[str, str]] = field(default_factory=list)  # (text, reason)
    banners: list[str] = field(default_factory=list)
    disclaimers: list[str] = field(default_factory=list)

    @property
    def n_dropped(self) -> int:
        return len(self.dropped)


# ------------------------------------------------------------------------------- helpers
def citations_of(text: str) -> list[str]:
    ids: list[str] = []
    for grp in CITATION.findall(text):
        ids += [x.strip() for x in re.split(r"[;,]", grp) if x.strip()]
    return ids


def _numbers_in_obj(obj) -> list[float]:
    out: list[float] = []
    if obj is None or isinstance(obj, bool):
        return out
    if isinstance(obj, int | float):
        return [float(obj)]
    if isinstance(obj, str):
        return [float(m) for m in re.findall(r"\d+(?:\.\d+)?", obj)]
    if isinstance(obj, dict):
        for v in obj.values():
            out += _numbers_in_obj(v)
        return out
    if isinstance(obj, list | tuple | set):
        for v in obj:
            out += _numbers_in_obj(v)
    return out


def _scenario_numbers(s: dict) -> list[float]:
    vals = _numbers_in_obj({k: s.get(k) for k in ("x_o2", "p_kpa", "u_cms", "gravity_g0")})
    if s.get("p_kpa"):
        vals.append(Q_(s["p_kpa"], "kPa").to("psi").magnitude)
    return vals


def _matches(value: str, unit: str | None, allowed: list[float]) -> bool:
    x = float(value)
    tol = 10.0 ** -(len(value.split(".")[1]) if "." in value else 0)
    tol *= 1.0000001  # float slack
    cands = [(x, tol)]
    if unit in CONVERT:
        factor, _ = CONVERT[unit]
        cands.append((x * factor, tol * factor))
    return any(abs(c - a) <= t for c, t in cands for a in allowed)


def _is_unit(tok: str) -> bool:
    """True if ``tok`` looks like a physical unit (pint parses it with a dimension)."""
    if tok in NOT_UNITS or tok.lower() in NOT_UNITS or not tok:
        return False
    try:
        q = Q_(1, tok)
    except Exception:  # noqa: BLE001 - pint raises many types
        return False
    return not q.dimensionless


def _fix_units(text: str) -> str:
    def repl(m: re.Match) -> str:
        num, unit = m.group(1), m.group(2)
        if unit is None or unit in CONTROLLED_UNITS or not _is_unit(unit):
            return m.group(0)
        return f"{num} (unit not stated)"

    return NUMBER.sub(repl, text)


# ------------------------------------------------------------------------------- main
def verify(
    text: str,
    payload: dict,
    scenario: dict | None = None,
    question: str | None = None,
) -> Verified:
    """Check narrator text against the payload it was given.

    ``payload`` = {"records": {id: record-dict}, "sources": {id: source-dict},
    "claims": {claim_id: claim-dict}, "top_D": [D, ...]}
    """
    scenario = scenario or {}
    records: dict = payload.get("records", {})
    sources: dict = payload.get("sources", {})
    claims: dict = payload.get("claims", {})
    known = set(records) | set(sources) | set(claims)
    scen_nums = _scenario_numbers(scenario)
    out = Verified()

    for raw in text.splitlines():
        line = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s+", "", raw).strip()
        if not line:
            continue
        cites = citations_of(line)
        # Rule 1
        if not cites:
            out.dropped.append((line, "no citation"))
            continue
        unknown = [c for c in cites if c not in known]
        if unknown:
            out.dropped.append((line, f"cites unknown id {', '.join(unknown)}"))
            continue
        body = CITATION.sub(" ", line)
        # Rule 8
        m = FORBIDDEN.search(body)
        if m:
            out.dropped.append((line, f"forbidden word '{m.group(0)}'"))
            continue
        # Rule 4 (second half)
        if MEASURED_PARTIAL_G.search(body):
            ok = any(any(tag in c for tag in PARTIAL_G_SOURCES) for c in cites) and re.search(
                r"non-PSI", body, re.I
            )
            if not ok:
                out.dropped.append((line, "claims a partial-gravity measurement"))
                continue
        # Rule 3
        if re.search(r"(?<![\d.])85(?![\d])", body) and re.search(r"CFI-?G", line, re.I):
            if not re.search(r"burner|oxidi[sz]er", body, re.I):
                out.dropped.append((line, "CFI-G 85% without 'burner'/'oxidizer'"))
                continue
        # Rule 5 (replace, then check numbers on the fixed text)
        line = _fix_units(line)
        body = CITATION.sub(" ", line)
        # Rule 2
        allowed = list(scen_nums)
        for c in cites:
            allowed += _numbers_in_obj(records.get(c) or sources.get(c) or claims.get(c))
            allowed += _numbers_in_obj(c)  # an id like NTRS-20210021318 may be restated
        bad = [
            m.group(1)
            for m in NUMBER.finditer(body)
            if not _matches(m.group(1), (m.group(2) or "").strip() or None, allowed)
        ]
        if bad:
            out.dropped.append((line, f"number(s) not in cited records: {', '.join(bad)}"))
            continue
        # Rule 7
        types = sorted({claims[c]["claim_type"] for c in cites if c in claims})
        badge = " / ".join(t.replace("_", " ") for t in types) if types else "registry record"
        out.kept.append(Statement(text=line, citations=cites, badge=badge))

    # Rule 6
    if any(d > config.D_ENVELOPE_THRESHOLD for d in payload.get("top_D", [])):
        out.banners.append(BANNER_ENVELOPE)
    # Rule 4 (first half)
    g = scenario.get("gravity_g0")
    mentions = PARTIAL_G_WORDS.search(text) or (question and PARTIAL_G_WORDS.search(question))
    if (g is not None and g not in config.BRACKET_GRAVITIES) or mentions:
        out.disclaimers.append(partial_g_disclaimer())
    return out
