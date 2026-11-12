"""Cite-or-drop narrator (spec §11.3).

The narrator sees ONLY the confirmed scenario, the top-k ranked records (conditions, flags, D parts)
and the claims attached to them. Its output goes through ``verifier.verify``; failing sentences are
dropped and counted. When the LLM is unavailable, the template narration (§11.4) is used and goes
through the same verifier, so both modes obey the same rules.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from ember.llm.templates import template_sentence
from ember.llm.verifier import Verified, verify
from ember.registry import Registry
from ember.schemas import Range

SYSTEM = """You summarize NASA fire-experiment evidence for one scenario. The user message is a JSON payload.
Rules:
- Use ONLY facts in the payload. Do not add background knowledge.
- Write 3 to 6 sentences, one sentence per line, with no headings, bullets or blank lines.
- End every sentence with one or more citations in square brackets, using only ids that appear in the
  payload, e.g. [SAFFIRE6:SIBAL] or [PSI-159].
- Every number you write must appear in the record you cite. Do not compute, round to new values, or convert.
- D is EMBER's extrapolation distance: smaller means closer to the tested conditions. Ranks are given; do not re-rank.
- Never call a material or scenario safe, and never say evidence proves or guarantees anything.
- PSI holds no partial-gravity combustion data. Never say anything was measured, tested or observed on the Moon or Mars.
- If CFI-G 85% oxygen appears, it is burner/oxidizer-side flow, not the cabin atmosphere; say so in the same sentence.
- Mention flags such as INCOMPLETE_CONDITIONS or BEYOND_TESTED_ENVELOPE when a record carries them."""


@dataclass
class Narration:
    mode: str  # "llm" | "template"
    verified: Verified
    error: str | None = None
    raw: str = ""
    payload: dict = field(default_factory=dict)


def _range(r: Range) -> dict | str:
    if r.status != "known":
        return r.status
    return {"min": r.min, "max": r.max}


def build_payload(scenario: dict, results: list[dict], reg: Registry, k: int = 5) -> dict:
    by_id = reg.evidence_by_id()
    srcs = reg.source_by_id()
    top = results[:k]
    records, sources, claims = {}, {}, {}
    for r in top:
        e = by_id[r["evidence_id"]]
        records[e.evidence_id] = {
            "rank": r["rank"],
            "investigation": e.investigation,
            "fuel": e.fuel_name or e.fuel_class.value,
            "fuel_class": e.fuel_class.value,
            "phenomena": [p.value for p in e.phenomena],
            "gravity": e.gravity.value,
            "x_o2": _range(e.x_o2),
            "o2_context": e.o2_context.value,
            "p_kpa": _range(e.p_kpa),
            "u_cms": _range(e.u_cms),
            "D": round(r["D"], 3),
            "exp_D": round(r["expD"], 3),
            "D_lower_bound": r["D_lower_bound"],
            "D_parts": {d: (None if v is None else round(v, 3)) for d, v in r["parts"].items()},
            "flags": [f.split(":", 1)[0] for f in r["flags"]],
            "records_in_group": r.get("n_group", 1),
            "sources": list(e.sources),
        }
        for sid in e.sources:
            s = srcs.get(sid)
            if s:
                sources[sid] = {"title": s.title, "year": s.year, "in_psi": s.in_psi}
        for c in reg.claims_for(e.evidence_id):
            claims[c.claim_id] = {
                "evidence_id": c.evidence_id,
                "text": c.text,
                "claim_type": c.claim_type.value,
                "source_id": c.source_id,
            }
    return {
        "scenario": {
            k2: scenario.get(k2)
            for k2 in (
                "x_o2",
                "p_kpa",
                "u_cms",
                "gravity_g0",
                "phenomenon",
                "fuel_class",
                "fuel_name",
            )
        },
        "records": records,
        "sources": sources,
        "claims": claims,
        "top_D": [r["D"] for r in top],
    }


def template_text(results: list[dict], reg: Registry, k: int = 5) -> str:
    by_id = reg.evidence_by_id()
    return "\n".join(template_sentence(by_id[r["evidence_id"]], r) for r in results[:k])


def narrate(
    scenario: dict,
    results: list[dict],
    reg: Registry,
    *,
    k: int = 5,
    question: str | None = None,
    use_llm: bool = True,
    complete=None,
) -> Narration:
    payload = build_payload(scenario, results, reg, k)
    if use_llm:
        from ember.llm.client import LLMUnavailable
        from ember.llm.client import complete as default_complete

        user = json.dumps(
            {
                "question": question,
                **{x: payload[x] for x in ("scenario", "records", "sources", "claims")},
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        try:
            raw = (complete or default_complete)(SYSTEM, user)
            return Narration(
                "llm", verify(raw, payload, scenario, question), raw=raw, payload=payload
            )
        except LLMUnavailable as exc:
            err = str(exc)
    else:
        err = None
    raw = template_text(results, reg, k)
    return Narration(
        "template", verify(raw, payload, scenario, question), error=err, raw=raw, payload=payload
    )
