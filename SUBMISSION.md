# EMBER: Space Apps 2026 submission pack

Drafts for the project page, the slides and the demo video. Every number below was read from the
app or its data on 2026-11-15. If you change the registry, re-check the numbers against the live
app before submitting. Copy each section into the matching field of the Space Apps project form and
edit it in your own voice. Items in [brackets] are yours to fill in.

---

## Project name

EMBER: Evidence-Mapped Bounds for Exploration fire Risk

## One-line summary (for the project card)

Tell EMBER a habitat's oxygen, pressure, airflow and gravity, and it shows which NASA fire
experiments apply, how far you are extrapolating from them, and what nobody has tested yet.

## High-level summary (about 150 words)

Future habitats on the Moon and Mars will run at lower pressure and higher oxygen than the ISS, and
fire behaves differently there. NASA has flown many combustion experiments, but their results are
spread across the Physical Science Informatics (PSI) system, technical reports and papers, each at
different conditions. EMBER turns them into one evidence registry of 982 records from 11 NASA
investigations and 19 cited sources. A designer enters an atmosphere; EMBER ranks every experiment by a
transfer distance D, built from NASA's published flame-spread scaling exponents (Ruff 2021), so you can
see both which tests apply and how far you are extrapolating. A gap map shows conditions no one has
tested. EMBER never fills in unknown values, never calls an atmosphere safe, and treats Moon and Mars
gravity as a bracket between microgravity and 1-g tests, because PSI holds no partial-gravity
combustion data. It runs fully offline.

## How EMBER addresses the challenge

- **Finds the relevant evidence.** Every PSI combustion record is placed in oxygen–pressure–flow
  space, with its gravity, fuel and phenomenon. A scenario is matched against all of them at once.
- **Measures extrapolation instead of hiding it.** D is an elasticity-weighted log distance, so
  exp(D) reads as "how much the flame-spread response could differ". D > 1 is flagged as beyond the
  tested envelope.
- **Shows what is missing.** The Gaps page maps coverage per gravity regime and against NASA's
  target exploration atmospheres (NASA-TP-2010-216134), and exports a gap report.
- **Checks whether two results can be compared.** Compare runs rule gates (gravity, fuel, flow,
  hardware, granularity) and lists every confounder before giving a verdict.
- **Stays honest.** Missing conditions make D a lower bound rather than being imputed. CFI-G's 85%
  O₂ is labelled burner-side oxidizer flow, never a cabin atmosphere. LUCI's simulated lunar gravity
  is labelled non-PSI.

## What we measured

- **Rank stability:** in both demo scenarios (lunar habitat at 34% O₂ and 56.5 kPa / 8.2 psi, and
  Earth air), all of the top 5 stay in the top 5 in at least 80% of 1,000 re-rankings with every
  weight perturbed (elasticities ±30%, priors ±50%).
- **Trick prompts:** 5 of 5 handled (for example "Is Nomex safe at 34% O₂?" is refused, and "What did
  FLEX measure on the Moon?" is flagged as a partial-gravity question).
- **Hostile sentences:** 8 of 8 dropped by the cite-or-drop verifier (invented numbers, fake citations,
  "safe" claims).
- **Compare rules:** 0 false "comparable" verdicts on 12 starter pairs (a smoke test, not a rate).
- **Data integrity:** 29 of 47 listed NASA files are mirrored locally and SHA-256 verified.
- **Not yet measured:** the retrieval benchmark (40 questions, five baselines) is built and its
  rankings are recorded, but it needs two human relevance labellers before it reports a score. We show
  it as pending rather than self-grade it.

## NASA data and resources used

- NASA Physical Science Informatics (PSI) investigation records and data tables: BASS (PSI-26),
  BASS-II (PSI-25), Saffire-I (PSI-98), Saffire-III (PSI-100), ACME CFI-G (PSI-159), FLEX (PSI-69),
  SAME (PSI-102), SAME-R (PSI-101), DAFT / DAFT-2 (PSI-47).
- NASA Technical Reports Server: Saffire VI preliminary results (NTRS-20240002981); LUCI simulated
  lunar gravity burns (NTRS-20250010653); Flammability of Materials on the Moon, FM2
  (NTRS-20240015307); Ruff, Technology Development for Spacecraft Fire Safety (NTRS-20210021318).
- NASA-TP-2010-216134, Recommendations for Exploration Spacecraft Internal Atmospheres.
- NASA DAFT fact sheet (2025).
- Peer-reviewed papers cited in the registry: Link et al. 2018 (Scientific Reports,
  10.1038/s41598-017-18398-4); Nayagam et al. 2014 (Microgravity Science and Technology,
  10.1007/s12217-014-9372-2); Meyer et al. (PMC7918997).

## Tools and technologies

Python 3.12, Streamlit, Plotly, pandas, pydantic, pint (units), DuckDB/Parquet, rank_bm25 and
sentence-transformers (FAISS) baselines for the benchmark, pytest (216 tests). Optional Claude API layer for parsing questions
and writing cited summaries; without it EMBER uses a rule-based parser and template summaries that go
through the same verifier.

## Use of AI (disclosure)

[Check the wording the form asks for.] We built EMBER with help from Anthropic's Claude (Claude Code)
for writing and testing code, data-pipeline tooling and interface design. Every value in the registry
comes from a NASA table or a named source, and values proposed from papers are accepted only by a named
human reviewer. The app's optional language-model layer can propose a scenario and write a summary,
but every sentence must cite a registry record and every number is checked against it; failing
sentences are dropped. The ranking itself is deterministic code, not a model.

## Links

- Code: [https://github.com/YOUR-USERNAME/ember]
- Demo video or slides: [link]
- Live app (if deployed): [link]

---

## Slide outline (7 slides)

1. **The problem.** Moon and Mars habitats will run at lower pressure and higher oxygen than the
   ISS. "Which of NASA's fire experiments actually tell us something about that atmosphere?" has no
   quick answer today.
2. **EMBER in one sentence.** Enter an atmosphere; see which NASA experiments apply, how far you are
   extrapolating, and what nobody has tested. One screenshot of the Overview.
3. **The evidence.** 982 records, 11 investigations, 19 sources, every value traced to a table row or
   page. Screenshot of the Evidence map with the scenario star.
4. **How it ranks.** D from Ruff 2021's flame-spread exponents; unknowns make D a lower bound;
   gravity is a flag, never interpolated. Screenshot of Ask's "Why: D by dimension" chart.
5. **What nobody has tested.** Gaps page: no PSI evidence at lunar or Mars gravity; NASA's target
   atmospheres against coverage. Screenshot of the gap heatmaps.
6. **Why you can trust it.** Top 5 stable in 1,000 perturbed re-rankings; 5 of 5 trick prompts and
   8 of 8 hostile sentences handled; files checksum-verified; the benchmark shown as pending, not
   self-graded.
7. **What's next.** Human relevance labels for the benchmark, more NTRS papers through the reviewed
   pipeline, partial-gravity data from LUCI/FM2 as it is published. Team names and links.

---

## Demo video script (about 2 minutes)

Record with the app's Guided demo page, which walks the same story. Numbers come from the app, so say
what the screen shows if anything differs.

**0:00–0:15, Overview.** "Moon habitats will run at about a third oxygen and well under sea-level
pressure. NASA has flown dozens of fire experiments, but which ones apply? EMBER answers that in
one screen."

**0:15–0:40, Ask.** Type: *Which NASA experiments best inform fabric and plastic flammability in a
lunar habitat at 34% oxygen and 8.2 psi?* "EMBER turns the question into a scenario and ranks
every NASA record. BASS-II comes out on top. The 'Lower bound' badge means some of its conditions
are not reported, so the real distance could be larger. EMBER never fills those in."

**0:40–1:00, Why chart and stability.** "Each bar shows how much each condition, oxygen, pressure or
flow, adds to the distance. Re-ranked a thousand times with every weight shaken, the same five
stay in the top five."

**1:00–1:20, Evidence map.** "Here is every test in oxygen–pressure space, with our habitat as the
star. And note the gravity: almost everything is microgravity. There is no PSI fire data at lunar
gravity at all, so EMBER brackets it and says so."

**1:20–1:40, Gaps.** "This is what nobody has tested. The boxes are NASA's own target exploration
atmospheres; at lunar and Mars gravity there is no PSI evidence around them at all. That's where the
next experiments should go."

**1:40–2:00, Trust.** Validation page. "Every number here is measured. Trick questions like 'is
Nomex safe?' are refused. The retrieval benchmark is built but waiting for human labels, so we
show it as pending instead of grading ourselves. And all of this runs offline, on this laptop."

---

## Likely judge questions

- **Why should I trust D?** Its weights are NASA's published flame-spread exponents (Ruff 2021),
  not tuned by us. Every D splits into per-condition parts you can check by hand, and the ranking
  holds up when every weight is perturbed.
- **You rank lunar scenarios without lunar data?** Yes, and we say so on every lunar result. Gravity
  is a flag, never interpolated: lunar results are brackets from microgravity and 1-g tests. LUCI's
  simulated lunar burns are included and labelled non-PSI.
- **Why isn't CFI-G at 85% oxygen a match for high-oxygen cabins?** That 85% is the oxidizer stream
  feeding the burner, not the surrounding atmosphere. EMBER stores it with that context and never
  uses it as an ambient value.
- **Where's your accuracy number?** The benchmark is built: 40 questions, five baselines, rankings
  recorded. Scores need two independent human labellers, and we chose to show "pending" over a
  self-graded score.
- **What does the AI do?** It can turn a question into a scenario and write a summary. Every sentence
  must cite a record and every number is checked; anything that fails is dropped. The ranking is
  plain code.
