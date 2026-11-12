"""Guided demo (spec §17.1, ticket T17): scenarios, steps, pre-cache and offline check.

    uv run python -m ember.demo precache   # warm every cache the demo reads
    uv run python -m ember.demo check      # run the whole demo with the network blocked

Every number the demo shows is computed from the registry at run time. Nothing in this file states a
result; the spec's example numbers (e.g. "O₂ contributes 0.43 of D = 0.46") are NOT hard-coded.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import socket
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from ember.engine.robustness import cached_rank_stability
from ember.engine.score import collapse, rank
from ember.llm.parser import parse_question
from ember.paths import CACHE_DIR, MANIFEST_CSV, ROOT
from ember.registry import Registry, load_registry

DEMO_QUESTION = (
    "Which NASA experiments best inform fabric and plastic flammability in a lunar habitat at "
    "34% oxygen and 8.2 psi?"
)
# Step 8 of the script: drag the scenario to Earth-normal air (21% O₂, 14.7 psia = 101.3 kPa).
# Only O₂ and pressure move; gravity, phenomenon and fuel stay as parsed.
AIR = {"x_o2": 0.21, "p_kpa": 101.3}
# Step 4 of the script: the comparison pair.
COMPARE_PAIR = ("BASS-II:campaign", "PSI-100:S1")
STATUS_FILE = CACHE_DIR / "demo_status.json"

STEPS: list[tuple[str, str]] = [
    ("Before you start", "Check that everything the demo needs is on this machine."),
    (
        "Ask in plain language",
        "Type the question. EMBER proposes a scenario; nothing changes until you confirm.",
    ),
    ("Ranked evidence", "Deterministic ranking with why-bars, D, exp(D) and badges."),
    ("Compare two results", "Can BASS-II and Saffire-III be compared directly?"),
    ("Conditions and DOIs", "Where every number comes from."),
    (
        "Cited summary",
        "Cite-or-drop: every sentence is checked against the records; failures are dropped and counted.",
    ),
    ("Gaps at lunar gravity", "What nobody has tested."),
    ("Move to Earth air", "Drag the scenario to 21% O₂ / 14.7 psia and watch the ranking change."),
    ("Would we trust #1?", "The honest answer, and exactly which test is missing."),
]


# ------------------------------------------------------------------------------------- scenarios
def lunar_fields() -> dict:
    """The demo scenario = whatever the parser proposes for the demo question (cached LLM or rules)."""
    return dict(parse_question(DEMO_QUESTION).fields)


def air_fields(base: dict) -> dict:
    return {**base, **AIR}


def scenario_dict(fields: dict) -> dict:
    """The dict ``rank`` expects, built from parser-style fields."""
    return {
        "name": "demo",
        "x_o2": fields["x_o2"],
        "p_kpa": fields["p_kpa"],
        "u_cms": fields.get("u_cms"),
        "gravity_g0": fields["gravity_g0"],
        "phenomenon": fields["phenomenon"],
        "fuel_class": fields.get("fuel_class"),
        "fuel_name": fields.get("fuel_name"),
    }


def ranked(s: dict, reg: Registry, grouped: bool = True) -> tuple[list[dict], dict, bool]:
    """Ranking + Monte Carlo stability, exactly as the Ask page computes it."""
    ev = reg.evidence_dicts()
    results = rank(s, ev)
    stability, was_cached = cached_rank_stability(
        s, ev, group_by="investigation" if grouped else None
    )
    if grouped:
        results = collapse(results, "investigation")
    for r in results:
        k = r["group"] if grouped else r["evidence_id"]
        r["p_topk"] = stability["p_topk"].get(k, 0.0)
        r["stable"] = stability["stable"].get(k, False)
    return results, stability, was_cached


def part_share(result: dict, dim: str = "x_o2") -> tuple[float | None, float]:
    """(contribution of ``dim`` to D, D) for one ranked row."""
    return result["parts"].get(dim), result["D"]


def reshuffle(before: list[dict], after: list[dict], n: int = 10) -> pd.DataFrame:
    """Rank and flag changes per investigation between two grouped rankings."""
    a = {r["investigation"]: r for r in before}
    b = {r["investigation"]: r for r in after}
    names = list(
        dict.fromkeys(
            [r["investigation"] for r in after[:n]] + [r["investigation"] for r in before[:n]]
        )
    )
    rows = []
    for name in names:
        ra, rb = a.get(name), b.get(name)
        fa = {f.split(":", 1)[0] for f in ra["flags"]} if ra else set()
        fb = {f.split(":", 1)[0] for f in rb["flags"]} if rb else set()
        rows.append(
            {
                "Investigation": name,
                "Rank before": ra["rank"] if ra else None,
                "Rank after": rb["rank"] if rb else None,
                "Move": (ra["rank"] - rb["rank"]) if ra and rb else None,
                "D before": round(ra["D"], 3) if ra else None,
                "D after": round(rb["D"], 3) if rb else None,
                "Flags cleared": ", ".join(sorted(fa - fb)) or "—",
                "Flags added": ", ".join(sorted(fb - fa)) or "—",
            }
        )
    return pd.DataFrame(rows).sort_values("Rank after", na_position="last").reset_index(drop=True)


# ------------------------------------------------------------------------------------- readiness
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def mirror_check(manifest: Path = MANIFEST_CSV) -> dict:
    """Every mirrored file exists and matches its manifest SHA-256."""
    m = pd.read_csv(manifest)
    mirrored = m[m["sha256"].notna() & m["path"].notna()]
    missing, mismatched = [], []
    for _, r in mirrored.iterrows():
        p = ROOT / r["path"]
        if not p.exists():
            missing.append(r["path"])
        elif sha256_file(p) != r["sha256"]:
            mismatched.append(r["path"])
    return {
        "listed": len(m),
        "mirrored": len(mirrored),
        "not_mirrored": len(m) - len(mirrored),
        "missing": missing,
        "sha_mismatch": mismatched,
        "ok": not missing and not mismatched,
    }


def read_status() -> dict | None:
    try:
        return json.loads(STATUS_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def precache(reg: Registry | None = None) -> dict:
    """Warm every cache the demo reads: MC stability for both scenarios (grouped and per-test), the
    parsed question and the narration. LLM answers are cached only if an API key is available;
    otherwise the demo uses the rule parser and template narration, and the status says so."""
    from ember.llm.narrator import narrate

    reg = reg or load_registry()
    parsed = parse_question(DEMO_QUESTION)
    lunar = scenario_dict(parsed.fields)
    air = scenario_dict(air_fields(parsed.fields))
    stab = {}
    narr = {}
    for name, s in (("lunar", lunar), ("air", air)):
        for grouped in (True, False):
            results, _, was_cached = ranked(s, reg, grouped)
            stab[f"{name}{'' if grouped else '_per_test'}"] = (
                "cached" if was_cached else "computed now"
            )
        top = ranked(s, reg, True)[0][:10]
        n = narrate(s, top, reg, k=5, question=DEMO_QUESTION, use_llm=True)
        narr[name] = {
            "mode": n.mode,
            "llm_error": n.error,
            "kept": len(n.verified.kept),
            "dropped": n.verified.n_dropped,
        }
    status = {
        "created": datetime.now(UTC).isoformat(timespec="seconds"),
        "question": DEMO_QUESTION,
        "parser": {"mode": parsed.mode, "llm_error": parsed.error, "fields": parsed.fields},
        "stability": stab,
        "narration": narr,
        "llm_answers_cached": parsed.mode == "llm"
        and all(v["mode"] == "llm" for v in narr.values()),
    }
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(status, indent=1))
    return status


# ------------------------------------------------------------------------------------- offline check
_LOCAL = {"127.0.0.1", "::1", "localhost", "0.0.0.0"}


class NetworkBlocked(OSError):
    pass


@contextlib.contextmanager
def no_network():
    """Refuse every non-loopback connection and DNS lookup inside the block (simulated cable pull)."""
    attempts: list[str] = []
    real_connect = socket.socket.connect
    real_gai = socket.getaddrinfo

    def connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if self.family == getattr(socket, "AF_UNIX", None) or host in _LOCAL:
            return real_connect(self, address)
        attempts.append(str(host))
        raise NetworkBlocked(f"offline check: connection to {host} blocked")

    def getaddrinfo(host, *a, **k):
        if host in _LOCAL or host is None:
            return real_gai(host, *a, **k)
        attempts.append(str(host))
        raise socket.gaierror(f"offline check: DNS lookup of {host} blocked")

    old_env = os.environ.get("EMBER_LLM_OFFLINE")
    socket.socket.connect = connect
    socket.getaddrinfo = getaddrinfo
    os.environ["EMBER_LLM_OFFLINE"] = "1"
    try:
        yield attempts
    finally:
        socket.socket.connect = real_connect
        socket.getaddrinfo = real_gai
        if old_env is None:
            os.environ.pop("EMBER_LLM_OFFLINE", None)
        else:
            os.environ["EMBER_LLM_OFFLINE"] = old_env


DEMO_PAGE = ROOT / "app" / "pages" / "0_Demo.py"
ALL_PAGES = [ROOT / "app" / "Home.py", *sorted((ROOT / "app" / "pages").glob("*.py"))]


def offline_check() -> dict:
    """Walk every demo step, then load every page, with the network blocked."""
    from streamlit.testing.v1 import AppTest

    report: dict = {"steps": [], "pages": {}, "mirror": mirror_check()}
    with no_network() as attempts:
        at = AppTest.from_file(str(DEMO_PAGE), default_timeout=120).run()
        for i in range(len(STEPS)):
            ok = not at.exception
            report["steps"].append(
                {
                    "step": i,
                    "title": STEPS[i][0],
                    "ok": ok,
                    "error": None if ok else str(at.exception[0].value),
                }
            )
            if i < len(STEPS) - 1:
                at.button(key="demo_next").click().run()
        for p in ALL_PAGES:
            pt = AppTest.from_file(str(p), default_timeout=120).run()
            report["pages"][p.name] = "ok" if not pt.exception else str(pt.exception[0].value)
    report["blocked_attempts"] = sorted(set(attempts))
    report["ok"] = (
        all(s["ok"] for s in report["steps"])
        and all(v == "ok" for v in report["pages"].values())
        and report["mirror"]["ok"]
    )
    return report


def main(argv: list[str] | None = None) -> int:
    cmd = (argv or sys.argv[1:] or ["check"])[0]
    if cmd == "precache":
        s = precache()
        print(json.dumps(s, indent=1))
        return 0
    if cmd == "check":
        r = offline_check()
        for s in r["steps"]:
            print(
                f"  step {s['step']} {s['title']:<24} {'ok' if s['ok'] else 'FAIL: ' + s['error']}"
            )
        for p, v in r["pages"].items():
            print(f"  page {p:<20} {v}")
        m = r["mirror"]
        print(
            f"  mirror: {m['mirrored']}/{m['listed']} files mirrored, missing {len(m['missing'])}, "
            f"SHA mismatch {len(m['sha_mismatch'])}"
        )
        print(f"  blocked network attempts: {r['blocked_attempts'] or 'none'}")
        print("OFFLINE CHECK", "PASSED" if r["ok"] else "FAILED")
        return 0 if r["ok"] else 1
    print("usage: python -m ember.demo [precache|check]")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
