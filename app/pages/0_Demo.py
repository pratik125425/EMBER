"""Guided demo (spec §17.1, T17): the live-demo script, one step at a time, every number computed now."""

import html
import math

import pandas as pd
import streamlit as st
from streamlit.errors import StreamlitAPIException

from ember import config
from ember.demo import (
    COMPARE_PAIR,
    DEMO_QUESTION,
    STEPS,
    air_fields,
    mirror_check,
    part_share,
    ranked,
    read_status,
    reshuffle,
    scenario_dict,
)
from ember.engine.comparelab import CAVEATS, COMPARABLE, compare_evidence
from ember.engine.gapscope import all_gravities, gap_report_markdown, target_coverage
from ember.llm.client import LLM_CACHE_DIR, offline
from ember.llm.guards import question_guards
from ember.llm.narrator import narrate
from ember.llm.parser import parse_question
from ember.llm.templates import format_range
from ember.registry import load_registry
from ember.schemas import FuelClass, Phenomenon, Scenario
from ember.ui.badges import badges_for
from ember.ui.charts import why_bars
from ember.ui.gaps_chart import gap_panels
from ember.ui.layout import page_header
from ember.ui.scenario import (
    PARSE_LABELS,
    PHENOMENON_LABELS,
    apply_parsed,
    scenario_chips_html,
    scenario_sidebar,
)
from ember.ui.theme import show_chart

st.set_page_config(page_title="EMBER · Demo", layout="wide")


@st.cache_resource
def _registry():
    return load_registry()


@st.cache_data(show_spinner=False)
def _parsed():
    p = parse_question(DEMO_QUESTION)
    return p.fields, p.mode, p.error, p.notes


@st.cache_data(show_spinner=False)
def _mirror():
    return mirror_check()


reg = _registry()
fields, parse_mode, parse_error, parse_notes = _parsed()
LUNAR, AIR = fields, air_fields(fields)
N = len(STEPS)


# The fast path for a short live demo: scenario → ranked evidence → source → gap. Every step stays
# reachable in the full walkthrough, which keeps the comparison, the cited summary and the method.
FULL, FAST = "Full walkthrough", "Fast path (about 90 s)"
FAST_STEPS = (1, 2, 4, 6)


def _go(i: int) -> None:
    """Move to step i and set the shared sidebar scenario to what that step shows (runs before widgets)."""
    st.session_state["demo_step"] = i
    if i >= 2:
        apply_parsed(AIR if i == 7 else LUNAR)


def _mode_changed() -> None:
    """Switching to the fast path lands on its first stop unless the current step is already one."""
    if (
        st.session_state.get("demo_mode") == FAST
        and st.session_state["demo_step"] not in FAST_STEPS
    ):
        _go(FAST_STEPS[0])


st.session_state.setdefault("demo_step", 0)
st.session_state.setdefault("demo_mode", FULL)
scenario_sidebar()  # keeps the scenario chip on other pages in step with the demo
step = st.session_state["demo_step"]
fast = st.session_state["demo_mode"] == FAST


def to_scenario(f: dict) -> Scenario:
    return Scenario(
        name="demo",
        x_o2=f["x_o2"],
        p_kpa=f["p_kpa"],
        u_cms=f.get("u_cms"),
        gravity_g0=f["gravity_g0"],
        phenomenon=Phenomenon(f["phenomenon"]),
        fuel_class=FuelClass(f["fuel_class"]) if f.get("fuel_class") else None,
        fuel_name=f.get("fuel_name"),
    )


def ranked_table(results: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "#": r["rank"],
                "Investigation": r["investigation"],
                "Evidence": r["evidence_id"],
                "R": round(r["R"], 3),
                "D": round(r["D"], 3),
                "exp(D)": round(r["expD"], 2),
                "P(top-5)": round(r["p_topk"], 2),
                "Badges": " · ".join(badges_for(r)),
            }
            for r in results
        ]
    )


def gap_spotlight(f: dict) -> str:
    """The lunar-gravity result brought into focus: GapScope coverage at the NASA target nearest the
    scenario, in orbit and at the scenario's gravity, and the experiment nobody has run."""
    tc = target_coverage(reg.evidence_dicts(), f["phenomenon"], f["fuel_class"], f["u_cms"])

    def near(r: dict) -> float:
        return abs(r["x_o2"] - f["x_o2"]) + abs(math.log(r["p_kpa"] / f["p_kpa"]))

    name = min(tc, key=near)["target"]
    here = next(r for r in tc if r["target"] == name and r["g"] == f["gravity_g0"])
    orbit = next((r for r in tc if r["target"] == name and r["g"] == 0.0), None)
    phen = PHENOMENON_LABELS.get(f["phenomenon"], f["phenomenon"]).lower()
    fuel = (f.get("fuel_class") or "unspecified fuel").replace("_", " ")
    o = (
        f'<div><p class="k">Coverage C in orbit (0 g)</p><div class="v">{orbit["C"]:.2f}</div>'
        f"<p>nearest record {html.escape(orbit['nearest'] or 'none')}</p></div>"
        if orbit
        else ""
    )
    flags = ", ".join(here["flags"]) or "none"
    return (
        f'<div class="ember-spot"><p class="k">GapScope at {html.escape(name)} '
        f"({here['x_o2'] * 100:.1f}% O₂, {here['p_kpa']:.1f} kPa)</p>"
        f'<div class="grid">{o}<div><p class="k">Coverage C at {f["gravity_g0"]:g} g</p>'
        f'<div class="v">{here["C"]:.2f}</div><p>{here["n_pool"]} records in the pool · flag '
        f"{html.escape(flags)}</p></div></div>"
        f'<p class="miss">Missing experiment: {html.escape(phen)} on a {html.escape(fuel)} at '
        f"{f['gravity_g0']:g} g, {f['x_o2'] * 100:.0f}% O₂, {f['p_kpa']:.1f} kPa.</p></div>"
    )


def rank_motion(before: list[dict], after: list[dict], n: int = 8) -> str:
    """Ranking before → after as rows that slide from their old rank to their new one."""
    b = {r["investigation"]: r for r in before}
    rows = []
    for i, r in enumerate(after[:n]):
        old = b.get(r["investigation"])
        shift = (old["rank"] - r["rank"]) if old else 0
        mv = (
            "new"
            if not old
            else ("held" if shift == 0 else (f"▲ up {shift}" if shift > 0 else f"▼ down {-shift}"))
        )
        cls = "up" if shift > 0 else ""

        def dtxt(x: dict) -> str:
            return f"{'≥ ' if x['D_lower_bound'] else ''}{x['D']:.2f}"

        d = f"D {dtxt(old)} → {dtxt(r)}" if old else f"D {dtxt(r)}"
        rows.append(
            f'<li style="--from:{shift * 2.6:.1f}rem;--delay:{300 + i * 40}ms">'
            f'<span class="n">{r["rank"]}</span><span class="inv">{html.escape(r["investigation"])}</span>'
            f'<span class="mv {cls}">{mv}</span><span class="d">{d}</span></li>'
        )
    return f'<ol class="ember-move" aria-label="Ranking at the new atmosphere">{"".join(rows)}</ol>'


# ------------------------------------------------------------------------------------- header
page_header(
    "Guided demo",
    "The live-demo script, one step at a time. Every number on these steps is computed now from the registry.",
    section="Start",
)
st.segmented_control(
    "Demo length",
    [FAST, FULL],
    key="demo_mode",
    on_change=_mode_changed,
    help="The fast path shows scenario, ranked evidence, its source and the gap. The full walkthrough adds every step.",
)
if fast:
    later = [i for i in FAST_STEPS if i > step]
    earlier = [i for i in FAST_STEPS if i < step]
    nxt, prev, first_step = (
        (later[0] if later else None),
        (earlier[-1] if earlier else None),
        FAST_STEPS[0],
    )
    k = sum(1 for i in FAST_STEPS if i <= step)
    st.progress(
        k / len(FAST_STEPS), text=f"Fast path · stop {k} of {len(FAST_STEPS)} · {STEPS[step][0]}"
    )
else:
    nxt = step + 1 if step < N - 1 else None
    prev = step - 1 if step > 0 else None
    first_step = 0
    st.progress((step + 1) / N, text=f"Step {step + 1} of {N} · {STEPS[step][0]}")
nav = st.columns([1, 1, 1, 5])
nav[0].button(
    "← Back",
    key="demo_back",
    on_click=_go,
    args=(prev if prev is not None else step,),
    disabled=prev is None,
    width="stretch",
)
nav[1].button(
    "Confirm scenario →" if step == 1 else "Next →",
    key="demo_next",
    type="primary",
    on_click=_go,
    args=(nxt if nxt is not None else step,),
    disabled=nxt is None,
    width="stretch",
)
nav[2].button("Restart", key="demo_restart", on_click=_go, args=(first_step,), width="stretch")
if fast and nxt is None:
    st.caption(
        "End of the fast path. Switch to the full walkthrough for the comparison, the cited summary and the method."
    )
st.subheader(f"{step + 1}. {STEPS[step][0]}")
st.caption(STEPS[step][1])

s_lunar, s_air = scenario_dict(LUNAR), scenario_dict(AIR)

# ------------------------------------------------------------------------------------- steps
if step == 0:
    status = read_status()
    m = _mirror()
    n_llm = len(list(LLM_CACHE_DIR.glob("*.json"))) if LLM_CACHE_DIR.exists() else 0
    rows = [
        {
            "Check": "NASA files mirrored locally",
            "Status": f"{m['mirrored']} of {m['listed']} present, SHA-256 verified"
            if m["ok"]
            else f"PROBLEM: {len(m['missing'])} missing, {len(m['sha_mismatch'])} checksum mismatches",
            "Note": f"{m['not_mirrored']} listed files were never mirrored; the registry does not depend on them.",
        },
        {
            "Check": "Demo caches warmed",
            "Status": f"yes, {status['created']}" if status else "not yet",
            "Note": "uv run python -m ember.demo precache",
        },
        {
            "Check": "LLM answers for the demo question",
            "Status": "cached" if status and status.get("llm_answers_cached") else "not cached",
            "Note": "Without them the demo uses the rule parser and template narration (deterministic, "
            f"same verifier). {n_llm} LLM answers in cache.",
        },
        {
            "Check": "Live network calls",
            "Status": "blocked (EMBER_LLM_OFFLINE=1)"
            if offline()
            else "allowed only for uncached LLM calls",
            "Note": "uv run python -m ember.demo check  runs every step with the network blocked.",
        },
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.info(
        "**Say:** EMBER tells you which NASA fire experiments apply to a habitat atmosphere, how far you are "
        "extrapolating, and what nobody has tested. Everything you'll see runs on this laptop."
    )

elif step == 1:
    st.text_input("Question", value=DEMO_QUESTION, disabled=True)
    for n in question_guards(DEMO_QUESTION):
        (st.error if n.kind == "refuse" else st.warning)(n.text)
    rows = [
        {
            "Field": label,
            "Proposed": "—" if fields.get(k) is None else str(fields.get(k)),
            "Origin": "from the question"
            if fields.get(k) is not None
            else ("not stated: stays unspecified" if k == "u_cms" else "not stated"),
        }
        for k, label in PARSE_LABELS.items()
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    for note in parse_notes:
        st.caption(note)
    mode = "LLM (cached)" if parse_mode == "llm" else "rule-based parser"
    st.caption(f"Parsed by: {mode}." + (f" LLM unavailable: {parse_error}." if parse_error else ""))
    st.info(
        "**Say:** The scenario appears as a chip I can check. Gravity 0.166 g lights the gravity flag: PSI holds "
        "no partial-gravity combustion data. Airflow wasn't stated, so EMBER leaves it unspecified rather than "
        "guess. I confirm."
    )

elif step == 2:
    st.markdown(scenario_chips_html(to_scenario(LUNAR)), unsafe_allow_html=True)
    results, stability, _ = ranked(s_lunar, reg)
    top = results[:10]
    st.dataframe(ranked_table(top), hide_index=True, width="stretch")
    show_chart(why_bars(top), width="stretch")
    first = top[0]
    bass2 = next((r for r in top if r["investigation"] == "BASS-II"), None)
    lines = [
        f"#1 is **{first['investigation']}** ({first['evidence_id']}), R {first['R']:.3f}, D {first['D']:.3f}."
    ]
    if bass2:
        o2, d = part_share(bass2)
        dim_names = {"x_o2": "oxygen", "p_kpa": "pressure", "u_cms": "flow"}
        unknown = [dim_names.get(k, k) for k, v in bass2["parts"].items() if v is None]
        lines.append(
            f"Hover BASS-II: O₂ contributes **{o2:.2f}** of D = **{d:.2f}**"
            + (f"; {', '.join(unknown)} unknown, so D is a lower bound." if unknown else ".")
        )
    s6 = next((r for r in top if r["investigation"] == "Saffire-VI"), None)
    if s6:
        lines.append(
            f"Saffire-VI is #{s6['rank']} with D {s6['D']:.3f}: closer in conditions, but carries "
            + ", ".join(b for b in badges_for(s6) if b.lower() in ("non-psi", "tension"))
            + "."
        )
    st.info("**Say:** " + " ".join(lines))

elif step == 3:
    by_id = reg.evidence_by_id()
    a, b = (by_id[i] for i in COMPARE_PAIR)
    r = compare_evidence(a, b)
    label = {COMPARABLE: "Comparable", CAVEATS: "Comparable with caveats"}.get(
        r["verdict"], "Not comparable"
    )
    box = {COMPARABLE: st.success, CAVEATS: st.warning}.get(r["verdict"], st.error)
    box(f"**Verdict: {label}**")
    st.markdown(f"{a.investigation} ({a.evidence_id}) vs {b.investigation} ({b.evidence_id})")
    st.markdown("**Confounders**")
    for c in r["confounders"] or ["None found by the rules."]:
        st.markdown(f"- {c}")
    with st.expander("Rule trace"):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "#": x["rule"],
                        "Rule": x["name"],
                        "Result": "pass" if x["passed"] else "FAIL",
                        "Detail": x["detail"],
                    }
                    for x in r["rules"]
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    st.info(
        f"**Say:** Can I put these side by side? EMBER says *{label.lower()}*, and lists why: "
        f"{len(r['confounders'])} confounder(s) from different hardware, scale or enclosure."
    )

elif step == 4:
    results, _, _ = ranked(s_lunar, reg)
    by_id, srcs = reg.evidence_by_id(), reg.source_by_id()
    rows = []
    for r in results[:5]:
        e = by_id[r["evidence_id"]]
        for sid in e.sources:
            s = srcs.get(sid)
            rows.append(
                {
                    "#": r["rank"],
                    "Evidence": e.evidence_id,
                    "X_O₂": format_range(e.x_o2, "{:.3g}"),
                    "P (kPa)": format_range(e.p_kpa, "{:.4g}"),
                    "O₂ from": f"{e.x_o2.source_id or ''} {e.x_o2.source_locator or ''}".strip()
                    or "—",
                    "Source": sid,
                    "PSI": ("yes" if s.in_psi else "no") if s else "unknown",
                    "DOI": (s.doi or "none") if s else "unknown",
                }
            )
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    n_doi = sum(1 for x in rows if x["DOI"].startswith("10."))
    st.info(
        f"**Say:** Every condition carries its source and locator; {n_doi} of these {len(rows)} source rows "
        "have a DOI. Unknown stays unknown: we never impute a missing pressure."
    )

elif step == 5:
    results, _, _ = ranked(s_lunar, reg)
    n = narrate(s_lunar, results[:10], reg, k=5, question=DEMO_QUESTION, use_llm=True)
    v = n.verified
    for b in v.banners:
        st.warning(b)
    for d in v.disclaimers:
        st.info(d)
    for stmt in v.kept:
        st.markdown(f"- {stmt.text}  \n  <small>`{stmt.badge}`</small>", unsafe_allow_html=True)
    mode = "LLM narrator (cached)" if n.mode == "llm" else "template narration"
    st.metric("Dropped sentences", v.n_dropped)
    st.caption(f"{mode} · kept {len(v.kept)} · dropped {v.n_dropped}")
    st.info(
        f"**Say:** Every sentence cites a record, and every number is string-checked against it. "
        f"Dropped sentences: {v.n_dropped}."
    )

elif step == 6:
    sc = to_scenario(LUNAR)
    st.markdown(gap_spotlight(s_lunar), unsafe_allow_html=True)
    grids = all_gravities(
        reg.evidence_dicts(), s_lunar["phenomenon"], s_lunar["fuel_class"], s_lunar["u_cms"]
    )
    show_chart(gap_panels(grids, mode="coverage", scenario=sc, show_targets=True), width="stretch")
    ov = config.PARTIAL_G_OVERLAYS
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Source": o["name"],
                    "g": o["gravity_g0"],
                    "X_O₂": o["x_o2"],
                    "P (kPa)": o["p_kpa"],
                    "Status": o["status"],
                    "Ref": o["source_id"],
                }
                for o in ov
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    st.info(
        "**Say:** The hatched lunar band: no PSI evidence. "
        + " and ".join(o["name"].split(" (")[0] for o in ov)
        + " are the only partial-g sources, and they are overlays, not ranking evidence."
    )

elif step == 7:
    before, _, _ = ranked(s_lunar, reg)
    after, _, _ = ranked(s_air, reg)
    st.markdown("**Scenario now**")
    st.markdown(scenario_chips_html(to_scenario(AIR)), unsafe_allow_html=True)
    st.markdown(
        f'<span class="ember-chip fixed">Gravity held at <b>{s_air["gravity_g0"]:g} g</b> (lunar)</span>'
        f'<span class="ember-chip">Atmosphere <b>{s_lunar["x_o2"] * 100:.0f}% · {s_lunar["p_kpa"]:.1f} kPa</b>'
        f" → <b>{s_air['x_o2'] * 100:.0f}% · {s_air['p_kpa']:.1f} kPa</b></span>"
        '<span class="ember-chip">Earth-normal air is an atmosphere setting here, not Earth gravity</span>',
        unsafe_allow_html=True,
    )
    st.markdown(rank_motion(before, after), unsafe_allow_html=True)
    df = reshuffle(before, after)
    with st.expander("Full before and after table, with flags"):
        st.dataframe(df, hide_index=True, width="stretch")
    show_chart(why_bars(after[:10]), width="stretch")
    up = df[df["Move"].fillna(0) > 0]
    down = df[df["Move"].fillna(0) < 0]
    said = []
    if len(up):
        said.append(
            "rises: "
            + ", ".join(
                f"{r['Investigation']} (#{r['Rank before']}→#{r['Rank after']})"
                for _, r in up.iterrows()
            )
        )
    if len(down):
        said.append(
            "falls: "
            + ", ".join(
                f"{r['Investigation']} (#{r['Rank before']}→#{r['Rank after']})"
                for _, r in down.iterrows()
            )
        )
    cleared = [x for x in df["Flags cleared"] if x != "—"]
    flag_note = (
        f"Flags cleared: {'; '.join(cleared)}."
        if cleared
        else "No flags clear: gravity is still lunar, so the gravity flag stays on every row."
    )
    st.info("**Say:** At Earth air the ranking reshuffles. " + " · ".join(said) + ". " + flag_note)

elif step == 8:
    results, _, _ = ranked(s_lunar, reg)
    first = results[0]
    st.markdown(
        f"### Would we trust #1 ({first['investigation']}) to choose a cabin fabric for "
        f"{s_lunar['x_o2'] * 100:.0f}% O₂? **No.**"
    )
    for f in first["flags"]:
        st.markdown(f"- {f}")
    tc = target_coverage(
        reg.evidence_dicts(), s_lunar["phenomenon"], s_lunar["fuel_class"], s_lunar["u_cms"]
    )
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Target": r["target"],
                    "X_O₂": r["x_o2"],
                    "P (kPa)": r["p_kpa"],
                    "g": r["g"],
                    "Coverage C": round(r["C"], 2),
                    "Nearest": r["nearest"] or "none",
                }
                for r in tc
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    md = gap_report_markdown(
        reg.evidence_dicts(), s_lunar["phenomenon"], s_lunar["fuel_class"], s_lunar["u_cms"]
    )
    st.download_button(
        "Download the gap report (Markdown)", md, "ember_gap_report_demo.md", "text/markdown"
    )
    with st.expander("Gap report", expanded=True):
        st.markdown(md)
    st.markdown("**Now open the evidence yourself**")
    end = st.columns(3)
    links = [
        ("pages/1_Ask.py", "Ask: the ranked evidence", ":material/search:"),
        ("pages/2_Evidence_Map.py", "Evidence map: every record", ":material/scatter_plot:"),
        ("views/overview.py", "Back to the atlas", ":material/home:"),
    ]
    for col, (path, label, icon) in zip(end, links, strict=True):
        try:
            col.page_link(path, label=label, icon=icon)
        except StreamlitAPIException:  # page run on its own, outside the app's navigation
            col.markdown(f"**{label}**")
    st.info(
        "**Say:** Here's exactly which test is missing: no combustion test at lunar gravity in a "
        f"{s_lunar['x_o2'] * 100:.0f}% / {s_lunar['p_kpa']:.1f} kPa atmosphere. EMBER shows the gap instead of hiding it."
    )
