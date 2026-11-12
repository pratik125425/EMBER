"""Deterministic question guards (spec §0 rules 9-10, §12.5 adversarial prompts).

They run on the user's question before anything is narrated and return notices the UI shows
verbatim. Kinds:
  refuse      the registry cannot answer this at all (water mist, rockets); no narration
  no_safety   the question asks whether something is safe; EMBER never says that
  burner_o2   CFI-G's 85% O₂ is burner/oxidizer-side flow, not cabin atmosphere
  partial_g   the question is about Moon/Mars, where PSI holds no data
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ember.llm.templates import partial_g_disclaimer


@dataclass(frozen=True)
class Notice:
    kind: str
    text: str


REFUSALS: list[tuple[str, str]] = [
    (
        r"water[- ]?mist|sprinkler|fine water spray",
        "EMBER's registry holds no water-mist or sprinkler tests, so it will not rank or describe any. "
        "The PSI suppression evidence it does hold is gaseous diluents in droplet flames (FLEX: CO₂ and "
        "helium). [PSI-69]",
    ),
    (
        r"\brockets?\b|propellant|launch vehicle|engine plume",
        "EMBER covers spacecraft-cabin and habitat fire evidence from PSI. Rocket and propellant "
        "combustion is outside its registry, so it will not answer this. [CHALLENGE-2026]",
    ),
]
SAFETY = re.compile(r"\b(safe|safely|safety margin|is it ok|okay to use|will it burn)\b", re.I)
CFIG = re.compile(r"CFI-?G|cool flame investigation", re.I)
CABIN_O2 = re.compile(r"cabin|ambient|atmosphere|chamber", re.I)
PARTIAL_G = re.compile(r"\b(moon|lunar|mars|martian|partial[- ]g)", re.I)


def question_guards(q: str) -> list[Notice]:
    out: list[Notice] = []
    for pat, text in REFUSALS:
        if re.search(pat, q, re.I):
            out.append(Notice("refuse", text))
    if SAFETY.search(q):
        out.append(
            Notice(
                "no_safety",
                "EMBER does not say whether a material or scenario is safe. It shows which NASA tests are "
                "closest to your conditions and how far you are extrapolating from them. [CHALLENGE-2026]",
            )
        )
    if CFIG.search(q) and (CABIN_O2.search(q) or re.search(r"oxygen|o2|o₂", q, re.I)):
        out.append(
            Notice(
                "burner_o2",
                "CFI-G's 85% O₂ figure is the burner oxidizer flow, not the cabin or chamber atmosphere. "
                "EMBER never uses it as ambient oxygen; ranking uses the chamber conditions from the CFI-G "
                "PSI data tables. [CHALLENGE-2026; PSI-159]",
            )
        )
    if PARTIAL_G.search(q):
        out.append(Notice("partial_g", partial_g_disclaimer()))
    return out


def refused(notices: list[Notice]) -> bool:
    return any(n.kind == "refuse" for n in notices)
