# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: NASA Space Apps Challenge 2026 judges evaluating EMBER in a few minutes, on a laptop, often
during a live demo. They need a strong first impression and a clear story, and they need to see that
the depth is real (sources, checksums, validation numbers) without digging for it.

Secondary: spacecraft fire-safety engineers and scientists who use the analysis pages in earnest, and
curious readers new to the topic, served by the plain-language guides and glossary.

## Product Purpose

EMBER (Evidence-Mapped Bounds for Exploration fire Risk) takes a habitat atmosphere (oxygen fraction,
total pressure, airflow, gravity, fuel) and shows which NASA fire experiments apply, how far the
scenario extrapolates from each, and which conditions nobody has tested. Success: a judge understands
the mechanism within one viewport and trusts it after one click into the evidence.

## Positioning

Ranking weights come from NASA's published microgravity flame-spread correlations (Ruff 2021) as
elasticities, not hand-set scores. The transfer distance D and exp(D) can be checked by hand. Unknown
conditions stay unknown and make D a lower bound. Gravity is a flag, never interpolated: PSI holds no
partial-gravity combustion data, so Moon and Mars scenarios are brackets from µg and 1-g tests.

## Operating Context

Streamlit app (`app/Home.py` router, pages under `app/pages/`, overview at `app/views/overview.py`),
run locally with `uv run streamlit run app/Home.py`. Demoed live at the hackathon (Nov 14–15, 2026),
following the guided demo script. Must work fully offline.

## Capabilities and Constraints

- Stack stays Streamlit; custom interactive pieces are self-contained HTML/CSS/JS components embedded
  in Streamlit. No framework rewrite.
- Offline only: no web fonts from CDNs, no remote scripts or images. Fonts must be bundled locally.
- Never change data, numbers, ranking, distance, gap or comparability logic. Unknown values stay
  "unknown". Nothing may call a material or atmosphere "safe".
- CFI-G 85% O₂ is burner-side flow, never cabin atmosphere. Nothing may say a result was measured at
  lunar or Mars gravity.
- Validation shows only measured numbers; anything not run says "pending".
- `uv run ruff check .` and `uv run pytest -q` (210 tests) must pass after every change.
- Pages: Overview, Guided demo, Ask, Evidence map, Compare, Gaps, Registry, Sources, Validation.

## Brand Commitments

Name: EMBER, expansion "Evidence-Mapped Bounds for Exploration fire Risk". Built for the NASA Space
Apps Challenge 2026, challenge "Flame in Freefall". The previous visual look (violet accent, serif
headings, warm off-white) is not binding; the user approved replacing it. Voice: plain, precise,
honest about limits.

## Evidence on Hand

Live from the registry (`data/`): 982 evidence records, 11 NASA investigations, 19 cited sources,
29 of 47 files mirrored with SHA-256 checksums, ambient O₂ known for 60% of records. NASA target
atmospheres (ISS air, Exploration Atmosphere 34% / 56.5 kPa, 26.5% / 70.3 kPa). Validation results
under `data/` when run. No testimonials, customers or endorsements exist; none may be invented.

## Product Principles

1. Prove, don't claim: every number on screen is computed from the registry and traceable to a source.
2. Honest bounds: show distance, unknowns and gaps as prominently as matches.
3. One mechanism, visible: scenario → distance to every NASA test → ranked evidence and gaps.
4. Depth one click away: the story leads for judges and newcomers; the full technical detail is never
   removed, only layered.

## Accessibility & Inclusion

WCAG AA contrast in light and dark themes, visible keyboard focus, reduced-motion support, usable at
phone width.
