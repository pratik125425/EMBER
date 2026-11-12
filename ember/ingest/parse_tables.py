"""Generic table loading, sentinel handling and inspection (spec §9.3, ticket T11).

    uv run python -m ember.ingest.parse_tables inspect data/raw/PSI-25/"PSI-25_Experimental table_BASS-II.csv"
    uv run python -m ember.ingest.parse_tables parse  <file> [--out data/parsed/<name>.parquet]

Raw strings are kept beside parsed values: for every column ``<col>`` the parsed Parquet holds
``<col>`` (numeric where the column is mostly numeric, else string) and ``<col>__raw`` (the exact
cell text). Sentinels (``-``, ``n/a``, ``NA``, ``#DIV/0!``, ``-999``, blank) become null and are
counted per column, never silently coerced to 0.

Per-investigation parsers (table → Evidence rows) are deliberately NOT written until the real
columns have been inspected and confirmed (spec §15, T11 rule).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from ember.paths import DATA_DIR

PARSED_DIR = DATA_DIR / "parsed"
SENTINELS = {
    "",
    "-",
    "--",
    "—",
    "n/a",
    "na",
    "n.a.",
    "none",
    "nan",
    "null",
    "#div/0!",
    "#n/a",
    "#value!",
    "-999",
    "-999.0",
    "?",
}
NUMERIC_RE = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")


def is_sentinel(s: str) -> bool:
    return s.strip().lower() in SENTINELS


def to_number(s: str) -> float | None:
    t = s.strip().replace(",", "")
    if is_sentinel(t):
        return None
    t = t.rstrip("%").strip()
    if NUMERIC_RE.match(t):
        return float(t)
    return None


def load_raw(path: Path, sheet: str | int | None = 0) -> pd.DataFrame:
    """Load csv/tsv/xlsx/xls as strings, exactly as written (no NA inference)."""
    suf = path.suffix.lower()
    if suf in (".csv", ".txt", ".tsv"):
        sep = "\t" if suf == ".tsv" else None
        # PSI CSVs are mostly UTF-8 (some with a BOM); FLEX is Windows-1252 (0x96 = en dash).
        encoding = "utf-8-sig"
        try:
            path.read_bytes().decode("utf-8-sig")
        except UnicodeDecodeError:
            encoding = "cp1252"
        df = pd.read_csv(
            path,
            dtype=str,
            keep_default_na=False,
            na_filter=False,
            sep=sep,
            engine="python",
            encoding=encoding,
        )
    elif suf in (".xlsx", ".xlsm", ".xls"):
        df = pd.read_excel(
            path, dtype=str, keep_default_na=False, na_filter=False, sheet_name=sheet
        )
    else:
        raise ValueError(f"unsupported table type: {path.suffix}")
    df.columns = [str(c).strip() for c in df.columns]
    return df.map(lambda v: "" if v is None else str(v).strip())


def inspect(path: Path, sheet: str | int | None = 0, examples: int = 3) -> dict[str, Any]:
    df = load_raw(path, sheet)
    cols = []
    for c in df.columns:
        vals = df[c].tolist()
        nums = [to_number(v) for v in vals]
        n_num = sum(1 for n in nums if n is not None)
        n_sent = sum(1 for v in vals if is_sentinel(v))
        n_text = len(vals) - n_num - n_sent
        guess = "numeric" if n_num >= 0.5 * max(1, len(vals) - n_sent) and n_num > 0 else "text"
        finite = [n for n in nums if n is not None]
        cols.append(
            {
                "name": c,
                "guess": guess,
                "n_numeric": n_num,
                "n_sentinel": n_sent,
                "n_text": n_text,
                "min": min(finite) if finite else None,
                "max": max(finite) if finite else None,
                "examples": [v for v in vals if v and not is_sentinel(v)][:examples],
                "n_unique": len(set(vals)),
            }
        )
    sheets = None
    if path.suffix.lower() in (".xlsx", ".xlsm", ".xls"):
        sheets = pd.ExcelFile(path).sheet_names
    return {
        "file": str(path),
        "rows": int(len(df)),
        "n_columns": len(df.columns),
        "sheets": sheets,
        "columns": cols,
    }


def parse(path: Path, sheet: str | int | None = 0) -> pd.DataFrame:
    """Raw strings beside parsed values; sentinel → null. Adds source_file and row_index."""
    raw = load_raw(path, sheet)
    out = pd.DataFrame({"source_file": path.name, "row_index": range(len(raw))})
    for c in raw.columns:
        vals = raw[c].tolist()
        nums = [to_number(v) for v in vals]
        n_num = sum(1 for n in nums if n is not None)
        n_sent = sum(1 for v in vals if is_sentinel(v))
        if n_num > 0 and n_num >= 0.5 * max(1, len(vals) - n_sent):
            out[c] = pd.array(nums, dtype="Float64")
        else:
            out[c] = [None if is_sentinel(v) else v for v in vals]
        out[f"{c}__raw"] = vals
    return out


def parse_to_parquet(
    path: Path, out: Path | None = None, sheet: str | int | None = 0
) -> tuple[Path, int]:
    df = parse(path, sheet)
    out = out or PARSED_DIR / (re.sub(r"[^A-Za-z0-9_.-]+", "_", path.stem) + ".parquet")
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    return out, len(df)


def print_inspection(info: dict[str, Any]) -> None:
    print(
        f"{info['file']}\n  rows={info['rows']} columns={info['n_columns']}"
        + (f" sheets={info['sheets']}" if info.get("sheets") else "")
    )
    for c in info["columns"]:
        rng = f" range=[{c['min']:g}, {c['max']:g}]" if c["min"] is not None else ""
        print(
            f"  - {c['name']!r}: {c['guess']} (num={c['n_numeric']}, sentinel={c['n_sentinel']}, text={c['n_text']}, unique={c['n_unique']}){rng} e.g. {c['examples']}"
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("inspect")
    p1.add_argument("file", type=Path)
    p1.add_argument("--sheet", default=0)
    p1.add_argument("--json", action="store_true")
    p2 = sub.add_parser("parse")
    p2.add_argument("file", type=Path)
    p2.add_argument("--out", type=Path, default=None)
    p2.add_argument("--sheet", default=0)
    a = ap.parse_args(argv)
    sheet = int(a.sheet) if str(a.sheet).isdigit() else a.sheet
    if a.cmd == "inspect":
        info = inspect(a.file, sheet)
        print(json.dumps(info, indent=1, default=str)) if a.json else print_inspection(info)
    else:
        out, n = parse_to_parquet(a.file, a.out, sheet)
        print(f"wrote {out} ({n} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
