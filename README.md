# EMBER — Evidence-Mapped Bounds for Exploration fire Risk

NASA Space Apps Challenge 2026 · *Flame in Freefall*

EMBER is a condition-space evidence engine over NASA Physical Science Informatics (PSI)
combustion investigations. Give it a habitat atmosphere (O₂, pressure, airflow, gravity)
and it shows which NASA fire experiments apply, how far you are extrapolating from them
(a transfer distance `D` weighted by published flame-spread scaling exponents), and what
nobody has tested yet.

The full specification is in [EMBER_BUILD_SPEC.md](EMBER_BUILD_SPEC.md).

## Quick start

```bash
uv sync --extra dev                  # add --extra retrieval (dense/hybrid baselines), --extra llm (Claude API)
uv run pytest -q
uv run streamlit run app/Home.py
uv run python -m ember.demo precache   # warm demo caches before presenting
uv run python -m ember.demo check      # run every demo step + page with the network blocked
```

## Data acquisition

```bash
uv run python -m ember.ingest.download            # mirror PSI tables + NTRS papers per data/ingest_plan.yaml
uv run python -m ember.ingest.parse_tables inspect "data/raw/PSI-25/PSI-25_Experimental table_BASS-II.csv"
uv run python -m ember.ingest.extract_psi         # PSI tables → data/extracted/*.jsonl (committed)
uv run python -m ember.curate.build_registry      # seeds + extracted + reviewed → data/curated
```

### Reviewing values proposed from papers

```bash
uv run python -m ember.ingest.extract_llm                      # propose + span-check → data/review/proposals.jsonl
uv run python -m ember.curate.review_cli list --source NTRS-20240002981
uv run python -m ember.curate.review_cli accept P53f7896093 P461e978c10 P1e57667a36 --evidence SAFFIRE6:SIBAL --by "Your Name"
uv run python -m ember.curate.review_cli review --by "Your Name"   # interactive
```

A proposal is shown only if its quote occurs on the stated page and every number appears in that
quote. Nothing reaches the registry until a named reviewer accepts it.

PSI has no documented API; the downloader uses the JSON endpoints the PSI web app itself calls
(see `ember/ingest/psi.py`). Every fetched file gets a SHA-256 and HTTP status in `data/manifest.csv`;
failures are logged to `data/raw/download_log.csv`, never hidden. The app never calls these at run time.

## Design rules (from the spec, §0)

- Every numeric condition in the registry carries a `source_id` and `source_locator`. Unknowns stay unknown; nothing is imputed.
- Ranking, distances, gap maps and comparability verdicts are deterministic Python. The LLM never produces a ranking or a number.
- Gravity is a flag, never a distance term. PSI holds no partial-gravity combustion data.
- CFI-G "85% oxygen" is burner/oxidizer-side flow, not cabin atmosphere.
- All units go through `pint`. Canonical units: O₂ mole fraction (0–1), kPa, cm/s, g₀ multiples, cm, s.
- Ranges stay ranges.
- The app works offline.

## Status

| Ticket | Status |
|---|---|
| T01 Scaffold | done |
| T02 Schemas + units | done |
| T03 Config | done |
| T04 Engine: distance + score + flags | done |
| T05 Seed registry | done (23 locators still TODO, see data/curated/review_todo.csv) |
| T06 Ask page (deterministic) | done — first demoable milestone |
| T07 Evidence Map page | done |
| T08 Monte Carlo rank stability | done |
| T09 GapScope + Gaps page | done |
| T10 CompareLab + Compare page | done (starter pair set; 60-pair labeling pending) |
| T11 Ingest (PSI/NTRS clients, downloader, per-investigation parsers) | done — 968 per-test rows from 7 PSI tables |
| T12 Paper extraction + review CLI | done — 332 verified proposals awaiting human review |
| T13 Retrieval baselines (random, BM25, dense, hybrid, additive) | done |
| T14 Gold set + evaluation harness | done — harness built; relevance labels pending (two human annotators) |
| T15 LLM layer (client, parser, narrator, verifier, adversarial suite) | done — runs on cache or deterministic fallback; no live LLM output measured yet |
| T16 Registry + Sources pages, CSV/Parquet export + data dictionary | done — `uv run python -m ember.export` → `exports/` |
| T17 Polish: badge legend on every page, guided Demo page, demo pre-cache, offline check | done — offline check is simulated (sockets/DNS blocked in-process); LLM answers not cached (no API key) |
| T18 (stretch) | pending |

## Validation

Pending. No gold-set evaluation has been run yet. Per spec §0.9, if EMBER does not beat the
best baseline on the gold set, this section and the Validation page will say so.

## Limitations

- **No partial-gravity data.** PSI contains no partial-g combustion data. EMBER flags any
  lunar/Mars scenario as an extrapolation and never interpolates between µg and 1-g, because
  NASA reports lunar-g flammability can exceed both brackets (FM2 abstract, NTRS 20240015307;
  Ruff 2021, NTRS 20210021318).
- **Elasticities are correlation exponents, not predictions.** `exp(D)` is the largest response
  factor the published correlation implies. Saffire VI shows such expectations can fail; those
  cases are surfaced as "tension" flags.
- **Phenomena without a published correlation use uniform weights** and are badged "unweighted".
- **Priors (`M_φ`, `M_f`, `Q`) are disclosed ordinal choices**, not physics. Their sensitivity is
  tested by Monte Carlo rank stability.
- **Records with no known conditions are ranked below records with data.** Unknown dimensions
  contribute zero to D, so a record with no condition data would otherwise tie a perfect match.
  R is left unchanged; the record is badged "no conditions" (see `DEMOTE_NO_CONDITION_EVIDENCE`).
- **Per-test rows come from seven PSI experimental tables** (BASS-II, BASS, FLEX, Saffire-III, SAME-R,
  CFI-G normal and inverse). Many conditions are not in those tables: BASS-II has no pressure column
  and records flow only as uncalibrated fan settings; BASS, Saffire-III and SAME-R state no O₂ or pressure.
  Those stay `unknown`. 19 seed locators are still `TODO` (`data/curated/review_todo.csv`).
- **CFI-G inverse-flame oxygen (up to 85%) is burner-side.** It is stored with its context and never
  enters distance, coverage or the O₂ axis of the map.
- **FLEX header assumptions:** the CSV lost subscripts, so the column `CO` is read as CO₂ and
  `Burning rate; mm` as mm²/s. The table has no space/ground column; gravity is taken from the PSI
  record (ISS microgravity investigation).
- **Saffire IV–VI presence in PSI is unverified**; they are labeled as non-PSI NASA sources.
- **Paper proposals need a human.** The rule-based proposer cannot tell an imposed airflow from a
  flame-spread velocity (both are cm/s), so every proposal is reviewed. The LLM proposer uses the
  T15 client and needs ANTHROPIC_API_KEY for pages not yet cached.
- **No water-mist data** exist in PSI; water mist is shown as a gap, not invented.
- **Out of scope:** rocket/propellant combustion.
- **LLM layer runs without an LLM by default.** `ember/llm/client.py` caches every Claude API response
  in `cache/llm/` and replays it offline. With no cached answer and no `ANTHROPIC_API_KEY`, the parser
  falls back to a rule-based parser and the narrator to template sentences; both go through the same
  verifier. Model: `EMBER_LLM_MODEL` (default `claude-opus-5-5`, server-side refusal fallback on).
  `EMBER_LLM_OFFLINE=1` forbids live calls. The spec's temperature 0 is not sent because current
  Claude models reject sampling parameters; the cache provides reproducibility instead.
- **Adversarial results so far cover the fallback path only** (5/5 prompts, 8/8 hostile sentences).
  LLM-mode results and the 50-sentence verifier audit need live output and are not yet measured.
