"""PDF page text with a persistent cache (spec §9.4 support, ticket T12).

pdfplumber is slow on graphics-heavy pages (the Saffire VI paper takes ~100 s), so each mirrored PDF
is extracted once into data/pdf_text/<source_id>.json, keyed by the PDF's SHA-256. The span check in
``ember.ingest.extract_llm`` runs against these cached pages, so it also works offline without data/raw.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pdfplumber

from ember.paths import DATA_DIR, MANIFEST_CSV, ROOT

PDF_TEXT_DIR = DATA_DIR / "pdf_text"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cache_path(source_id: str, cache_dir: Path = PDF_TEXT_DIR) -> Path:
    safe = source_id.replace("/", "_").replace(":", "_")
    return cache_dir / f"{safe}.json"


def page_texts(
    pdf_path: Path, source_id: str, cache_dir: Path = PDF_TEXT_DIR, force: bool = False
) -> list[str]:
    """Text of each page (1-based page n is element n-1). Cached by PDF hash."""
    cp = cache_path(source_id, cache_dir)
    sha = _sha256(pdf_path)
    if cp.exists() and not force:
        data = json.loads(cp.read_text())
        if data.get("sha256") == sha:
            return data["pages"]
    with pdfplumber.open(pdf_path) as pdf:
        pages = [pg.extract_text() or "" for pg in pdf.pages]
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_text(
        json.dumps(
            {"source_id": source_id, "file": pdf_path.name, "sha256": sha, "pages": pages},
            ensure_ascii=False,
            indent=0,
        )
    )
    return pages


def cached_pages(source_id: str, cache_dir: Path = PDF_TEXT_DIR) -> list[str] | None:
    cp = cache_path(source_id, cache_dir)
    if not cp.exists():
        return None
    return json.loads(cp.read_text())["pages"]


def mirrored_pdfs(manifest_path: Path = MANIFEST_CSV) -> list[tuple[str, Path]]:
    """(source_id, absolute path) for every PDF recorded in the manifest that exists on disk."""
    out = []
    if not manifest_path.exists():
        return out
    with manifest_path.open(newline="") as f:
        for row in csv.DictReader(f):
            p = row.get("path") or ""
            if p.lower().endswith(".pdf") and (ROOT / p).exists():
                out.append((row["source_id"], ROOT / p))
    return out
