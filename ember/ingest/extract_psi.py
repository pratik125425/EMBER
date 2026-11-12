"""Per-investigation parsers: PSI experimental tables → Evidence + Measurement rows (ticket T11).

    uv run python -m ember.ingest.extract_psi        # reads data/raw, writes data/extracted/*.jsonl

Every known value carries ``source_id`` = the PSI record and a ``source_locator`` of the form
``<file> · data row <n> · col '<column>'`` (n is 1-based, header excluded). Nothing is imputed:
a blank, sentinel or unparsable cell leaves the condition ``unknown``. Column mappings were reviewed
against the real files on 2026-11-11 (see the T11 summary); deviations from the spec are noted inline.

Output (committed, so the registry rebuilds without re-downloading):
    data/extracted/evidence_<PSI-ID>.jsonl, measurements_<PSI-ID>.jsonl, extraction_report.json
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from ember.ingest.parse_tables import is_sentinel, load_raw, to_number
from ember.paths import DATA_DIR, RAW_DIR
from ember.schemas import Evidence, Measurement, Range
from ember.units import convert

EXTRACTED_DIR = DATA_DIR / "extracted"
UNK = Range(status="unknown")
NA = Range(status="not_applicable")


@dataclass
class Extraction:
    psi_id: str
    file: str
    rows_in: int = 0
    evidence: list[Evidence] = field(default_factory=list)
    measurements: list[Measurement] = field(default_factory=list)
    skipped: Counter = field(default_factory=Counter)  # reason -> count
    unknown_cells: Counter = field(
        default_factory=Counter
    )  # condition -> count of rows left unknown
    notes: list[str] = field(default_factory=list)

    def report(self) -> dict:
        return {
            "psi_id": self.psi_id,
            "file": self.file,
            "rows_in": self.rows_in,
            "evidence_out": len(self.evidence),
            "measurements_out": len(self.measurements),
            "skipped": dict(self.skipped),
            "left_unknown": dict(self.unknown_cells),
            "notes": self.notes,
        }


# ------------------------------------------------------------------------------------ helpers
def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def col(df: pd.DataFrame, name: str) -> str:
    """Find a column by whitespace/case-insensitive name (PSI headers contain doubled spaces)."""
    want = _norm(name)
    for c in df.columns:
        if _norm(c) == want:
            return c
    raise KeyError(f"column {name!r} not found; have {list(df.columns)}")


def loc(fname: str, i: int, *cols: str) -> str:
    label = "col" if len(cols) == 1 else "cols"
    return f"{fname} · data row {i + 1} · {label} " + ", ".join(repr(_norm_header(c)) for c in cols)


def _norm_header(c: str) -> str:
    return re.sub(r"\s+", " ", c.strip())


def point(v: float, sid: str, locator: str) -> Range:
    return Range(min=v, max=v, status="known", source_id=sid, source_locator=locator)


def span(a: float, b: float, sid: str, locator: str) -> Range:
    return Range(
        min=min(a, b), max=max(a, b), status="known", source_id=sid, source_locator=locator
    )


def clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "", s.replace(" ", ""))


class IdMaker:
    def __init__(self, prefix: str):
        self.prefix, self.seen = prefix, set()

    def __call__(self, key: str, i: int) -> str:
        base = f"{self.prefix}{slug(key) or f'row{i + 1}'}"
        eid = base if base not in self.seen else f"{base}#r{i + 1}"
        self.seen.add(eid)
        return eid


THIN_WORDS = ("sibal", "nomex", "fabric", "cotton", "paper", "cellulose", "micron", "film", "sheet")
THICK_WORDS = (
    "rod",
    "sphere",
    "spherical",
    "slab",
    "candle",
    "wax",
    "mm thick",
    "pmma",
    "cylinder",
)


def fuel_class_from_text(t: str) -> str:
    """Thin vs thick from the material text as written. Thin wins (films/fabrics/sheets)."""
    s = t.lower()
    if any(w in s for w in THIN_WORDS):
        return "thin_solid"
    if any(w in s for w in THICK_WORDS):
        return "thick_solid"
    return "thick_solid"


def flow_direction_from_text(t: str) -> str:
    s = t.lower()
    if "opposed" in s or "oppsed" in s:
        return "opposed"
    if "concurrent" in s:
        return "concurrent"
    return "unknown"


# ------------------------------------------------------------------------------------ parsers
def parse_bass2(path: Path) -> Extraction:
    """PSI-25 BASS-II: O₂ from calibrated initial O₂ (% by vol). No pressure column; flow is recorded
    as fan/air display settings (needs the fan calibration file) → pressure and flow stay unknown."""
    sid, df = "PSI-25", load_raw(path)
    ex = Extraction(sid, path.name, len(df))
    c_test, c_mat, c_o2 = (
        col(df, "Test #"),
        col(df, "Fuel Sample Material"),
        col(df, "Calibrated initial O2 % by vol"),
    )
    mk = IdMaker("PSI-25:")
    ex.notes += [
        "pressure: no column in table → unknown",
        "flow: fan/air display only (uncalibrated) → unknown",
        "gravity: PSI-25 record projectType 'Microgravity Investigation', platform ISS",
    ]
    for i, r in df.iterrows():
        mat = clean_text(r[c_mat])
        o2 = to_number(r[c_o2])
        x = (
            point(convert(o2, "%", "dimensionless"), sid, loc(path.name, i, c_o2))
            if o2 is not None
            else UNK
        )
        if o2 is None:
            ex.unknown_cells["x_o2"] += 1
        ex.evidence.append(
            Evidence(
                evidence_id=mk(r[c_test], i),
                investigation="BASS-II",
                psi_id=sid,
                hardware_family="MSG+SPICE-duct",
                fuel_class=fuel_class_from_text(mat),
                fuel_name=mat or None,
                phenomena=["spread_opposed", "spread_concurrent", "extinction"],
                gravity="microgravity",
                x_o2=x,
                o2_context="ambient",
                p_kpa=UNK,
                u_cms=UNK,
                flow_direction="unknown",
                granularity="per_test_table",
                sources=[sid],
            )
        )
    ex.unknown_cells["p_kpa"] += len(df)
    ex.unknown_cells["u_cms"] += len(df)
    return ex


def parse_bass(path: Path) -> Extraction:
    """PSI-26 BASS: the experimental table lists only test and sample identity → conditions unknown."""
    sid, df = "PSI-26", load_raw(path)
    ex = Extraction(sid, path.name, len(df))
    c_run, c_test, c_mat = (
        col(df, "As Run Test #"),
        col(df, "Test #"),
        col(df, "Fuel Sample Material"),
    )
    mk = IdMaker("PSI-26:")
    ex.notes += [
        "no O2/pressure/flow columns → all conditions unknown (as-run test matrix xlsx not yet mapped)",
        "flow direction taken from the material note only when it says 'opposed'",
    ]
    for i, r in df.iterrows():
        mat = clean_text(r[c_mat])
        if "soot cleaning" in mat.lower():
            ex.skipped["not a burn test (soot cleaning)"] += 1
            continue
        key = r[c_run] if not is_sentinel(r[c_run]) else r[c_test]
        ex.evidence.append(
            Evidence(
                evidence_id=mk(key, i),
                investigation="BASS",
                psi_id=sid,
                hardware_family="MSG+SPICE-duct",
                fuel_class=fuel_class_from_text(mat),
                fuel_name=mat or None,
                phenomena=["ignition", "spread_opposed", "spread_concurrent", "extinction"],
                gravity="microgravity",
                x_o2=UNK,
                o2_context="ambient",
                p_kpa=UNK,
                u_cms=UNK,
                flow_direction=flow_direction_from_text(mat),
                granularity="per_test_table",
                sources=[sid],
            )
        )
    return ex


def parse_flex(path: Path) -> Extraction:
    """PSI-69 FLEX droplets. Header subscripts were lost in the CSV: 'O'→O₂, 'N'→N₂, 'CO'→CO₂
    (fractions up to 0.70 are CO₂ dilution), 'Burning rate; mm' → K in mm²/s."""
    sid, df = "PSI-69", load_raw(path)
    ex = Extraction(sid, path.name, len(df))
    c = {
        k: col(df, v)
        for k, v in {
            "test": "FLEX Test #",
            "ident": "FLEX Identifier",
            "fuel": "Fuel",
            "p": "Ambient pressure; mmHg",
            "o2": "O initial ambient composition; mole fraction",
            "n2": "N initial ambient composition; mole fraction",
            "co2": "CO initial ambient composition; mole fraction",
            "he": "He initial ambient composition; mole fraction",
            "d0": "Droplet initial diameter; mm",
            "dext": "Visible flame extinction diameter; mm",
            "k": "Burning rate; mm",
            "end": "Test end",
        }.items()
    }
    mk = IdMaker("PSI-69:T")
    ex.notes += [
        "header 'CO' read as CO2 and 'Burning rate; mm' as mm^2/s (subscripts/superscripts lost in CSV)",
        "ambient pressure 0 mmHg treated as missing",
        "flow: not stated in table or record → unknown",
        "gravity: PSI-69 record projectType 'Microgravity Investigation', platform ISS; table has no space/ground column",
        "extinction diameter is the VISIBLE-flame extinction diameter; cool flames can persist (not true extinction)",
    ]
    for i, r in df.iterrows():
        test = r[c["test"]]
        eid = mk(test.zfill(3) if test.isdigit() else test, i)
        o2 = to_number(r[c["o2"]])
        x = point(o2, sid, loc(path.name, i, c["o2"])) if o2 is not None else UNK
        p_mm = to_number(r[c["p"]])
        if p_mm is None or p_mm == 0:
            p = UNK
            ex.unknown_cells["p_kpa"] += 1
        else:
            p = point(
                round(convert(p_mm, "mmHg", "kPa"), 4),
                sid,
                loc(path.name, i, c["p"]) + " (mmHg→kPa)",
            )
        dil = [
            name
            for name, key in (("N2", "n2"), ("CO2", "co2"), ("He", "he"))
            if (to_number(r[c[key]]) or 0) > 0
        ]
        d0 = to_number(r[c["d0"]])
        size = (
            point(
                round(convert(d0, "mm", "cm"), 5),
                sid,
                loc(path.name, i, c["d0"]) + " (initial droplet diameter, mm→cm)",
            )
            if d0
            else None
        )
        end = r[c["end"]].strip().lower()
        phen = ["burning_rate"]
        if end == "extinction":
            phen.append("extinction")
        if {"CO2", "He"} & set(dil):
            phen.append("suppression")
        meas_names: list[str] = []
        k = to_number(r[c["k"]])
        if k is not None:
            ex.measurements.append(
                Measurement(
                    measurement_id=f"M-{eid}-K",
                    evidence_id=eid,
                    quantity="burning_rate_K_mm2_s",
                    value=k,
                    unit="mm**2/s",
                    value_kind="measured",
                    context="ambient",
                    source_id=sid,
                    source_locator=loc(path.name, i, c["k"]),
                    note="header unit 'mm' read as mm²/s (superscript lost)",
                )
            )
            meas_names.append("burning_rate_K_mm2_s")
        dext = to_number(r[c["dext"]])
        if end == "extinction" and dext is not None and dext > 0:
            ex.measurements.append(
                Measurement(
                    measurement_id=f"M-{eid}-dext",
                    evidence_id=eid,
                    quantity="extinction_diameter_mm",
                    value=dext,
                    unit="mm",
                    value_kind="measured",
                    context="ambient",
                    source_id=sid,
                    source_locator=loc(path.name, i, c["dext"]),
                    note="visible-flame extinction diameter; a cool flame may continue after visible flame-out",
                )
            )
            meas_names.append("extinction_diameter_mm")
        elif dext is not None and end != "extinction":
            ex.skipped["extinction diameter present but test end ≠ Extinction (not stored)"] += 1
        ex.evidence.append(
            Evidence(
                evidence_id=eid,
                investigation="FLEX",
                psi_id=sid,
                hardware_family="MDCA/CIR",
                fuel_class="liquid_droplet",
                fuel_name=r[c["fuel"]].strip() or None,
                geometry="single droplet",
                size_cm=size,
                phenomena=phen,
                gravity="microgravity",
                x_o2=x,
                o2_context="ambient",
                p_kpa=p,
                u_cms=UNK,
                flow_direction="unknown",
                diluent="+".join(dil) or None,
                granularity="per_test_table",
                measurements=meas_names,
                sources=[sid],
            )
        )
    return ex


def parse_cfig_normal(path: Path) -> Extraction:
    """PSI-159 CFI-G normal flames: fuel issues into the chamber → XO2 is the AMBIENT oxygen.
    O₂ falls during a test, so the range [after, before] is kept (ranges stay ranges)."""
    sid, df = "PSI-159", load_raw(path)
    ex = Extraction(sid, path.name, len(df))
    c_test, c_fuel, c_cool = col(df, "Test"), col(df, "Fuel"), col(df, "Cool flame?")
    c_b, c_a, c_p, c_se = (
        col(df, "XO2 before test"),
        col(df, "XO2 after test"),
        col(df, "approx p (bar)"),
        col(df, "Self-ext or flow term"),
    )
    mk = IdMaker("PSI-159:N:")
    ex.notes += [
        "x_o2 = [after, before] ambient mole fraction (o2_context ambient)",
        "pressure 'approx p (bar)' → kPa",
        "flow: fuel mass flow only (mg/s), no velocity → unknown",
        "cool_flame only where 'Cool flame?' starts with 'yes'",
        "extinction where 'Self-ext or flow term' = SE (self-extinguished)",
    ]
    for i, r in df.iterrows():
        b, a, pb = to_number(r[c_b]), to_number(r[c_a]), to_number(r[c_p])
        if b is not None and a is not None:
            x = span(a, b, sid, loc(path.name, i, c_b, c_a))
        elif b is not None:
            x = point(b, sid, loc(path.name, i, c_b))
        else:
            x = UNK
            ex.unknown_cells["x_o2"] += 1
        p = (
            point(round(convert(pb, "bar", "kPa"), 4), sid, loc(path.name, i, c_p) + " (bar→kPa)")
            if pb is not None
            else UNK
        )
        phen = ["flame_structure"]
        if r[c_cool].strip().lower().startswith("yes"):
            phen.append("cool_flame")
        if r[c_se].strip().upper() == "SE":
            phen.append("extinction")
        ex.evidence.append(
            Evidence(
                evidence_id=mk(r[c_test], i),
                investigation="ACME CFI-G",
                psi_id=sid,
                hardware_family="ACME/CIR",
                fuel_class="gas_jet",
                fuel_name=r[c_fuel].strip() + " (normal flame)",
                phenomena=phen,
                gravity="microgravity",
                x_o2=x,
                o2_context="ambient",
                p_kpa=p,
                u_cms=UNK,
                flow_direction="unknown",
                granularity="per_test_table",
                sources=[sid],
            )
        )
    ex.unknown_cells["u_cms"] += len(df)
    return ex


def parse_cfig_inverse(path: Path) -> Extraction:
    """PSI-159 CFI-G inverse flames: OXIDIZER issues from the burner into a fuel ambient → XO2 is
    burner/oxidizer-side oxygen (up to 0.85), NEVER cabin atmosphere. Stored with o2_context
    burner_oxidizer_flow; the engine excludes it from distance and the map never plots it."""
    sid, df = "PSI-159", load_raw(path)
    ex = Extraction(sid, path.name, len(df))
    c_test, c_fuel, c_o2 = col(df, "Test"), col(df, "Fuel"), col(df, "XO2")
    c_p, c_se = col(df, "approx p (bar)"), col(df, "Self -ext or flow term")
    mk = IdMaker("PSI-159:I:")
    ex.notes += [
        "XO2 = burner/oxidizer-side oxygen (o2_context burner_oxidizer_flow), never ambient",
        "blank spreadsheet rows skipped",
        "flow: mass flows only → unknown",
    ]
    for i, r in df.iterrows():
        if not r[c_test].strip():
            ex.skipped["blank spreadsheet row"] += 1
            continue
        o2, pb = to_number(r[c_o2]), to_number(r[c_p])
        x = (
            point(o2, sid, loc(path.name, i, c_o2) + " (burner/oxidizer-side)")
            if o2 is not None
            else UNK
        )
        p = (
            point(round(convert(pb, "bar", "kPa"), 4), sid, loc(path.name, i, c_p) + " (bar→kPa)")
            if pb is not None
            else UNK
        )
        phen = ["flame_structure"] + (["extinction"] if r[c_se].strip().upper() == "SE" else [])
        ex.evidence.append(
            Evidence(
                evidence_id=mk(r[c_test], i),
                investigation="ACME CFI-G",
                psi_id=sid,
                hardware_family="ACME/CIR",
                fuel_class="gas_jet",
                fuel_name=r[c_fuel].strip() + " (inverse flame)",
                phenomena=phen,
                gravity="microgravity",
                x_o2=x,
                o2_context="burner_oxidizer_flow",
                p_kpa=p,
                u_cms=UNK,
                flow_direction="unknown",
                granularity="per_test_table",
                sources=[sid],
            )
        )
    return ex


def parse_saffire3(path: Path) -> Extraction:
    """PSI-100 Saffire-III: 2 SIBAL samples, 30 cm/s, concurrent or opposed. O₂/P not in the table."""
    sid, df = "PSI-100", load_raw(path)
    ex = Extraction(sid, path.name, len(df))
    c = {
        k: col(df, v)
        for k, v in {
            "s": "Sample Number",
            "mat": "Material",
            "t": "Sample Thickness",
            "l": "Sample Length",
            "w": "Sample Width",
            "u": "Air Flow",
            "dir": "Direction",
        }.items()
    }
    mk = IdMaker("PSI-100:")
    ex.notes += [
        "O2 and pressure not in table → unknown",
        "enclosure note from the Saffire VI paper (NTRS-20240002981)",
    ]
    for i, r in df.iterrows():
        m = re.match(r"\s*([\d.]+)\s*(.+)", r[c["u"]])
        u = UNK
        if m:
            u = point(
                convert(float(m.group(1)), m.group(2).strip(), "cm/s"),
                sid,
                loc(path.name, i, c["u"]),
            )
        direction = flow_direction_from_text(r[c["dir"]])
        phen = {"concurrent": ["spread_concurrent"], "opposed": ["spread_opposed"]}.get(
            direction, ["spread_concurrent", "spread_opposed"]
        )
        ex.evidence.append(
            Evidence(
                evidence_id=mk(r[c["s"]], i),
                investigation="Saffire-III",
                psi_id=sid,
                hardware_family="Saffire Flow Unit/Cygnus",
                fuel_class="thin_solid",
                fuel_name=clean_text(r[c["mat"]]),
                geometry=f"{r[c['l']]} × {r[c['w']]} × {r[c['t']]} (L × W × thickness)",
                phenomena=phen,
                gravity="microgravity",
                x_o2=UNK,
                o2_context="ambient",
                p_kpa=UNK,
                u_cms=u,
                flow_direction=direction,
                enclosure_note="Duct half-height 25 cm (Saffire I–III)",
                granularity="per_test_table",
                sources=[sid, "NTRS-20240002981"],
            )
        )
    return ex


def parse_samer(path: Path) -> Extraction:
    """PSI-101 SAME-R: pyrolysis smoke runs; inlet velocity in cm/s. O₂ not applicable (seed convention), P unknown."""
    sid, df = "PSI-101", load_raw(path)
    ex = Extraction(sid, path.name, len(df))
    c_type, c_test, c_u = (
        col(df, "Sample Type"),
        col(df, "SAME Test #"),
        col(df, "Inlet velocity (cm/s)"),
    )
    mk = IdMaker("PSI-101:")
    ex.notes += [
        "x_o2 not applicable (pyrolysis smoke source; seed convention)",
        "pressure unknown",
    ]
    for i, r in df.iterrows():
        uv = to_number(r[c_u])
        u = point(uv, sid, loc(path.name, i, c_u)) if uv is not None else UNK
        ex.evidence.append(
            Evidence(
                evidence_id=mk(r[c_test], i),
                investigation="SAME-R",
                psi_id=sid,
                hardware_family="MSG",
                fuel_class="pyrolysis_source",
                fuel_name=r[c_type].strip() or None,
                phenomena=["smoke_particles", "detector_response"],
                gravity="microgravity",
                x_o2=NA,
                o2_context="unknown",
                p_kpa=UNK,
                u_cms=u,
                flow_direction="unknown",
                granularity="per_test_table",
                sources=[sid],
            )
        )
    return ex


PARSERS: list[tuple[str, str, Callable[[Path], Extraction]]] = [
    ("PSI-25", "PSI-25_Experimental table_BASS-II.csv", parse_bass2),
    ("PSI-26", "PSI-26_Experimental table_BASS.csv", parse_bass),
    ("PSI-69", "PSI-69_Experimental table_FLEX.csv", parse_flex),
    ("PSI-100", "PSI-100_Experimental table_SAFFIRE-3.csv", parse_saffire3),
    ("PSI-101", "PSI-101_Experimental table_SAME-R.csv", parse_samer),
    ("PSI-159", "PSI-159_Experimental table_CFI-G_Normal Flames.csv", parse_cfig_normal),
    ("PSI-159", "PSI-159_Experimental table_CFI-G_Inverse Flames.csv", parse_cfig_inverse),
]


def run(raw_dir: Path = RAW_DIR, out_dir: Path = EXTRACTED_DIR) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    by_psi: dict[str, list[Extraction]] = {}
    reports = []
    for psi_id, fname, fn in PARSERS:
        path = raw_dir / psi_id / fname
        if not path.exists():
            reports.append({"psi_id": psi_id, "file": fname, "missing": True})
            continue
        ex = fn(path)
        by_psi.setdefault(psi_id, []).append(ex)
        reports.append(ex.report())
    for psi_id, exs in by_psi.items():
        with (out_dir / f"evidence_{psi_id}.jsonl").open("w") as f:
            for ex in exs:
                for e in ex.evidence:
                    f.write(json.dumps(e.model_dump(mode="json"), ensure_ascii=False) + "\n")
        with (out_dir / f"measurements_{psi_id}.jsonl").open("w") as f:
            for ex in exs:
                for m in ex.measurements:
                    f.write(json.dumps(m.model_dump(mode="json"), ensure_ascii=False) + "\n")
    (out_dir / "extraction_report.json").write_text(
        json.dumps(reports, indent=1, ensure_ascii=False)
    )
    return reports


def load_extracted(out_dir: Path = EXTRACTED_DIR) -> tuple[list[Evidence], list[Measurement]]:
    ev, ms = [], []
    if out_dir is None or not out_dir.exists():
        return ev, ms
    for p in sorted(out_dir.glob("evidence_*.jsonl")):
        ev += [Evidence(**json.loads(line)) for line in p.read_text().splitlines() if line.strip()]
    for p in sorted(out_dir.glob("measurements_*.jsonl")):
        ms += [
            Measurement(**json.loads(line)) for line in p.read_text().splitlines() if line.strip()
        ]
    return ev, ms


def main() -> int:
    for r in run():
        if r.get("missing"):
            print(f"MISSING  {r['psi_id']:<8} {r['file']}  (run ember.ingest.download first)")
            continue
        print(
            f"{r['psi_id']:<8} {r['file'][:52]:<53} rows {r['rows_in']:>5} → evidence {r['evidence_out']:>4}, "
            f"measurements {r['measurements_out']:>4}  skipped {r['skipped'] or '-'}  unknown {r['left_unknown'] or '-'}"
        )
    print(f"\nwrote {EXTRACTED_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
