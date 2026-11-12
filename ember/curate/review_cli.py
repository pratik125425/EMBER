"""Human review of paper-extracted proposals (spec §9.5, ticket T12).

    uv run python -m ember.curate.review_cli list [--status pending|accepted|rejected|all] [--source S] [--quantity Q]
    uv run python -m ember.curate.review_cli show P1a2b3c4d5
    uv run python -m ember.curate.review_cli accept P… [P… …] --evidence SAFFIRE6:SIBAL --by "Your Name" [--min X --max Y]
    uv run python -m ember.curate.review_cli reject P… --by "Your Name" --reason "table column is Saffire IV"
    uv run python -m ember.curate.review_cli review --by "Your Name" [--source S]      # interactive loop

Rules (spec §0.1, §9.5):
- Only proposals that passed the span check can be accepted, and only by a named reviewer.
- Accepting several proposals for the same quantity stores their envelope (min of mins, max of maxes);
  ranges stay ranges, and the locator lists every page/column used.
- An edited value (--min/--max) must still appear as a number in one of the accepted quotes.
- Burner/oxidizer-side oxygen can never be written onto a record whose O₂ context is ambient.
- Accepted values are converted to canonical units with pint; nothing else is transformed.
Decisions are appended to data/review/accepted.jsonl and rejected.jsonl; build_registry applies
accepted.jsonl on every build, so a decision survives re-running the proposers.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from ember.ingest.extract_llm import NUMERIC, PROPOSALS, REVIEW_DIR, numbers_in
from ember.units import normalize

ACCEPTED = REVIEW_DIR / "accepted.jsonl"
REJECTED = REVIEW_DIR / "rejected.jsonl"


class ReviewError(Exception):
    pass


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _append(path: Path, rec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load_proposals(review_dir: Path = REVIEW_DIR) -> dict[str, dict]:
    return {p["proposal_id"]: p for p in _read(review_dir / PROPOSALS.name)}


def decisions(review_dir: Path = REVIEW_DIR) -> dict[str, str]:
    st: dict[str, str] = {}
    for r in _read(review_dir / REJECTED.name):
        st[r["proposal_id"]] = "rejected"
    for r in _read(review_dir / ACCEPTED.name):
        for pid in r["proposal_ids"]:
            st[pid] = "accepted"
    return st


def status_of(pid: str, review_dir: Path = REVIEW_DIR) -> str:
    return decisions(review_dir).get(pid, "pending")


def _now() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()


def _locator(props: list[dict]) -> str:
    parts = []
    for p in props:
        col = f" · column {p['column']}" if p.get("column") else ""
        hdr = f" (header: “{p['header_quote']}”)" if p.get("header_quote") else ""
        parts.append(f"p.{p['page']}{col}: “{p['quote'][:300]}”{hdr}")
    return " | ".join(parts)


def accept(
    proposal_ids: list[str],
    evidence_id: str,
    by: str,
    new_min: float | None = None,
    new_max: float | None = None,
    note: str | None = None,
    review_dir: Path = REVIEW_DIR,
    evidence_index: dict | None = None,
) -> dict:
    """Validate and record an acceptance. Returns the accepted record (canonical units)."""
    if not by or not by.strip():
        raise ReviewError(
            "a reviewer name (--by) is required; no value enters the registry without reviewed_by"
        )
    props_all = load_proposals(review_dir)
    missing = [p for p in proposal_ids if p not in props_all]
    if missing:
        raise ReviewError(f"unknown proposal ids: {missing}")
    props = [props_all[p] for p in proposal_ids]
    for p in props:
        if not p.get("verified"):
            raise ReviewError(
                f"{p['proposal_id']} failed the span check ({p.get('reject_reason')}) and cannot be accepted"
            )
        if status_of(p["proposal_id"], review_dir) != "pending":
            raise ReviewError(
                f"{p['proposal_id']} is already {status_of(p['proposal_id'], review_dir)}"
            )
    quantities = {p["quantity"] for p in props}
    if len(quantities) != 1:
        raise ReviewError(f"proposals mix quantities {sorted(quantities)}; accept them separately")
    q = quantities.pop()
    if q not in NUMERIC:
        raise ReviewError(
            f"only numeric conditions {NUMERIC} can be applied to the registry (got {q})"
        )
    sources = {p["source_id"] for p in props}
    if len(sources) != 1:
        raise ReviewError("proposals come from different sources; accept them separately")
    if evidence_index is None:
        from ember.curate.build_registry import load_all_models

        evidence_index = {e.evidence_id: e for e in load_all_models(review_dir=None)["evidence"]}
    if evidence_id not in evidence_index:
        raise ReviewError(f"unknown evidence id {evidence_id!r}")
    ev = evidence_index[evidence_id]
    if q == "x_o2":
        burner = any(p.get("o2_context") == "burner_oxidizer_flow" for p in props)
        if burner and ev.o2_context.value != "burner_oxidizer_flow":
            raise ReviewError(
                "burner/oxidizer-side O₂ cannot be written onto a record whose O₂ context is not burner-side"
            )

    # Canonical values of every quoted point, then the envelope (or the reviewer's edit).
    canon = []
    for p in props:
        for v in (p.get("min"), p.get("max")):
            if v is None:
                continue
            n = normalize(v, p["unit_as_written"], q)
            if n.status != "known":
                raise ReviewError(
                    f"{p['proposal_id']}: cannot convert {v} {p['unit_as_written']!r} ({n.note})"
                )
            canon.append(n.value)
    edited = new_min is not None or new_max is not None
    if edited:
        quoted = [x for p in props for x in numbers_in(p["quote"])]
        unit = props[0]["unit_as_written"]
        vals = []
        for v in (new_min, new_max):
            if v is None:
                continue
            if not any(abs(v - n) < 1e-9 for n in quoted):
                raise ReviewError(f"edited value {v} does not appear in any accepted quote")
            vals.append(normalize(v, unit, q).value)
        lo, hi = min(vals), max(vals)
    else:
        lo, hi = min(canon), max(canon)
    rec = {
        "review_id": "R" + proposal_ids[0][1:] + f"-{len(proposal_ids)}",
        "proposal_ids": proposal_ids,
        "evidence_id": evidence_id,
        "field": q,
        "min": round(lo, 6),
        "max": round(hi, 6),
        "source_id": sources.pop(),
        "source_locator": _locator(props),
        "reviewed_by": by.strip(),
        "reviewed_at": _now(),
        "edited": edited,
        "note": note,
    }
    _append(review_dir / ACCEPTED.name, rec)
    return rec


def reject(proposal_id: str, by: str, reason: str, review_dir: Path = REVIEW_DIR) -> dict:
    if not by or not by.strip():
        raise ReviewError("a reviewer name (--by) is required")
    if proposal_id not in load_proposals(review_dir):
        raise ReviewError(f"unknown proposal id {proposal_id}")
    rec = {
        "proposal_id": proposal_id,
        "reviewed_by": by.strip(),
        "reviewed_at": _now(),
        "reason": reason,
    }
    _append(review_dir / REJECTED.name, rec)
    return rec


def accepted_records(review_dir: Path = REVIEW_DIR) -> list[dict]:
    """Accepted decisions that carry a reviewer (anything else is ignored by the build)."""
    return [r for r in _read(review_dir / ACCEPTED.name) if r.get("reviewed_by")]


# ------------------------------------------------------------------------------------------ CLI
def _fmt(p: dict, st: str) -> str:
    v = p["min"] if p.get("min") == p.get("max") else f"{p.get('min')}–{p.get('max')}"
    col = f" [{p['column']}]" if p.get("column") else ""
    ok = "ok " if p.get("verified") else "REJ"
    return f"{p['proposal_id']}  {st:<8} {ok} {p['source_id']:<22} p.{p['page']:<3} {p['quantity']:<6} {v} {p.get('unit_as_written') or ''}{col}"


def _show(p: dict, st: str) -> None:
    print(_fmt(p, st))
    print(f"  quote ({p.get('match_mode')}): “{p['quote']}”")
    if p.get("header_quote"):
        print(f"  header: “{p['header_quote']}”")
    if p.get("o2_context"):
        print(f"  O₂ context: {p['o2_context']}")
    if not p.get("verified"):
        print(f"  span check FAILED: {p.get('reject_reason')}")
    print(
        f"  candidate evidence: {', '.join(p.get('candidates') or []) or '(none; pass --evidence)'}"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("list")
    pl.add_argument(
        "--status", default="pending", choices=["pending", "accepted", "rejected", "all"]
    )
    pl.add_argument("--source")
    pl.add_argument("--quantity")
    pl.add_argument(
        "--include-failed",
        action="store_true",
        help="also list proposals that failed the span check",
    )
    ps = sub.add_parser("show")
    ps.add_argument("proposal_id")
    pa = sub.add_parser("accept")
    pa.add_argument("proposal_ids", nargs="+")
    pa.add_argument("--evidence", required=True)
    pa.add_argument("--by", required=True)
    pa.add_argument("--min", type=float)
    pa.add_argument("--max", type=float)
    pa.add_argument("--note")
    pr = sub.add_parser("reject")
    pr.add_argument("proposal_id")
    pr.add_argument("--by", required=True)
    pr.add_argument("--reason", required=True)
    pi = sub.add_parser("review")
    pi.add_argument("--by", required=True)
    pi.add_argument("--source")
    a = ap.parse_args(argv)

    props, st = load_proposals(), decisions()
    try:
        if a.cmd == "list":
            n = 0
            for p in props.values():
                s = st.get(p["proposal_id"], "pending")
                if a.status != "all" and s != a.status:
                    continue
                if (a.source and p["source_id"] != a.source) or (
                    a.quantity and p["quantity"] != a.quantity
                ):
                    continue
                if not p.get("verified") and not a.include_failed:
                    continue
                print(_fmt(p, s))
                n += 1
            print(f"\n{n} shown")
        elif a.cmd == "show":
            _show(props[a.proposal_id], st.get(a.proposal_id, "pending"))
        elif a.cmd == "accept":
            rec = accept(a.proposal_ids, a.evidence, a.by, a.min, a.max, a.note)
            print(
                f"accepted → {rec['evidence_id']}.{rec['field']} = {rec['min']}–{rec['max']} (canonical) by {rec['reviewed_by']}"
            )
            print("run: uv run python -m ember.curate.build_registry")
        elif a.cmd == "reject":
            reject(a.proposal_id, a.by, a.reason)
            print(f"rejected {a.proposal_id}")
        elif a.cmd == "review":
            pending = [
                p
                for p in props.values()
                if p.get("verified")
                and st.get(p["proposal_id"]) is None
                and (not a.source or p["source_id"] == a.source)
            ]
            for i, p in enumerate(pending, 1):
                print(f"\n[{i}/{len(pending)}]")
                _show(p, "pending")
                choice = input("  [a]ccept / [r]eject / [s]kip / [q]uit: ").strip().lower()
                if choice == "q":
                    break
                if choice == "r":
                    reject(
                        p["proposal_id"], a.by, input("  reason: ").strip() or "rejected in review"
                    )
                elif choice == "a":
                    default = (p.get("candidates") or [""])[0]
                    eid = input(f"  evidence id [{default}]: ").strip() or default
                    try:
                        rec = accept([p["proposal_id"]], eid, a.by)
                        print(
                            f"  accepted → {rec['evidence_id']}.{rec['field']} = {rec['min']}–{rec['max']}"
                        )
                    except ReviewError as exc:
                        print(f"  not accepted: {exc}")
    except ReviewError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
