"""Manuscript Figure 2: viability sensitivity (a) beside daily scheduling (b).

Panel (a) is a paired horizontal bar chart of viable-city counts under historical
vs projected climate, one pair per analytical scenario, read from
data/viability_sensitivity.csv. The >600k population scenario has its own axes
because its counts are ~4.5x the others.

Panel (b) is the time-of-day density of outdoor competition sessions at Rio 2016,
Tokyo 2020 and Paris 2024. Density is *occupancy*: a session counts towards every
30-minute window any part of it overlaps, so 13:00-14:20 credits three windows
(13:00, 13:30, 14:00) and a session ending exactly on a boundary does not credit
the window beyond it. Sessions crossing midnight wrap. Sessions are counted
equally; no weighting by medal-event count is applied. All times are local to the
venue. Two components are drawn, both as shares of that Games' total occupancy
across every discipline: the `strict` long-duration outdoor sports as a filled
area, and the rest of the programme as a dashed step.

Athletics carries one label per Games covering everything from the 100 m to the
marathon, so it cannot be split by label. Sessions tiered `athletics` in the
crosswalk are resolved individually: a session counts as strict if it contains at
least one event of 5000 m or longer. This is session-level, consistent with how
every other sport is treated -- a qualifying session contributes its whole
duration, not just the race itself. Medal ceremonies are not competition and are
ignored when testing. Shooting and sport climbing are resolved the same way.

Sized to the Nature Cities limits: 180 mm maximum width, 5-7 pt sans-serif for
standard labelling. Panel letters sit slightly above that range, which is
conventional and keeps them findable.

Inputs
    data/olympics_sessions_long.csv    parsed session table
    data/sport_crosswalk.csv           discipline -> canonical sport + tier
    data/viability_sensitivity.csv     panel (a) counts

Outputs
    output/figure2_sensitivity_scheduling.{png,pdf,eps}
    output/session_density_30min.csv
"""

import re
from pathlib import Path

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.gridspec import GridSpec
from matplotlib.patches import ConnectionPatch

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
OUT = HERE / "output"

# ---------------------------------------------------------------- constants --

BIN_MINUTES = 30
N_BINS = 24 * 60 // BIN_MINUTES

GAMES = ["Rio 2016", "Tokyo 2020", "Paris 2024"]
# Panels run most-recent-first, top to bottom.
PANEL_ORDER = ["Paris 2024", "Tokyo 2020", "Rio 2016"]

# Local sunrise / sunset, averaged over each Games' own date range; hours
# outside these are shaded. Computed with the NOAA solar algorithm at each host
# city's coordinates, using the zenith of 90.833 deg that accounts for
# refraction and the solar disc, and that Games' civil time -- Rio BRT (UTC-3,
# Brazil's DST ran Oct-Feb so August is standard time), Tokyo JST (UTC+9, no
# DST), Paris CEST (UTC+2).
#
# Daylight shortens over each Games, so these are period means and the true
# edges move: Paris sunset runs 21:40 down to 21:13 across its 19 days, Tokyo
# 18:55 to 18:40, Rio 17:39 to 17:33.
DAYLIGHT = {
    "Rio 2016": (6.317, 17.600),  # 06:19 / 17:36
    "Tokyo 2020": (4.783, 18.800),  # 04:47 / 18:48
    "Paris 2024": (6.433, 21.450),  # 06:26 / 21:27
}

# Occupancy is counted for two nested sets -- the long-duration outdoor sports,
# and the whole programme -- so that the plotted components can be expressed
# against a common denominator. `None` means no tier filter at all: indoor,
# short-duration outdoor and long-duration outdoor alike.
SERIES = {"all": None, "strict": ("strict",)}

# Fills are solid rather than alpha-blended: the EPS backend has no alpha
# channel, and these values are the colours a semi-transparent red would produce
# over white, so all three exports render identically.
STYLE = {
    "strict": {
        "fill": "#C7443A", "line": "#8F2116", "z": 4, "dash": None,
        "label": "Long-duration outdoor",
    },
    # The remainder of the programme, drawn as an unfilled dashed step so it
    # reads as a reference curve rather than a second stacked area. Charcoal
    # rather than a second hue: it separates from the red by *lightness*
    # (contrast 13.4 on white against the strict outline's 8.8), so it survives
    # greyscale and colour-vision deficiency, where a blue or teal of the same
    # lightness would not. The white casing carries it over the dark red fill,
    # where its own contrast is only 2.8.
    "diff": {
        "fill": None, "line": "#2F2F2C", "z": 6, "dash": (0, (4, 2)),
        "label": "All other disciplines",
    },
}

NIGHT = "#dfdfdf"  # 13% black on white, pre-blended for the same reason

MM = 1 / 25.4
# Drawn wider than the 180 mm Nature Cities maximum for legibility while
# drafting. Font sizes are scaled by the same factor, so once the figure is
# placed at 180 mm the standard labelling still lands in the 5-7 pt band --
# e.g. 8 pt here renders as 8 * 180/240 = 6 pt on the page.
WIDTH = 240 * MM
HEIGHT = 142 * MM
SCALE = 240 / 180

FS = {k: round(v * SCALE, 1) for k, v in {
    "tick": 6,
    "axis": 7,
    "title": 7.5,
    "games": 7,
    "dates": 5.5,
    "scenario": 7,
    "value": 5.5,
    "legend": 6,
    "letter": 9,
}.items()}

HIST = "#2a5d9f"   # historical climate
PROJ = "#B3261E"   # projected climate -- same red family as panel (b)

# Keep text as editable text in the vector exports rather than outlines, so the
# figure can be relabelled in Illustrator without re-running this script.
plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42

# 5000 m and longer. "5 000m" (spaced) appears in the Paris source, "10,000m"
# in the IAAF timetable.
LONG_EVENT = re.compile(
    r"5[\s,]?000\s?m|10[\s,]?000\s?m|Marathon|Race\s?Walk|\bRW\b|\d+\s?km\s?(Race\s?)?Walk",
    re.I,
)
MEDAL_CEREMONY = re.compile(r"\bMC\b|Victory Ceremony")

# Paris files all shooting under one code (SHO) covering the indoor rifle/pistol
# ranges and the outdoor shotgun fields at the same venue, so venue cannot split
# them -- but no session mixes the two, and the event names do. Trap and skeet
# are the outdoor (shotgun) events; Tokyo and Rio label them separately already.
SHOTGUN = re.compile(r"\b(Trap|Skeet)\b", re.I)

# Sport climbing is stratified the same way: boulder and lead are the
# long-duration disciplines, speed is a few seconds per run and belongs with the
# short-duration outdoor sports. Neither Games ran a speed-only session -- Tokyo
# used the combined format (speed, boulder and lead in one block) and Paris
# paired each speed round with a boulder or lead round in the same session -- so
# in practice every session qualifies. The rule is still written out rather than
# hard-coded to strict, because LA28 runs speed as a standalone event.
BOULDER_LEAD = re.compile(r"\b(Boulder\w*|Lead)\b", re.I)


# ------------------------------------------------------------ session table --

def _minutes(value):
    hh, mm = str(value).split(":")[:2]
    return int(hh) * 60 + int(mm)


def resolve_athletics(event_raw):
    """strict if the session holds a competition event of 5000 m or longer."""
    if not isinstance(event_raw, str):
        return "broad"
    for event in event_raw.split("/"):
        if LONG_EVENT.search(event) and not MEDAL_CEREMONY.search(event):
            return "strict"
    return "broad"


def resolve_shooting(event_raw):
    """strict for outdoor shotgun (trap/skeet); indoor rifle/pistol excluded."""
    if not isinstance(event_raw, str):
        return "exclude"
    return "strict" if SHOTGUN.search(event_raw) else "exclude"


def resolve_climbing(event_raw):
    """strict for boulder/lead sessions; speed-only sessions are short-duration."""
    if not isinstance(event_raw, str):
        return "broad"
    for event in event_raw.split("/"):
        if BOULDER_LEAD.search(event) and not MEDAL_CEREMONY.search(event):
            return "strict"
    return "broad"


def load_sessions():
    """Sessions joined to the crosswalk, with the dynamic tiers resolved.

    The per-tier counts printed here are the audit trail for the three
    event-level rules: athletics 6/15 Rio, 10/21 Tokyo, 9/21 Paris; shooting
    7/13 Tokyo, 7/21 Paris; climbing 4/4 Tokyo, 6/6 Paris.
    """
    sessions = pd.read_csv(DATA / "olympics_sessions_long.csv")
    crosswalk = pd.read_csv(DATA / "sport_crosswalk.csv")

    merged = sessions.merge(
        crosswalk[["games", "discipline_raw", "sport_canonical", "tier"]],
        on=["games", "discipline_raw"],
        how="left",
    )

    unmapped = merged[merged.tier.isna()]
    if len(unmapped):
        print("WARNING: disciplines missing from the crosswalk:")
        for (g, d), n in unmapped.groupby(["games", "discipline_raw"]).size().items():
            print(f"  {g:12s} {d!r} ({n} sessions)")

    for label, resolver, blurb in (
        ("athletics", resolve_athletics, "hold a >=5000 m event"),
        ("shooting", resolve_shooting, "are outdoor shotgun (trap/skeet)"),
        ("climbing", resolve_climbing, "hold a boulder or lead round"),
    ):
        mask = merged.tier == label
        merged.loc[mask, "tier"] = merged.loc[mask, "event_raw"].map(resolver)
        for games in GAMES:
            rows = merged[mask & (merged.games == games)]
            if len(rows):
                print(
                    f"  [{label}] {games:12s} {(rows.tier == 'strict').sum():2d} of "
                    f"{len(rows):2d} sessions {blurb}"
                )
    return merged


def occupancy(df):
    """Sessions overlapping each 30-minute window of the day."""
    counts = np.zeros(N_BINS)
    for start, end in zip(df["start"], df["end"]):
        s, e = _minutes(start), _minutes(end)
        if e < s:  # runs past midnight, e.g. 21:00-00:00
            e += 24 * 60
        elif e == s:  # zero-length cell; credit the window it sits in
            e = s + 1
        for b in range(N_BINS):
            lo, hi = b * BIN_MINUTES, (b + 1) * BIN_MINUTES
            if min(e, hi) > max(s, lo) or min(e, hi + 1440) > max(s, lo + 1440):
                counts[b] += 1
    return counts


def build_table(sessions):
    """Occupancy per 30-minute window, for each Games and each series.

    `diff` is the whole programme minus the long-duration outdoor sports, i.e.
    indoor plus short-duration outdoor. Shares use the *same* denominator for
    every series -- that Games' total occupancy -- so `strict` and `diff` are
    additive components of `all` rather than three separately-scaled curves.
    Neither integrates to 100% on its own (long-duration outdoor is 45-48% of
    the programme by volume); the two together do.
    """
    rows = []
    for games in GAMES:
        counts = {}
        for series, keep in SERIES.items():
            subset = sessions[sessions.games == games]
            if keep is not None:
                subset = subset[subset.tier.isin(keep)]
            counts[series] = occupancy(subset)
        counts["diff"] = counts["all"] - counts["strict"]

        total = counts["all"].sum()
        for series, c in counts.items():
            for b, v in enumerate(c):
                rows.append(
                    {
                        "series": series,
                        "games": games,
                        "bin_start": f"{b * BIN_MINUTES // 60:02d}:"
                        f"{b * BIN_MINUTES % 60:02d}",
                        "sessions": int(v),
                        "share": v / total if total else 0.0,
                    }
                )
    return pd.DataFrame(rows)


def date_range(sessions, games):
    """'Jul. 24 - Aug. 11' for the panel subtitle."""
    d = pd.to_datetime(sessions[sessions.games == games].date)
    fmt = lambda x: f"{x.strftime('%b')}. {x.day}"
    return f"{fmt(d.min())} – {fmt(d.max())}"


# ----------------------------------------------------------------- panel (b) --

def draw_scheduling_panels(axes, table, sessions, fs, metric="share",
                           series=("strict", "diff")):
    """Render the three scheduling panels onto `axes` (already created).

    metric      'share' (of that Games' total occupancy) or 'sessions' (raw)
    series      which of all / strict / diff to draw, back to front. A series
                whose STYLE entry has fill=None is drawn as an unfilled dashed
                step with a white casing.
    fs          font sizes, so the same code serves 5-7 pt and larger drafts
    """
    drawn = table[table.series.isin(series)]
    ymax = drawn[metric].max() * 1.12

    x = np.arange(N_BINS)
    for ax, games in zip(axes, PANEL_ORDER):
        # Bin b covers [b, b+1) on the bar axis, so clock hour h maps to 2h and
        # a band edge sits at 2h - 0.5.
        sunrise, sunset = DAYLIGHT[games]
        for lo, hi in ((-0.6, sunrise * 2 - 0.5), (sunset * 2 - 0.5, N_BINS - 0.4)):
            ax.axvspan(lo, hi, color=NIGHT, linewidth=0, zorder=0)

        for name in series:
            d = table[(table.series == name) & (table.games == games)]
            y = d.sort_values("bin_start")[metric].values
            st = STYLE[name]
            if st["fill"]:
                ax.fill_between(
                    x, y, step="post", color=st["fill"],
                    linewidth=0, zorder=st["z"], label=st["label"])
            line, = ax.step(
                x, y, where="post", color=st["line"], linewidth=1.0,
                zorder=st["z"] + 1, linestyle=st["dash"] or "-",
                label=None if st["fill"] else st["label"])
            if not st["fill"]:
                line.set_path_effects(
                    [pe.Stroke(linewidth=1.8, foreground="white"), pe.Normal()])

        ax.set_ylim(0, ymax)
        if metric == "share":
            ax.yaxis.set_major_formatter(lambda v, _: f"{v * 100:.0f}%")

        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color("#8f8e88")
            ax.spines[side].set_linewidth(0.6)
        ax.tick_params(colors="#52514e", labelsize=fs["tick"], length=2, pad=1.5)

        ax.text(0.015, 0.93, games, transform=ax.transAxes, fontsize=fs["games"],
                fontweight="bold", color="#0b0b0b", va="top")
        ax.text(0.015, 0.76, f"({date_range(sessions, games)})",
                transform=ax.transAxes, fontsize=fs["dates"], color="#52514e",
                va="top")

    axes[-1].set_xticks(np.arange(0, N_BINS + 1, 4))
    axes[-1].set_xticklabels([f"{h:02d}" for h in range(0, 25, 2)])
    axes[-1].set_xlim(-0.6, N_BINS - 0.4)


# ------------------------------------------------------- panel (a) + assembly --

def _style_bar_axes(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#8f8e88")
        ax.spines[side].set_linewidth(0.6)
    ax.tick_params(colors="#52514e", labelsize=FS["tick"], length=2, pad=1.5)
    ax.set_axisbelow(True)


def _draw_pairs(ax, rows, xmax, baseline=None, bar_h=0.40, change_x=None):
    """Paired bars, historical above projected, newest scenario at the top."""
    y = np.arange(len(rows))[::-1]          # first row at the top
    ax.barh(y + bar_h / 2, rows.historical, height=bar_h, color=HIST,
            linewidth=0, zorder=3, label="Historical")
    ax.barh(y - bar_h / 2, rows.projected, height=bar_h, color=PROJ,
            linewidth=0, zorder=3, label="Projected")

    # Count at the end of each bar, and the change once per pair.
    for yi, r in zip(y, rows.itertuples()):
        for offset, val, colour in ((bar_h / 2, r.historical, HIST),
                                    (-bar_h / 2, r.projected, PROJ)):
            ax.text(val + xmax * 0.012, yi + offset, f"{val:g}", va="center",
                    ha="left", fontsize=FS["value"], color=colour)
        change = ("no change" if r.change_cities == 0
                  else f"−{r.change_cities:g} ({r.change_pct:.0f}%)")
        ax.text(change_x, yi, change, va="center", ha="right",
                fontsize=FS["value"], color="#0b0b0b", fontweight="bold",
                zorder=5)

    if baseline is not None:
        for val, colour in ((baseline.historical, HIST), (baseline.projected, PROJ)):
            ax.axvline(val, color=colour, linestyle=(0, (3.5, 2)), linewidth=0.9,
                       zorder=2)   # behind the bars, above the gridlines

    # Descriptive scenario names only; '|' in axis_label marks a line break,
    # which keeps the tick column narrow and leaves more width for the bars.
    labels = [r.axis_label.replace("|", "\n") for r in rows.itertuples()]
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=FS["scenario"])
    for tick in ax.get_yticklabels():
        tick.set_linespacing(1.25)
    ax.set_ylim(y.min() - 0.75, y.max() + 0.75)
    ax.set_xlim(0, xmax)
    ax.grid(axis="x", color="#e2e1dd", linewidth=0.5, zorder=0)
    _style_bar_axes(ax)


def main():
    OUT.mkdir(exist_ok=True)

    sens = pd.read_csv(DATA / "viability_sensitivity.csv").sort_values("order")
    main_rows = sens[sens.axis_group == "main"].reset_index(drop=True)
    pop_rows = sens[sens.axis_group == "population"].reset_index(drop=True)
    baseline = main_rows.iloc[0]

    sessions = load_sessions()
    table = build_table(sessions)
    table.to_csv(OUT / "session_density_30min.csv", index=False)

    fig = plt.figure(figsize=(WIDTH, HEIGHT))
    gs = GridSpec(
        2, 2, figure=fig,
        width_ratios=[0.44, 0.56], height_ratios=[len(main_rows), 1.35],
        left=0.088, right=0.985, top=0.855, bottom=0.09,
        wspace=0.30, hspace=0.32,
    )
    ax_main = fig.add_subplot(gs[0, 0])
    ax_pop = fig.add_subplot(gs[1, 0])

    # Sharing must be declared at creation; Grouper.join() was removed in
    # matplotlib 3.6.
    gs_b = gs[:, 1].subgridspec(3, 1, hspace=0.07)
    axes_b = []
    for i in range(3):
        kw = {} if i == 0 else {"sharex": axes_b[0], "sharey": axes_b[0]}
        axes_b.append(fig.add_subplot(gs_b[i], **kw))
    for a in axes_b[:-1]:
        a.tick_params(labelbottom=False)

    _draw_pairs(ax_main, main_rows, xmax=250, baseline=baseline, change_x=248)
    # Both sub-panels reference the same Baseline scenario (168 / 131), so the
    # dashed lines carry one meaning throughout panel (a) even though the
    # population axis runs ~5x further and they therefore sit well left of its
    # bars.
    _draw_pairs(ax_pop, pop_rows, xmax=1220, bar_h=0.44, change_x=1210,
                baseline=baseline)
    # Diagonal connectors carrying the baseline lines across the scale change.
    # The two sub-panels share the reference (168 / 131) but not the x-scale, so
    # without these the marks in the lower panel read as stray lines at
    # unrelated positions rather than as the same baseline.
    for val, colour in ((baseline.historical, HIST), (baseline.projected, PROJ)):
        fig.add_artist(ConnectionPatch(
            xyA=(val, ax_main.get_ylim()[0]), coordsA=ax_main.transData,
            xyB=(val, ax_pop.get_ylim()[1]), coordsB=ax_pop.transData,
            color=colour, linestyle=(0, (3.5, 2)), linewidth=0.9, zorder=1,
        ))

    ax_main.set_xticks([0, 50, 100, 150])
    ax_pop.set_xticks([0, 200, 400, 600, 800])
    ax_pop.set_xlabel("Number of viable cities", fontsize=FS["axis"],
                      color="#0b0b0b", labelpad=2)

    draw_scheduling_panels(axes_b, table, sessions, fs=FS,
                           metric="share", series=("strict", "diff"))
    axes_b[-1].set_xlabel("Hour of day (local time)", fontsize=FS["axis"],
                          color="#0b0b0b", labelpad=2)

    # Header for the change column, in axes fraction so it tracks the layout.
    ax_main.text(0.912, 0.985, "Δ viable cities", transform=ax_main.transAxes,
                 ha="center", va="top", fontsize=FS["value"], fontweight="bold",
                 color="#0b0b0b")

    fig.text(0.012, 0.975, "a", fontsize=FS["letter"], fontweight="bold",
             va="top", ha="left")
    fig.text(0.034, 0.972, "Viable host cities under alternative assumptions",
             fontsize=FS["title"], fontweight="bold", color="#0b0b0b",
             va="top", ha="left")
    fig.text(0.470, 0.975, "b", fontsize=FS["letter"], fontweight="bold",
             va="top", ha="left")
    fig.text(0.492, 0.972, "Olympics daily scheduling", fontsize=FS["title"],
             fontweight="bold", color="#0b0b0b", va="top", ha="left")

    # Legends: one per panel, since the two reds mean different things.
    ax_main.legend(loc="lower left", bbox_to_anchor=(0.0, 1.02), ncol=2,
                   fontsize=FS["legend"], frameon=False, handlelength=1.1,
                   handletextpad=0.5, columnspacing=1.2, borderaxespad=0.0)
    b_box = axes_b[0].get_position()
    b_centre = (b_box.x0 + b_box.x1) / 2
    hb, lb = axes_b[0].get_legend_handles_labels()
    fig.legend(hb, lb, loc="upper center", bbox_to_anchor=(b_centre, 0.925),
               bbox_transform=fig.transFigure, ncol=2, fontsize=FS["legend"],
               frameon=False, handlelength=1.2, handletextpad=0.4,
               columnspacing=1.4)

    # Shared axis title for panel (b). The denominator is named explicitly,
    # because "share" alone invites the reader to expect each curve to sum to
    # 100% on its own.
    fig.text(b_box.x0 - 0.040, 0.47,
             "Share of total session-occupancy by sport program",
             fontsize=FS["axis"], color="#52514e", rotation=90,
             ha="center", va="center")
    out = OUT / "figure2_sensitivity_scheduling"
    for ext in ("png", "pdf", "eps"):
        fig.savefig(out.with_suffix(f".{ext}"), dpi=400)
    plt.close(fig)
    print(f"  {out.name}  {WIDTH/MM:.0f} x {HEIGHT/MM:.0f} mm")


if __name__ == "__main__":
    main()
