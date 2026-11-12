# EMBER gold-set labeling guideline

Written from the challenge text and NASA documents only, before any system output was inspected
(spec §12.1). Annotator B must not look at EMBER's or any baseline's rankings before finishing.

## What you label

For each question and each investigation in the sheet (alphabetical order, never ranked order),
give one label for how useful that investigation's **documented data** are for answering the
question as stated. Use only NASA sources: the PSI record pages (description, objective, approach,
files), the NASA papers listed in `EMBER_BUILD_SPEC.md` §19, and the challenge text.

| Label | Meaning |
|---|---|
| 0 | Irrelevant. Different phenomenon, material class and conditions; no useful data. |
| 1 | Tangential. Related physics or hardware, or useful only as background. |
| 2 | Relevant. Data on the asked phenomenon or material that an engineer would cite, with caveats. |
| 3 | Directly applicable. Measured data on the asked phenomenon, material class and close conditions. |

## Rules

1. Judge the investigation's data, not its title or how well its record is written.
2. **Unreached conditions cap the label at 1.** If the question requires a condition no test in the
   investigation reached (partial gravity, 8.2 psia smoke data, water mist, Mars), the highest label
   is 1. Microgravity and 1-g results are brackets for partial gravity, never answers (FM2 abstract,
   NTRS 20240015307).
3. **Burner-side oxygen is not cabin oxygen.** CFI-G inverse-flame oxygen up to 85% is oxidizer
   flow from the burner (challenge text). It does not make CFI-G relevant to cabin-atmosphere questions.
4. **Non-PSI sources count** (e.g. the Saffire VI paper) but note them in the notes column.
5. Leave a note whenever you hesitate between two labels.
6. Do not discuss labels with the other annotator until both sheets are complete.

## After labeling

```bash
uv run python -m ember.eval.gold_tools status
uv run python -m ember.eval.gold_tools merge     # computes weighted κ; lists disagreements ≥ 2
uv run python -m ember.eval.gold_tools freeze    # hashes queries + final labels; tag the commit gold-v1
```

Disagreements of 2 or more must be adjudicated in `qrels_final.csv` (`adjudicated` column) before
`merge` will write final labels. Once frozen, `run_eval` refuses changed labels.
