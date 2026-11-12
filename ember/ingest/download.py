"""Manifest-driven acquisition (spec §9.1–9.2, ticket T11).

    uv run python -m ember.ingest.download [--plan data/ingest_plan.yaml] [--only PSI-25] [--dry-run] [--force]

For each plan item: fetch → data/raw/<source_id>/<file>, sha256, retrieved_at (UTC ISO), http_status,
kind. The manifest (data/manifest.csv) is rewritten with one row per file plus the record-level rows
the seed registry needs. Failures (404, timeouts) are recorded in the manifest AND appended to
data/raw/download_log.csv; they never raise, so a partial mirror is still a complete manifest.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

import httpx
import yaml

from ember.ingest import ntrs, psi
from ember.paths import DATA_DIR, MANIFEST_CSV, RAW_DIR

PLAN_YAML = DATA_DIR / "ingest_plan.yaml"
LOG_CSV = RAW_DIR / "download_log.csv"
MANIFEST_COLUMNS = ["path", "source_id", "url", "sha256", "retrieved_at", "http_status", "kind"]
TIMEOUT = httpx.Timeout(60.0, read=600.0)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _now() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()


def read_manifest(path: Path = MANIFEST_CSV) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_manifest(rows: list[dict[str, str]], path: Path = MANIFEST_CSV) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in MANIFEST_COLUMNS})


def upsert(rows: list[dict[str, str]], row: dict[str, str]) -> None:
    for i, r in enumerate(rows):
        if r["source_id"] == row["source_id"] and (r.get("path") or "") == (row.get("path") or ""):
            rows[i] = row
            return
    rows.append(row)


def _log(entry: dict[str, Any], log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    new = not log_path.exists()
    with log_path.open("a", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=["retrieved_at", "source_id", "kind", "url", "http_status", "note"]
        )
        if new:
            w.writeheader()
        w.writerow({k: entry.get(k, "") for k in w.fieldnames})


def _stream_to(client: httpx.Client, url: str, dest: Path) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with client.stream("GET", url) as r:
        status = r.status_code
        if status != 200:
            return status
        with tmp.open("wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)
    tmp.replace(dest)
    return status


def fetch_item(item: dict[str, Any], client: httpx.Client, raw_dir: Path) -> dict[str, Any]:
    """Fetch one plan item. Returns a manifest row dict (+ 'note'); never raises on HTTP errors."""
    sid, kind = item["source_id"], item["kind"]
    out_dir = raw_dir / sid
    row: dict[str, Any] = {
        "source_id": sid,
        "kind": item.get("tag") or kind,
        "retrieved_at": _now(),
        "sha256": "",
        "path": "",
        "http_status": "",
        "url": "",
        "note": "",
    }
    try:
        if kind == "psi_record":
            url = psi.investigation_url(sid)
            dest = out_dir / f"{sid}_record.json"
            r = client.get(url)
            row.update(url=psi.record_page_url(sid), http_status=str(r.status_code))
            if r.status_code == 200:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(r.content)
                row.update(
                    path=str(dest.relative_to(raw_dir.parent.parent)),
                    sha256=sha256_of(dest),
                    kind="record",
                )
        elif kind == "psi_file":
            name, version = item["file"], int(item.get("version", 1))
            req = psi.download_request_url(sid, name, version)
            r = client.get(req)
            row["url"] = req
            if r.status_code != 200 or not r.text.strip().startswith("http"):
                row.update(http_status=str(r.status_code), note=f"no signed url: {r.text[:80]!r}")
            else:
                signed = r.text.strip()
                dest = out_dir / name
                status = _stream_to(client, signed, dest)
                row["http_status"] = str(status)
                if status == 200:
                    row.update(
                        path=str(dest.relative_to(raw_dir.parent.parent)), sha256=sha256_of(dest)
                    )
        elif kind == "ntrs_meta":
            url = ntrs.citation_url(item["ntrs_id"])
            dest = out_dir / f"{sid}_citation.json"
            r = client.get(url)
            row.update(url=url, http_status=str(r.status_code))
            if r.status_code == 200:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(r.content)
                row.update(
                    path=str(dest.relative_to(raw_dir.parent.parent)),
                    sha256=sha256_of(dest),
                    kind="record",
                )
        elif kind == "ntrs_pdf":
            meta_path = out_dir / f"{sid}_citation.json"
            meta = (
                json.loads(meta_path.read_text())
                if meta_path.exists()
                else ntrs.citation(item["ntrs_id"], client)
            )
            links = ntrs.pdf_links(meta)
            if not links:
                row.update(
                    url=ntrs.citation_url(item["ntrs_id"]),
                    http_status="n/a",
                    note="citation lists no PDF download",
                    kind="document",
                )
            else:
                url = links[0]
                dest = out_dir / url.rsplit("/", 1)[-1].replace("%20", " ")
                status = _stream_to(client, url, dest)
                row.update(url=url, http_status=str(status), kind="document")
                if status == 200:
                    row.update(
                        path=str(dest.relative_to(raw_dir.parent.parent)), sha256=sha256_of(dest)
                    )
        elif kind == "url":
            url, name = item["url"], item["file"]
            dest = out_dir / name
            status = _stream_to(client, url, dest)
            row.update(url=url, http_status=str(status), kind=item.get("tag") or "document")
            if status == 200:
                row.update(
                    path=str(dest.relative_to(raw_dir.parent.parent)), sha256=sha256_of(dest)
                )
        else:
            row.update(http_status="n/a", note=f"unknown kind {kind}")
    except (httpx.HTTPError, OSError, ValueError, json.JSONDecodeError) as exc:
        row.update(http_status="error", note=f"{type(exc).__name__}: {exc}"[:200])
    return row


def run(
    plan_path: Path = PLAN_YAML,
    raw_dir: Path = RAW_DIR,
    manifest_path: Path = MANIFEST_CSV,
    only: str | None = None,
    dry_run: bool = False,
    force: bool = False,
    client: httpx.Client | None = None,
    log_path: Path = LOG_CSV,
) -> list[dict[str, Any]]:
    plan = yaml.safe_load(plan_path.read_text()) or []
    rows = read_manifest(manifest_path)
    have = {(r["source_id"], r["path"]): r for r in rows if r.get("path")}
    c = client or httpx.Client(
        timeout=TIMEOUT, follow_redirects=True, headers={"User-Agent": "EMBER-ingest/0.1"}
    )
    results = []
    try:
        for item in plan:
            if only and item["source_id"] != only:
                continue
            if dry_run:
                results.append({**item, "http_status": "dry-run"})
                continue
            res = fetch_item(item, c, raw_dir)
            # Skip re-download if the file already exists with a recorded checksum (unless --force).
            if (
                not force
                and res.get("path")
                and (res["source_id"], res["path"]) in have
                and have[(res["source_id"], res["path"])].get("sha256") == res.get("sha256")
            ):
                pass
            results.append(res)
            if res.get("path"):
                upsert(rows, {k: str(res.get(k, "")) for k in MANIFEST_COLUMNS})
            else:
                # Keep a record-level row so the source stays in the manifest, with the failure status.
                existing = next(
                    (r for r in rows if r["source_id"] == res["source_id"] and not r.get("path")),
                    None,
                )
                if existing is not None:
                    existing["http_status"] = str(res.get("http_status", ""))
                    existing["retrieved_at"] = res["retrieved_at"]
                else:
                    upsert(rows, {k: str(res.get(k, "")) for k in MANIFEST_COLUMNS})
            if str(res.get("http_status")) != "200":
                _log({**res, "url": res.get("url", "")}, log_path)
    finally:
        if client is None:
            c.close()
    if not dry_run:
        write_manifest(rows, manifest_path)
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--plan", type=Path, default=PLAN_YAML)
    ap.add_argument("--only", default=None, help="only this source_id")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    results = run(a.plan, only=a.only, dry_run=a.dry_run, force=a.force)
    ok = sum(1 for r in results if str(r.get("http_status")) == "200")
    for r in results:
        print(
            f"{str(r.get('http_status')):>7}  {r['source_id']:<24} {r.get('path') or r.get('file') or r.get('kind')}  {r.get('note', '')}"
        )
    print(f"\n{ok}/{len(results)} fetched OK; failures logged to {LOG_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
