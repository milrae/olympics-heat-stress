# Figure 2 — viability sensitivity and Olympic daily scheduling

Reproduces Figure 2 of Raeber et al., *"Increasing risk of heat stress at the Summer Olympics"*
(Nature Cities). Self-contained: one script, three CSVs.

```bash
pip install -r requirements.txt
python make_figure2.py
```

Writes `output/figure2_sensitivity_scheduling.{png,pdf,eps}` (240 × 142 mm, 400 dpi) and
`output/session_density_30min.csv`, the binned occupancy table behind panel (b). The PNG is what
the manuscript compiles.

## What the figure shows

**Panel (a)** — viable host cities under historical vs projected climate, one pair of bars per
analytical scenario. A city is "viable" at an event-suspension probability below 25% (baseline);
each other row varies one assumption. The ≥600 k population scenario gets its own axes because its
counts are ~4.5× the others; dashed lines and diagonal connectors carry the baseline reference
(168 / 131) across that scale change.

**Panel (b)** — when outdoor competition is actually scheduled, at Rio 2016, Tokyo 2020 and
Paris 2024, as the observational counterpart to panel (a)'s "Time of Day" scenario.

Density is **occupancy**, not session starts: a session counts towards every 30-minute window any
part of it overlaps, so a 09:00–18:00 golf round credits eighteen windows, not one. Sessions
crossing midnight wrap, sessions are unweighted, and all times are local to the venue — city is
deliberately not a filter, so at e.g., Paris 2024, football's six host cities, Marseille sailing 
and Tahitian surfing each appear at their own local time.

Both plotted components share one denominator, that Games' total occupancy across *every*
discipline, so the filled long-duration-outdoor area and the dashed remainder are additive
components of the whole programme. Neither integrates to 100% alone (long-duration outdoor is
45–48% by volume); the two together do.

Shaded bands are hours of darkness, from local sunrise/sunset computed with the NOAA solar
algorithm at each host city's coordinates and civil time, averaged over that Games' own dates.

## Inputs

| file | rows | what it is |
|---|---|---|
| `data/olympics_sessions_long.csv` | 2,202 sessions | parsed from the official Rio/Tokyo/Paris schedule PDFs and the IAAF athletics timetable |
| `data/sport_crosswalk.csv` | 137 disciplines | maps each Games' own discipline vocabulary onto canonical sports and a tier |
| `data/viability_sensitivity.csv` | 7 scenarios | panel (a) counts — **hand-entered**, see below |

**Panel (a) has no generating code.** `viability_sensitivity.csv` is transcribed by hand from the
heat-risk analysis, which ran on NSF NCAR's Casper cluster and is not part of this package. If those
numbers are revised, this CSV must be re-transcribed; nothing here will catch a drift.

The session table is the parser's output, kept as CSV so the figure never depends on PDF parsing.
The parsers are not included here — each Games' schedule is a different kind of document (Paris a
106-page hybrid of Gantt grid and per-sport detail, Tokyo a row-per-session table, Rio a two-page
grid delimited by ruled lines) and none of that is needed to redraw the figure.

## Sport tiers

`sport_crosswalk.csv` is the file to edit when the sport filter is wrong, not the code.

- `strict` — long-duration outdoor sports; the filled series in panel (b)
- `broad` — outdoor but short-duration (skateboarding, BMX, track sprints, surfing, marathon
  swimming). Not plotted separately, but retained rather than collapsed into `strict` or `exclude`,
  which would lose real information
- `athletics`, `shooting`, `climbing` — **dynamic**: one label per Games covers both long and short
  events, so `resolve_*()` in `make_figure2.py` tiers each session from its event names instead
- `exclude` — indoor, ceremonies

The dynamic rules print a reconciliation line on every run. Expected:

```
[athletics] Rio 6/15, Tokyo 10/21, Paris 9/21     sessions holding a >=5000 m event
[shooting]  Tokyo 7/13, Paris 7/21                outdoor shotgun (trap/skeet)
[climbing]  Tokyo 4/4, Paris 6/6                  holding a boulder or lead round
```

A "disciplines missing from the crosswalk" warning means a label appeared with no crosswalk row; it
is dropped from the tier filter until you add one.

## Rendering choices that should survive edits

- **Fills are solid, not alpha-blended.** The EPS backend has no alpha channel; the colours used are
  what a semi-transparent red would produce over white, so all three exports render identically.
- **The dashed remainder is charcoal**, not a second red. It separates by lightness (13.4:1 on white
  against the strict outline's 8.8:1), so it survives greyscale and colour-vision deficiency. Its
  white casing exists because its contrast over the dark red fill is only 2.8:1.
- The red pair is a **sequential** ramp, not categorical (strict ⊂ all) — a categorical palette
  validator will fail it, correctly and irrelevantly.
- `pdf.fonttype` / `ps.fonttype` are 42, so text stays live and editable rather than outlined.
- Layout is **manual**, not `constrained_layout`, which stacked the title and legend on top of each
  other. `bbox_inches="tight"` is deliberately not used — it would crop the reserved top band.
- Fonts are sized for a 180 mm placement but drawn at 240 mm and scaled, so 8 pt here lands at 6 pt
  on the page, inside the Nature Cities 5–7 pt band.

## Reproducibility

Generated with matplotlib 3.11.1, pandas 3.0.5, numpy 2.4.6 on Python 3.11.15. On that stack the
output is byte-identical to the published figure (PNG md5 `b47aeea16cb252a08634a639972c79ae`).
Other matplotlib versions give a visually identical figure that is not byte-identical.
