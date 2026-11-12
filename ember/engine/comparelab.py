"""CompareLab: rule-gated comparability verdicts (spec §10.7, ticket T10).

Rules run in order. A failing *gate* rule (1, 2, 4) ends evaluation with ``not_comparable``;
a failing *caveat* rule (3, 5, 6) adds confounders and the verdict becomes
``comparable_with_caveats``. Everything is deterministic; nothing is inferred from text.

Two entry points:
- ``compare_measurements(ma, ea, mb, eb)``: two Measurement records with their Evidence.
- ``compare_evidence(ea, eb)``: two Evidence envelopes (rule 1 then means "share a phenomenon").

Output dict: verdict, rules (trace), shared_conditions, differing_conditions, unknown_conditions,
confounders, normalizations_applied.
"""

from __future__ import annotations

import re

import pint

from ember.schemas import Evidence, Measurement, Range
from ember.units import convert

COMPARABLE = "comparable"
CAVEATS = "comparable_with_caveats"
NOT_COMPARABLE = "not_comparable"

GATE = "gate"
CAVEAT = "caveat"

RULES = [
    (1, "Same canonical quantity", GATE),
    (2, "Units convertible (pint)", GATE),
    (3, "Same value kind (measured / set-point / range / computed)", CAVEAT),
    (4, "Same context (ambient vs burner O₂; cabin vs duct)", GATE),
    (5, "Hardware / scale confounders", CAVEAT),
    (6, "Same regime (gravity, flow direction, diluent)", CAVEAT),
]

# Hardware families whose comparison is a known scale confounder (spec §10.7 rule 5).
SCALE_NOTE = {
    frozenset(
        {"MSG+SPICE-duct", "Saffire Flow Unit/Cygnus"}
    ): "Small MSG/SPICE duct samples vs large Saffire Flow Unit samples on Cygnus: sample scale and enclosure differ.",
}
ENCLOSURE_SOURCE = "NTRS-20240002981"


def _norm_unit(u: str) -> str:
    u = u.strip()
    u = re.sub(r"(?<=[a-zA-Z])3\b", "**3", u)
    u = re.sub(r"(?<=[a-zA-Z])2\b", "**2", u)
    return {"dimensionless": "dimensionless", "1/cm**3": "1/cm**3"}.get(u, u)


def units_convertible(u1: str, u2: str) -> bool:
    a, b = _norm_unit(u1), _norm_unit(u2)
    if a == b:
        return True
    try:
        convert(1.0, a, b)
        return True
    except (
        pint.errors.UndefinedUnitError,
        pint.errors.DimensionalityError,
        ValueError,
        AttributeError,
    ):
        return False


def _duct_half_height(note: str | None) -> float | None:
    if not note:
        return None
    m = re.search(r"half-height\s*(\d+(?:\.\d+)?)\s*cm", note, flags=re.I)
    return float(m.group(1)) if m else None


def _overlap(a: Range, b: Range) -> bool:
    return a.min <= b.max and b.min <= a.max


def _fmt(r: Range, fmt="{:.3g}") -> str:
    if r.status != "known":
        return r.status.replace("_", " ")
    return fmt.format(r.min) if r.min == r.max else f"{fmt.format(r.min)}–{fmt.format(r.max)}"


def _conditions(ea: Evidence, eb: Evidence) -> tuple[list[dict], list[dict], list[dict], list[str]]:
    shared, differing, unknown, norms = [], [], [], []
    for key, label in (("x_o2", "X_O₂"), ("p_kpa", "P (kPa)"), ("u_cms", "flow (cm/s)")):
        ra, rb = getattr(ea, key), getattr(eb, key)
        row = {"condition": label, ea.evidence_id: _fmt(ra), eb.evidence_id: _fmt(rb)}
        if ra.status == "known" and rb.status == "known":
            (shared if _overlap(ra, rb) else differing).append(row)
        else:
            unknown.append(row)
    for key, label in (
        ("gravity", "gravity"),
        ("flow_direction", "flow direction"),
        ("diluent", "diluent"),
        ("fuel_class", "fuel class"),
        ("hardware_family", "hardware"),
        ("o2_context", "O₂ context"),
    ):
        va, vb = getattr(ea, key), getattr(eb, key)
        va = getattr(va, "value", va)
        vb = getattr(vb, "value", vb)
        row = {"condition": label, ea.evidence_id: str(va), eb.evidence_id: str(vb)}
        if va in (None, "unknown") or vb in (None, "unknown"):
            unknown.append(row)
        else:
            (shared if va == vb else differing).append(row)
    if all(getattr(e, k).status == "known" for e in (ea, eb) for k in ("x_o2", "p_kpa")):
        pa = (ea.x_o2.min * ea.p_kpa.min, ea.x_o2.max * ea.p_kpa.max)
        pb = (eb.x_o2.min * eb.p_kpa.min, eb.x_o2.max * eb.p_kpa.max)
        norms.append(
            f"ppO₂ = X_O₂·P computed: {ea.evidence_id} {pa[0]:.1f}–{pa[1]:.1f} kPa; "
            f"{eb.evidence_id} {pb[0]:.1f}–{pb[1]:.1f} kPa"
        )
        row = {
            "condition": "ppO₂ (kPa, derived)",
            ea.evidence_id: f"{pa[0]:.1f}–{pa[1]:.1f}",
            eb.evidence_id: f"{pb[0]:.1f}–{pb[1]:.1f}",
        }
        (shared if pa[0] <= pb[1] and pb[0] <= pa[1] else differing).append(row)
    return shared, differing, unknown, norms


def _hardware_confounders(ea: Evidence, eb: Evidence) -> list[str]:
    out = []
    if ea.hardware_family != eb.hardware_family:
        note = SCALE_NOTE.get(frozenset({ea.hardware_family, eb.hardware_family}))
        out.append(
            f"Different hardware: {ea.hardware_family} vs {eb.hardware_family}."
            + (f" {note}" if note else "")
        )
    ha, hb = _duct_half_height(ea.enclosure_note), _duct_half_height(eb.enclosure_note)
    if ha is not None and hb is not None and ha != hb:
        out.append(
            f"Enclosure size changed: duct half-height {ha:g} cm vs {hb:g} cm. NASA found enclosure size "
            f"has more impact on flame spread than anticipated [{ENCLOSURE_SOURCE}]."
        )
    elif (
        (ea.enclosure_note or eb.enclosure_note)
        and ea.enclosure_note != eb.enclosure_note
        and (ha is None or hb is None)
    ):
        out.append(
            f"Enclosure differs or is unstated: '{ea.enclosure_note or 'not stated'}' vs '{eb.enclosure_note or 'not stated'}'."
        )
    if ea.fuel_class != eb.fuel_class:
        out.append(
            f"Different fuel class: {ea.fuel_class.value.replace('_', ' ')} vs {eb.fuel_class.value.replace('_', ' ')}."
        )
    if (
        ea.size_cm
        and eb.size_cm
        and ea.size_cm.status == "known"
        and eb.size_cm.status == "known"
        and not _overlap(ea.size_cm, eb.size_cm)
    ):
        out.append(f"Sample size differs: {_fmt(ea.size_cm)} cm vs {_fmt(eb.size_cm)} cm.")
    if ea.psi_id is None or eb.psi_id is None:
        out.append(
            "At least one record is a non-PSI NASA source (conditions from a paper, not a PSI table)."
        )
    return out


def _regime_confounders(ea: Evidence, eb: Evidence) -> list[str]:
    out = []
    if ea.gravity != eb.gravity:
        out.append(
            f"Different gravity regime: {ea.gravity.value} vs {eb.gravity.value}. µg and 1-g results are brackets, not interpolable."
        )
    fa, fb = ea.flow_direction or "unknown", eb.flow_direction or "unknown"
    if fa != "unknown" and fb != "unknown" and fa != fb:
        out.append(
            f"Different flow direction: {fa} vs {fb} (opposed and concurrent spread follow different correlations)."
        )
    if ea.diluent and eb.diluent and ea.diluent != eb.diluent:
        out.append(f"Different diluent: {ea.diluent} vs {eb.diluent}.")
    return out


def _finish(
    verdict_rules: list[dict],
    ea: Evidence,
    eb: Evidence,
    confounders: list[str],
    extra_norms: list[str],
) -> dict:
    shared, differing, unknown, norms = _conditions(ea, eb)
    gate_failed = any(r["kind"] == GATE and not r["passed"] for r in verdict_rules)
    if gate_failed:
        verdict = NOT_COMPARABLE
    elif confounders or any(r["kind"] == CAVEAT and not r["passed"] for r in verdict_rules):
        verdict = CAVEATS
    else:
        verdict = COMPARABLE
    return {
        "verdict": verdict,
        "a": ea.evidence_id,
        "b": eb.evidence_id,
        "rules": verdict_rules,
        "shared_conditions": shared,
        "differing_conditions": differing,
        "unknown_conditions": unknown,
        "confounders": confounders,
        "normalizations_applied": extra_norms + norms,
    }


def _rule(n: int, passed: bool, detail: str) -> dict:
    num, name, kind = RULES[n - 1]
    return {"rule": num, "name": name, "kind": kind, "passed": passed, "detail": detail}


def compare_measurements(ma: Measurement, ea: Evidence, mb: Measurement, eb: Evidence) -> dict:
    rules, confounders, norms = [], [], []
    # 1 quantity
    ok = ma.quantity == mb.quantity
    rules.append(_rule(1, ok, f"{ma.quantity} vs {mb.quantity}"))
    if not ok:
        return _finish(rules, ea, eb, confounders, norms)
    # 2 units
    ok = units_convertible(ma.unit, mb.unit)
    rules.append(_rule(2, ok, f"{ma.unit} vs {mb.unit}"))
    if not ok:
        return _finish(rules, ea, eb, confounders, norms)
    if _norm_unit(ma.unit) != _norm_unit(mb.unit):
        vb = mb.value if mb.value is not None else mb.max
        norms.append(
            f"{mb.measurement_id}: {vb:g} {mb.unit} → {convert(vb, _norm_unit(mb.unit), _norm_unit(ma.unit)):.4g} {ma.unit}"
        )
    # 3 value kind
    ok = ma.value_kind == mb.value_kind
    rules.append(_rule(3, ok, f"{ma.value_kind} vs {mb.value_kind}"))
    if not ok:
        confounders.append(
            f"Different value kinds: {ma.value_kind} vs {mb.value_kind} (a set-point or range is not a measurement)."
        )
    # 4 context
    ctx_a = ma.context if ma.context != "unknown" else ea.o2_context.value
    ctx_b = mb.context if mb.context != "unknown" else eb.o2_context.value
    burner = {"burner", "burner_oxidizer_flow"}
    ok = not ((ctx_a in burner) != (ctx_b in burner)) and not ({ctx_a, ctx_b} == {"cabin", "duct"})
    rules.append(_rule(4, ok, f"{ctx_a} vs {ctx_b}"))
    if not ok:
        confounders.append(
            f"Context mismatch: {ctx_a} vs {ctx_b}. Burner/oxidizer-side oxygen is not a cabin atmosphere."
        )
        return _finish(rules, ea, eb, confounders, norms)
    # 5 hardware / scale
    hw = _hardware_confounders(ea, eb)
    rules.append(
        _rule(5, not hw, "; ".join(hw) or "same hardware family, enclosure and fuel class")
    )
    confounders += hw
    # 6 regime
    rg = _regime_confounders(ea, eb)
    rules.append(_rule(6, not rg, "; ".join(rg) or "same gravity, flow direction and diluent"))
    confounders += rg
    return _finish(rules, ea, eb, confounders, norms)


def compare_evidence(ea: Evidence, eb: Evidence) -> dict:
    """Compare two condition envelopes. Rule 1 = shared phenomenon; rule 2–3 are not applicable."""
    rules, confounders = [], []
    shared_ph = sorted({p.value for p in ea.phenomena} & {p.value for p in eb.phenomena})
    rules.append(_rule(1, bool(shared_ph), "shared phenomena: " + (", ".join(shared_ph) or "none")))
    if not shared_ph:
        return _finish(rules, ea, eb, confounders, [])
    rules.append(_rule(2, True, "n/a for envelopes (canonical units enforced by schema)"))
    gran_same = ea.granularity == eb.granularity
    rules.append(_rule(3, gran_same, f"{ea.granularity.value} vs {eb.granularity.value}"))
    if not gran_same:
        confounders.append(
            f"Different data granularity: {ea.granularity.value.replace('_', ' ')} vs {eb.granularity.value.replace('_', ' ')}."
        )
    ca, cb = ea.o2_context.value, eb.o2_context.value
    ok = not ((ca == "burner_oxidizer_flow") != (cb == "burner_oxidizer_flow"))
    rules.append(_rule(4, ok, f"{ca} vs {cb}"))
    if not ok:
        confounders.append(
            f"O₂ context mismatch: {ca} vs {cb}. CFI-G burner/oxidizer-side oxygen is not a cabin atmosphere."
        )
        return _finish(rules, ea, eb, confounders, [])
    hw = _hardware_confounders(ea, eb)
    rules.append(
        _rule(5, not hw, "; ".join(hw) or "same hardware family, enclosure and fuel class")
    )
    confounders += hw
    rg = _regime_confounders(ea, eb)
    rules.append(_rule(6, not rg, "; ".join(rg) or "same gravity, flow direction and diluent"))
    confounders += rg
    return _finish(rules, ea, eb, confounders, [])


# ----------------------------------------------------------------------------------- validation
def false_comparable_rate(results: list[tuple[str, str]]) -> dict:
    """results: (predicted_verdict, labeled_verdict). Primary metric: predicted 'comparable' when the
    label is 'not_comparable' (target 0). Also reports exact agreement and 'too permissive' counts."""
    n = len(results)
    false_comp = sum(1 for p, lab in results if lab == NOT_COMPARABLE and p != NOT_COMPARABLE)
    too_permissive = sum(
        1
        for p, lab in results
        if (lab == CAVEATS and p == COMPARABLE) or (lab == NOT_COMPARABLE and p != NOT_COMPARABLE)
    )
    exact = sum(1 for p, lab in results if p == lab)
    return {
        "n": n,
        "false_comparable": false_comp,
        "false_comparable_rate": (false_comp / n if n else 0.0),
        "too_permissive": too_permissive,
        "exact_agreement": (exact / n if n else 0.0),
    }
