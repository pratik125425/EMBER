# EMBER: Space Apps 2026 submission pack

Drafts laid out in the same order as the fields on the Space Apps project form (2026 Project
Submission Guide). Every number below was read from the app or its data on 2026-11-15. Paste each
section into the field with the same name and put it in your own words. Items in [brackets] are
yours to fill in.

**Deadline: Sunday Nov 15, 11:59 p.m., local time of your Local Event** (for the Universal Event, the
team owner's local time). The final checklist is at the bottom.

---

## Project Name

EMBER: Evidence-Mapped Bounds for Exploration fire Risk

## High-Level Project Summary

*(What you built, how it addresses the challenge, why it matters.)*

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

## Link to Project Demo

[Public link to the 30-second video OR the slide deck of at most 7 slides. Test it in a private
browser window: no login, permission or sign-up.]

## Link to Final Project

[Public GitHub repository, e.g. https://github.com/YOUR-USERNAME/ember. Optionally also a live app
link. Test in a private window.]

## Detailed Project Description

*(What it does, how it works, benefits, what you hope to achieve, tools and languages.)*

**What it does.** You describe a habitat atmosphere (oxygen, pressure, airflow, gravity, material)
or ask a question in plain English. EMBER shows which NASA fire experiments apply, ranks them, says
how far each one is from your conditions, and maps what has never been tested.

**How it works.**

- **Evidence registry.** Every PSI combustion record is placed in oxygen–pressure–flow space with
  its gravity, fuel and phenomenon. Every value traces to a table row or a page in a cited source.
  Values from papers enter only after a named human reviewer accepts them.
- **Transfer distance D.** An elasticity-weighted log distance whose weights are NASA's published
  flame-spread exponents (Ruff 2021), so exp(D) reads as "how much the flame-spread response could
  differ". D > 1 is flagged as beyond the tested envelope. Missing conditions make D a lower bound
  instead of being imputed. Gravity is a flag, never interpolated.
- **Gap map.** Coverage per gravity regime, plotted against NASA's target exploration atmospheres
  (NASA-TP-2010-216134), with an exportable gap report.
- **Compare.** Rule gates (gravity, fuel, flow, hardware, granularity) list every confounder before
  saying whether two results can be compared.
- **Honesty rules.** CFI-G's 85% O₂ is labelled burner-side oxidizer flow, never a cabin
  atmosphere. LUCI's simulated lunar gravity is labelled non-PSI. Nothing is called "safe".

**What we measured.**

- Rank stability: in both demo scenarios (lunar habitat at 34% O₂ and 56.5 kPa / 8.2 psi, and
  Earth air), all of the top 5 stay in the top 5 in at least 80% of 1,000 re-rankings with every
  weight perturbed (elasticities ±30%, priors ±50%).
- Trick prompts: 5 of 5 handled ("Is Nomex safe at 34% O₂?" is refused; "What did FLEX measure on
  the Moon?" is flagged as a partial-gravity question).
- Hostile sentences: 8 of 8 dropped by the cite-or-drop verifier.
- Compare rules: 0 false "comparable" verdicts on 12 starter pairs (a smoke test, not a rate).
- Data integrity: 29 of 47 listed NASA files mirrored locally and SHA-256 verified.
- Not yet measured: the retrieval benchmark (40 questions, five baselines) is built, but it needs
  two human relevance labellers before it reports a score. We show it as pending rather than grade
  ourselves.

**Benefits.** A habitat or materials engineer gets, in one screen, the experiments that bear on
their atmosphere, an honest measure of extrapolation, and a list of what has not been tested. That
saves days of searching PSI and NTRS, and it makes the gaps visible instead of hidden behind a
confident-looking answer.

**What we hope to achieve.** Point the next round of spacecraft fire experiments at the untested
conditions that matter for Artemis and Mars habitats: lunar and Mars gravity at the exploration
atmospheres NASA is considering. Next steps are human relevance labels for the benchmark, more
reviewed NTRS papers, and partial-gravity data from LUCI and FM2 as it is published.

**Tools, languages, hardware and software.** Python 3.12; Streamlit (interface); Plotly (charts);
pandas, NumPy, SciPy; pydantic (schemas); pint (units); DuckDB and Parquet/pyarrow (storage);
pdfplumber (PDF tables); httpx (downloads); rank_bm25, sentence-transformers and FAISS (benchmark
baselines); pytest (216 tests) and ruff; uv (environments). Optional Anthropic Claude API for
question parsing and cited summaries; without it a rule-based parser and template summaries run
through the same verifier. Runs offline on a laptop; no special hardware.

## Use of Super Intelligence (SI)

*(Not shown to judges, but must be honest. SI indicators inside the project are visible to them.)*

The idea, the challenge approach and the design of the transfer distance were ours. We used
Anthropic's Claude (through Claude Code) as a coding assistant: writing and testing code, data
pipeline tooling, interface design and drafting documentation text. This is acknowledged in the
repository README. No images or video in the project were generated with SI, and no NASA branding is
used. Every value in the evidence registry comes from a NASA table or a named source, and values
proposed from papers are accepted only by a named human reviewer. The app has an optional language
model layer that can turn a question into a scenario and write a summary; every sentence must cite a
registry record and every number is checked against it, and failing sentences are dropped. The
ranking itself is deterministic code.

[Edit this so it is exactly true for your team. If any slide images or video were made with SI, they
need a visible watermark.]

## NASA Data

- NASA Physical Science Informatics (PSI) investigation records and data tables: BASS (PSI-26),
  BASS-II (PSI-25), Saffire-I (PSI-98), Saffire-III (PSI-100), ACME CFI-G (PSI-159), FLEX (PSI-69),
  SAME (PSI-102), SAME-R (PSI-101), DAFT / DAFT-2 (PSI-47). https://psi.ndc.nasa.gov
- NASA Technical Reports Server (https://ntrs.nasa.gov): Saffire VI preliminary results
  (20240002981); LUCI simulated lunar gravity burns (20250010653); Flammability of Materials on the
  Moon, FM2 (20240015307); Ruff, Technology Development for Spacecraft Fire Safety (20210021318).
- NASA-TP-2010-216134, Recommendations for Exploration Spacecraft Internal Atmospheres.
- NASA DAFT fact sheet (2025).

## Space Agency Partner Data and Other References

**Other references (peer-reviewed papers cited in the registry).** Link et al. 2018, Scientific
Reports, 10.1038/s41598-017-18398-4; Nayagam et al. 2014, Microgravity Science and Technology,
10.1007/s12217-014-9372-2; Meyer et al., PMC7918997.

**Software (all open source).** Python, Streamlit, Plotly, pandas, NumPy, SciPy, pydantic, pint,
DuckDB, pyarrow, pdfplumber, httpx, PyYAML, rank_bm25, sentence-transformers, FAISS, pytest, ruff,
uv. Optional: Anthropic Python SDK.

**Fonts.** Libre Caslon Text, Libre Caslon Display and Libre Franklin (SIL Open Font License),
bundled in `app/static/fonts` so the app works offline.

**AI tools.** Anthropic Claude (Claude Code) as a coding assistant; see Use of SI.

[No space agency partner data is used. If you add any, list it here.]

---

## Slide deck (7 slides including title — the hard limit)

Required on the slides: team name, team member names, the challenge, an image of the project, the
user experience, and how NASA data makes it possible. Use your own app screenshots (no NASA logos).

1. **Title.** EMBER: Evidence-Mapped Bounds for Exploration fire Risk. Team Mustangs; members
   Pratik Bhattiprolu and Mihir Patel. Challenge: *Flame in Freefall*, NASA Space Apps 2026. One Overview screenshot.
2. **The problem.** Moon and Mars habitats will run at lower pressure and higher oxygen than the
   ISS. Which of NASA's fire experiments tell us anything about that atmosphere? Today there is no
   quick answer.
3. **NASA data makes it possible.** 982 records from 11 PSI investigations plus NTRS reports and
   NASA-TP-2010-216134; every value traced to a table row or page. Evidence map screenshot.
4. **The user experience.** Ask a question or set an atmosphere → ranked experiments, a "lower
   bound" badge where data is missing, and a "why" chart by condition. Ask page screenshot.
5. **What nobody has tested.** No PSI fire data at lunar or Mars gravity; NASA's target
   atmospheres against coverage. Gaps heatmap screenshot.
6. **Why you can trust it.** Top 5 stable in 1,000 perturbed re-rankings; 5 of 5 trick prompts and
   8 of 8 hostile sentences handled; files checksum-verified; benchmark shown as pending, not
   self-graded. Weights are NASA's published exponents, not tuned by us.
7. **The future.** Human labels for the benchmark, more reviewed NTRS papers, LUCI/FM2
   partial-gravity data as it is published; aim experiments at the gaps. Repo link.

## Demo video script (30 seconds or less — the hard limit)

Over 30 seconds makes the project ineligible for Global Judging. Aim for 28. Speak in English (or
add English subtitles). No one under 18 on screen. Record the screen with the Guided demo page.

- **0:00–0:02 — Who.** "Hi, we're team Mustangs." *(Overview on screen.)*
- **0:02–0:05 — Challenge.** "Flame in Freefall: will fire on the Moon behave like our tests?"
- **0:05–0:10 — Name and tagline.** "This is EMBER: which NASA fire experiments apply to your
  habitat, and how far you're stretching them." *(Type the lunar question in Ask.)*
- **0:10–0:20 — How it works, with NASA data.** "It ranks 982 records from NASA's PSI and NTRS by a
  distance built on NASA's flame-spread exponents, and never fills in what wasn't measured."
  *(Ranked list, then the Gaps heatmap.)*
- **0:20–0:28 — The future.** "There's no fire data at lunar gravity. EMBER shows exactly where
  the next experiments should go."

---

## Final submission checklist

- [ ] GitHub repo created, code pushed, repo set to **public**. Open it in a private window.
- [ ] Demo uploaded (≤30 s video **or** ≤7 slides), link public; check it in a private window.
- [ ] Team name and member names filled in above and on the title slide.
- [ ] All [bracket] placeholders replaced; Use of SI edited to be exactly true for your team.
- [ ] All team members confirmed at the same Local Event.
- [ ] Optional: a project image (≤10 MB) on the project page. No videos or documents there.
- [ ] Tick **Terms and Conditions** and **Confirm All Work is Original**, then **Submit for Judging**
      before 11:59 p.m. local time. You can edit and resubmit until the deadline.

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
