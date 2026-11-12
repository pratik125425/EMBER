"""T11: ingest layer, fully offline (httpx mocked)."""

import csv
import json

import httpx
import pytest
import yaml

from ember.ingest import download, ntrs, parse_tables, psi


# ------------------------------------------------------------------------------ parse_tables
def test_parse_keeps_raw_strings_and_nulls_sentinels(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text(
        "Test #,O2 %,Flow,Note\nB1,22.2,5,ok\nB2,-,n/a,#DIV/0!\nB3,21.8,-999,fine\nB4,,2.5,\n"
    )
    df = parse_tables.parse(p)
    assert list(df["O2 %"]) == [22.2, None, 21.8, None] or df["O2 %"].isna().tolist() == [
        False,
        True,
        False,
        True,
    ]
    assert df["O2 %__raw"].tolist() == ["22.2", "-", "21.8", ""]
    assert df["Flow"].isna().tolist() == [False, True, True, False]  # -999 is a sentinel, never 0
    assert df["Note"].isna().tolist() == [False, True, False, True] and df["Note"].iloc[0] == "ok"
    assert df["source_file"].iloc[0] == "t.csv" and df["row_index"].tolist() == [0, 1, 2, 3]
    out, n = parse_tables.parse_to_parquet(p, tmp_path / "t.parquet")
    assert out.exists() and n == 4


def test_inspect_reports_columns(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text("a,b\n1,x\n2,y\n-,z\n")
    info = parse_tables.inspect(p)
    assert info["rows"] == 3 and info["n_columns"] == 2
    a = info["columns"][0]
    assert a["guess"] == "numeric" and a["n_sentinel"] == 1 and (a["min"], a["max"]) == (1.0, 2.0)
    assert info["columns"][1]["guess"] == "text"


# ------------------------------------------------------------------------------------- psi
def test_psi_helpers():
    meta = {
        "accession": "PSI-25",
        "doi": "10.60555/4qc4-de67",
        "experimentalTable": [{"file_name": "PSI-25_Experimental table_BASS-II.csv", "version": 1}],
        "added": [{"file_name": "a.mp4", "version": 2}],
        "publications": [{"title": "T", "doi": "d"}],
    }
    assert psi.experimental_tables(meta) == [("PSI-25_Experimental table_BASS-II.csv", 1)]
    assert (
        psi.record_summary(meta)["n_files"] == 1
        and psi.record_summary(meta)["publications"][0]["doi"] == "d"
    )
    assert psi.download_request_url("PSI-25", "PSI-25_Experimental table_BASS-II.csv", 1).endswith(
        "studies/PSI-25/download?file=PSI-25_Experimental%20table_BASS-II.csv&version=1&redirect=false"
    )


def test_ntrs_helpers():
    meta = {
        "title": "Saffire VI",
        "distributionDate": "2024-07-25T04:00:00",
        "stiType": "CONFERENCE_PAPER",
        "downloads": [
            {
                "links": {
                    "original": "/api/citations/20240002981/downloads/x.pdf",
                    "pdf": "/api/citations/20240002981/downloads/x.pdf",
                }
            }
        ],
    }
    assert ntrs.pdf_links(meta) == [
        "https://ntrs.nasa.gov/api/citations/20240002981/downloads/x.pdf"
    ]
    s = ntrs.citation_summary(meta)
    assert s["year"] == "2024" and s["pdfs"][0].endswith("x.pdf")


# -------------------------------------------------------------------------------- download
def _mock_client(routes):
    def handler(request: httpx.Request) -> httpx.Response:
        for prefix, (status, body, ctype) in routes.items():
            if str(request.url).startswith(prefix):
                return httpx.Response(status, content=body, headers={"content-type": ctype})
        return httpx.Response(404, content=b"not found")

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_download_records_checksums_and_logs_404(tmp_path):
    raw = tmp_path / "data" / "raw"
    manifest = tmp_path / "data" / "manifest.csv"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        "path,source_id,url,sha256,retrieved_at,http_status,kind\n,PSI-25,https://psi.nasa.gov/x,,,,record\n"
    )
    plan = tmp_path / "plan.yaml"
    plan.write_text(
        yaml.safe_dump(
            [
                {"source_id": "PSI-25", "kind": "psi_record"},
                {
                    "source_id": "PSI-25",
                    "kind": "psi_file",
                    "file": "PSI-25_Experimental table_BASS-II.csv",
                    "version": 1,
                    "tag": "table",
                },
                {
                    "source_id": "PSI-99",
                    "kind": "psi_file",
                    "file": "missing.csv",
                    "version": 1,
                    "tag": "table",
                },
                {"source_id": "NTRS-1", "kind": "ntrs_meta", "ntrs_id": 1},
                {"source_id": "NTRS-1", "kind": "ntrs_pdf", "ntrs_id": 1},
            ]
        )
    )
    csv_body = b"Test #,O2\nB1,22.2\n"
    routes = {
        "https://psi.nasa.gov/geode-py/ws/repo/investigations/PSI-25": (
            200,
            json.dumps({"accession": "PSI-25"}).encode(),
            "application/json",
        ),
        "https://psi.nasa.gov/geode-py/ws/studies/PSI-25/download": (
            200,
            b"https://s3.example/signed.csv",
            "text/plain",
        ),
        "https://s3.example/signed.csv": (200, csv_body, "text/csv"),
        "https://psi.nasa.gov/geode-py/ws/studies/PSI-99/download": (404, b"nope", "text/plain"),
        "https://ntrs.nasa.gov/api/citations/1": (
            200,
            json.dumps(
                {"downloads": [{"links": {"pdf": "/api/citations/1/downloads/p.pdf"}}]}
            ).encode(),
            "application/json",
        ),
        "https://ntrs.nasa.gov/api/citations/1/downloads/p.pdf": (
            200,
            b"%PDF-1.4 fake",
            "application/pdf",
        ),
    }
    log = raw / "download_log.csv"
    results = download.run(plan, raw, manifest, client=_mock_client(routes), log_path=log)
    statuses = [str(r["http_status"]) for r in results]
    assert statuses == ["200", "200", "404", "200", "200"]
    table = raw / "PSI-25" / "PSI-25_Experimental table_BASS-II.csv"
    assert table.read_bytes() == csv_body
    rows = download.read_manifest(manifest)
    by = {(r["source_id"], r["path"]): r for r in rows}
    t = by[("PSI-25", "data/raw/PSI-25/PSI-25_Experimental table_BASS-II.csv")]
    assert t["sha256"] == download.sha256_of(table) and t["kind"] == "table" and t["retrieved_at"]
    assert ("PSI-25", "data/raw/PSI-25/PSI-25_record.json") in by
    assert ("NTRS-1", "data/raw/NTRS-1/p.pdf") in by
    # 404 is recorded, not hidden: manifest row with status 404 and a log line.
    assert any(r["source_id"] == "PSI-99" and r["http_status"] == "404" for r in rows)
    with log.open() as f:
        logged = list(csv.DictReader(f))
    assert (
        len(logged) == 1
        and logged[0]["source_id"] == "PSI-99"
        and logged[0]["http_status"] == "404"
    )
    # Dry run touches nothing.
    assert all(
        r["http_status"] == "dry-run"
        for r in download.run(plan, raw, manifest, dry_run=True, client=_mock_client({}))
    )


def test_plan_file_is_valid_and_covers_p0_tables():
    plan = yaml.safe_load((download.PLAN_YAML).read_text())
    tables = {i["file"] for i in plan if i["kind"] == "psi_file" and i.get("tag") == "table"}
    for sid in ("PSI-25", "PSI-26", "PSI-69", "PSI-100", "PSI-101", "PSI-159"):
        assert any(t.startswith(sid + "_Experimental table") for t in tables), sid
    assert all(
        i["kind"] in {"psi_record", "psi_file", "ntrs_meta", "ntrs_pdf", "url"} for i in plan
    )


@pytest.mark.parametrize(
    "value,expected",
    [
        ("22.2", 22.2),
        ("1,234", 1234.0),
        ("34%", 34.0),
        ("-", None),
        ("-999", None),
        ("abc", None),
        ("", None),
    ],
)
def test_to_number(value, expected):
    assert parse_tables.to_number(value) == expected
