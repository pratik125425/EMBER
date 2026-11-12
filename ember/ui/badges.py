"""Badge vocabulary shared by all pages (spec §13)."""

from __future__ import annotations

from ember import config

# flag code -> (short badge, legend text)
BADGES: dict[str, tuple[str, str]] = {
    "STABLE": ("Stable", "top-5 in ≥80% of Monte Carlo perturbations (T08)"),
    "UNWEIGHTED": ("Unweighted", "no published correlation for this phenomenon; uniform weights"),
    "INCOMPLETE_CONDITIONS": ("Lower bound", "some conditions unknown; D is a lower bound"),
    "NO_CONDITIONS": (
        "No conditions",
        "none of the weighted conditions known; ranked below records with data",
    ),
    "GRAVITY_EXTRAPOLATION": ("Partial-g", "scenario is partial-g; evidence is µg/1-g only"),
    "BURNER_SIDE_O2": ("Burner-side O₂", "oxygen value is burner/oxidizer flow, not ambient"),
    "NON_PSI_SOURCE": ("Non-PSI", "NASA source not in the PSI repository"),
    "TENSION": ("Tension", "result disagreed with prior model expectations"),
    "BEYOND_TESTED_ENVELOPE": ("Beyond envelope", "implied response factor exp(D) > e ≈ 2.7×"),
}


def badges_for(result: dict) -> list[str]:
    codes = [f.split(":", 1)[0] for f in result.get("flags", [])]
    if result.get("tier") == config.TIER_NO_CONDITIONS:
        codes = [c for c in codes if c != "INCOMPLETE_CONDITIONS"] + ["NO_CONDITIONS"]
    if result.get("stable"):
        codes.insert(0, "STABLE")
    seen, out = set(), []
    for c in codes:
        if c in BADGES and c not in seen:
            seen.add(c)
            out.append(BADGES[c][0])
    return out


def legend_markdown() -> str:
    return "\n".join(f"- **{short}** · {text}" for short, text in BADGES.values())


# Claim-type badges on summary sentences (spec §11.3 rule 7).
CLAIM_BADGES: dict[str, str] = {
    "registry record": "the sentence restates a registry record (conditions, D, flags)",
    "measured": "a value the source measured",
    "derived": "computed by the source from its measurements",
    "modeled": "a model or correlation result",
    "author interpretation": "the source authors' reading of their results",
    "system inference": "EMBER's own inference, not stated by a source",
}


def sidebar_legend() -> None:
    """Badge legend, always visible in the sidebar (spec §13: 'A badge legend is always visible')."""
    import streamlit as st

    sb = st.sidebar
    sb.divider()
    sb.markdown("**Badge legend**")
    sb.caption("  \n".join(f"**{short}** · {text}" for short, text in BADGES.values()))
    sb.caption("Summary sentences: " + " · ".join(f"`{k}` {v}" for k, v in CLAIM_BADGES.items()))
