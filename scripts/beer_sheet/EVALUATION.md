# Beer Sheet — Model Evaluation & Backtesting

This file documents `snapshot.py`, `evaluate.py`, and `sweep.py` — the tools
for finding out whether the beer sheet's model is actually any good, instead
of assuming it. Read `CONTRACT.md` first for the data shapes these three
scripts consume.

## Evaluation protocol

### What to run, and when

| When | Command | Why |
|---|---|---|
| Right before your draft | `python snapshot.py --label preseason` | Freezes the board that actually informed your picks. This is the ONE snapshot that matters most — it's the only thing evaluate.py can honestly grade later. |
| A few times mid-season (optional) | `python snapshot.py --label week04`, `--label week08`, etc. | Lets you see how the model's *in-season* calls held up too, not just the preseason board. Each label gets its own frozen file — nothing overwrites the preseason snapshot. |
| After the season ends | `python evaluate.py --snapshot data/beer_sheet/snapshots/2026_preseason_20260822-3.json --live` | Joins the frozen board to real final-season ESPN stats and scores it. `--live` is required — without it you get synthetic actuals, useful only for testing the scoring code itself (see below). |
| Whenever you want to test a hypothesis about weights | `python sweep.py --snapshot <preseason snapshot> --live` | Re-derives the board under alternative BLEND weights from the SAME frozen inputs, scores each, and ranks them with bootstrap uncertainty. Never edits config.py — it's a what-if tool, not a way to auto-tune the real board. |

Both `evaluate.py` and `sweep.py` default to the most recently modified
snapshot file if you don't pass `--snapshot` explicitly. Always double-check
which file was picked (it's logged) before trusting the output — nothing
stops you from accidentally grading a `week01` snapshot against
end-of-season actuals instead of the `preseason` one.

### Why point-in-time capture is mandatory, not a nice-to-have

ESPN's projection API only ever serves the CURRENT state of its model. There
is no endpoint that returns "what ESPN's projection said for player X in
August 2026" once August 2026 has passed — by the time the season ends,
`kona_player_info` for 2026 either no longer exists in its preseason form or
has been overwritten by ESPN's own post-hoc revisions. If you tried to
"evaluate" a preseason call by re-pulling ESPN today, you would actually be
comparing your OLD board against ESPN's NEW, already-corrected numbers —
classic lookahead bias, and it would flatter the model for reasons that have
nothing to do with how good the original forecast was.

`snapshot.py` exists to make that mistake structurally impossible: it copies
every number `evaluate.py` and `sweep.py` could ever need — the board, the
raw projected AND prior-season stat COMPONENTS (not just the blended
totals), ADP, auction values, expert ranks, league scoring/roster, and every
config.py constant that shaped the board — into one file, at one moment,
before the season can revise anything. A year from now, when the live ESPN
endpoint no longer remembers what 2026 preseason projections looked like,
the snapshot file is the only remaining source of truth. If you skip the
preseason snapshot, there is no way to honestly evaluate that season's model
ever again — not a "harder" way, no way.

### What each metric means

- **MAE / value-weighted MAE** (`evaluate.py`) — mean absolute error between
  projected and actual season points. Value-weighted uses `weight = 1 /
  vor_rank`: being off on the #3 overall player costs ~60x as much as being
  off on the #180 player. Flat MAE treats a bust at #3 the same as a bust at
  #180, which is backwards for a tool whose entire purpose is informing
  early-round decisions.
- **Spearman rank correlation, full pool vs. drafted range** — the drafted
  range (`teams x total roster slots`, ~180 players in this league) is the
  only part of the board a fantasy manager ever actually acts on. Computing
  correlation across the FULL 300+/900-player pool inflates the number: the
  long sub-replacement tail is compressed near zero for both prediction and
  outcome (everyone agrees those players are worthless), which manufactures
  agreement without reflecting any real predictive skill where it matters.
  Always read the drafted-range number as the honest one; the full-pool
  number is reported for contrast, not as the headline.
- **Per-position breakdown** — the same two metrics, split by position. A
  model can be well-calibrated in aggregate while being quietly broken at
  one position (e.g., K/DST, which are `component_blind` passthroughs of
  ESPN's own total to begin with — see `BEER_SHEET.md`).
- **Risk band calibration** — what fraction of players' actual points fell
  inside their `[floor_points, ceiling_points]` band. This is the model's
  most falsifiable claim: risk_agent.py implicitly promises "this player
  will usually land in this range," and either it does or it doesn't.
  `risk_agent.py` does not commit to an explicit target coverage
  probability (`band_base`/`band_max` are heuristic fractions of
  proj_points, not derived from a stated confidence level), so
  `evaluate.py` assumes an ~80% central interval for grading purposes only
  — that assumption is a judgment call made in `evaluate.py`
  (`ASSUMED_BAND_COVERAGE`), not a promise from the original model, and the
  output says so explicitly.
- **Head-to-head vs. ADP** — the load-bearing verdict. If `vor_rank`
  doesn't out-predict the market's own `adp_rank` against real outcomes,
  the entire value-over-replacement pipeline is decorative — a fancier way
  of restating what ESPN's draft crowd already knew for free. `evaluate.py`
  prints this as a banner, not a buried number, on purpose.
- **Bootstrap confidence intervals** (`sweep.py`) — resampling PLAYERS (not
  weeks) with replacement, 95% CI from the 2.5th/97.5th percentiles. Exists
  specifically so a sweep can't report "config B beat config A" off a point
  estimate alone.

### The honest limits of one season of data

A single NFL season gives you roughly 150-180 fantasy-relevant players who
matter to the drafted range, and their outcomes are NOT independent draws —
they share an offensive line, a quarterback, a scheme, a division's pass
defense. Effectively you have far fewer independent data points than 180.
That sample size:

- **Cannot** reliably distinguish `BLEND = 65/20/15` from `60/25/15` or
  `70/15/15`. `sweep.py`'s bootstrap CIs on real data will very likely
  overlap for any two nearby configurations — and the tool is built to say
  so plainly rather than crown a "winner" anyway.
- **Can** catch a genuinely broken config (e.g., an `espn-only` blend that
  discards real signal, or a corrupted board) if the gap is large enough
  that the CIs stop overlapping. Large, structural mistakes are visible in
  one season; small weight-tuning differences generally are not.
- **Compounds** if you sweep many configurations and only report the best
  one — multiple-comparisons noise. `sweep.py`'s default grid is
  deliberately small (5 named configs) for this reason, not because a
  finer grid isn't possible.
- **Gets better slowly.** Each additional season of frozen snapshots adds a
  real (if still small) independent data point. Treat year-over-year
  results as evidence to accumulate, not a single verdict to act on after
  one pass.

If a sweep result looks decisive after one season, the correct response is
suspicion, not excitement — check the CI width before believing it.

## Validation status

`snapshot.py`, `evaluate.py`, and `sweep.py` were built and tested against
the real (in-progress) `data/beer_sheet/board.json` /
`intermediate/projections.json` / `intermediate/espn_raw.json` on disk as of
2026-08-22 — the snapshot mechanics, joins, and metric math all run
end-to-end on real data shapes. What has NOT been validated is whether the
metrics say anything true about a real season, because the 2026 season
hasn't happened yet. Each module's `--self-test` flag instead validates the
metrics against SYNTHETIC actuals (projections plus controlled noise) and
proves:

- a deliberately corrupted board scores worse than a merely noisy one, and a
  merely noisy one scores worse than a perfect one (`evaluate.py --self-test`)
- an artificially perfect board (`actual == proj_points` exactly) scores
  near-optimal on every metric, including the risk-band hit rate
  (`evaluate.py --self-test`)
- the bootstrap confidence interval widens as injected noise increases, and
  a full sweep runs end-to-end producing a CI for every config
  (`sweep.py --self-test`)

That proves the SCORING CODE isn't lying — it does not and cannot prove the
MODEL is good. Real validation happens once, in January 2027, when
`evaluate.py --live` can finally be pointed at a completed 2026 season.
