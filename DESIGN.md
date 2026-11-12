---
name: EMBER
description: Evidence-Mapped Bounds for Exploration fire Risk, set as a celestial star-atlas plate.
colors:
  plate: "#12213f"
  plate-raised: "#192b52"
  plate-card: "#152649"
  plate-deep: "#0d1830"
  ivory-ink: "#efe9da"
  ink-secondary: "#b9c3dc"
  ink-muted: "#8d9bbd"
  steel-hairline: "#2c406c"
  graticule: "#22355c"
  axis-rule: "#4a5f8f"
  star-link: "#a9c6ff"
  ember: "#ff8a4c"
  ember-wash: "#5a3424"
  target-gold: "#e3c46e"
  print-sky: "#f7f8fb"
  print-ink: "#13234a"
  print-ink-secondary: "#3b4a6b"
  print-muted: "#56627f"
  print-hairline: "#c9d1e2"
  print-wash: "#eef1f7"
  print-ember: "#c4501c"
  print-ember-wash: "#fbe2d4"
  print-gold: "#8a6a1c"
typography:
  display:
    fontFamily: "Libre Caslon Display, Libre Caslon Text, Georgia, serif"
    fontSize: "70px"
    fontWeight: 400
    lineHeight: 0.92
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Libre Caslon Text, Georgia, serif"
    fontSize: "2.6rem"
    fontWeight: 500
    lineHeight: 1.1
    letterSpacing: "-0.012em"
  title:
    fontFamily: "Libre Caslon Text, Georgia, serif"
    fontSize: "1.6rem"
    fontWeight: 500
    letterSpacing: "-0.004em"
  annotation:
    fontFamily: "Libre Caslon Text, Georgia, serif"
    fontSize: "1.12rem"
    fontWeight: 400
    lineHeight: 1.4
  lede:
    fontFamily: "Libre Caslon Text, Georgia, serif"
    fontSize: "1.12rem"
    fontWeight: 400
    lineHeight: 1.55
  body:
    fontFamily: "Libre Franklin, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.6
  readout:
    fontFamily: "Libre Franklin, system-ui, sans-serif"
    fontSize: "24px"
    fontWeight: 500
    lineHeight: 1.25
    letterSpacing: "-0.01em"
    fontFeature: "tnum"
  metric:
    fontFamily: "Libre Franklin, system-ui, sans-serif"
    fontSize: "1.7rem"
    fontWeight: 500
    lineHeight: 1.15
    letterSpacing: "-0.01em"
    fontFeature: "tnum"
  label:
    fontFamily: "Libre Franklin, system-ui, sans-serif"
    fontSize: "0.8rem"
    fontWeight: 400
  tick:
    fontFamily: "Libre Franklin, system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 400
    fontFeature: "tnum"
rounded:
  none: "0px"
  hairline: "2px"
spacing:
  xs: "0.35rem"
  sm: "0.7rem"
  md: "1.2rem"
  lg: "2rem"
  xl: "4rem"
components:
  button-primary:
    backgroundColor: "{colors.ember}"
    textColor: "{colors.plate}"
    rounded: "{rounded.hairline}"
  button-secondary:
    backgroundColor: "{colors.plate}"
    textColor: "{colors.ivory-ink}"
    rounded: "{rounded.hairline}"
  metric-entry:
    backgroundColor: "{colors.plate}"
    textColor: "{colors.ivory-ink}"
    typography: "{typography.metric}"
    rounded: "{rounded.none}"
    padding: "0.7rem 0 0.2rem"
  margin-note:
    backgroundColor: "{colors.plate-deep}"
    textColor: "{colors.ivory-ink}"
    rounded: "{rounded.none}"
  index-cell:
    backgroundColor: "{colors.plate}"
    textColor: "{colors.ivory-ink}"
    rounded: "{rounded.none}"
    padding: "10px 12px 11px 0"
  plate-tooltip:
    backgroundColor: "{colors.plate-deep}"
    textColor: "{colors.ivory-ink}"
    rounded: "{rounded.hairline}"
    padding: "7px 10px"
  empty-state:
    backgroundColor: "{colors.plate-deep}"
    textColor: "{colors.ink-secondary}"
    rounded: "{rounded.hairline}"
    padding: "1.4rem 1.6rem"
---

# Design System: EMBER

## Overview

**Creative North Star: "The Evidence Sky Atlas"**

EMBER is a printed star-atlas plate. Every NASA fire test with a known oxygen level and total pressure is a star on an oxygen-pressure sky (O₂ % across, pressure on a log scale up); the visitor's habitat is an ember reticle they aim, and the engine draws one committed vector from it to the best-ranked test. The plate is engraved, not rendered: navy ground, ivory ink, steel-blue hairlines, a double-rule frame, graticule ticks, dotted ppO₂ isolines running like ecliptic curves, magnitude-scaled stars over a faint haze where tests exist and plain dark sky where none do.

Everything around the plate reads as plate margin. Metrics are margin entries under a hairline, callouts are margin notes with one rule, steps and the index of plates are ruled rows. There are no card fills and no ambient shadows on the page; depth comes from the plate's own layering (haze, graticule, constellations, stars, labels, reticle). Libre Caslon sets titling and italic engraved annotations; Libre Franklin sets margin text, numbers and controls. All faces are bundled under `app/static/fonts` (SIL OFL) and served by Streamlit, so the system works fully offline.

The navy plate is the default (Streamlit dark base). Streamlit's Light theme gives a "white-sky print" with the same roles mapped to print values. Honesty is part of the visual grammar: what the plate draws is exactly what the evidence supports.

**Key Characteristics:**
- Navy plate ground, ivory engraving ink, steel-blue hairlines; flat, ruled, no card fills.
- One ember-orange mark for the scenario; gold only for NASA target atmospheres.
- Caslon italic for every engraved note and caveat; Franklin with tabular figures for every number.
- Stars sized by test count; haze for tested sky, dark sky for untested.
- 2px hairline radius or square; nothing rounder.
- Motion is a 460ms draw-on of the vector and quiet 160 to 260ms settles, all off under reduced motion.

## Colors

A three-ink engraving on navy: ivory for evidence, ember for the visitor's scenario, gold for NASA's targets, and steel-blue for the structure that holds them.

### Primary
- **Ember** (#ff8a4c on the plate, #c4501c in print): the scenario and nothing else on the plate: the reticle ring and crosshair, its fading trail, the vector and its engraved D note, the ranked target ring, the O₂-only meridian band when the best record has no pressure, the scenario tick on every index strip, and the O₂ and kPa values in the live readout. In Streamlit chrome it is the theme primary, so it also carries the scenario controls (sliders, primary action), the keyboard focus ring, the text caret and the hover name of an index cell. On a primary button the label is set in plate navy (#12213f) for legibility.
- **Ember Wash** (#5a3424 / print #fbe2d4): text selection only.

### Secondary
- **Target Gold** (#e3c46e / print #8a6a1c): NASA target habitat atmospheres only: the gold ring with broken crosshair, its dashed tolerance box and its italic label. Charts map the same gold through `DARK_MAP`.

### Neutral
- **Navy Plate** (#12213f): the page and the plate ground; also the halo stroke behind plate labels and the knock-out ring behind each star.
- **Raised Plate** (#192b52) and **Plate Card** (#152649): Streamlit secondary surfaces and widget fills.
- **Deep Plate** (#0d1830): sidebar, dataframe headers, margin-note wash, tooltip and empty-state ground.
- **Ivory Ink** (#efe9da): primary text, stars, haze, index strips.
- **Secondary Ink** (#b9c3dc): ledes, labels, axis titles, constellation lines, isolines, caveats, the inner frame rule.
- **Muted Ink** (#8d9bbd): ticks, isoline labels, hints, footer.
- **Steel Hairline** (#2c406c): every rule, border, graticule line and outer frame rule. Charts use **Graticule** (#22355c) for grid and **Axis Rule** (#4a5f8f) for axes.
- **Star Link** (#a9c6ff): link colour.
- Print counterparts: sky #f7f8fb, ink #13234a, secondary #3b4a6b, muted #56627f, hairline #c9d1e2, wash #eef1f7.

Chart series use a separate categorical set (plate: #86b1f2, #e7a0b4, #6fd0a8, #e3c46e, #c9a3e8, #b7d77a, #a99cf0, #ff8f8f; print: #2a78d6, #eb6834, #1baf7a, #eda100, #e87ba4, #008300, #6250d6, #e34948), applied to marks only. Sequential ramps run from the plate up to bright ink so "more" still reads as "stronger".

### Named Rules
**The One Ember Rule.** Ember belongs to the visitor's scenario: reticle, vector, readout values, scenario controls and the user's own focus. It never marks evidence, a category or decoration.

**The Gold Is NASA's Rule.** Gold marks NASA target atmospheres and nothing else. A gold mark that is not a target is a lie on the plate.

**The Caveat Voice Rule.** Caveats (beyond the tested envelope, no test at this gravity, pressure not reported) are set in secondary ink, italic. They are never alarm-coloured.

## Typography

**Display Font:** Libre Caslon Display (with Libre Caslon Text, Georgia)
**Heading / Annotation Font:** Libre Caslon Text, roman and italic (with Georgia)
**Body / Label Font:** Libre Franklin, variable 100 to 900 with italic (with system-ui)

**Character:** An engraver's Caslon for the plate's title block and its italic hand-lettered notes, against a plain Franklin grotesque for the margin's working text and every number.

### Hierarchy
- **Display** (400, 70px, 0.92, -0.02em; 56px under 900px): the EMBER title block in the plate margin; step numerals use the same face at 2rem in secondary ink.
- **Headline** (500, 2.6rem, 1.1, -0.012em, balanced): page titles.
- **Title** (500, 1.6rem / 1.25rem, -0.004em): section headings, 2rem above and 0.35rem below.
- **Annotation** (Caslon italic, 13 to 15px on the plate, 1.12 to 1.15rem in the margin): constellation names, axis titles, target labels, the vector note, the readout label, reading-guide heads, index questions, sidebar headings.
- **Lede** (Caslon, 1.12rem, 1.55, max 58rem, secondary ink): one-sentence purpose line under each title.
- **Body** (Franklin 400, 15px base, 1.6, pretty-wrapped; reading columns max 34rem).
- **Readout / Metric** (Franklin 500, 24px / 1.7rem, tabular figures): live scenario coordinates and metric values.
- **Label / Tick** (Franklin, 0.8rem labels in secondary ink; 10.5 to 11px ticks in muted ink, tabular).

### Named Rules
**The Engraved Note Rule.** Anything that annotates the plate (names, targets, the D note, caveats) is Caslon italic. Anything you read as a quantity is Franklin with tabular figures.

**The Halo Rule.** Every label set over the plate carries a 4px plate-colour stroke (paint-order: stroke) so it reads cleanly over lines and stars.

## Layout

The overview is a two-column atlas: a 300px plate margin (title block, pitch, live readout, tally) beside a fluid plate, with a 28px gutter, and a full-width investigation index below. Under 900px it collapses to one column in story order: plate, readout, tally, index. The plate reserves headroom so top-of-range stars stay inside the frame.

Page frame: max width 1360px, 2rem top and 4rem bottom padding (1.2rem top under 640px). Below the plate, ruled grids carry the reading guide (3 columns, one under 900px), the four steps (4, 2 under 1180px, 1 under 520px) and the index of plates (one ruled row per page: italic question and description, link at right). More space sits above a heading than below it.

Plate labels never overlap: each label tries ordered candidate positions and takes the first clear one (or the least covered), avoiding stars, target marks, rank rings, the reticle and each other.

## Elevation & Depth

The page is flat. Surfaces do not lift; containers are transparent with hairline frames, metrics are transparent with a top rule, and the plate's depth is purely printed layering in a fixed order: haze (Gaussian blur, 20% opacity), graticule, ppO₂ isolines, target marks, constellations (55%), nebulae for range records, stars (each knocked out of the plate by a 1.2px plate ring), labels, trail, vector, reticle. Highlighting an investigation dims every other star and constellation to 22%.

### Shadow Vocabulary
- **Plate tooltip** (`box-shadow: 0 6px 18px rgba(0, 0, 0, .28)`): the only shadow, under the transient hover tooltip on the plate.

### Named Rules
**The Printed Depth Rule.** Depth on the plate comes from print layering and opacity, never from shadows or glows on page surfaces.

## Shapes

Square and ruled. Corners are 0 (metric entries, margin notes, index cells) or a 2px hairline (buttons, widgets, focus ring, tooltip, empty state). The plate frame is a double rule: an inner secondary-ink rule at 55% and an outer steel hairline 4px outside it. Lines are thin: 0.7 to 1px for structure, 1.6px for the scenario's reticle and vector. Dashes encode uncertainty or reference: dotted isolines (1 4), dashed nebula ellipses and target tolerance boxes (2 2), dashed meridians (3 4), dotted trail (1 3).

## Components

### Buttons
- **Shape:** hairline corners (2px).
- **Primary:** ember fill, plate-navy label at weight 600.
- **Secondary:** Streamlit default on the plate with a steel hairline border.
- **Press:** settle to scale(0.97) over 160ms cubic-bezier(0.23, 1, 0.32, 1), transform and background only; disabled under reduced motion.
- **Focus:** 2px ember outline, 2px offset, 2px radius, shared by links, buttons, summaries, page links and the plate iframe.

### Metric Entries
Plate-margin entries, not tiles: transparent, square, a 1px steel top rule, label (0.8rem, secondary ink) above, value (1.7rem, 500, tabular) below.

### Margin Notes (alerts)
Deep-plate wash, ivory text, square, one 2px left rule in secondary ink. Errors swap the rule to ember so they still stand apart; nothing else changes colour.

### Ruled Rows (steps, index of plates, reading guide)
Each item opens with a 1px steel top rule. Steps carry a Caslon Display numeral (2rem, secondary ink, lining figures) above a 600-weight title and a 0.9rem description. Index rows pair an italic Caslon question (1.12rem) and a 0.88rem description with a page link at right.

### Inputs / Fields
Streamlit widgets with visible borders (steel hairline), 2px radius, ember caret, ember thumb on scenario sliders.

### Navigation
Streamlit sidebar on deep plate (#0d1830) with italic 1.05rem section headings and tight separators. Page links read as index entries at weight 600, 1rem, with the same press settle.

### Empty State
A dashed steel border (solid under high contrast), 2px radius, deep-plate wash, bold ivory title over secondary-ink body. Never a blank area.

### Evidence Sky Atlas (signature)
The self-contained plate component on the overview.
- **Stars:** ivory discs, radius min(7, 1.5 + 1.25·log2(n + 0.5)) by test count, over a blurred ivory haze. Range records are dashed ellipses at 5% fill. Constellation lines join one investigation's tests.
- **Graticule:** steel hairlines; major ticks in secondary ink, minor 1% O₂ ticks in steel; Caslon italic axis titles.
- **Isolines:** ppO₂ curves (x·p constant) dotted in secondary ink at 70%, labelled in muted 10.5px tabular.
- **Targets:** gold 6px ring with a broken crosshair and a dashed tolerance box, gold italic label.
- **Reticle:** ember 13px ring and broken crosshair at 1.6px, 2px centre dot, a dashed 21px focus ring on keyboard focus; draggable, clickable and arrow-key driven, glides 260ms when moved by a control.
- **Trail:** up to eight past positions as ember dots rising in opacity, joined by a dotted line.
- **Vector:** one ember line from reticle to the best-ranked star (10px ember ring on the target), drawn on with stroke-dashoffset over 460ms cubic-bezier(0.23, 1, 0.32, 1); its Caslon italic 600 note "D · exp(D)× · investigation" fades in after 260ms. Dims to 35% while the ranking is pending.
- **Readout:** Caslon italic label, 24px tabular coordinates with O₂ and kPa values in ember, then psia, ppO₂, gravity and the best-ranked record.
- **Index cells:** an auto-fill grid (min 200px; two columns on narrow) of ruled cells: italic name, tabular counts, and a 12px O₂ strip of the investigation's coverage with an ember scenario tick. Hover or focus highlights the investigation on the plate; click pins it. Press scale 0.98, ember inset focus outline.

## Do's and Don'ts

### Do:
- **Do** draw a star only when both O₂ and total pressure are reported. Nothing is placed at a guessed value.
- **Do** draw an O₂-only record as a meridian (a dashed vertical line or band at its oxygen range across every pressure), labelled "pressure not reported".
- **Do** write a lower bound as "D ≥" whenever an unknown condition makes D a lower bound, and say so in the readout.
- **Do** leave untested sky dark and count the uncharted records in the tally.
- **Do** reserve ember (#ff8a4c / #c4501c) for the scenario and gold (#e3c46e / #8a6a1c) for NASA target atmospheres.
- **Do** set caveats in secondary ink italic and every number in tabular figures.
- **Do** give every plate label a 4px plate-colour halo and a clear, non-overlapping position.
- **Do** keep motion on transform, opacity and stroke-dashoffset, using cubic-bezier(0.23, 1, 0.32, 1), and drop all of it under prefers-reduced-motion.
- **Do** keep page surfaces flat and ruled: hairline top rules, transparent containers, 0 or 2px corners.

### Don't:
- **Don't** call a material or atmosphere "safe", in copy, labels or colour.
- **Don't** interpolate gravity; partial-gravity scenarios are flagged brackets from µg and 1-g.
- **Don't** use ember for evidence, categories or decoration, or gold for anything but NASA targets.
- **Don't** fill cards or add shadows to page surfaces; the plate tooltip is the only shadow.
- **Don't** fetch fonts or assets from the network; faces ship under app/static/fonts.
