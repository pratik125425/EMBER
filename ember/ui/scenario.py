"""Sidebar scenario chip: sliders, presets, unit toggle (spec §13). Returns a Scenario."""

from __future__ import annotations

import streamlit as st

from ember import config
from ember.schemas import FuelClass, Phenomenon, Scenario
from ember.ui.badges import sidebar_legend
from ember.units import kpa_to_psi, psi_to_kpa

GRAVITY_OPTIONS: dict[str, float] = {
    "Microgravity (ISS, 0 g)": config.G_MICRO,
    "Moon (0.166 g)": config.G_MOON,
    "Mars (0.38 g)": config.G_MARS,
    "Earth (1 g)": config.G_EARTH,
}
PHENOMENON_LABELS: dict[str, str] = {
    "spread_opposed": "Flame spread (opposed flow)",
    "spread_concurrent": "Flame spread (concurrent flow)",
    "ignition": "Ignition",
    "extinction": "Extinction",
    "limiting_oxygen": "Limiting oxygen concentration",
    "suppression": "Suppression",
    "burning_rate": "Burning rate",
    "cool_flame": "Cool flames",
    "flame_structure": "Flame structure",
    "soot_smoke_point": "Soot / smoke point",
    "smoke_particles": "Smoke particles",
    "detector_response": "Detector response",
}
DEFAULTS = {
    "x_o2": 0.34,
    "p_kpa": 56.5,
    "gravity_g0": config.G_MOON,
    "u_specified": False,
    "u_cms": 10.0,
}


def _apply_preset() -> None:
    name = st.session_state.get("preset")
    p = config.PRESETS.get(name)
    if not p:
        return
    if p["x_o2"] is not None:
        st.session_state["x_o2_pct"] = round(p["x_o2"] * 100, 2)
    if p["p_kpa"] is not None:
        st.session_state["p_kpa"] = float(p["p_kpa"])
        st.session_state["p_psi"] = round(kpa_to_psi(p["p_kpa"]), 2)
    for label, g in GRAVITY_OPTIONS.items():
        if g == p["gravity_g0"]:
            st.session_state["gravity_label"] = label


def _init_state() -> None:
    st.session_state.setdefault("x_o2_pct", DEFAULTS["x_o2"] * 100)
    st.session_state.setdefault("p_kpa", DEFAULTS["p_kpa"])
    st.session_state.setdefault("p_psi", round(kpa_to_psi(DEFAULTS["p_kpa"]), 2))
    st.session_state.setdefault("gravity_label", "Moon (0.166 g)")
    st.session_state.setdefault("u_specified", DEFAULTS["u_specified"])
    st.session_state.setdefault("u_cms", DEFAULTS["u_cms"])


def scenario_sidebar() -> Scenario:
    _init_state()
    sb = st.sidebar
    sb.header("Scenario")
    sb.selectbox(
        "Preset",
        ["Custom", *config.PRESETS],
        key="preset",
        on_change=_apply_preset,
        help="Presets come from NASA/TP-2010-216134; [A] marks an assumption.",
    )
    preset = config.PRESETS.get(st.session_state.get("preset"))
    if preset:
        sb.caption(f"Source: {preset['source']}")

    x_pct = sb.slider(
        "Oxygen, % (mole fraction × 100)",
        10.0,
        60.0,
        step=0.5,
        key="x_o2_pct",
        help="Share of the air that is oxygen. Earth air is about 21%; NASA's Exploration "
        "Atmosphere is 34%.",
    )

    unit = sb.radio("Pressure unit", ["kPa", "psia"], horizontal=True, key="p_unit")
    if unit == "kPa":
        p_kpa = sb.slider(
            "Total pressure, kPa",
            20.0,
            210.0,
            step=0.5,
            key="p_kpa",
            help="Sea level is 101.3 kPa. NASA's Exploration Atmosphere is 56.5 kPa.",
        )
        st.session_state["p_psi"] = round(kpa_to_psi(p_kpa), 2)
    else:
        p_psi = sb.slider(
            "Total pressure, psia",
            3.0,
            30.0,
            step=0.1,
            key="p_psi",
            help="Sea level is 14.7 psia. NASA's Exploration Atmosphere is 8.2 psia.",
        )
        p_kpa = psi_to_kpa(p_psi)
        st.session_state["p_kpa"] = round(p_kpa, 2)
    sb.caption(
        f"= {p_kpa:.1f} kPa / {kpa_to_psi(p_kpa):.2f} psia · ppO₂ = {x_pct / 100 * p_kpa:.1f} kPa"
    )

    u_specified = sb.checkbox(
        "Airflow specified",
        key="u_specified",
        help="Air moving past the material, e.g. from fans. Without gravity this flow is what feeds a "
        "flame oxygen. Leave unchecked if unknown. EMBER never guesses airflow.",
    )
    u_cms = (
        sb.slider("Imposed flow, cm/s", 0.0, 50.0, step=0.5, key="u_cms") if u_specified else None
    )

    g_label = sb.selectbox(
        "Gravity",
        list(GRAVITY_OPTIONS),
        key="gravity_label",
        help="NASA's PSI archive has no fire tests at Moon or Mars gravity; those scenarios are "
        "bracketed by microgravity and Earth results and flagged.",
    )
    gravity = GRAVITY_OPTIONS[g_label]

    phen = sb.selectbox(
        "Phenomenon",
        list(PHENOMENON_LABELS),
        format_func=PHENOMENON_LABELS.get,
        key="phenomenon",
        help="What you want to know about the fire: how fast it spreads, whether it ignites, "
        "when it goes out, and so on.",
    )
    fuel_opts = ["any", *[f.value for f in FuelClass]]
    fuel_class = sb.selectbox(
        "Fuel class",
        fuel_opts,
        format_func=lambda v: v.replace("_", " "),
        key="fuel_class",
        help="The kind of material burning: thin sheets like fabric or paper, thick solids like "
        "plastic blocks, liquid droplets, gas jets and so on.",
    )
    fuel_name = sb.text_input(
        "Fuel / material (optional)", key="fuel_name", placeholder="e.g. PMMA, SIBAL, Nomex"
    )

    scenario = Scenario(
        name=st.session_state.get("preset") or "custom",
        x_o2=x_pct / 100.0,
        p_kpa=float(p_kpa),
        u_cms=u_cms,
        gravity_g0=gravity,
        phenomenon=Phenomenon(phen),
        fuel_class=None if fuel_class == "any" else FuelClass(fuel_class),
        fuel_name=fuel_name.strip() or None,
    )

    if gravity not in config.BRACKET_GRAVITIES:
        sb.warning(
            "Partial gravity: no PSI evidence exists at this gravity. Results are µg/1-g brackets, flagged."
        )
    if phen not in config.ELASTICITY:
        sb.info(
            "No published correlation for this phenomenon → uniform (unweighted) distance weights."
        )
    sidebar_legend()
    return scenario


def scenario_chip(s: Scenario) -> str:
    u = "not specified" if s.u_cms is None else f"{s.u_cms:g} cm/s"
    g = next((k for k, v in GRAVITY_OPTIONS.items() if v == s.gravity_g0), str(s.gravity_g0))
    fuel = (s.fuel_class.value.replace("_", " ") if s.fuel_class else "any fuel") + (
        f" · {s.fuel_name}" if s.fuel_name else ""
    )
    return (
        f"**X_O₂ {s.x_o2:.3f}** ({s.x_o2 * 100:.1f}%) · **P {s.p_kpa:.1f} kPa** ({kpa_to_psi(s.p_kpa):.2f} psia) · "
        f"**flow {u}** · **{g}** · {PHENOMENON_LABELS.get(s.phenomenon.value, s.phenomenon.value)} · {fuel}"
    )


PARSE_LABELS: dict[str, str] = {
    "x_o2": "Oxygen (mole fraction)",
    "p_kpa": "Total pressure (kPa)",
    "u_cms": "Imposed flow (cm/s)",
    "gravity_g0": "Gravity (g₀)",
    "phenomenon": "Phenomenon",
    "fuel_class": "Fuel class",
    "fuel_name": "Fuel / material",
}
SLIDER_LIMITS = {"x_o2_pct": (10.0, 60.0), "p_kpa": (20.0, 210.0), "u_cms": (0.0, 50.0)}


def apply_parsed(fields: dict) -> None:
    """Button callback: copy a parsed proposal into the sidebar widgets (runs before they render).

    Unstated fields keep their sidebar value, except airflow: unstated airflow is set to
    'not specified' because EMBER never guesses it. Values outside a slider's range are not
    clamped; they are skipped and reported.
    """
    ss = st.session_state
    skipped: list[str] = []

    def put(key: str, value: float, label: str) -> None:
        lo, hi = SLIDER_LIMITS[key]
        if lo <= value <= hi:
            ss[key] = value
        else:
            skipped.append(f"{label} {value:g} is outside the slider range {lo:g}–{hi:g}")

    ss["preset"] = "Custom"
    if fields.get("x_o2") is not None:
        put("x_o2_pct", round(fields["x_o2"] * 100, 2), "oxygen %")
    if fields.get("p_kpa") is not None:
        put("p_kpa", round(float(fields["p_kpa"]), 2), "pressure kPa")
        ss["p_psi"] = round(kpa_to_psi(ss["p_kpa"]), 2)
        ss["p_unit"] = "kPa"
    if fields.get("u_cms") is not None:
        ss["u_specified"] = True
        put("u_cms", float(fields["u_cms"]), "flow cm/s")
    else:
        ss["u_specified"] = False
    if fields.get("gravity_g0") is not None:
        for label, g in GRAVITY_OPTIONS.items():
            if g == fields["gravity_g0"]:
                ss["gravity_label"] = label
    if fields.get("phenomenon"):
        ss["phenomenon"] = fields["phenomenon"]
    if fields.get("fuel_class"):
        ss["fuel_class"] = fields["fuel_class"]
    if fields.get("fuel_name"):
        ss["fuel_name"] = fields["fuel_name"]
    if skipped:
        ss["parse_warning"] = "Not applied: " + "; ".join(skipped) + ". Set these in the sidebar."
