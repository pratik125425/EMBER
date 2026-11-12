"""PSI (Physical Sciences Informatics) client.

PSI has no documented public API. The Angular front end at psi.nasa.gov/physci/repo calls these
endpoints (observed 2026-11-11 by watching the record page's network traffic):

  GET  https://psi.nasa.gov/geode-py/ws/repo/investigations/{PSI-ID}
       → JSON: doi, projectTitle, description, objective, approach, hypothesis, experimentHardware,
         experimentalTable [{file_name, version}], added [{file_name, version, ...}], publications
  GET  https://psi.nasa.gov/geode-py/ws/studies/{PSI-ID}/download?file={name}&version={v}&redirect=false
       → text/plain body: a time-limited signed S3 URL for the file

These are undocumented and may change; every call is logged by the downloader with its HTTP
status, and nothing in the app depends on live access (spec §0.8).
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

BASE = "https://psi.nasa.gov/geode-py/ws"
RECORD_URL = "https://psi.nasa.gov/physci/repo/data/investigations/{psi_id}"
TIMEOUT = httpx.Timeout(60.0, read=300.0)


def record_page_url(psi_id: str) -> str:
    return RECORD_URL.format(psi_id=psi_id)


def investigation_url(psi_id: str) -> str:
    return f"{BASE}/repo/investigations/{psi_id}"


def download_request_url(psi_id: str, file_name: str, version: int = 1) -> str:
    return (
        f"{BASE}/studies/{psi_id}/download?file={quote(file_name)}&version={version}&redirect=false"
    )


def investigation(psi_id: str, client: httpx.Client | None = None) -> dict[str, Any]:
    c = client or httpx.Client(timeout=TIMEOUT, follow_redirects=True)
    try:
        r = c.get(investigation_url(psi_id))
        r.raise_for_status()
        return r.json()
    finally:
        if client is None:
            c.close()


def signed_url(
    psi_id: str, file_name: str, version: int = 1, client: httpx.Client | None = None
) -> str:
    c = client or httpx.Client(timeout=TIMEOUT, follow_redirects=True)
    try:
        r = c.get(download_request_url(psi_id, file_name, version))
        r.raise_for_status()
        url = r.text.strip()
        if not url.startswith("http"):
            raise ValueError(f"unexpected download response for {file_name}: {url[:120]!r}")
        return url
    finally:
        if client is None:
            c.close()


def experimental_tables(meta: dict[str, Any]) -> list[tuple[str, int]]:
    return [
        (t["file_name"], int(t.get("version") or 1)) for t in (meta.get("experimentalTable") or [])
    ]


def listed_files(meta: dict[str, Any]) -> list[dict[str, Any]]:
    return [a for a in (meta.get("added") or []) if isinstance(a, dict) and a.get("file_name")]


def record_summary(meta: dict[str, Any]) -> dict[str, Any]:
    """The fields the registry/UI cares about, pulled out of the large record JSON."""
    pubs = meta.get("publications") or []
    return {
        "psi_id": meta.get("accession") or meta.get("projectIdentifier"),
        "doi": meta.get("doi"),
        "title": meta.get("projectTitle") or meta.get("investigationAcronym"),
        "acronym": meta.get("investigationAcronym"),
        "description": meta.get("description"),
        "objective": meta.get("objective"),
        "approach": meta.get("approach"),
        "hypothesis": meta.get("hypothesis"),
        "hardware": meta.get("experimentHardware"),
        "license": meta.get("licenseIdentifier"),
        "mission": meta.get("missionName"),
        "start": meta.get("investigationStartDate"),
        "end": meta.get("investigationEndDate"),
        "n_files": len(listed_files(meta)),
        "experimental_tables": experimental_tables(meta),
        "publications": [
            {"title": p.get("title"), "doi": p.get("doi")} for p in pubs if isinstance(p, dict)
        ],
    }
