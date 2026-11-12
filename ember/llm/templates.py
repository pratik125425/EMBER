"""No-LLM fallback narration (spec §11.4). Deterministic, every sentence carries an id.

Used by the Ask page until the LLM narrator (T15) exists, and as the offline fallback after.
"""

from __future__ import annotations

from ember.schemas import Evidence, Range

GRAVITY_LABEL = {
    "microgravity": "microgravity",
    "1g": "1-g",
    "simulated_partial": "simulated partial gravity (non-PSI)",
    "unknown": "an unstated gravity regime",
}


def format_range(r: Range | None, fmt: str = "{:g}", unit: str = "") -> str:
    """'0.136–0.222', '0.17', 'unknown', 'n/a'. Ranges stay ranges (spec §0.7)."""
    if r is None or r.status == "not_applicable":
        return "n/a"
    if r.status != "known":
        return "unknown"
    lo, hi = fmt.format(r.min), fmt.format(r.max)
    body = lo if lo == hi else f"{lo}–{hi}"
    return f"{body}{(' ' + unit) if unit else ''}"


def template_sentence(e: Evidence, result: dict) -> str:
    """One templated, cited sentence for a ranked record.

    ``result`` is the dict returned by ``ember.engine.score.score``.
    """
    phen = ", ".join(p.value.replace("_", " ") for p in e.phenomena)
    fuel = e.fuel_name or e.fuel_class.value.replace("_", " ")
    o2 = format_range(e.x_o2, "{:.3g}")
    if e.o2_context.value == "burner_oxidizer_flow":
        o2 += " (burner/oxidizer-side flow, not ambient atmosphere)"
    p = format_range(e.p_kpa, "{:.3g}", "kPa")
    u = format_range(e.u_cms, "{:.3g}", "cm/s")
    g = GRAVITY_LABEL.get(e.gravity.value, e.gravity.value)
    flags = ", ".join(f.split(":", 1)[0] for f in result.get("flags", [])) or "none"
    d_note = " (lower bound: some conditions unknown)" if result.get("D_lower_bound") else ""
    return (
        f"{e.investigation} ({e.evidence_id}) tested {phen} with {fuel} at X_O₂ {o2}, "
        f"P {p}, flow {u} in {g}. Distance to your scenario D = {result['D']:.2f}{d_note} "
        f"(implied factor ≤ {result['expD']:.2f}×). Flags: {flags}. [{e.evidence_id}]"
    )


def partial_g_disclaimer() -> str:
    return (
        "Partial-gravity disclaimer: PSI holds no partial-gravity combustion data. All evidence "
        "shown was obtained in microgravity or 1-g. Lunar/Mars behavior may lie outside both "
        "brackets (FM2 abstract, NTRS 20240015307; Ruff 2021, NTRS 20210021318). [CHALLENGE-2026]"
    )
