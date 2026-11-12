"""Condition proposals from papers, with an automatic span check (spec §9.4, ticket T12).

    uv run python -m ember.ingest.extract_llm [--proposer rules|llm] [--source NTRS-20240002981]

Two proposers produce the SAME proposal shape; neither writes to the registry:
  rules  deterministic, offline: inline mentions ("28.8–31.0% oxygen", "8.2 psia", "30 cm/s") and
         table rows ("Ambient Pressure (kPa) 100.0 70.7 54.1 …", one proposal per column).
  llm    the spec's extraction prompt over each page through a completion function
         ``complete(system, user) -> str``, by default ``ember.llm.client.complete`` (cached;
         needs ANTHROPIC_API_KEY for pages not yet in the cache).

Every proposal is checked before a human sees it (``verify``):
  1. the quote occurs on the stated page (exact, or after collapsing whitespace/line breaks);
  2. every number in min/max appears in the quote as written;
  3. numeric quantities carry a unit that pint can convert to the canonical unit.
Failures are kept in proposals.jsonl with ``verified=false`` and a reason, never shown for acceptance.
Values enter the registry only through ``ember.curate.review_cli`` with a named reviewer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from ember.ingest.parse_pdf import cached_pages, mirrored_pdfs, page_texts
from ember.paths import DATA_DIR
from ember.units import normalize

REVIEW_DIR = DATA_DIR / "review"
PROPOSALS = REVIEW_DIR / "proposals.jsonl"
QUANTITIES = ("x_o2", "p_kpa", "u_cms", "size_cm", "diluent", "fuel_name", "gravity")
NUMERIC = ("x_o2", "p_kpa", "u_cms", "size_cm")

EXTRACTION_SYSTEM = (
    "You are extracting experimental CONDITIONS from a NASA combustion document.\n"
    "Return JSON list. Each item:\n"
    '{ "investigation": str, "quantity": one of [x_o2, p_kpa, u_cms, size_cm, diluent, fuel_name, gravity],\n'
    '  "min": number|null, "max": number|null, "unit_as_written": str,\n'
    '  "o2_context": "ambient"|"burner_oxidizer_flow"|"unknown",\n'
    '  "quote": "<verbatim text from the document containing the value>",\n'
    '  "page": int }\n'
    "Rules: Copy numbers exactly as written. Do not convert units. If a value is not stated, omit it.\n"
    "Never infer. If oxygen refers to burner/oxidizer flow rather than chamber atmosphere, set o2_context accordingly."
)

NUM = r"\d+(?:\.\d+)?"
NUM_RE = re.compile(r"(?<![\w.])[-+]?\d+(?:\.\d+)?")
O2_WORDS = re.compile(r"\b(?:O2|O₂|oxygen)\b", re.I)


# ----------------------------------------------------------------------------------- utilities
def ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def numbers_in(text: str) -> list[float]:
    return [float(m.group(0)) for m in NUM_RE.finditer(text.replace(",", ""))]


def proposal_id(p: dict) -> str:
    key = json.dumps(
        [
            p["source_id"],
            p["page"],
            p["quantity"],
            p.get("min"),
            p.get("max"),
            p.get("unit_as_written"),
            ws(p["quote"]),
            p.get("column"),
        ],
        ensure_ascii=False,
    )
    return "P" + hashlib.sha256(key.encode()).hexdigest()[:10]


def o2_context_of(text: str) -> str:
    t = text.lower()
    if "burner" in t or "oxidizer" in t or "oxidiser" in t:
        return "burner_oxidizer_flow"
    if "ambient" in t or "atmosphere" in t or "cabin" in t:
        return "ambient"
    return "unknown"


def classify(unit: str, context: str) -> str | None:
    u = unit.lower().strip()
    if u in ("%", "percent", "mol %", "mol%", "vol %", "% by vol"):
        return "x_o2" if O2_WORDS.search(context) else None
    if u in ("kpa", "psia", "psi", "atm", "bar", "mmhg", "torr"):
        return "p_kpa"
    if u in ("cm/s", "mm/s", "m/s"):
        return "u_cms"
    return None


# --------------------------------------------------------------------------------- span check
def verify(p: dict, pages: list[str]) -> dict:
    """Return a copy of the proposal with verified / match_mode / reject_reason set."""
    out = dict(p, verified=False, match_mode=None, reject_reason=None)

    def fail(reason: str) -> dict:
        out["reject_reason"] = reason
        return out

    if p.get("quantity") not in QUANTITIES:
        return fail(f"unknown quantity {p.get('quantity')!r}")
    page = p.get("page")
    if not isinstance(page, int) or not 1 <= page <= len(pages):
        return fail(f"page {page!r} outside 1..{len(pages)}")
    quote = p.get("quote") or ""
    if not quote.strip():
        return fail("empty quote")
    text = pages[page - 1]
    if quote in text:
        out["match_mode"] = "exact"
    elif ws(quote) in ws(text):
        out["match_mode"] = "whitespace"
    else:
        return fail("quote not found on the stated page")
    in_quote = numbers_in(quote)
    for key in ("min", "max"):
        v = p.get(key)
        if v is not None and not any(abs(v - n) < 1e-9 for n in in_quote):
            return fail(f"{key}={v} does not appear in the quote")
    if p["quantity"] in NUMERIC:
        if p.get("min") is None and p.get("max") is None:
            return fail("numeric quantity without a value")
        probe = p.get("min") if p.get("min") is not None else p.get("max")
        if normalize(probe, p.get("unit_as_written"), p["quantity"]).status != "known":
            return fail(f"unit {p.get('unit_as_written')!r} not convertible for {p['quantity']}")
    out["verified"] = True
    return out


# ------------------------------------------------------------------------------ rules proposer
INLINE = re.compile(
    rf"(?P<a>{NUM})(?:\s*(?:%|psia|psi|kPa)?\s*(?:–|-|to)\s*(?P<b>{NUM}))?\s*"
    r"(?P<u>%|percent|psia|psi|kPa|atm|bar|mmHg|torr|cm/s|mm/s|m/s)(?![A-Za-z])"
)
TABLE_ROW = re.compile(
    rf"^(?P<label>[A-Za-z][A-Za-z0-9 ./,\-]*?)\s*\((?P<unit>[^)\d]*?)\)?\s+(?P<nums>(?:{NUM}\s+)+{NUM})\s*$"
)
HEADER_START = re.compile(r"^(?:Flight|Sample|Test|Case|Run|Condition|Point)", re.I)


def _sentences(page_text: str) -> list[str]:
    joined = ws(page_text)
    return [s for s in re.split(r"(?<=[.;!?])\s+(?=[A-Z(])", joined) if s]


def rule_proposals(source_id: str, pages: list[str]) -> list[dict]:
    props: list[dict] = []
    for pno, text in enumerate(pages, start=1):
        # Inline mentions, one proposal per match, quote = the sentence (whitespace-joined).
        for sent in _sentences(text):
            for m in INLINE.finditer(sent):
                q = classify(m.group("u"), sent[max(0, m.start() - 60) : m.end() + 60])
                if q is None:
                    continue
                a = float(m.group("a"))
                b = float(m.group("b")) if m.group("b") else a
                props.append(
                    {
                        "source_id": source_id,
                        "page": pno,
                        "quantity": q,
                        "min": min(a, b),
                        "max": max(a, b),
                        "unit_as_written": m.group("u"),
                        "o2_context": o2_context_of(sent) if q == "x_o2" else None,
                        "quote": sent
                        if len(sent) <= 400
                        else sent[max(0, m.start() - 180) : m.end() + 180],
                        "kind": "inline",
                        "proposer": "rules",
                    }
                )
        # Table rows: label (unit) n1 n2 …; one proposal per column, labelled from the header line.
        lines = text.splitlines()
        for i, line in enumerate(lines):
            m = TABLE_ROW.match(line.strip())
            if not m:
                continue
            unit = m.group("unit").strip()
            if ")" not in line and i + 1 < len(lines) and ")" in lines[i + 1]:
                unit = f"{unit} {lines[i + 1].split(')')[0].strip()}".strip()
            q = classify(unit, m.group("label") + " " + unit)
            if q is None:
                continue
            nums = m.group("nums").split()
            header, labels = None, None
            # Column labels: nearest header-like line above whose last n tokens look like IDs
            # (contain a digit, e.g. "IV-1", "B12"); a "Sample Material PMMA …" line does not qualify.
            fallback = None
            for j in range(i - 1, max(-1, i - 10), -1):
                toks = lines[j].split()
                if not HEADER_START.match(lines[j].strip()) or len(toks) <= len(nums):
                    continue
                cand = toks[-len(nums) :]
                if all(re.search(r"\d", t) for t in cand):
                    header, labels = lines[j].strip(), cand
                    break
                fallback = fallback or (lines[j].strip(), cand)
            if header is None and fallback:
                header, labels = fallback
            for k, raw in enumerate(nums):
                v = float(raw)
                props.append(
                    {
                        "source_id": source_id,
                        "page": pno,
                        "quantity": q,
                        "min": v,
                        "max": v,
                        "unit_as_written": unit,
                        "o2_context": o2_context_of(m.group("label")) if q == "x_o2" else None,
                        "quote": line.strip(),
                        "header_quote": header,
                        "column": labels[k] if labels else f"column {k + 1}",
                        "kind": "table",
                        "proposer": "rules",
                    }
                )
    return props


# -------------------------------------------------------------------------------- llm proposer
def llm_proposals(
    source_id: str, pages: list[str], complete: Callable[[str, str], str]
) -> list[dict]:
    props: list[dict] = []
    for pno, text in enumerate(pages, start=1):
        if not text.strip():
            continue
        raw = complete(EXTRACTION_SYSTEM, f"Document {source_id}, page {pno}:\n\n{text}")
        try:
            items = json.loads(raw[raw.find("[") : raw.rfind("]") + 1]) if "[" in raw else []
        except json.JSONDecodeError:
            items = []
        for it in items if isinstance(items, list) else []:
            if not isinstance(it, dict):
                continue
            props.append(
                {
                    "source_id": source_id,
                    "page": it.get("page", pno),
                    "quantity": it.get("quantity"),
                    "min": it.get("min"),
                    "max": it.get("max"),
                    "unit_as_written": it.get("unit_as_written"),
                    "o2_context": it.get("o2_context"),
                    "quote": it.get("quote") or "",
                    "investigation": it.get("investigation"),
                    "kind": "llm",
                    "proposer": "llm",
                }
            )
    return props


# ------------------------------------------------------------------------------------------ run
def candidates_by_source() -> dict[str, list[str]]:
    from ember.curate.build_registry import load_all_models

    out: dict[str, list[str]] = {}
    for e in load_all_models()["evidence"]:
        sids = set(e.sources) | {
            getattr(e, k).source_id for k in ("x_o2", "p_kpa", "u_cms") if getattr(e, k).source_id
        }
        for sid in sids:
            if not e.evidence_id.startswith("PSI-"):  # per-test rows already carry table values
                out.setdefault(sid, []).append(e.evidence_id)
    return out


def run(
    proposer: str = "rules",
    only: str | None = None,
    out_path: Path = PROPOSALS,
    complete: Callable[[str, str], str] | None = None,
    docs: list[tuple[str, list[str]]] | None = None,
) -> dict:
    if docs is None:
        docs = []
        for sid, path in mirrored_pdfs():
            if only and sid != only:
                continue
            docs.append((sid, page_texts(path, sid)))
        if not docs and only:
            pages = cached_pages(only)
            if pages:
                docs.append((only, pages))
    if proposer == "llm" and complete is None:
        from ember.llm.client import complete as complete  # noqa: PLC0415
    from ember.llm.client import LLMUnavailable  # noqa: PLC0415

    cands = candidates_by_source()
    seen, allp = set(), []
    for sid, pages in docs:
        try:
            raw = (
                rule_proposals(sid, pages)
                if proposer == "rules"
                else llm_proposals(sid, pages, complete)
            )
        except LLMUnavailable as exc:
            raise SystemExit(f"LLM unavailable ({exc}); use --proposer rules.") from exc
        for p in raw:
            p = verify(p, pages)
            p["proposal_id"] = proposal_id(p)
            if p["proposal_id"] in seen:
                continue
            seen.add(p["proposal_id"])
            p["candidates"] = cands.get(sid, [])
            allp.append(p)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        for p in allp:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    by = Counter((p["source_id"], p["quantity"], p["verified"]) for p in allp)
    return {
        "n": len(allp),
        "verified": sum(p["verified"] for p in allp),
        "by_source_quantity": {
            f"{a}|{b}|{'ok' if c else 'rejected'}": n for (a, b, c), n in sorted(by.items())
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--proposer", choices=["rules", "llm"], default="rules")
    ap.add_argument("--source", default=None)
    a = ap.parse_args(argv)
    rep = run(a.proposer, a.source)
    print(f"{rep['n']} proposals, {rep['verified']} passed the span check → {PROPOSALS}")
    for k, n in rep["by_source_quantity"].items():
        print(f"  {n:>4}  {k}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
