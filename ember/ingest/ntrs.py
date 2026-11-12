"""NASA Technical Reports Server (NTRS) client (spec §4.1).

GET https://ntrs.nasa.gov/api/citations/search?q=<query>
GET https://ntrs.nasa.gov/api/citations/<id>
PDF: https://ntrs.nasa.gov/api/citations/<id>/downloads/<name>  (listed in the citation's "downloads")
"""

from __future__ import annotations

from typing import Any

import httpx

BASE = "https://ntrs.nasa.gov/api/citations"
TIMEOUT = httpx.Timeout(60.0, read=300.0)


def citation_url(ntrs_id: str | int) -> str:
    return f"{BASE}/{ntrs_id}"


def search_url(query: str, size: int = 10) -> str:
    return f"{BASE}/search?q={httpx.QueryParams({'q': query})['q']}&page.size={size}"


def citation(ntrs_id: str | int, client: httpx.Client | None = None) -> dict[str, Any]:
    c = client or httpx.Client(timeout=TIMEOUT, follow_redirects=True)
    try:
        r = c.get(citation_url(ntrs_id))
        r.raise_for_status()
        return r.json()
    finally:
        if client is None:
            c.close()


def search(query: str, size: int = 10, client: httpx.Client | None = None) -> list[dict[str, Any]]:
    c = client or httpx.Client(timeout=TIMEOUT, follow_redirects=True)
    try:
        r = c.get(f"{BASE}/search", params={"q": query, "page.size": size})
        r.raise_for_status()
        return r.json().get("results", [])
    finally:
        if client is None:
            c.close()


def pdf_links(meta: dict[str, Any]) -> list[str]:
    """Absolute URLs of downloadable PDFs listed in a citation record."""
    out = []
    for d in meta.get("downloads") or []:
        links = d.get("links") or {}
        for key in ("pdf", "original"):
            link = links.get(key)
            if link and link.lower().endswith(".pdf"):
                out.append(link if link.startswith("http") else "https://ntrs.nasa.gov" + link)
    return list(dict.fromkeys(out))


def citation_summary(meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "ntrs_id": meta.get("id")
        if isinstance(meta.get("id"), int)
        else meta.get("submissionId") or meta.get("copyright", {}).get("submissionId"),
        "title": meta.get("title"),
        "year": (meta.get("distributionDate") or meta.get("publicationDate") or "")[:4] or None,
        "type": meta.get("stiType"),
        "authors": [
            a.get("meta", {}).get("author", {}).get("name")
            for a in meta.get("authorAffiliations") or []
        ],
        "report_numbers": meta.get("otherReportNumbers") or [],
        "abstract": meta.get("abstract"),
        "pdfs": pdf_links(meta),
    }
