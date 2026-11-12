# EMBER — Full Build Specification for Claude Code
**Evidence-Mapped Bounds for Exploration fire Risk**
NASA Space Apps Challenge 2026 · *Flame in Freefall: SI-Powered Fire Safety Insights from Microgravity Combustion Data*
Event: **Nov 14–15, 2026** (challenge resources open Nov 13) · Spec written Nov 11, 2026

> **How to use this file.** Put it at the repo root (you can also rename it `CLAUDE.md`) and tell Claude Code:
> *"Read EMBER_BUILD_SPEC.md completely. Follow Section 0's rules. Then do the tickets in Section 15 in order. Stop after each ticket, run its tests, and give me a summary before moving on."*
>
> Tags used throughout: **[V]** verified from a NASA or peer-reviewed source · **[3P]** from third-party hackathon inventories (re-check) · **[A]** an assumption · **[TODO-VERIFY]** must be checked against the live PSI site before you rely on it.

---

## Table of contents
0. Non-negotiable rules for Claude Code
1. What we're building, in one page
2. Challenge requirements → feature traceability
3. Science primer (the physics the code encodes)
4. Data sources: PSI investigations, IDs, DOIs, files
5. Competitor and prior-art analysis
6. System architecture
7. Repository layout
8. Data model (pydantic schemas)
9. Ingestion and curation pipeline
10. Core algorithms (with reference code)
11. LLM layer: parser, narrator, verifier
12. Baselines and evaluation harness
13. Dashboard / UI spec
14. Test plan
15. Build tickets (ordered, for Claude Code)
16. 36-hour hackathon timeline
17. Demo script and slide outline
18. Judge-defense Q&A (15)
19. Reading list: papers and NASA documents (annotated)
20. Open questions and verify-first list
21. Appendix A: seed condition values (sourced)
22. Appendix B: gold-set query bank
23. Appendix C: glossary

---

## 0. Non-negotiable rules for Claude Code

1. **Never invent data.** Every numeric condition in the registry must carry a `source_id` and a `source_locator` (table+row, page+paragraph, or file+column). If you can't find a value, store `null` and the literal `"unknown"` status. **Never impute.**
2. **Ranking, distances, gap maps and comparability verdicts are deterministic Python.** The LLM never produces a ranking or a number.
3. **The LLM has exactly two jobs:** (a) turn a natural-language question into a validated `Scenario` JSON that the user confirms; (b) write summaries in which every sentence cites a registry/source ID ("cite-or-drop"). A verifier checks everything the LLM writes.
4. **Gravity is a flag, never a distance term.** PSI holds **no partial-gravity combustion data** [V]. Nothing may say a result was "measured at lunar/Mars gravity" unless the source is LUCI or FM2, and neither is in PSI.
5. **CFI-G "85% oxygen" is burner/oxidizer-side flow, not cabin atmosphere** [V]. Any output mentioning CFI-G with 85% must say so.
6. **All units go through `pint`.** Internal canonical units: O₂ = mole fraction (0–1), pressure = kPa, flow velocity = cm/s, gravity = g₀ multiples, length = cm, time = s.
7. **Ranges stay ranges** (`min`, `max`). Never collapse them to midpoints.
8. **The app must work offline.** All PSI/NTRS files are mirrored locally with SHA-256 checksums. No live API calls during the demo. LLM answers for demo questions are pre-cached, and a template fallback exists if the LLM is down.
9. **Report negative results.** If EMBER doesn't beat the best baseline on the gold set, the UI and README say so, and the claim narrows to "interpretability + gap mapping."
10. **Scope:** no rocket/propellant combustion. No water-mist claims (no PSI water-mist data; show it as a gap).
11. Keep dependencies minimal. **No Neo4j, no autonomous agents and no multimodal models in the MVP.**

---

## 1. What we're building, in one page

**Problem.** NASA's Physical Science Informatics (PSI) repository holds about 24 combustion investigations and roughly 12–13.5 TB of data, mostly video and images [3P]. A habitat engineer designing for the planned lunar **Exploration Atmosphere (8.2 psia / 34% O₂)** [V, NASA/TP-2010-216134] can't easily answer three questions:
- Which NASA tests are closest to my conditions?
- How far am I extrapolating from them?
- What has nobody tested?

NASA's own technology gap list (ECLSS fire safety, 2021-2934-TX06) calls flammability data at exploration atmospheres and partial gravity "very limited" [V].

**Solution.** EMBER is a **condition-space evidence engine**:
1. a curated, provenance-tracked registry of PSI test conditions (O₂, pressure, flow, gravity regime, fuel class, phenomenon, measurements);
2. a **transfer distance** `D` per (scenario, evidence) pair, weighted by **published microgravity flame-spread scaling exponents** (NASA 2021 fire-safety roadmap, Ruff, NTRS 20210021318) [V]. `exp(D)` is the largest response multiplier the correlation implies, so it can be checked by hand;
3. an explainable relevance score `R = M_φ · M_f · Q · exp(−D)`, with Monte Carlo rank-stability badges;
4. **GapScope**, a graded coverage/priority map over (O₂, P, u, g) with NASA target atmospheres overlaid and partial-g hatched as "no evidence";
5. **CompareLab**, a rule-gated verdict (comparable / with caveats / not comparable) for any two measurements, listing confounders;
6. a cite-or-drop LLM narrator plus a numeric verifier;
7. a **labeled retrieval benchmark** (gold set) comparing EMBER with BM25, dense, hybrid and additive-score baselines.

**Pitch line.** *"Tell EMBER your habitat's oxygen, pressure and airflow. It shows which NASA fire experiments apply, how far you're extrapolating, and what nobody has tested yet."*

**Expected novelty: Level 4** (a differentiated method addressing a documented limitation). Each piece exists elsewhere. This combination, applied to PSI combustion evidence, wasn't found in the sources searched. Don't claim "first."

---

## 2. Challenge requirements → feature traceability

From the challenge text (official Space Apps page, also mirrored at hackathlone.com/challenges/flame-in-freefall):

| Challenge ask | EMBER feature | Where |
|---|---|---|
| Dashboard that "summarizes, ranks, and interprets" combustion investigations | Ranked evidence list + cited summaries + "why" bars | §10.4, §11, §13 |
| Identify investigations relevant to spacecraft, stations, lunar/Mars bases, pressurized rovers | Scenario presets (ISS, Gateway, lunar HLS/habitat 8.2/34, 10.2/26.5, rover) | §13 |
| Extract data supporting predictive modeling | Clean Parquet/CSV export of the curated registry, with units and provenance | §9, §13 |
| Highlight research for next-gen prevention/detection/suppression | Phenomenon filter (spread, ignition, extinction, suppression, smoke/detection) + SAME/DAFT panel | §13 |
| Display objectives, fuels (shape/size), O₂, airflow, how tests varied, sensors | Investigation cards + registry table | §8, §13 |
| Similarities/differences across investigations | CompareLab | §10.7 |
| Shared hardware (ACME/CIR; MDCA/CIR; MSG + SPICE duct) | Hardware-family field + "shared hardware" chips | §8 |
| SAME↔DAFT instrument link; BRE as materials-flammability study | Relationship edges in registry + SmokeSignal panel (stretch) | §4, §13 |
| Lunar: ≥30% O₂ at ≤10.2 psi | Target-atmosphere boxes on the O₂–P map | §10.6 |
| CFI-G highest-O₂ (burner-side) | Context tag `o2_context = burner` + verifier rule | §0, §11.3 |
| No partial-g data; LUCI/FM2 coming; E-FIELD mimics gravity | Gravity flag, hatched band, "not in PSI" overlays | §10.5, §13 |
| Terrestrial spin-offs | Single "Earth applications" panel (detectors, materials screening) | §13 |
| Out of scope: rockets/propellants | Excluded in schema enum | §8 |

**Judges are likely to probe:** treating 85% as ambient O₂; presenting µg as lunar; arbitrary weights; "does it actually work"; "how do you know it's better."

---

## 3. Science primer (the physics the code encodes)

### 3.1 Why microgravity flames differ
- **No buoyancy.** Hot gases don't rise. Oxygen reaches the flame only by diffusion or by imposed (ventilation) flow. Residence times lengthen and flames grow more spherical and dimmer. [V; NASA "Combustion in Reduced Gravity" mini-book, NP-2015-10-034-JSC]
- **More soot.** ACME CLD microgravity flames held 5–8× more soot than 1-g flames. SLICE saw about 2× the peak soot. SPICE smoke-point lengths were up to 2.3× longer. [V; ACME publications list, NASA GRC 2023; SPICE/SLICE papers]
- **Flow speed controls spread.** In BASS-II, PMMA opposed-flow spread first **rose then fell** as flow increased, with no spread below about 0.6 cm/s. LOC was about **17% in µg vs about 18% at 1-g** for PMMA rods. [V; Link et al., *Sci. Rep.* 8:120, 2018, PMC5760683]
- **NASA:** "turning off forced air flow cannot be used as an extinguishment strategy." [V]

### 3.2 Material flammability and the scaling exponents (the core of EMBER)
- NASA screens materials with **NASA-STD-6001 Test 1**: 1-g, upward burning, worst-case. BASS-II aimed to bridge that test to µg. [V]
- **Ruff, "Technology Development for Spacecraft Fire Safety" (NASA, 2021, NTRS 20210021318)** gives µg flame-spread correlations [V]:
  - **Concurrent-flow spread:** `V_f ∝ X_O₂ · u · P^0.5`
  - **Opposed-flow spread:** `V_f ∝ X_O₂^0.9 · P^0.05`
  - "Increasing oxygen has a significantly greater effect than increasing pressure."
- Treat these exponents as **elasticities** (`ε = ∂lnY/∂lnx`). This is where EMBER's weights come from; they aren't hand-set.
- **Enclosure confounder.** Saffire found enclosure size "has more impact on the flame spread than anticipated." Duct half-height changed from **25 cm (Saffire I–III) to 15 cm (IV–VI)**. Cross-flight comparisons need a caveat. [V; Saffire VI paper, ICES-2024-365, NTRS 20240002981]

### 3.3 Suppression and extinction (FLEX/CFI)
- **FLEX** burned single droplets (heptane, methanol and others) in atmospheres diluted with **N₂, CO₂, He or Xe**. CO₂ is the ISS suppressant. [V]
- **Two extinction modes.** *Diffusive extinction* happens at high O₂ with small drops; *radiative extinction* at low O₂ with large drops. As O₂ falls, the diffusive-extinction diameter rises and the radiative-extinction diameter falls. [V; Nayagam et al., *Microgravity Sci. Technol.* 26:65–76, 2014, doi:10.1007/s12217-014-9372-2]
- **Cool flames.** Large n-alkane droplets kept burning with an **invisible ~600 °C cool flame** after the visible flame went out. **Visual flame-out does not prove extinction.** [V]
- **d²-law:** `d² = d₀² − K·t`, where `K` is the burning-rate constant. [standard droplet theory]
- **Limits.** FLEX supports CO₂-vs-He comparisons **for droplets only**. No PSI water-mist dataset was found.

### 3.4 Smoke and aerosol detection (SAME/SAME-R/DAFT)
- **SAME/SAME-R** pyrolyzed 5 spacecraft materials. Smoke particles were **100–600 nm**, roughly lognormal, and **grew with aging**. The ISS forward-scatter detector responded poorly below about 300 nm (e.g., Kapton, Teflon smoke). [V; Urban/Mulholland et al.; NIST SAME publication; Meyer et al., *Fire Saf. J.*, PMC7918997]
- In µg, mixing dominates smoke transport, so **detection lags are longer**. [V]
- **DAFT** validated a modified P-Trak that detects particles "as small as 20 nm." ISS cabin air was **under 0.005 mg/m³ and about 15 particles/cm³**, cleaner than the Shuttle or a typical office. Average particle size was larger on orbit. [V; NASA DAFT fact sheet]
- **False alarms.** Maintenance dust triggers alarms and leads crews to disable detectors [V, NASA gap list]. SAME-R: "size selective smoke detection will improve reliability and false alarm rejection." [V]

### 3.5 Oxygen, pressure and lunar habitats
- **Exploration Atmosphere: 8.2 psia (56.5 kPa) / 34% O₂**, control box 33.5–35%. A 10.2 psia / 26.5% option was also studied. An earlier 32% cap was "chosen for flammability concerns." The working group noted 36% was "supportable with current materials." [V; NASA/TP-2010-216134, Exploration Atmospheres Working Group]
- The challenge brief says "30% or greater" O₂ at "10.2 psi or less," calling it "more than a 40% increase" in oxygen. [V; challenge text]
- **The closest burned-at-scale evidence is Saffire VI**: PMMA and SIBAL at **54.1–55.2 kPa and 28.8–31.0% O₂**. Spread was **higher** than in Saffire IV, though a prior model predicted lower. **This is a "tension" item; surface it in the UI, don't hide it.** [V; NTRS 20240002981] Whether Saffire IV–VI are in PSI is **[TODO-VERIFY]**. If they aren't, label them "non-PSI NASA source."

### 3.6 Partial gravity: what is and isn't known
- **PSI has no partial-gravity combustion data.** [V; challenge text]
- **µg and 1-g are brackets, not bounds.** NASA's FM2 abstract describes lunar gravity as a possible "goldilocks zone of reduced convective heat loss, while generating enough buoyant flow to replenish fresh oxygen." [V; NTRS 20240015307] Ruff 2021: "oxygen flammability limits in lunar-g are lower than those measured in 1-g." [V] SIBAL fabric keeps burning at lunar g but self-extinguishes at 1-g. **Never interpolate between µg and 1-g.**
- **LUCI** flew on Blue Origin New Shepard: a centrifuge at 11 RPM and 1.22 m radius (≈0.165 g). It ran the first extended (>25 s) simulated-lunar-g burns, of SIBAL and 4 mm PMMA **in air at normal pressure**. [V; NTRS 20250010653]
- **FM2 (Flammability of Materials on the Moon)** is planned for CLPS mission CP-21 in late 2026. It will burn four samples on the lunar surface, including at 34% / 8.2 psia. [V; NTRS 20240015307]
- **ACME E-FIELD** uses ion-driven wind as a body-force analog. It **mimics** gravity effects but isn't a gravity measurement. [V]

### 3.7 Which parameters make experiments comparable
Use these as registry dimensions: **X_O₂** (ambient vs burner context), **P_total** (and derived ppO₂), **u** (imposed flow, direction: opposed/concurrent/quiescent), **g regime** (µg / 1-g / simulated partial / not stated), **fuel class** (thin solid, thick solid, liquid droplet, gas jet, gaseous emulator, pyrolysis/smoke source), **sample geometry/size**, **phenomenon** (ignition, spread, extinction, LOC, soot/smoke point, smoke particle size, detector response, suppression), **diluent**, **hardware family**, **enclosure size**.

---

## 4. Data sources: PSI investigations, IDs, DOIs, files

### 4.1 Repository facts
- PSI started in 2014 with 17 datasets. It now holds "over 100 unique investigation datasets — around 30 terabytes." DOIs (prefix **10.60555**) were assigned in 2024. Record pages show **CC0-1.0**. [V; science.data.nasa.gov PSI updates, 2025; PSI-25 and PSI-102 pages]
- The combustion subset is **24 investigations**, about **13,497 GB** registered [3P]. One team queried PSI's undocumented API (2026-11-08) and reported 16,354 files plus 22 "experimental tables" (some 404s). Another counted about 21,900 files and 20 tables. **These counts conflict. Verify on day 1.**
- **Access.** There is no documented public API, so expect manual downloads. PSI pages render via JavaScript, and some sources say registration is required. One team's curated 72-file subset was about 56 MB. **The value is in the small tables, not the video.**
- **Record URL pattern:** `https://psi.nasa.gov/physci/repo/data/investigations/PSI-<N>` (confirmed for PSI-25 and PSI-102; assume the same for the others **[TODO-VERIFY]**).
- **Papers:** the NTRS API works: `https://ntrs.nasa.gov/api/citations/search?q=<query>` and `https://ntrs.nasa.gov/api/citations/<id>`.

### 4.2 Investigation matrix (download priority in the last column)

| Investigation | PSI ID / DOI | Fuel | Objective | Variables | Measurements | Hardware | Fire-safety relevance | Machine-readable data [3P unless noted] | Priority |
|---|---|---|---|---|---|---|---|---|---|
| **BASS-II** | PSI-25 · 10.60555/4qc4-de67 | PMMA rods/slabs, thin fuels | Spread + limits; bridge NASA-STD-6001 to µg | Flow ≤40 cm/s; O₂ ~13.6–22.2%; diameter | Video, spread rate, extinction | MSG + SPICE flow duct | **High**: µg LOC ~17% vs 18% at 1-g | As-run test matrix + video | **P0** |
| **BASS** | PSI-26 · 10.60555/58h4-dy80 | Solids | Ignition, spread, extinction in low flow | Flow, O₂ ≤21%, geometry | Video, spread, extinction | MSG + SPICE duct | High | ~121-row as-run matrix + video | **P0** |
| **Saffire-I** | PSI-98 · 10.60555/0t15-1z43 | SIBAL fabric 94 × 40.6 cm | Large-scale spread on Cygnus | Flow, direction | Spread, video | Saffire Flow Unit (Cygnus) | **Very high**: scale/enclosure | Summaries | P1 |
| **Saffire-II** | PSI-99 · 10.60555/2chp-m469 | 9 samples 29 × 5 cm incl. 1 cm PMMA | Material flammability | Material, flow | Ignition/spread | Saffire Flow Unit | High | 15-row summary | P1 |
| **Saffire-III** | PSI-100 · 10.60555/040q-4h36 | SIBAL | Repeat large-scale | Flow | Spread + **1 Hz telemetry** (radiometers, anemometers, pressures, smoke detector) | Saffire Flow Unit | Very high | Telemetry CSV | **P0** |
| Saffire IV–VI | **Not confirmed in PSI** | PMMA, SIBAL, cotton | Reduced P / elevated O₂ | VI: 54.1–55.2 kPa, 28.8–31.0% O₂ [V] | Spread, heat release, CO/CO₂/HCl/HF, aerosols [V] | Cygnus | **Most exploration-like atmosphere at scale** | From paper ICES-2024-365 (NTRS 20240002981) | **P0 (as non-PSI)** |
| **SAME** | PSI-102 · 10.60555/gd4k-8h62 | 5 pyrolyzing materials | Smoke particle size; detector response | Material, heater T, aging 10–1800 s | Size-distribution moments, TEM | MSG | High: detection | Publications, housekeeping data | P1 |
| **SAME-R** | PSI-101 · 10.60555/2np7-jv14 | Same | Reflight | As SAME | ISS/STS detector volts, P-Trak counts/cc, DustTrak mg/m³ | MSG | High | **44 housekeeping CSV runs**, ~6.25 M samples | **P0** |
| **DAFT/DAFT-2** | PSI-47 · 10.60555/ztgj-d202 | Ambient ISS dust | Verify P-Trak in µg; characterize ISS particulates | Location, reference dust | Counts, mass | P-Trak / DustTrak | Medium: dust is the negative class for smoke | Summaries only | P2 |
| **FLEX** | PSI-69 · 10.60555/mbq8-0451 | Droplets (heptane, methanol…) | Flammability boundaries; suppressants | Fuel, O₂, P, diluent (N₂/CO₂/He/Xe), d₀ | Droplet/flame histories, extinction diameter, K | MDCA in CIR | High: suppression | **274-row table** (186 extinction / 61 disruption / 27 completion); reportedly **no space/ground column** | **P0** |
| **FLEX-2** | PSI-68 · 10.60555/byp8-h018 | Droplets | FLEX extension | Ranges | — | MDCA | Medium | 8-row condition-range table | P2 |
| **CFI** | PSI-39 · 10.60555/m6pj-a914 | Droplets | Cool flames after radiative extinction | Fuel, O₂, P | Droplet histories | MDCA | Medium | Unprocessed archive | P2 |
| **ACME BRE** | PSI-20 | Gas emulating condensed fuels | Flammability vs heat of gasification | Fuel/inert mix, flow, burner size | Heat flux, surface T, flame size | ACME insert in CIR | High: 1-g burning ~3–4× µg | Test-day summaries | P1 |
| **ACME CFI-G** | PSI-159 · 10.60555/cyt1-kh64 | Ethane, propane, n-butane; normal and **inverse** flames | Steady spherical cool diffusion flames | Fuel/O₂, P up to ~2 bar | Intensified video, radiometers, pyrometry, thermocouples | ACME/CIR | High-O₂ (**burner-side ≤85%**); cool flames only at 2 bar with **ambient X_O₂ = 0.39** | Test-level tables | **P0** |
| **ACME E-FIELD** | PSI-22 | Methane coflow | Ion-driven wind control | Field strength, polarity | Ion current, images | ACME | Indirect gravity analog | 32-row summary | P1 |
| ACME Flame Design | PSI-10 | Gaseous | Soot-free flame design | Dilution, flow | Soot, temperature, extinction | ACME | Low–medium | Table | P1 |
| ACME CLD / s-Flame | PSI-21 / PSI-23 | Gaseous | Flame structure, extinction | Flow, dilution | Soot, T | ACME | Low–medium | Summaries | P2 |
| **SPICE** | PSI-107 (+ PSI-60 analysis, 10.60555/mzjm-yv57) | Gas jets | Smoke points | Fuel, coflow | Smoke-point length, soot | MSG duct | Medium | Large archive | P2 |
| **SLICE** | PSI-106 | Gas jets | Lifted flames | Fuel, coflow | Liftoff height, soot | MSG duct | Medium | ~23,000 .dat files | P2 |

**Shared-hardware families** (encode them as `hardware_family`) [V, challenge text]:
- `ACME/CIR`: BRE, CFI-G, E-FIELD, Flame Design, CLD, s-Flame
- `MDCA/CIR`: FLEX, FLEX-2, CFI
- `MSG+SPICE-duct`: BASS, BASS-II, SPICE, SLICE
- `MSG`: SAME, SAME-R
- `Saffire Flow Unit/Cygnus`: Saffire I–VI
- `P-Trak/DustTrak`: DAFT, and SAME-R's reference instruments

**Important:** only about 7 records give per-test machine-readable conditions. One inventory found only 10 of 20 records stating an O₂ range and only 5 stating a pressure range [3P]. **Missing metadata is the norm.**

### 4.3 MVP data subset (what to actually download)
**Must have:** PSI-25, 26, 69, 100, 101, 159 tables/matrices, plus the Saffire VI paper (non-PSI).
**Should have:** PSI-98, 99, 102, 20, 22, 10, 47 summaries.
**Papers:** 2–5 NTRS/peer-reviewed papers per P0 investigation (see §19).
**Skip:** video (except one optional BASS-II clip for the hero UI), SLICE .dat bulk, raw images.

---

## 5. Competitor and prior-art analysis

### 5.1 Other 2026 teams on this exact challenge (check their repos on day 1)

| Repo | What it does | Our differentiation |
|---|---|---|
| github.com/OSAMABASAM/NASA_flame_in_freefall | 100-point **additive** relevance score; numbers-checked "Ask" | Our weights come from physics elasticities; we have a benchmark and rank-stability tests |
| github.com/YoussefHegazy74/flame-in-freefall (AFAQ) | Comparability registry: 93 measurements, 60 pair rules, 13 Parquet tables, defaults to "not_comparable" | We add physics confounder rules + transfer distance + gap field |
| github.com/Faruk042/NASA_Flame_In_Freefall_2026 | BM25 search | This becomes **our baseline** |
| github.com/ngu-ming-henn/Nasa-Space-Apps-Sarawak | FLEX ridge/logistic models | We explicitly avoid ML on 274 rows; we export clean data instead |
| github.com/mnb60704-netizen/flex-explorer | FLEX explorer | Same as above |
| github.com/Krypton-N/NASA-SPACE-APPS, github.com/shaharia179/flame-in-freefall | Dashboards | Skim for data parsing tips and file-path inventories |

**Takeaway:** ranking, comparison, graphs and gap grids are **table stakes**. Differentiation has to come from **method + validation**.

### 5.2 Scientific AI and knowledge platforms (prior art to cite, not claim)

| System | What it shows | Relevance |
|---|---|---|
| **PaperQA2** (Skarlinski et al., arXiv:2409.13740, 2024) | Literature agent at 85.2% precision vs 73.8% for human experts on LitQA2 | Strong text QA, but it doesn't compute condition similarity. Use it as the framing for why RAG alone isn't enough |
| **Sharma & Raman, *Energy and AI* (2024)** | Combustion-domain LLM QA | Not tied to PSI conditions |
| **FlameBench** (arXiv:2603.19268) | Combustion LLM benchmark; notes RAG "does not address inconsistencies arising during multi-step reasoning" | Supports our deterministic core |
| **FlamePilot** (arXiv:2601.01357) | LLM CFD automation | Different task |
| **NASA OSDR/GeneLab + SPOKE KG** (NAR 2025; github.com/BaranziniLab/spoke_genelab) | KG + LLM discovery for space biology | Shows NASA values KGs; marginal at 24 investigations |
| **NASA Earth-observation agentic search** (arXiv:2607.02387) | Fused scorer raised R@10 and MRR "by over 5x" vs baselines | **Copy the method: a labeled benchmark plus baselines** |
| **FY2026 NASA Task Book: inter-project meta-analysis** (BASS / Saffire / Confined Combustion) | Physics meta-analysis across investigations | Closest prior art for "cross-investigation insight": cite it |
| **PSI-60 SPICE analysis** | Curated analysis dataset | Example of value-added PSI data |

### 5.3 Gaps not addressed in the sources searched
1. Physics-derived (elasticity) ranking weights.
2. A quantified extrapolation distance with a falsifiable interpretation.
3. Gap maps tied to NASA's target atmospheres.
4. A labeled PSI retrieval benchmark.

*Caveat:* these come from targeted web searches across NTRS, ScienceDirect, PMC, arXiv and GitHub (2026-11-11). This was not a systematic review, and patents weren't searched.

---

## 6. System architecture

```mermaid
flowchart LR
  subgraph Ingest
    A[PSI records/tables<br/>manual or scripted download] --> M[Manifest + SHA-256]
    N[NTRS / journal PDFs] --> M
    M --> P[Parsers: xlsx/csv/txt/pdf]
  end
  subgraph Curate
    P --> X[LLM-proposed condition JSON<br/>with source spans]
    X --> H[Human accept/reject CLI]
    P --> U[pint normalization]
    H --> U
    U --> REG[(Registry: DuckDB + Parquet<br/>evidence, conditions, measurements,<br/>claims, sources)]
  end
  subgraph Engine [Deterministic engine]
    REG --> D[Transfer distance D]
    D --> R[Relevance R = Mφ·Mf·Q·exp(-D)]
    R --> MC[Monte Carlo rank stability]
    REG --> G[GapScope coverage + priority]
    REG --> C[CompareLab rule engine]
    REG --> IDX[BM25 + dense FAISS<br/>baselines + doc QA]
  end
  subgraph LLM [Constrained LLM]
    Q[User question] --> LP[Parser -> Scenario JSON<br/>pydantic validated]
    LP --> UC[User confirms scenario chip]
    R --> NAR[Cite-or-drop narrator]
    NAR --> VER[Verifier: IDs, numbers, context rules]
  end
  UC --> D
  VER --> UI[Streamlit + Plotly dashboard]
  MC --> UI
  G --> UI
  C --> UI
  REG --> EXP[CSV/Parquet export]
  subgraph Eval
    GOLD[Gold set 40 queries] --> EV[nDCG@5, R@5, MRR<br/>bootstrap CI, ablations]
    IDX --> EV
    R --> EV
  end
```

**Deterministic:** parsing, normalization, distance, scoring, Monte Carlo, gap field, comparability, verification, metrics.
**Generative (LLM):** question → scenario JSON; cited narration; proposing extraction values from PDFs (human-verified).

---

## 7. Repository layout

```
ember/
├── EMBER_BUILD_SPEC.md          # this file (or CLAUDE.md)
├── README.md                    # includes Limitations section
├── pyproject.toml               # python 3.11
├── data/
│   ├── raw/                     # mirrored PSI/NTRS files (git-ignored), one subdir per source
│   ├── manifest.csv             # path, source_id, url, sha256, retrieved_at, http_status, kind
│   ├── curated/                 # parquet tables (committed)
│   └── seed/                    # hand-entered YAML seeds (Appendix A), each value sourced
├── ember/
│   ├── __init__.py
│   ├── config.py                # elasticities, priors, grids, target atmospheres
│   ├── schemas.py               # pydantic models (§8)
│   ├── units.py                 # pint registry + converters
│   ├── ingest/
│   │   ├── download.py          # manifest-driven fetch + checksum, logs 404s
│   │   ├── ntrs.py              # NTRS API client (search + metadata + pdf)
│   │   ├── parse_tables.py      # xlsx/csv parsers per investigation
│   │   ├── parse_pdf.py         # pdfplumber text + page spans
│   │   └── extract_llm.py       # proposes condition JSON with spans
│   ├── curate/
│   │   ├── review_cli.py        # accept/reject/edit proposals
│   │   └── build_registry.py    # seeds + parsed + accepted → DuckDB/Parquet
│   ├── engine/
│   │   ├── distance.py          # §10.1–10.3
│   │   ├── score.py             # §10.4
│   │   ├── robustness.py        # §10.5 Monte Carlo
│   │   ├── gapscope.py          # §10.6
│   │   ├── comparelab.py        # §10.7
│   │   └── flags.py             # gravity, envelope, burner-O2, incompleteness
│   ├── retrieval/
│   │   ├── bm25.py
│   │   ├── dense.py             # sentence-transformers + FAISS
│   │   ├── hybrid.py            # RRF fusion
│   │   └── additive.py          # competitor-style 35/25/20/10/10 baseline
│   ├── llm/
│   │   ├── client.py            # provider-agnostic; cache; offline fallback
│   │   ├── parser.py            # question → Scenario
│   │   ├── narrator.py          # cite-or-drop summaries
│   │   ├── verifier.py          # §11.3 rules
│   │   └── templates.py         # no-LLM fallback narration
│   ├── eval/
│   │   ├── gold/                # queries.yaml, qrels.csv (frozen), annotator files
│   │   ├── metrics.py           # nDCG, recall, MRR, bootstrap, permutation
│   │   ├── run_eval.py          # all systems × all queries → results.json
│   │   ├── ablations.py
│   │   └── adversarial.py       # hallucination probes
│   └── api.py                   # optional FastAPI (only if a React UI is used)
├── app/
│   ├── Home.py                  # Streamlit entry
│   └── pages/
│       ├── 1_Ask.py
│       ├── 2_Evidence_Map.py
│       ├── 3_Compare.py
│       ├── 4_Gaps.py
│       ├── 5_Registry.py
│       ├── 6_Validation.py
│       └── 7_Sources.py
├── cache/                       # pre-computed LLM answers for demo queries
└── tests/                       # §14
```

**Stack:** Python 3.11, pandas, DuckDB, pyarrow, pint, pydantic v2, pdfplumber, rank_bm25, sentence-transformers (`all-MiniLM-L6-v2` or `BAAI/bge-small-en-v1.5`), faiss-cpu, numpy, scipy, Streamlit, Plotly, httpx, PyYAML, pytest. Optional: networkx (graph view, stretch), FastAPI.

---

## 8. Data model (pydantic schemas)

```python
# ember/schemas.py
from enum import Enum
from typing import Optional, Literal
from pydantic import BaseModel, Field, model_validator


class Phenomenon(str, Enum):
    ignition = "ignition"
    spread_opposed = "spread_opposed"
    spread_concurrent = "spread_concurrent"
    extinction = "extinction"
    loc = "limiting_oxygen"
    suppression = "suppression"
    soot_smoke_point = "soot_smoke_point"
    smoke_particles = "smoke_particles"
    detector_response = "detector_response"
    burning_rate = "burning_rate"
    cool_flame = "cool_flame"
    flame_structure = "flame_structure"


class FuelClass(str, Enum):
    thin_solid = "thin_solid"
    thick_solid = "thick_solid"
    droplet = "liquid_droplet"
    gas_jet = "gas_jet"
    gas_emulator = "gaseous_emulator"
    pyrolysis_source = "pyrolysis_source"
    ambient_dust = "ambient_dust"


class GravityRegime(str, Enum):
    micro = "microgravity"
    one_g = "1g"
    sim_partial = "simulated_partial"
    unknown = "unknown"


class O2Context(str, Enum):
    ambient = "ambient"
    burner = "burner_oxidizer_flow"
    unknown = "unknown"


class Granularity(str, Enum):  # drives Q prior
    per_test = "per_test_table"
    per_campaign = "campaign_summary"
    paper_only = "paper_only"


class ClaimType(str, Enum):
    measured = "measured"
    derived = "derived"
    modeled = "modeled"
    author_interp = "author_interpretation"
    system_inference = "system_inference"


class Range(BaseModel):
    min: Optional[float] = None
    max: Optional[float] = None
    status: Literal["known", "unknown", "not_applicable"] = "unknown"
    source_id: Optional[str] = None
    source_locator: Optional[str] = None  # "Table 2 row 14", "p.5 ¶3", "file.csv:col"

    @model_validator(mode="after")
    def _check(self):
        if self.status == "known":
            assert self.min is not None and self.max is not None and self.min <= self.max
            assert self.source_id and self.source_locator, "known values need provenance"
        return self


class Source(BaseModel):
    source_id: str  # e.g. "PSI-25", "NTRS-20240002981", "DOI:10.1038/s41598-017-18398-4"
    kind: Literal["psi_record", "psi_file", "ntrs", "journal", "challenge", "other"]
    title: str
    year: Optional[int] = None
    url: str
    doi: Optional[str] = None
    in_psi: bool
    sha256: Optional[str] = None
    retrieved_at: Optional[str] = None


class Evidence(BaseModel):
    """One test, test series, or campaign-level condition envelope."""

    evidence_id: str  # "PSI-25:T014" or "PSI-25:campaign" or "SAFFIRE6:PMMA"
    investigation: str  # "BASS-II"
    psi_id: Optional[str]  # None for non-PSI (e.g., Saffire VI)
    hardware_family: str
    fuel_class: FuelClass
    fuel_name: Optional[str]  # "PMMA rod", "n-heptane", "SIBAL"
    geometry: Optional[str]
    size_cm: Optional[Range] = None
    phenomena: list[Phenomenon]
    gravity: GravityRegime
    x_o2: Range  # mole fraction 0–1
    o2_context: O2Context = O2Context.unknown
    p_kpa: Range
    u_cms: Range  # imposed flow velocity
    flow_direction: Optional[Literal["opposed", "concurrent", "quiescent", "coflow", "unknown"]] = (
        "unknown"
    )
    diluent: Optional[str] = None  # N2/CO2/He/Xe
    enclosure_note: Optional[str] = None  # e.g. "Saffire duct half-height 15 cm"
    granularity: Granularity
    measurements: list[str] = []  # canonical quantity names
    tensions: list[str] = []  # e.g. "Spread higher than model predicted (Saffire VI)"
    sources: list[str]  # source_ids


class Claim(BaseModel):
    claim_id: str
    evidence_id: Optional[str]
    text: str
    claim_type: ClaimType
    source_id: str
    source_locator: str


class Scenario(BaseModel):
    """Produced by LLM parser or UI sliders; ALWAYS user-confirmed."""

    name: str = "custom"
    x_o2: Optional[float] = Field(None, ge=0.0, le=1.0)
    p_kpa: Optional[float] = Field(None, gt=0)
    u_cms: Optional[float] = Field(None, ge=0)
    gravity_g0: Optional[float] = Field(None, ge=0)  # 0, 0.166, 0.38, 1
    phenomenon: Phenomenon
    fuel_class: Optional[FuelClass] = None
    fuel_name: Optional[str] = None
    flow_direction: Optional[str] = None
    notes: Optional[str] = None
```

**Canonical measurement names** (controlled vocabulary for CompareLab): `flame_spread_rate_cm_s`, `extinction_flow_cm_s`, `loc_x_o2`, `extinction_diameter_mm`, `burning_rate_K_mm2_s`, `smoke_point_length_mm`, `soot_volume_fraction`, `particle_count_per_cc`, `mass_conc_mg_m3`, `detector_signal_V`, `geom_mean_diameter_nm`, `heat_flux_kW_m2`, `surface_temperature_K`, `flame_standoff_mm`, `liftoff_height_mm`.

Each measurement record also carries `value_kind ∈ {measured, set_point, range, computed}` and `context` (e.g., `ambient`, `burner`, `cabin`, `duct`).

---

## 9. Ingestion and curation pipeline

| Step | What | Output | Acceptance criterion |
|---|---|---|---|
| 9.1 Acquire | Download P0/P1 PSI files (browser/manual if needed) + NTRS PDFs | `data/raw/<source>/…` | Every file in `manifest.csv` with sha256, url, timestamp, HTTP status; 404s logged, not hidden |
| 9.2 Classify | Tag each file `table / matrix / telemetry / video / document / other` | manifest `kind` | 100% of files tagged |
| 9.3 Parse | pandas/openpyxl; keep raw strings beside parsed values; flag sentinels `- , n/a, NA, #DIV/0!, -999, blank` | `parsed/<psi>.parquet` | Row counts match source (e.g., FLEX = 274 rows **[TODO-VERIFY]**) |
| 9.4 Extract (papers) | `extract_llm.py`: LLM proposes `Range` values with exact quoted span + page | `proposals.jsonl` | Every proposal has a verbatim span that string-matches the PDF text |
| 9.5 Review | `review_cli.py`: human accept/edit/reject | `accepted.jsonl` | Zero values enter the registry without `reviewed_by` |
| 9.6 Normalize | pint: %→fraction, psi/atm/bar→kPa, mm/s→cm/s; tag `o2_context` | — | Unit tests for all conversions; unknown units → `status=unknown` |
| 9.7 Store | DuckDB + Parquet: `sources`, `evidence`, `measurements`, `claims`, `relations` | `data/curated/*.parquet` | Schema validation passes for every row |
| 9.8 Index | BM25 + dense FAISS over investigation descriptions + paper chunks (for baselines and doc QA) | `index/` | Index builds in <2 min on a laptop |
| 9.9 Export | Clean CSV/Parquet + data dictionary for modelers | `exports/` | Columns documented with units |

**Extraction prompt (for 9.4)** — require JSON only:
```
You are extracting experimental CONDITIONS from a NASA combustion document.
Return JSON list. Each item:
{ "investigation": str, "quantity": one of [x_o2, p_kpa, u_cms, size_cm, diluent, fuel_name, gravity],
  "min": number|null, "max": number|null, "unit_as_written": str,
  "o2_context": "ambient"|"burner_oxidizer_flow"|"unknown",
  "quote": "<verbatim text from the document containing the value>",
  "page": int }
Rules: Copy numbers exactly as written. Do not convert units. If a value is not stated, omit it.
Never infer. If oxygen refers to burner/oxidizer flow rather than chamber atmosphere, set o2_context accordingly.
```
The code then checks `quote in page_text` and that the number appears in `quote`. Otherwise the proposal is rejected automatically.

**Time budget:** expect **6–8 person-hours** of human verification for about 15 investigations.

---

## 10. Core algorithms (with reference code)

### 10.1 Per-dimension interval distance (log space)
Flame responses follow power laws, so distances are computed in log space. Distance to a tested **interval** [a, b] is 0 inside the interval and the log distance to the nearest edge outside it.

```python
# ember/engine/distance.py
from math import log

DIMS = ("x_o2", "p_kpa", "u_cms")
U_FLOOR_CMS = 0.1  # avoid log(0) for quiescent tests; document this choice


def interval_log_distance(x: float, lo: float, hi: float) -> float:
    if lo <= x <= hi:
        return 0.0
    return min(abs(log(x / lo)), abs(log(x / hi)))
```

### 10.2 Elasticities (weights from NASA correlations)
```python
# ember/config.py
ELASTICITY = {
    # Ruff 2021, NTRS 20210021318: opposed  V_f ∝ X_O2^0.9 · P^0.05
    "spread_opposed": {"x_o2": 0.9, "p_kpa": 0.05, "u_cms": 0.0},
    # Ruff 2021: concurrent  V_f ∝ X_O2 · u · P^0.5
    "spread_concurrent": {"x_o2": 1.0, "p_kpa": 0.5, "u_cms": 1.0},
}
UNIFORM = {"x_o2": 1.0, "p_kpa": 1.0, "u_cms": 1.0}  # labeled "unweighted" in UI
```
Phenomena without a published correlation (ignition, extinction, smoke, etc.) use `UNIFORM`, and the UI shows an **"unweighted"** badge. *Note for the team:* BASS-II's non-monotonic flow dependence (§3.1) means `u` elasticity for opposed spread isn't constant. Keeping `ε_u = 0` for opposed spread follows the published correlation. Show a tooltip about it.

### 10.3 Transfer distance D
`D(s,e) = Σ_k |ε_k^φ| · Δ_k(s,e)`

If `Y ∝ Π x_k^{ε_k}`, then `|Δ ln Y| ≤ D`, so **`exp(D)` is the largest response factor the correlation implies** between the evidence and the scenario. It's interpretable and falsifiable (Saffire VI is a case where model expectations failed). Unknown dimensions contribute 0 and set `D_is_lower_bound = True`.

```python
def transfer_distance(s: dict, e: dict, phen: str) -> tuple[float, bool, dict]:
    eps = ELASTICITY.get(phen, UNIFORM)
    D, lower_bound, parts = 0.0, False, {}
    for k in DIMS:
        w = abs(eps.get(k, 0.0))
        if s.get(k) is None or w == 0:
            continue
        lo, hi = e.get(f"{k}_min"), e.get(f"{k}_max")
        if lo is None or hi is None:
            lower_bound = True
            parts[k] = None
            continue
        x = s[k]
        if k == "u_cms":
            x, lo, hi = max(x, U_FLOOR_CMS), max(lo, U_FLOOR_CMS), max(hi, U_FLOOR_CMS)
        d = w * interval_log_distance(x, lo, hi)
        parts[k] = d
        D += d
    return D, lower_bound, parts  # parts → "why" bars in UI
```

### 10.4 Relevance score
`R = M_φ · M_f · Q · exp(−D)`

These are **disclosed ordinal priors, not physics**, and their sensitivity is tested in §10.5:

| Factor | Values |
|---|---|
| `M_φ` phenomenon match | 1.0 exact · 0.5 related (e.g., spread↔extinction, smoke↔detector) · 0.1 other |
| `M_f` fuel match | 1.0 same fuel class + same material · 0.6 same class · 0.3 different class |
| `Q` granularity | 1.0 per-test table · 0.6 campaign summary · 0.3 paper-only |

```python
# ember/engine/score.py
from math import exp

RELATED = {
    ("spread_opposed", "spread_concurrent"),
    ("spread_opposed", "extinction"),
    ("spread_concurrent", "extinction"),
    ("smoke_particles", "detector_response"),
    ("extinction", "suppression"),
    ("limiting_oxygen", "spread_opposed"),
    ("limiting_oxygen", "extinction"),
    ("cool_flame", "extinction"),
}
Q_PRIOR = {"per_test_table": 1.0, "campaign_summary": 0.6, "paper_only": 0.3}


def m_phi(q, ephens):
    if q in ephens:
        return 1.0
    if any((q, p) in RELATED or (p, q) in RELATED for p in ephens):
        return 0.5
    return 0.1


def m_f(s_class, s_name, e_class, e_name):
    if s_class is None:
        return 1.0
    if s_class == e_class and s_name and e_name and s_name.lower() in e_name.lower():
        return 1.0
    if s_class == e_class:
        return 0.6
    return 0.3


def score(s, e, priors=None):
    D, lb, parts = transfer_distance(s, e, s["phenomenon"])
    R = (
        m_phi(s["phenomenon"], e["phenomena"])
        * m_f(s.get("fuel_class"), s.get("fuel_name"), e["fuel_class"], e.get("fuel_name"))
        * Q_PRIOR[e["granularity"]]
        * exp(-D)
    )
    return {
        "R": R,
        "D": D,
        "expD": exp(D),
        "D_lower_bound": lb,
        "parts": parts,
        "flags": flags_for(s, e, D, lb),
    }
```

### 10.5 Flags and Monte Carlo rank stability
```python
# ember/engine/flags.py
def flags_for(s, e, D, lb):
    f = []
    g = s.get("gravity_g0")
    if g is not None and g not in (0.0, 1.0):
        f.append(
            "GRAVITY_EXTRAPOLATION: evidence is µg/1-g; partial-g behavior may lie OUTSIDE both (FM2/Ruff 2021)."
        )
    if D > 1.0:
        f.append("BEYOND_TESTED_ENVELOPE: implied response factor exp(D) > e ≈ 2.7×.")
    if lb:
        f.append("INCOMPLETE_CONDITIONS: one or more conditions unknown; D is a lower bound.")
    if e.get("o2_context") == "burner_oxidizer_flow":
        f.append("BURNER_SIDE_O2: oxygen value is burner/oxidizer flow, not ambient atmosphere.")
    if e.get("psi_id") is None:
        f.append("NON_PSI_SOURCE")
    if e.get("tensions"):
        f.append("TENSION: " + "; ".join(e["tensions"]))
    return f
```

```python
# ember/engine/robustness.py
import numpy as np
from scipy.stats import kendalltau


def rank_stability(scenario, evidence, n=1000, prior_pct=0.5, eps_pct=0.3, k=5, seed=0):
    rng = np.random.default_rng(seed)
    base = rank(scenario, evidence)  # list of evidence_ids
    topk_counts, taus = {eid: 0 for eid in base}, []
    for _ in range(n):
        pert = perturb(ELASTICITY, Q_PRIOR, M_PRIORS, rng, prior_pct, eps_pct)  # uniform ±
        r = rank(scenario, evidence, overrides=pert)
        for eid in r[:k]:
            topk_counts[eid] += 1
        taus.append(kendalltau(rank_positions(base), rank_positions(r, base)).statistic)
    p_topk = {eid: c / n for eid, c in topk_counts.items()}
    return {"p_topk": p_topk, "kendall_tau_median": float(np.median(taus))}


# UI: "stable" badge if p_topk[eid] >= 0.8
```

### 10.6 GapScope: coverage and priority
- **Grid:** X_O₂ 0.15→0.40 (26 steps); P 30→105 kPa (20 log-spaced steps); u ∈ {0, 1, 5, 10, 20, 40} cm/s; g ∈ {0, 0.166, 0.38, 1}.
- **Coverage:** `C(x) = max_e exp(−D(x, e))` over evidence with the same phenomenon (and fuel class if chosen). For `g ∉ {0, 1}`: `C = 0`, hatched as **"no evidence in PSI"**, with LUCI (air, ~1 atm, ~0.165 g, non-PSI) and FM2 (34%/8.2 psia, lunar, data pending) as labeled overlays.
- **Priority:** `π(x) = (1 − C(x)) · T(x)`, where `T = 1` within a tolerance box around NASA target atmospheres (21%/101.3 kPa; 26.5%/70.3 kPa; 34%/56.5 kPa) and 0.25 elsewhere. **Label π a heuristic, not information gain.**
- **Gap report** (templated, not LLM-free-text): top-N uncovered target cells, with the nearest evidence and its D, phrased as "absence of evidence," **never "safe."**
- **Validation:** the map must recover NASA's documented gaps (2021-2934-TX06 and 2021-2900-TX06: exploration atmospheres + partial g). Also test sensitivity to grid resolution.

```python
TARGETS = [
    ("ISS/Earth", 0.21, 101.3),
    ("10.2 psia option", 0.265, 70.3),
    ("Exploration Atm 8.2/34", 0.34, 56.5),
]


def coverage_grid(evidence, phen, fuel_class=None, u=None, g=0.0):
    X = np.linspace(0.15, 0.40, 26)
    P = np.geomspace(30, 105, 20)
    C = np.zeros((len(P), len(X)))
    if g not in (0.0, 1.0):
        return X, P, C  # all zero, hatched
    pool = [
        e
        for e in evidence
        if phen in e["phenomena"]
        and (fuel_class is None or e["fuel_class"] == fuel_class)
        and e["gravity"] == ("microgravity" if g == 0 else "1g")
    ]
    for i, p in enumerate(P):
        for j, x in enumerate(X):
            s = {"x_o2": x, "p_kpa": p, "u_cms": u, "phenomenon": phen}
            C[i, j] = max((np.exp(-transfer_distance(s, e, phen)[0]) for e in pool), default=0.0)
    return X, P, C
```

### 10.7 CompareLab: rule-gated comparability
Rules are evaluated in order. The first failing rule sets the verdict.

| # | Rule | Fail → |
|---|---|---|
| 1 | Same canonical quantity | not comparable |
| 2 | Units convertible (pint) | not comparable |
| 3 | Same `value_kind` (measured vs set-point vs range) | caveat |
| 4 | Same context (ambient vs burner O₂; cabin vs duct) | **not comparable** (e.g., CFI-G burner O₂ vs cabin O₂) |
| 5 | Hardware/scale confounders (MSG duct vs Saffire Flow Unit; Saffire duct 25 cm vs 15 cm; droplet vs solid) | caveat (list them) |
| 6 | Same regime (gravity, flow direction, extinction mode) | caveat |

Output: `{verdict, shared_conditions, differing_conditions, confounders[], normalizations_applied (e.g., ppO₂ = X_O₂·P)}`.
**Validation:** 60 hand-labeled pairs. **Primary metric: false-"comparable" rate (target 0).**

### 10.8 Worked example (hand-calculated; must be reproduced by tests)
Scenario: opposed-flow spread at X_O₂ = 0.34, P = 56.5 kPa (8.2 psia).
- vs **BASS-II-like point** (0.21, 101 kPa): `D = 0.9·ln(0.34/0.21) + 0.05·ln(101/56.5) = 0.4336 + 0.0290 ≈ 0.463` → `exp(D) ≈ 1.59`
- Same pair, **concurrent** spread (ignoring u): `1.0·0.4818 + 0.5·0.5809 ≈ 0.772` → `exp(D) ≈ 2.16`
- vs **Saffire VI point** (0.310, 54.1 kPa): `0.9·ln(0.34/0.31) + 0.05·ln(56.5/54.1) = 0.0831 + 0.0022 ≈ 0.085` → `exp(D) ≈ 1.09`
- vs **Saffire VI interval** (0.288–0.310, 54.1–55.2 kPa): `0.0831 + 0.05·ln(56.5/55.2) ≈ 0.084`

Interpretation for the demo: Saffire VI is far "closer," but it carries `NON_PSI_SOURCE` (until verified) and `TENSION` (spread exceeded model prediction) flags.

### 10.9 Optional stretch analytics (only after the MVP is done)
- **SmokeSignal:** from SAME-R CSVs, compute count/mass ratio per run, fit lognormal `(d_g, σ_g)` from moments M0, M1, M3 (Hatch–Choate). Compare smoke runs with the DAFT ambient baseline via ROC/AUC. Caveat (NASA): moment methods "work well only for spherical particles." First reproduce the published 100–600 nm range.
- **DropletKit:** d²-law fits and an extinction-mode map from FLEX's 274 rows; grouped CV by fuel/diluent. Watch for leakage (no space/ground column).
- **FlameVision:** a single BASS-II clip, threshold + front tracking, Theil–Sen slope with bootstrap CI. Needs a reference length in frame.
- **Graph view:** NetworkX of evidence ↔ hardware ↔ instrument ↔ fuel; Jaccard similarity.

---

## 11. LLM layer: parser, narrator, verifier

### 11.1 Client
Provider-agnostic wrapper (e.g., Anthropic `claude-sonnet-5-5` / `claude-haiku-5-5`, or any OpenAI-compatible endpoint), set by env var. It **caches every request/response by hash** to `cache/`. If there's no key or the network is down, it falls back to templates. Temperature 0.

### 11.2 Question parser
System prompt:
```
Convert the user's fire-safety question into JSON matching this schema: <Scenario JSON schema>.
Rules:
- Convert units: % O2 -> fraction; psi/psia -> kPa (×6.89476); atm -> kPa (×101.325); bar -> kPa (×100).
- "Moon/lunar" -> gravity_g0 = 0.166; "Mars" -> 0.38; "ISS/orbit/spacecraft cabin" -> 0.0; "Earth/ground" -> 1.0.
- "Exploration atmosphere" or "lunar habitat atmosphere" with no numbers -> x_o2 = 0.34, p_kpa = 56.5, and set notes = "assumed NASA Exploration Atmosphere (TP-2010-216134)".
- Map fabric/paper/thin films -> thin_solid; PMMA blocks/thick plastics -> thick_solid; fuel droplets -> liquid_droplet.
- If something is not stated, use null. Never guess airflow.
Return ONLY JSON.
```
The UI then shows a **scenario chip** (editable sliders). The user must confirm before ranking runs.

### 11.3 Narrator (cite-or-drop) + verifier
The narrator gets **only**: the confirmed scenario, the top-k ranked records (fields + flags + D parts), and the claims attached to those records. Instruction: every sentence ends with `[evidence_id]` or `[source_id]`. No numbers that aren't in the provided records.

**Verifier rules** (`ember/llm/verifier.py`). A sentence that fails is **dropped** (not rewritten) and the drop count is shown:
1. Every sentence has ≥1 citation, and every cited ID exists in the payload.
2. Every number in a sentence string-matches a number in the cited record (after unit normalization, tolerance ±1 in last digit).
3. If "85" appears near "CFI-G", the sentence must contain "burner" or "oxidizer".
4. If the scenario has `gravity_g0 ∉ {0, 1}` or the text mentions Moon/lunar/Mars, append the partial-g disclaimer. Reject any sentence matching `/(measured|tested|observed).{0,30}(lunar|moon|mars|partial)/i` unless it cites LUCI/FM2 and is marked non-PSI.
5. Units only from the controlled list; otherwise replace with "unit not stated."
6. If any top-k record has D > 1, prepend the "beyond tested envelope" banner.
7. Claims carry a `claim_type` badge (measured / derived / modeled / author interpretation / system inference).
8. Reject the words "safe", "proves", "guarantees" applied to scenarios.

### 11.4 Template fallback (no LLM)
`"{investigation} ({evidence_id}) tested {phenomenon} with {fuel_name} at X_O₂ {x_o2_range}, P {p_range} kPa, flow {u_range} cm/s in {gravity}. Distance to your scenario D = {D:.2f} (implied factor ≤ {expD:.2f}×). Flags: {flags}."`

---

## 12. Baselines and evaluation harness

### 12.1 Gold set
- **40 queries** (Appendix B gives the bank). Each query is a natural-language question plus its confirmed Scenario.
- **Two annotators** label each (query, evidence) pair 0–3 using **NASA documents only** (0 irrelevant, 1 tangential, 2 relevant, 3 directly applicable). Report **Cohen's κ** (weighted).
- **Freeze labels (git tag `gold-v1`) before any tuning.** Biggest risk: circularity, i.e. annotators labeling with EMBER's logic in mind. Mitigation: the second annotator doesn't see EMBER's output, and the labeling guideline is written from the challenge and NASA docs only.

Files: `eval/gold/queries.yaml`, `eval/gold/qrels_A.csv`, `qrels_B.csv`, `qrels_final.csv`.

### 12.2 Systems compared
1. **Random** (seeded).
2. **BM25** over investigation descriptions + abstracts.
3. **Dense**: sentence-transformers + FAISS cosine.
4. **Hybrid**: reciprocal rank fusion of BM25 + dense (k = 60).
5. **Additive** competitor-style: 35 phenomenon + 25 fuel + 20 O₂ match + 10 pressure match + 10 data quality (linear, hand-set).
6. **EMBER** (full).

### 12.3 Metrics
nDCG@5 (graded), Recall@5 (rel ≥ 2), MRR (first rel ≥ 2). **Bootstrap 95% CIs** (1,000 resamples over queries) and a **paired permutation test** EMBER vs best baseline.

```python
def ndcg_at_k(ranked, rels, k=5):
    import numpy as np

    gains = [(2 ** rels.get(d, 0) - 1) / np.log2(i + 2) for i, d in enumerate(ranked[:k])]
    ideal = sorted(rels.values(), reverse=True)[:k]
    idcg = sum((2**r - 1) / np.log2(i + 2) for i, r in enumerate(ideal))
    return sum(gains) / idcg if idcg > 0 else 0.0
```

### 12.4 Ablations
Uniform ε · drop Q · drop M_f · drop M_φ · midpoint distance instead of interval distance · linear instead of log distance.

### 12.5 Additional checks
- **Adversarial prompts** (must produce refusal or disclaimer): "What did FLEX measure on the Moon?", "Is Nomex safe at 34% O₂?", "What was the cabin oxygen in CFI-G?", "Give me the lunar flame spread rate for PMMA.", "Which water-mist test is best?" Metric: % handled correctly (target 100%).
- **Verifier audit:** 50 generated sentences hand-checked; report the unsupported-claim rate after verification.
- **CompareLab:** false-comparable rate on 60 pairs.
- **User test:** 5 users × 3 tasks (find the closest test to 8.2/34; decide if two measurements can be compared; name one untested condition). Compare EMBER with the PSI website on time-to-answer and correctness.
- **Falsification rule:** if EMBER ≤ best baseline on nDCG@5 (CI overlapping), say so on the Validation page and narrow the claim.

---

## 13. Dashboard / UI spec (Streamlit + Plotly)

**Global:** a sidebar scenario chip (O₂ slider, P slider with psi/kPa toggle, flow slider, gravity selector, phenomenon, fuel class) and **presets**: ISS (0.21/101.3/µg), Exploration Atmosphere Moon (0.34/56.5/0.166), 10.2-psia option (0.265/70.3), Mars habitat (user-entered; flag), Pressurized rover (preset = Exploration Atm, label [A]). A badge legend is always visible.

| Page | Contents |
|---|---|
| **Ask** | Question box → parsed scenario chip (confirm/edit) → ranked list (top 10): investigation, evidence_id, R, D, exp(D), stacked "why" bar (D parts by dimension × priors), badges (stable, unweighted, lower-bound, gravity, burner-O₂, non-PSI, tension). Cited summary below with hover-to-source. "Dropped sentences: n" counter. |
| **Evidence Map** | Scatter of X_O₂ vs P (log P), each evidence as a range box/point colored by phenomenon, marker shape by gravity. Scenario star. NASA target-atmosphere rectangles. Toggle ppO₂ isolines (ppO₂ = X_O₂·P). Dragging the scenario re-ranks live. |
| **Compare** | Pick 2+ evidence records or measurements → verdict card (green/amber/red), shared vs differing conditions table, confounders list, normalizations applied. Preloaded example: BASS-II vs Saffire-III → "comparable with caveats" (hardware, scale, enclosure). |
| **Gaps** | Coverage heatmap C(x) for the chosen phenomenon/fuel/flow; priority overlay π; **hatched partial-g panels** for 0.166 g and 0.38 g with LUCI/FM2 labeled "not in PSI"; templated gap report download (Markdown). |
| **Registry** | Filterable table of all evidence with units and provenance columns; "unknown" shown explicitly; CSV/Parquet export + data dictionary. |
| **Validation** | Gold-set results table (all systems, CIs), ablation chart, adversarial pass rate, CompareLab false-comparable rate, κ. **Only real numbers.** If not yet run, show "pending" rather than placeholder values. |
| **Sources** | Every source: title, year, URL/DOI, in_psi, sha256, retrieved_at, which records cite it. |

Design: clean scientific look (dark-on-light), color-blind-safe palette, one accent color for the scenario, hatching for "no evidence."

---

## 14. Test plan (pytest)

| Test | Asserts |
|---|---|
| `test_units.py` | 8.2 psi → 56.54 kPa; 10.2 psi → 70.33 kPa; 34% → 0.34; 2 bar → 200 kPa; mm/s→cm/s |
| `test_distance.py` | Inside interval → 0; worked examples: D(BASS-II pt, opposed) = 0.463±0.002; concurrent = 0.772±0.002; Saffire VI pt = 0.085±0.002; interval = 0.084±0.002 |
| `test_lower_bound.py` | Missing O₂ in evidence → `D_lower_bound=True` and the dimension excluded |
| `test_flags.py` | g=0.166 → gravity flag; CFI-G burner context → BURNER_SIDE_O2; D>1 → envelope flag |
| `test_score.py` | Monotonic: moving the scenario toward evidence never lowers R; priors applied |
| `test_robustness.py` | Deterministic with a seed; p_topk ∈ [0,1] |
| `test_gapscope.py` | g ∉ {0,1} → all-zero coverage; coverage = 1 at an evidence point |
| `test_comparelab.py` | CFI-G burner O₂ vs ambient O₂ → not comparable; Saffire I vs IV spread → caveat (duct size) |
| `test_schemas.py` | `known` Range without provenance raises |
| `test_verifier.py` | Drops uncited sentences, wrong numbers, "measured on the Moon," "85% … CFI-G" without "burner," and the word "safe" |
| `test_parser.py` (cached) | "lunar habitat at 34% and 8.2 psi, fabric" → x_o2 0.34, p 56.5, g 0.166, thin_solid |
| `test_metrics.py` | nDCG on toy rankings matches hand computation |
| `test_registry_integrity.py` | Every evidence row has ≥1 source; every source in manifest; no duplicate IDs |

---

## 15. Build tickets (ordered, for Claude Code)

Do these in order. Each ticket ends with the tests passing and a short summary.

1. **T01 Scaffold.** Create the repo per §7, pyproject with deps, pre-commit (ruff), pytest config, README skeleton with a Limitations section. Empty Streamlit app with 7 pages.
2. **T02 Schemas + units.** Implement §8 and `units.py`; `test_schemas.py`, `test_units.py`.
3. **T03 Config.** `config.py`: ELASTICITY, UNIFORM, priors, RELATED, grids, TARGETS, U_FLOOR, with source comments citing Ruff 2021 / TP-2010-216134.
4. **T04 Engine: distance + score + flags.** §10.1–10.5 (flags). Tests incl. the worked example (§10.8).
5. **T05 Seed registry.** Load `data/seed/*.yaml` from Appendix A into DuckDB/Parquet via `build_registry.py`. Every value gets source + locator; unknowns stay unknown. `test_registry_integrity.py`.
6. **T06 Ask page (deterministic).** Sliders/presets → ranked table + why-bars + badges + template narration. **This is the first demoable milestone.**
7. **T07 Evidence Map page.** Plotly O₂–P map with range boxes, target rectangles, ppO₂ isolines, scenario star.
8. **T08 Robustness.** Monte Carlo + stable badge; cache results per scenario.
9. **T09 GapScope.** §10.6 + Gaps page + templated gap report export.
10. **T10 CompareLab.** Measurement vocab + rule engine + Compare page; `test_comparelab.py`.
11. **T11 Ingest.** Manifest-driven downloader (checksums, 404 logging), NTRS client, table parsers for PSI-25/26/69/100/101/159 (adapt to actual file formats once downloaded); update the registry from parsed tables.
12. **T12 Paper extraction + review CLI.** §9.4–9.5 with the span check.
13. **T13 Retrieval baselines.** BM25, dense/FAISS, hybrid RRF, additive.
14. **T14 Eval harness.** Gold-set loader, metrics, bootstrap/permutation, ablations, `run_eval.py` → `results.json` → Validation page.
15. **T15 LLM layer.** Client with cache + fallback, parser, narrator, verifier; adversarial suite.
16. **T16 Registry + Sources pages + export.**
17. **T17 Polish.** Badge legend, guided demo mode (step-by-step), pre-cache demo queries, offline check (disconnect network, run demo).
18. **T18 (stretch)** SmokeSignal / DropletKit / graph view / one-video FlameVision, in that order, only if T01–T17 are done.

**Copy-paste prompt for Claude Code to start:**
> Read EMBER_BUILD_SPEC.md fully. Obey Section 0. Start with ticket T01. After each ticket: run `pytest -q`, show me the results, and list any assumption you made. Never add a numeric value to the registry without a source and locator from the spec or a downloaded file. If a PSI file's actual structure differs from the spec, stop and show me the columns before writing a parser.

---

## 16. 36-hour hackathon timeline

| Phase | Hours | Tasks | Done when |
|---|---|---|---|
| 1 Foundation | 0–3 | Read official resources (released Nov 13); assign roles; lock the 15-investigation scope | Everyone can explain ε, D, exp(D) and the gravity flag |
| 2 Acquisition | 3–8 | Download PSI tables and NTRS papers; checksums | Manifest complete; 404s logged |
| 3 Processing | 6–14 | Parsers, registry, LLM-assisted extraction + human verification | Provenance on every row |
| 4 Engine | 10–20 | Distance, ranker, Monte Carlo, gap field, CompareLab, baselines | Tests reproduce D ≈ 0.463 and 0.085 |
| 5 Dashboard | 14–26 | Ask → chip → ranking "why" → compare → gaps → sources | Error-free click-through |
| 6 Integration | 22–28 | LLM parser, narrator, verifier, cache | Adversarial prompts handled |
| 7 Validation | 24–32 | Gold set, metrics, ablations, 5-user test | CIs reported (whatever the result) |
| 8 Demo | 30–36 | Script, backup video, slides, README limitations | Two rehearsals under 5 minutes |

**Suggested roles (4 people):** (1) data/curation lead (ingest, review, registry); (2) engine/eval lead (distance, MC, GapScope, CompareLab, metrics); (3) UI lead (Streamlit, Plotly, demo mode); (4) science + LLM + pitch lead (parser/narrator/verifier, gold-set annotation B, slides, Q&A).

**Before Nov 13 (now):**
1. Open PSI-25, 69, 159, 100 and 101 in a browser; confirm the tables exist and can be downloaded; note the real file names and formats.
2. Hand-compute D for three scenarios (§10.8) so the team understands it.
3. Write and **freeze** 15 gold queries + labeling guideline.

---

## 17. Demo script and slide outline

### 17.1 Live demo (about 3 min, all answers pre-cached, real values only)
1. Type: *"Which NASA experiments best inform fabric and plastic flammability in a lunar habitat at 34% oxygen and 8.2 psi?"*
2. The scenario chip appears: X_O₂ 0.34, P 56.5 kPa, g 0.166 (**gravity flag lit**), phenomenon = spread, fuel = thin/thick solid. Confirm.
3. The ranked list: Saffire VI (non-PSI + tension flags), BASS-II, Saffire I–III, BASS, ... Each row has a why-bar, D, exp(D) and badges. Hover on BASS-II: "O₂ contributes 0.43 of D=0.46."
4. Compare BASS-II vs Saffire-III → **"comparable with caveats"**: different hardware (MSG duct vs Saffire Flow Unit), sample scale, enclosure.
5. Conditions table with DOIs (10.60555/...).
6. Cited summary; hover a citation → source page/row. "Dropped sentences: 0."
7. Gaps tab: the hatched lunar-g band. "No PSI evidence; LUCI (air, 1 atm) and FM2 (34%/8.2 psia, pending) are the only partial-g sources."
8. Drag the scenario to 21% / 14.7 psia → the ranking reshuffles, BASS-II rises, flags clear.
9. **Climax:** "Would we trust #1 to choose a cabin fabric for 34% O₂? **No.** Here's exactly which test is missing" (the gap report).

### 17.2 Slides (9)
1. Why fire safety matters in crewed spaceflight (Apollo 1, Mir 1997, ISS detector false alarms); Artemis-era habitat atmospheres.
2. The data problem: 24 investigations, ~13 TB, mostly video; applicability is the bottleneck.
3. The PSI landscape: the matrix, hardware families, what's machine-readable.
4. Why RAG and additive scores aren't enough (they retrieve text but don't measure condition distance; weights are hand-set).
5. **Transfer distance**: elasticities from Ruff 2021; BASS-II vs Saffire VI worked example; exp(D) as an implied bound.
6. Architecture (deterministic core, constrained LLM).
7. Live demo.
8. Validation: gold set, baselines, nDCG/MRR with CIs, ablations, adversarial pass rate. **Actual numbers only.**
9. Gap map, LUCI/FM2 integration path, Earth applications (detector design, materials screening), future work.

---

## 18. Judge-defense Q&A (15)

1. **Where do the weights come from?** NASA's 2021 fire-safety roadmap (Ruff, NTRS 20210021318) spread correlations, used only for the matching phenomenon. We perturb them ±30% and show rank stability.
2. **Is exp(D) a prediction?** No. It's the largest response factor the published correlation implies, and Saffire VI shows such expectations can fail. That's why we surface the tension.
3. **What if O₂ is missing for a test?** D becomes a lower bound and the row gets an "incomplete" badge. We never impute.
4. **Other teams rank too. What's different?** Their weights are hand-set. Ours come from physics, are stability-tested, and are benchmarked against lexical/dense/additive baselines on a frozen gold set.
5. **How do you stop hallucinations?** The LLM never ranks. Summaries are cite-or-drop, and numbers are string-verified against registry records; failing sentences are dropped and counted.
6. **Can I compare Saffire I with Saffire IV?** Only with caveats: the duct half-height changed from 25 to 15 cm, and NASA found enclosure size mattered more than expected.
7. **CFI-G tested 85% oxygen. Isn't that the best lunar evidence?** No. 85% was burner/oxidizer-side flow in inverse flames, not cabin atmosphere. Cool flames appeared only at 2 bar with ambient X_O₂ 0.39.
8. **Why no machine learning?** A few hundred structured tests, no partial-g labels and heterogeneous phenomena. A model would overfit and couldn't be validated for lunar conditions. We export clean, unit-normalized tables for modelers instead.
9. **Why not interpolate between 0-g and 1-g for the Moon?** NASA reports lunar-g flammability can exceed both (the "goldilocks zone," FM2 abstract; Ruff 2021). Interpolation could be unconservative.
10. **What about E-FIELD?** It's an ion-wind body-force analog that mimics buoyancy effects. Useful context, not a gravity measurement.
11. **Your gold set is self-labeled. Isn't it circular?** Two annotators, κ reported, guideline written from NASA documents, labels frozen before tuning. We report negative results.
12. **How would NASA deploy this?** The registry is portable Parquet with provenance. Adding LUCI/FM2 data is a data update, and the elasticity table can be extended as correlations are published.
13. **Did you process all 13 TB?** No, and we didn't need to. EMBER reasons over test conditions and measurements, not pixels. Video extraction is a scoped stretch module.
14. **Water mist?** No PSI water-mist dataset was found, so it's shown as a gap rather than invented.
15. **Detection at lunar conditions?** We use SAME/SAME-R size distributions and the DAFT ambient baseline. There are no 8.2-psia smoke data, and we flag that. Lunar dust overlapping smoke sizes is a hypothesis worth testing, not a finding.

---

## 19. Reading list: papers and NASA documents (annotated)

> **What to extract** tells the curation lead which values to pull into the registry. Verify every URL on download.

### 19.1 Challenge and repository
| # | Document | URL / ID | Establishes | What to extract |
|---|---|---|---|---|
| R1 | Space Apps 2026 challenge page | spaceappschallenge.org/2026/challenges/flame-in-freefall/ | Official objectives, hints, scope | Requirement checklist (§2) |
| R2 | HackAthlone mirror of challenge | hackathlone.com/challenges/flame-in-freefall | Same text; lunar 30%/10.2 psi; CFI-G 85% burner; no partial-g | Exact quotes for slides |
| R3 | NASA PSI repository | psi.nasa.gov/physci/repo/ | Investigation records, files, DOIs | Everything in §4 |
| R4 | NASA Science Data: PSI updates (2025) | science.data.nasa.gov/features-events/physical-sciences-informatics-updates | 2014 start (17 datasets) → >100 datasets, ~30 TB; DOIs in 2024 | Background slide |
| R5 | PSI-25 BASS-II record | psi.nasa.gov/physci/repo/data/investigations/PSI-25 | CC0, DOI, file list | Files, license |
| R6 | PSI-102 SAME record | psi.nasa.gov/physci/repo/data/investigations/PSI-102 | CC0, DOI | Files |
| R7 | Swapnil Tamse challenge resource page | spacedata.swapniltamse.com/challenges/flame-in-freefall/ | "No documented public API, expect manual downloads" | Access plan |

### 19.2 NASA programmatic and fire-safety documents
| # | Document | URL / ID | Establishes | What to extract |
|---|---|---|---|---|
| N1 | **Ruff, "Technology Development for Spacecraft Fire Safety" (2021)** | NTRS 20210021318 · ntrs.nasa.gov/api/citations/20210021318/downloads/Tech%20Dev%20for%20Spacecraft%20Fire%20Safety_Location_10-7-2021.pdf | µg spread correlations (concurrent `X·u·P^0.5`, opposed `X^0.9·P^0.05`); "O₂ effect ≫ P effect"; lunar-g LOC < 1-g | **Elasticities (config.py)**; quotes for slides |
| N2 | **NASA/TP-2010-216134, Exploration Atmospheres Working Group** | nasa.gov/wp-content/uploads/2023/03/henninger-8.2-34-atm-tp216134-2010.pdf | 8.2 psia / 34% O₂; 32% cap for flammability; 36% supportable | Target atmospheres |
| N3 | Exploration Atmosphere evidence report (HRP) | humanresearchroadmap.nasa.gov/evidence/reports/ExpAtm.pdf | Rationale and control box 33.5–35% | Target box tolerances |
| N4 | Internal Layout of a Lunar Surface Habitat (2022) | NTRS 20220013669 | Habitat atmosphere context | Preset descriptions |
| N5 | NASA "Combustion in Reduced Gravity" ISS mini-book | nasa.gov/wp-content/uploads/2016/05/np-2015-10-034-jsc_combustion_in_reduced_gravity-iss-mini-book-011116-508.pdf | Accessible physics overview; investigation descriptions | Investigation card text |
| N6 | NASA ACME fact sheet (2025) | nasa.gov/wp-content/uploads/2025/07/advanced-combustion-via-microgravity-experiments-acme.pdf | Six ACME experiments, objectives | Card text, hardware family |
| N7 | NASA GRC ACME publications list (2023) | www1.grc.nasa.gov/wp-content/uploads/ACME-publications-20230830.pdf | Paper list; CLD soot 5–8× | Paper targets for extraction |
| N8 | NASA DAFT fact sheet (2025) | nasa.gov/wp-content/uploads/2025/07/dust-and-aerosol-measurement-feasibility-test-daft.pdf | P-Trak to 20 nm; ISS <0.005 mg/m³, ~15/cm³ | DAFT baseline values |
| N9 | NASA ECLSS technology gaps 2021-2934-TX06, 2021-2900-TX06 | NASA Technology Taxonomy / gap list **[TODO-VERIFY exact URL]** | Exploration-atmosphere and partial-g flammability data "very limited"; detector false alarms | GapScope validation targets |
| N10 | NASA Task Book: inter-project meta-analysis (FY2026) | taskbook.nasaprs.com (TASKID 31FF2895CF11A3D63C9B8986DB12A22A) | Cross-investigation physics synthesis (BASS/Saffire/Confined Combustion) | Prior-art citation |

### 19.3 Saffire, LUCI, FM2
| # | Document | URL / ID | Establishes | What to extract |
|---|---|---|---|---|
| S1 | **Preliminary Results from the Saffire VI Experiment (ICES-2024-365)** | NTRS 20240002981 · ntrs.nasa.gov/api/citations/20240002981/downloads/Saffire-ICES-2024-ICES-365-accepted%20final.pdf | VI: 54.1–55.2 kPa, 28.8–31.0% O₂; spread higher than IV vs model; duct 25→15 cm; products CO/CO₂/HCl/HF | **Saffire IV–VI evidence rows**, tension item |
| S2 | Saffire overview / I–III results (NTRS 20160000593) | ntrs.nasa.gov/api/citations/20160000593/downloads/20160000593.pdf | SIBAL 94×40.6 cm; large-scale spread | Saffire I–III conditions |
| S3 | Saffire results (NTRS 20180005168) | ntrs.nasa.gov/search.jsp?R=20180005168 | Additional Saffire findings | Flow, spread values |
| S4 | Saffire telemetry/related (NTRS 20230015380) | ntrs.nasa.gov/citations/20230015380 | Saffire-related data **[TODO-VERIFY content]** | — |
| S5 | **LUCI (NTRS 20250010653)** | ntrs.nasa.gov/citations/20250010653 | New Shepard centrifuge, 11 RPM, 1.22 m; >25 s lunar-g burns of SIBAL and 4 mm PMMA in air | Non-PSI overlay facts |
| S6 | **FM2 abstract (NTRS 20240015307)** | ntrs.nasa.gov/citations/20240015307 | "Goldilocks zone"; CLPS CP-21 late 2026; 34%/8.2 psia tests | Gravity-flag text, overlay |
| S7 | Science Alert: NASA to test fire on the Moon | sciencealert.com/nasa-plans-to-test-fire-on-the-moon-ahead-of-future-missions | Popular summary of FM2 | Slide color (secondary source) |
| S8 | Fire & Safety Journal Americas: NASA to test fire on the Moon | fireandsafetyjournalamericas.com/nasa-to-test-fire-on-the-moon/ | Same | Secondary |

### 19.4 Solid flammability (BASS / BASS-II / BRE)
| # | Paper | ID | Establishes | What to extract |
|---|---|---|---|---|
| B1 | **Link et al., "The effect of gravity on flame spread over PMMA cylinders," *Scientific Reports* 8 (2018)** | doi:10.1038/s41598-017-18398-4 · PMC5760683 | Non-monotonic spread vs flow; no spread <~0.6 cm/s; LOC ~17% µg vs ~18% 1-g | BASS-II conditions + LOC rows |
| B2 | ScienceDirect, *Combust. Flame* (2017) S0010218017300846 | sciencedirect.com/science/article/abs/pii/S0010218017300846 | BASS-related flame spread/extinction **[TODO-VERIFY authors]** | Conditions |
| B3 | ScienceDirect, *Combust. Flame* (2018) S0010218018300543 | sciencedirect.com/science/article/abs/pii/S0010218018300543 | BASS/solid fuel results **[TODO-VERIFY authors]** | Conditions |
| B4 | Kim et al., *Proc. Combust. Inst.* 39 (2022/23) | doi:10.1016/j.proci.2022.07.015 | Microgravity solid/flame results **[TODO-VERIFY scope]** | Conditions |
| B5 | Chien et al., *Combust. Flame* 246 (2022) 112443 | sciencedirect.com/science/article/pii/S0010218022004606 | Flame spread modeling/experiment **[TODO-VERIFY scope]** | Conditions, model context |
| B6 | UMD DRUM thesis/report (BRE or BASS related) | api.drum.lib.umd.edu/server/api/core/bitstreams/7d925f43-307b-4408-b3a5-5fd408848ecc/content | BRE: 1-g burning ~3–4× µg **[TODO-VERIFY]** | BRE conditions |
| B7 | Recent *Proc. Combust. Inst.* (2026) S154074892600324X | sciencedirect.com/science/article/pii/S154074892600324X | Recent microgravity combustion result **[TODO-VERIFY]** | — |
| B8 | NASA-STD-6001B (Flammability test standard) | NASA standards site **[TODO-VERIFY URL]** | Test 1 upward flame propagation | Explainer panel |

### 19.5 Droplets, suppression, cool flames (FLEX / FLEX-2 / CFI / CFI-G)
| # | Paper | ID | Establishes | What to extract |
|---|---|---|---|---|
| F1 | **Nayagam et al., "Effects of ambient oxygen and diluents on droplet extinction," *Microgravity Sci. Technol.* 26:65–76 (2014)** | doi:10.1007/s12217-014-9372-2 | Diffusive vs radiative extinction; diameter trends vs O₂; diluent effects | Extinction-mode rows, regimes |
| F2 | Nayagam ISS R&D Conference 2013 slides | astronautical.org/sites/default/files/issrdc/2013/issrdc_2013-07-16-0945_nayagam.pdf | Cool-flame discovery (~600 °C), FLEX overview | Cool-flame claim |
| F3 | Dotson et al., *Fire Safety Journal* (2011) | terpconnect.umd.edu/~pbs/2011%20Dotson%20et%20al.%20FSJ.pdf | Droplet/fire-safety relevance **[TODO-VERIFY scope]** | Context |
| F4 | CORE PDF 42721353 | files01.core.ac.uk/download/pdf/42721353.pdf | FLEX/droplet technical report **[TODO-VERIFY]** | Conditions |
| F5 | CFI-G papers via ACME publications list (N7) | — | Ethane/propane/n-butane cool diffusion flames; 2 bar; ambient 0.39; burner ≤85% | CFI-G rows with `o2_context` |
| F6 | ISS Daily Summary 2021-05-07 | nasa.gov/blogs/stationreport/2021/05/07/iss-daily-summary-report-5-07-2021/ | ACME/CFI-G operations log | Dates |

### 19.6 Smoke, aerosols, detection (SAME / SAME-R / DAFT)
| # | Paper | ID | Establishes | What to extract |
|---|---|---|---|---|
| A1 | **Meyer et al., *Fire Safety Journal*** | PMC7918997 | Smoke particle size from spacecraft materials; detector implications | Size ranges per material |
| A2 | NIST: Smoke Aerosol Measurement Experiment (SAME) | nist.gov/publications/smoke-aerosol-measuremen-experiment-same | SAME design/results | Card text |
| A3 | NASA AAAR 2020 platform talk (SAME-R) | ntrs.nasa.gov/api/citations/20205008167/downloads/AAAR%202020%20Platform%20v1.pdf | "Size selective smoke detection will improve reliability and false alarm rejection" | Detection quote |
| A4 | SAME NTRS 20050215648 | ntrs.nasa.gov/citations/20050215648 | Early SAME design | Instruments |
| A5 | SAME NTRS 20070031686 | ntrs.nasa.gov/api/citations/20070031686/downloads/20070031686.pdf | Smoke measurement methods; spherical-particle caveat | Method caveats |
| A6 | NTRS 20150010172 | ntrs.nasa.gov/api/citations/20150010172/downloads/20150010172.pdf | SAME/SAME-R results **[TODO-VERIFY]** | Size distributions |
| A7 | NTRS 20130013505 | ntrs.nasa.gov/api/citations/20130013505/downloads/20130013505.pdf | DAFT/ISS particulate results **[TODO-VERIFY]** | DAFT baseline |

### 19.7 Gas jets and soot (SPICE / SLICE / ACME gaseous)
| # | Paper | ID | Establishes | What to extract |
|---|---|---|---|---|
| G1 | SPICE smoke-point papers (via PSI-107 / PSI-60) | PSI pages | µg smoke-point lengths up to 2.3× longer | Smoke-point rows |
| G2 | SLICE papers (via PSI-106) | PSI pages | Lifted-flame structure; ~2× peak soot | Liftoff rows |
| G3 | ACME CLD/s-Flame/Flame Design papers (via N7) | — | Soot 5–8× in µg (CLD); soot-free design | Gaseous rows |

### 19.8 AI / retrieval / knowledge-graph prior art
| # | Paper | ID | Establishes |
|---|---|---|---|
| L1 | **Skarlinski et al., "Language agents achieve superhuman synthesis of scientific knowledge" (PaperQA2), 2024** | arXiv:2409.13740 | 85.2% vs 73.8% precision on LitQA2; strong text RAG baseline |
| L2 | Sharma & Raman, *Energy and AI* (2024) | — **[TODO-VERIFY DOI]** | Combustion-domain LLM QA |
| L3 | FlameBench (2026) | arXiv:2603.19268 | Combustion LLM benchmark; RAG doesn't fix multi-step inconsistency |
| L4 | FlamePilot (2026) | arXiv:2601.01357 | LLM CFD automation |
| L5 | NASA Earth-observation agentic search (2026) | arXiv:2607.02387 | Fused scorer >5× R@10/MRR over baselines; **benchmark methodology to copy** |
| L6 | OSDR/GeneLab + SPOKE (NAR 2025) | spoke.ucsf.edu/prototype-open-knowledge-network-proto-okn-spoke-space-health; github.com/BaranziniLab/spoke_genelab | NASA KG + LLM discovery |
| L7 | Robertson & Zaragoza, "The Probabilistic Relevance Framework: BM25 and Beyond" (2009) | doi:10.1561/1500000019 | BM25 baseline (foundational) |
| L8 | Järvelin & Kekäläinen, "Cumulated gain-based evaluation of IR techniques," *ACM TOIS* (2002) | doi:10.1145/582415.582418 | nDCG definition (foundational) |
| L9 | Cormack, Clarke & Büttcher, "Reciprocal Rank Fusion" (SIGIR 2009) | doi:10.1145/1571941.1572114 | Hybrid fusion baseline (foundational) |
| L10 | Reimers & Gurevych, "Sentence-BERT" (EMNLP 2019) | arXiv:1908.10084 | Dense retrieval baseline (foundational) |
| L11 | Saltelli et al., *Global Sensitivity Analysis: The Primer* (Wiley, 2008) | ISBN 978-0470059975 | Monte Carlo sensitivity framing |
| L12 | Wilkinson et al., "FAIR Guiding Principles," *Sci. Data* 3:160018 (2016) | doi:10.1038/sdata.2016.18 | Provenance/metadata framing |
| L13 | W3C PROV-O (2013) | w3.org/TR/prov-o/ | Provenance model reference |

*(L7–L13 are standard foundational references added for the methods; they weren't part of the research report's search log.)*

---

## 20. Open questions and verify-first list

| # | Question | Why it matters | How to resolve | Fallback |
|---|---|---|---|---|
| Q1 | Are PSI tables downloadable without registration? | Blocks ingestion | Try PSI-25/69/159/100/101 in a browser now | Manual download; NTRS-paper-only registry |
| Q2 | Real file counts (16,354 vs ~21,900) and table count (22 vs 20)? | Credibility of slide 3 | Count from PSI pages | Cite as "third-party estimates" |
| Q3 | Are Saffire IV–VI in PSI? | Top-ranked evidence label | Search PSI | Keep as `NON_PSI_SOURCE` from NTRS 20240002981 |
| Q4 | Does FLEX's table have 274 rows and a space/ground column? | Leakage, row checks | Open file | Mark gravity per test from papers |
| Q5 | BASS-II per-test O₂/flow/diameter columns present? | Core spread evidence | Open matrix | Campaign-level ranges from Link 2018 |
| Q6 | Saffire-III telemetry units and calibration? | Smoke detector and flow panels | Read file headers + docs | Show raw with "uncalibrated" badge |
| Q7 | SAME-R CSV calibration constants? | SmokeSignal | Docs/papers | Indicative only |
| Q8 | Official challenge resources (Nov 13) include a modeling-ready dataset? | Could change priorities | Check on release | Re-evaluate DropletKit |
| Q9 | Exact URLs for NASA gap entries 2021-2934-TX06 / 2021-2900-TX06 | GapScope validation citation | NASA techport/taxonomy search | Quote via Ruff 2021 |
| Q10 | Do elasticities transfer to thick vs thin fuels identically? | Scientific defensibility | Read Ruff 2021 context | Separate vectors or "unweighted" badge |

---

## 21. Appendix A: seed condition values (sourced)

Seed only these campaign-level envelopes until real per-test tables are parsed. **Values not listed stay `unknown`.** Fill `source_locator` with the exact page/table once you open each document.

```yaml
# data/seed/evidence_seed.yaml
- evidence_id: BASS-II:campaign
  investigation: BASS-II
  psi_id: PSI-25
  hardware_family: MSG+SPICE-duct
  fuel_class: thick_solid
  fuel_name: PMMA rods/slabs (also thin fuels)
  phenomena: [spread_opposed, spread_concurrent, extinction, limiting_oxygen]
  gravity: microgravity
  x_o2: {min: 0.136, max: 0.222, status: known, source_id: PSI-25, source_locator: "TODO page/table"}
  o2_context: ambient
  p_kpa: {status: unknown}          # fill from matrix
  u_cms: {min: 0.0, max: 40.0, status: known, source_id: PSI-25, source_locator: "TODO"}
  granularity: per_test_table      # downgrade to campaign_summary if matrix not obtained
  tensions: []
  sources: [PSI-25, "DOI:10.1038/s41598-017-18398-4"]

- evidence_id: BASS-II:LOC
  investigation: BASS-II
  psi_id: PSI-25
  hardware_family: MSG+SPICE-duct
  fuel_class: thick_solid
  fuel_name: PMMA rod
  phenomena: [limiting_oxygen]
  gravity: microgravity
  x_o2: {min: 0.17, max: 0.17, status: known, source_id: "DOI:10.1038/s41598-017-18398-4", source_locator: "TODO"}
  o2_context: ambient
  p_kpa: {status: unknown}
  u_cms: {status: unknown}
  granularity: paper_only
  measurements: [loc_x_o2]
  sources: ["DOI:10.1038/s41598-017-18398-4"]
  # note: 1-g comparison LOC ~0.18 from the same paper → separate 1g evidence row

- evidence_id: BASS:campaign
  investigation: BASS
  psi_id: PSI-26
  hardware_family: MSG+SPICE-duct
  fuel_class: thin_solid            # mixed; refine per test
  phenomena: [ignition, spread_opposed, spread_concurrent, extinction]
  gravity: microgravity
  x_o2: {min: null, max: 0.21, status: unknown}   # "≤21%": set min once matrix parsed
  o2_context: ambient
  p_kpa: {status: unknown}
  u_cms: {status: unknown}
  granularity: per_test_table
  sources: [PSI-26]

- evidence_id: SAFFIRE6:PMMA_SIBAL
  investigation: Saffire-VI
  psi_id: null                      # TODO-VERIFY presence in PSI
  hardware_family: Saffire Flow Unit/Cygnus
  fuel_class: thin_solid            # SIBAL; add separate thick_solid row for PMMA
  fuel_name: SIBAL fabric; PMMA
  phenomena: [spread_concurrent, spread_opposed]
  gravity: microgravity
  x_o2: {min: 0.288, max: 0.310, status: known, source_id: NTRS-20240002981, source_locator: "TODO"}
  o2_context: ambient
  p_kpa: {min: 54.1, max: 55.2, status: known, source_id: NTRS-20240002981, source_locator: "TODO"}
  u_cms: {status: unknown}
  enclosure_note: "Duct half-height 15 cm (vs 25 cm in Saffire I–III)"
  granularity: paper_only
  tensions: ["Flame spread higher than in Saffire IV although prior model predicted lower"]
  sources: [NTRS-20240002981]

- evidence_id: SAFFIRE1:SIBAL
  investigation: Saffire-I
  psi_id: PSI-98
  hardware_family: Saffire Flow Unit/Cygnus
  fuel_class: thin_solid
  fuel_name: SIBAL fabric 94 x 40.6 cm
  phenomena: [spread_concurrent]
  gravity: microgravity
  x_o2: {status: unknown}           # [A] likely Cygnus cabin air — DO NOT seed until sourced
  p_kpa: {status: unknown}
  u_cms: {status: unknown}
  enclosure_note: "Duct half-height 25 cm"
  granularity: campaign_summary
  sources: [PSI-98]

- evidence_id: CFIG:campaign
  investigation: ACME CFI-G
  psi_id: PSI-159
  hardware_family: ACME/CIR
  fuel_class: gas_jet
  fuel_name: ethane, propane, n-butane (normal and inverse flames)
  phenomena: [cool_flame, extinction, flame_structure]
  gravity: microgravity
  x_o2: {status: unknown}           # ambient values per test from table
  o2_context: unknown
  p_kpa: {min: null, max: 200, status: unknown}   # "up to ~2 bar": confirm
  u_cms: {status: unknown}
  granularity: per_test_table
  tensions: []
  sources: [PSI-159]

- evidence_id: CFIG:coolflame_2bar
  investigation: ACME CFI-G
  psi_id: PSI-159
  hardware_family: ACME/CIR
  fuel_class: gas_jet
  phenomena: [cool_flame]
  gravity: microgravity
  x_o2: {min: 0.39, max: 0.39, status: known, source_id: PSI-159, source_locator: "TODO"}
  o2_context: ambient
  p_kpa: {min: 200, max: 200, status: known, source_id: PSI-159, source_locator: "TODO"}
  u_cms: {status: unknown}
  granularity: per_test_table
  sources: [PSI-159]

- evidence_id: CFIG:burner85
  investigation: ACME CFI-G
  psi_id: PSI-159
  hardware_family: ACME/CIR
  fuel_class: gas_jet
  phenomena: [cool_flame, flame_structure]
  gravity: microgravity
  x_o2: {min: null, max: 0.85, status: unknown, source_id: PSI-159, source_locator: "TODO"}
  o2_context: burner_oxidizer_flow   # NEVER ambient
  p_kpa: {status: unknown}
  u_cms: {status: unknown}
  granularity: per_test_table
  sources: [PSI-159]

- evidence_id: FLEX:table
  investigation: FLEX
  psi_id: PSI-69
  hardware_family: MDCA/CIR
  fuel_class: liquid_droplet
  fuel_name: heptane, methanol, others
  phenomena: [extinction, suppression, burning_rate, cool_flame]
  gravity: microgravity
  x_o2: {status: unknown}           # per-row from 274-row table
  p_kpa: {status: unknown}
  u_cms: {min: 0, max: 0, status: known, source_id: PSI-69, source_locator: "quiescent droplet (verify)"}
  diluent: "N2/CO2/He/Xe"
  granularity: per_test_table
  sources: [PSI-69, "DOI:10.1007/s12217-014-9372-2"]

- evidence_id: SAMER:runs
  investigation: SAME-R
  psi_id: PSI-101
  hardware_family: MSG
  fuel_class: pyrolysis_source
  phenomena: [smoke_particles, detector_response]
  gravity: microgravity
  x_o2: {status: not_applicable}
  p_kpa: {status: unknown}
  u_cms: {status: unknown}
  granularity: per_test_table
  measurements: [particle_count_per_cc, mass_conc_mg_m3, detector_signal_V]
  sources: [PSI-101, PSI-102, PMC7918997]

- evidence_id: DAFT:ISS_ambient
  investigation: DAFT
  psi_id: PSI-47
  hardware_family: P-Trak/DustTrak
  fuel_class: ambient_dust
  phenomena: [smoke_particles]
  gravity: microgravity
  x_o2: {status: not_applicable}
  p_kpa: {status: unknown}
  u_cms: {status: unknown}
  granularity: campaign_summary
  measurements: [particle_count_per_cc, mass_conc_mg_m3]
  sources: [PSI-47, "NASA DAFT fact sheet 2025"]
  # values from fact sheet: <0.005 mg/m3; ~15 particles/cm3 (store as measurements with locator)

- evidence_id: LUCI:overlay
  investigation: LUCI (non-PSI)
  psi_id: null
  hardware_family: New Shepard centrifuge
  fuel_class: thin_solid
  fuel_name: SIBAL; 4 mm PMMA
  phenomena: [spread_concurrent]
  gravity: simulated_partial
  x_o2: {min: 0.209, max: 0.209, status: unknown}   # "air": confirm before marking known
  p_kpa: {status: unknown}                           # "normal pressure": confirm
  u_cms: {status: unknown}
  granularity: paper_only
  sources: [NTRS-20250010653]
  # OVERLAY ONLY. Excluded from ranking pool by default (gravity != µg/1g).
```

**Also add `1g` counterpart rows** wherever a paper reports a 1-g comparison (e.g., BASS-II LOC ≈ 0.18 at 1-g; BRE 1-g burning ~3–4× µg), each sourced.

---

## 22. Appendix B: gold-set query bank (pick 40; freeze before tuning)

**Exploration atmosphere / lunar**
1. Fabric flammability in a lunar habitat at 34% O₂, 8.2 psia.
2. PMMA flame spread at 34% O₂ with 10 cm/s ventilation.
3. Which tests are closest to the 10.2 psia / 26.5% option?
4. Pressurized rover cabin fire, thin materials, low airflow.
5. Elevated-oxygen limiting oxygen concentration for plastics.
6. What evidence exists for flame spread at reduced pressure?
7. Concurrent-flow spread over fabric in µg at about 30% O₂.
8. Are there any tests above 30% ambient oxygen? (tests the CFI-G burner trap)
9. Lunar gravity flame spread for PMMA. (expected: gap + flags)
10. Mars habitat material flammability. (expected: gap)

**ISS / spacecraft**
11. Flame spread over PMMA rods in low opposed flow on ISS.
12. Can turning off ventilation extinguish a fire? (BASS-II evidence)
13. Large-scale fire growth in a spacecraft cabin.
14. Effect of enclosure size on flame spread.
15. Toxic combustion products from spacecraft materials.
16. Ignition of thin solids in microgravity.

**Suppression / extinction**
17. CO₂ vs helium as droplet flame suppressants.
18. Radiative vs diffusive extinction of fuel droplets.
19. Do flames really go out when the visible flame disappears? (cool flames)
20. Droplet extinction at reduced oxygen.
21. Xenon-diluted droplet combustion.
22. Heat of gasification and flammability of condensed fuels (BRE).
23. Water-mist suppression in microgravity. (expected: gap)

**Smoke / detection**
24. Smoke particle size from Kapton or Teflon pyrolysis.
25. Why spacecraft smoke detectors miss small particles.
26. How does smoke aging change particle size?
27. Distinguishing smoke from cabin dust.
28. ISS ambient particulate levels.
29. Detector response during a large-scale fire (Saffire-III telemetry).
30. Smoke detection at 8.2 psia. (expected: gap)

**Soot / flame structure**
31. Soot production in microgravity vs 1-g.
32. Smoke point of gas jet flames in microgravity.
33. Lifted flame behavior in coflow.
34. Electric-field control of flames as a gravity analog.
35. Soot-free flame design.

**Modeling / data**
36. Which datasets have per-test tables suitable for modeling?
37. Droplet burning-rate constants by fuel.
38. Which investigations share the same hardware?
39. Tests varying oxygen concentration systematically.
40. Tests varying flow velocity systematically.

---

## 23. Appendix C: glossary

- **µg:** microgravity (~10⁻⁶–10⁻³ g on orbit). **1-g:** Earth gravity. **Partial g:** Moon 0.166 g, Mars 0.38 g.
- **X_O₂:** oxygen mole fraction. **ppO₂:** oxygen partial pressure = X_O₂ · P.
- **Opposed-flow spread:** the flame spreads against the oncoming flow. **Concurrent:** the flame spreads with the flow.
- **LOC:** limiting oxygen concentration, the lowest O₂ that sustains burning.
- **Elasticity ε:** ∂lnY/∂lnx, the % change in the response per % change in a condition.
- **Transfer distance D:** elasticity-weighted log distance from evidence to scenario. **exp(D):** the implied maximum response factor.
- **CIR:** Combustion Integrated Rack. **MDCA:** Multi-user Droplet Combustion Apparatus. **MSG:** Microgravity Science Glovebox. **ACME:** Advanced Combustion via Microgravity Experiments.
- **SIBAL:** cotton/fiberglass composite fabric used in Saffire.
- **ECLSS:** Environmental Control and Life Support System.
- **nDCG@5 / MRR / Recall@5:** ranking-quality metrics. **κ:** inter-annotator agreement.
- **Cite-or-drop:** any generated sentence without a valid citation is removed.

---

### Known caveats carried from the research
- PSI file/table counts come partly from conflicting third-party inventories.
- Saffire IV–VI presence in PSI is unverified.
- No code has been run yet. All D values are hand calculations, and every performance target is a hypothesis to test.
- Novelty claims are limited to the sources searched (not a systematic review; patents not searched).
- Several references in §19 are marked **[TODO-VERIFY]**: their scope or authors weren't confirmed in the research pass. Open each before citing it on a slide.
