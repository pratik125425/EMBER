"""Clean CSV/Parquet export of the curated registry + data dictionary (spec §9.9, §13 Registry).

    uv run python -m ember.export            # → exports/

Rules the export keeps:
* Units live in column names (``x_o2_min`` is a mole fraction, ``p_kpa_min`` is kPa, ``u_cms_min``
  is cm/s). Nothing is converted here; the registry is already in canonical units.
* Every condition keeps its ``*_status`` (known / unknown / not_applicable) and its provenance
  (``*_source_id``, ``*_source_locator``). Unknown numbers are empty cells, never imputed.
* ``x_o2_ambient_usable`` is False for burner/oxidizer-side O₂ (CFI-G inverse flames) so modelers do
  not treat it as an atmosphere.
* List fields are joined with "; " so CSV and Parquet hold identical values.
* Every column of every table is documented in ``data_dictionary.csv`` / ``.md``; a test enforces it.
"""

from __future__ import annotations

import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from ember.paths import MANIFEST_CSV, ROOT
from ember.registry import Registry, load_registry

EXPORT_DIR = ROOT / "exports"
LIST_SEP = "; "
TABLES = ("evidence", "measurements", "claims", "sources", "files", "relations")

_RANGE_DOC = {
    "x_o2": ("mole fraction (0–1)", "oxygen mole fraction"),
    "p_kpa": ("kPa", "total pressure"),
    "u_cms": ("cm/s", "imposed flow velocity"),
    "size_cm": ("cm", "characteristic sample size"),
}


def _range_rows(table: str) -> list[tuple[str, str, str, str]]:
    rows = []
    for k, (unit, what) in _RANGE_DOC.items():
        rows += [
            (
                table,
                f"{k}_min",
                unit,
                f"Lower end of the tested {what}. Empty unless status is known.",
            ),
            (
                table,
                f"{k}_max",
                unit,
                f"Upper end of the tested {what}. Equal to min for a single value.",
            ),
            (
                table,
                f"{k}_status",
                "—",
                f"known / unknown / not_applicable for the {what}. Unknown is never imputed.",
            ),
            (table, f"{k}_source_id", "—", f"Source of the {what} value (see sources.source_id)."),
            (
                table,
                f"{k}_source_locator",
                "—",
                f"Where in the source the {what} value is (table row, page, column).",
            ),
        ]
    return rows


DATA_DICTIONARY: list[tuple[str, str, str, str]] = [
    ("evidence", "evidence_id", "—", "Unique id of one test, test series or campaign envelope."),
    ("evidence", "investigation", "—", "Investigation name (e.g. BASS-II, Saffire-VI)."),
    (
        "evidence",
        "psi_id",
        "—",
        "NASA Physical Sciences Informatics id; empty for non-PSI sources.",
    ),
    (
        "evidence",
        "hardware_family",
        "—",
        "Flight hardware or facility (e.g. MSG, Saffire Flow Unit).",
    ),
    (
        "evidence",
        "fuel_class",
        "—",
        "thin_solid / thick_solid / liquid_droplet / gas_jet / gaseous_emulator / pyrolysis_source / ambient_dust.",
    ),
    ("evidence", "fuel_name", "—", "Material or fuel as named by the source."),
    ("evidence", "geometry", "—", "Sample geometry as named by the source."),
    (
        "evidence",
        "phenomena",
        "—",
        "Phenomena studied, '; '-separated (spread_opposed, extinction, …).",
    ),
    (
        "evidence",
        "gravity",
        "—",
        "microgravity / 1g / simulated_partial / unknown. PSI holds no partial-g data.",
    ),
    (
        "evidence",
        "o2_context",
        "—",
        "ambient / burner_oxidizer_flow / unknown: what the O₂ value describes.",
    ),
    (
        "evidence",
        "x_o2_ambient_usable",
        "boolean",
        "True only when X_O₂ is known AND describes the ambient atmosphere.",
    ),
    ("evidence", "flow_direction", "—", "opposed / concurrent / quiescent / coflow / unknown."),
    ("evidence", "diluent", "—", "Diluent gas when stated (N2, CO2, He, Xe)."),
    ("evidence", "enclosure_note", "—", "Enclosure or duct note that can confound comparisons."),
    (
        "evidence",
        "granularity",
        "—",
        "per_test_table / campaign_summary / paper_only (drives the quality prior Q).",
    ),
    ("evidence", "measurements", "—", "Canonical measurement names recorded, '; '-separated."),
    ("evidence", "tensions", "—", "Documented disagreements between sources, '; '-separated."),
    ("evidence", "sources", "—", "Source ids backing the record, '; '-separated."),
    *_range_rows("evidence"),
    ("measurements", "measurement_id", "—", "Unique id of the measurement."),
    ("measurements", "evidence_id", "—", "Evidence record it belongs to."),
    (
        "measurements",
        "quantity",
        "—",
        "Canonical name from the controlled vocabulary; the suffix names the unit.",
    ),
    ("measurements", "value", "see unit", "Single value. Empty when only a range is reported."),
    ("measurements", "min", "see unit", "Range lower end, when reported as a range."),
    ("measurements", "max", "see unit", "Range upper end, when reported as a range."),
    ("measurements", "unit", "—", "Unit of value/min/max."),
    ("measurements", "value_kind", "—", "measured / set_point / range / computed."),
    ("measurements", "context", "—", "ambient / burner / cabin / duct / unknown."),
    ("measurements", "source_id", "—", "Source of the value."),
    ("measurements", "source_locator", "—", "Where in the source the value is."),
    ("measurements", "note", "—", "Free-text note from curation."),
    ("claims", "claim_id", "—", "Unique id of the claim."),
    ("claims", "evidence_id", "—", "Evidence record it is attached to; empty for general claims."),
    ("claims", "text", "—", "Claim text as stated or paraphrased from the source."),
    (
        "claims",
        "claim_type",
        "—",
        "measured / derived / modeled / author_interpretation / system_inference.",
    ),
    ("claims", "source_id", "—", "Source of the claim."),
    ("claims", "source_locator", "—", "Where in the source the claim is."),
    ("sources", "source_id", "—", "Unique id (PSI-25, NTRS-20240002981, …)."),
    ("sources", "kind", "—", "psi_record / psi_file / ntrs / journal / challenge / other."),
    ("sources", "title", "—", "Title of the source."),
    ("sources", "year", "year", "Publication or release year when known."),
    ("sources", "url", "—", "Landing page or download URL."),
    ("sources", "doi", "—", "DOI when known."),
    ("sources", "in_psi", "boolean", "True if the source is part of NASA PSI."),
    (
        "sources",
        "n_files_mirrored",
        "count",
        "Files of this source mirrored locally with a SHA-256 (see files).",
    ),
    (
        "sources",
        "n_evidence_citing",
        "count",
        "Evidence records that list this source or take a condition from it.",
    ),
    ("files", "source_id", "—", "Source the file belongs to."),
    ("files", "path", "—", "Local mirror path; empty when the file is not mirrored."),
    ("files", "url", "—", "URL the file was downloaded from."),
    ("files", "sha256", "—", "SHA-256 of the mirrored file."),
    ("files", "retrieved_at", "UTC ISO-8601", "Download time."),
    ("files", "http_status", "—", "HTTP status of the download; empty when not attempted."),
    ("files", "kind", "—", "record / document / table / matrix."),
    ("relations", "relation_id", "—", "Unique id of the relation."),
    ("relations", "from_id", "—", "Entity the relation starts at."),
    ("relations", "to_id", "—", "Entity the relation points to."),
    (
        "relations",
        "kind",
        "—",
        "shared_hardware / instrument_link / reflight / related_study / other.",
    ),
    ("relations", "source_id", "—", "Source stating the relation."),
    ("relations", "note", "—", "Free-text note."),
]


def dictionary_frame() -> pd.DataFrame:
    return pd.DataFrame(DATA_DICTIONARY, columns=["table", "column", "unit", "description"])


def _join(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, str):
        return v
    try:
        return LIST_SEP.join(str(x) for x in v)
    except TypeError:
        return str(v)


def manifest_frame(path: Path = MANIFEST_CSV) -> pd.DataFrame:
    m = pd.read_csv(path, dtype={"http_status": "Int64"})
    return m[["source_id", "path", "url", "sha256", "retrieved_at", "http_status", "kind"]]


def citing_evidence(reg: Registry) -> dict[str, set[str]]:
    """source_id → evidence ids that list it or take a condition value from it."""
    out: dict[str, set[str]] = {}
    for e in reg.evidence:
        ids = set(e.sources)
        for r in (e.x_o2, e.p_kpa, e.u_cms, e.size_cm):
            if r is not None and r.source_id:
                ids.add(r.source_id)
        for sid in ids:
            out.setdefault(sid, set()).add(e.evidence_id)
    return out


def tables(reg: Registry | None = None, manifest: Path = MANIFEST_CSV) -> dict[str, pd.DataFrame]:
    reg = reg or load_registry()
    ev = reg.frames["evidence"].copy()
    for c in ("phenomena", "measurements", "tensions", "sources"):
        ev[c] = ev[c].map(_join)
    # A value held next to a non-known status (e.g. an unconfirmed "air" placeholder in the seed) is
    # not data: blank it so the export never carries a number the registry does not stand behind.
    for k in _RANGE_DOC:
        nk = ev[f"{k}_status"] != "known"
        ev.loc[nk, [f"{k}_min", f"{k}_max"]] = None
    ev.insert(
        ev.columns.get_loc("o2_context") + 1,
        "x_o2_ambient_usable",
        (ev["x_o2_status"] == "known") & (ev["o2_context"] != "burner_oxidizer_flow"),
    )
    files = manifest_frame(manifest)
    cites = citing_evidence(reg)
    src = reg.frames["sources"].drop(columns=["sha256", "retrieved_at"], errors="ignore").copy()
    mirrored = files[files["sha256"].notna()].groupby("source_id").size()
    src["n_files_mirrored"] = src["source_id"].map(mirrored).fillna(0).astype(int)
    src["n_evidence_citing"] = src["source_id"].map(lambda s: len(cites.get(s, ()))).astype(int)
    return {
        "evidence": ev.reset_index(drop=True),
        "measurements": reg.frames["measurements"].reset_index(drop=True),
        "claims": reg.frames["claims"].reset_index(drop=True),
        "sources": src.reset_index(drop=True),
        "files": files.reset_index(drop=True),
        "relations": reg.frames["relations"].reset_index(drop=True),
    }


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def to_parquet_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    return buf.getvalue()


def dictionary_markdown() -> str:
    lines = [
        "# EMBER registry export: data dictionary",
        "",
        "Units are in column names and in the unit column. Empty cells mean the value is not known; "
        "the matching `*_status` column says why. Nothing is imputed.",
        "",
    ]
    for t in TABLES:
        lines += [f"## {t}", "", "| column | unit | description |", "|---|---|---|"]
        lines += [f"| `{c}` | {u} | {d} |" for tt, c, u, d in DATA_DICTIONARY if tt == t]
        lines.append("")
    return "\n".join(lines)


def write_exports(out_dir: Path = EXPORT_DIR, reg: Registry | None = None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    t = tables(reg)
    written: dict[str, str] = {}

    def save(name: str, data: bytes) -> None:
        (out_dir / name).write_bytes(data)
        written[name] = hashlib.sha256(data).hexdigest()

    for name, df in t.items():
        save(f"{name}.csv", to_csv_bytes(df))
        save(f"{name}.parquet", to_parquet_bytes(df))
    save("data_dictionary.csv", to_csv_bytes(dictionary_frame()))
    save("data_dictionary.md", dictionary_markdown().encode("utf-8"))
    summary = {
        "created": datetime.now(UTC).isoformat(timespec="seconds"),
        "rows": {k: len(v) for k, v in t.items()},
        "files": written,
    }
    (out_dir / "export_manifest.json").write_text(json.dumps(summary, indent=1))
    return summary


def main() -> int:
    s = write_exports()
    print(f"→ {EXPORT_DIR}")
    for k, n in s["rows"].items():
        print(f"  {k:<13} {n:>5} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
