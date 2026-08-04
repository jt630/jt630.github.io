---
title: "The Historical Food Economy Tracker"
date: 2026-08-04
description: "Ranking Anomalocaris, T. rex, Smilodon, and modern humans on energy economics instead of raw calories — and why humans are the biggest anomaly on the chart"
draft: false
---

## The pitch

Forget "biggest," "scariest," or "most calories eaten." Rank species the way
an economist would: by what it **cost** to make them, and how much of the
ecosystem's energy they got to keep. That's the Historical Food Economy
Tracker (HFET) — ten landmark species, four historical epochs, three
metrics, one uncomfortable conclusion about where we sit on the chart.

## The three metrics

**Trophic Production Cost (TPC)** — how many plant calories it takes to
make one calorie of the target species:

```
TPC = 10^(trophic_level - 1)
```

A trophic level 4.5 apex predator has a TPC of ~3,162 — it took 3,162
calories of sunlight-fixed plant matter, filtered up through several tiers
of eating and being eaten, to produce one calorie of predator. That's the
real price of being an apex predator, and it's why they're rare: the
economy can't afford many of them.

**Energetic Return on Investment (eROI)** — calories captured per hunt
divided by calories spent catching it. A cost side, not a market-share
side — not modeled numerically here, but it's the reason a lion can't just
"decide" to hunt more.

**Market Share (Ecosystem Energy Control)** — the % of a local ecosystem's
total energy throughput one species alone controls. This is the metric
that breaks when you get to the last row of the dataset.

## Plot A — King of the Hill: the longevity timeline

<img src="/images/brain/hfet-timeline.png" alt="Horizontal bar chart ranking ten species by millions of years spent at the top of their food economy, log-scaled x-axis, colored by historical epoch" style="width:100%;max-width:900px;display:block;margin:2rem auto;border:1px solid var(--gold);" />

Sorted by how long each species actually held its position, on a log
scale because the range is enormous — 20 million years for Anomalocaris
down to 12,000 years for the modern human food economy. Read that bar at
the bottom again: **it's not a typo.** Anatomically modern humans have run
the current arrangement — agriculture, domestication, industrial food
systems — for a rounding error of geological time, and already claim ~40%
of the chart's energy control. Nothing else on this list got that much
that fast.

## Plot B — Where We Are Today: the trophic map

<img src="/images/brain/hfet-trophic-map.png" alt="Scatter plot of trophic level versus ecosystem energy control, with modern humans highlighted in the low-trophic-level, high-control quadrant labeled the Agricultural Pivot" style="width:100%;max-width:900px;display:block;margin:2rem auto;border:1px solid var(--gold);" />

Every other species on this chart earns ecosystem control by climbing the
trophic ladder — Orca at trophic level 5.0 controls about 3%. Modern
*Homo sapiens* sits at trophic level **2.21** (a real published estimate —
Bonhommeau et al., 2013 — putting humans nutritionally closer to a pig or
an anchovy than to a wolf) while controlling an estimated **40%** of
ecosystem energy throughput. That combination — low trophic level, total
control — doesn't exist anywhere else on the historical record. It's not
that humans out-hunted T. rex. It's that agriculture made hunting
optional.

## Graphic 3 — The "Milkshake" Flow

<img src="/images/brain/hfet-flow.png" alt="Four-tier ecological pyramid showing the 10 percent energy transfer rule between trophic levels, with an arrow showing agriculture routing energy directly from primary producers to modern humans" style="width:100%;max-width:900px;display:block;margin:2rem auto;border:1px solid var(--gold);" />

The classic 10% rule: every tier up the pyramid keeps roughly a tenth of
the energy below it, lost to metabolism, movement, and heat. Apex
predators pay for their trophic level in compounding 90% losses. Agriculture
is humanity's workaround — a straw stuck directly into the producer tier,
skipping three tiers of loss instead of climbing them. We didn't out-compete
the apex predators. We changed which pyramid we're standing on.

## The dataset and the script

Ten species — Anomalocaris, T. rex, Megalodon, Smilodon, *Homo erectus*,
Pleistocene and modern *Homo sapiens*, African elephant, blue whale, orca —
each with an epoch, an era duration, a trophic level, and an estimated
ecosystem control %. TPC is computed programmatically from trophic level,
not hand-entered. The values are illustrative synthetic estimates (this is
a thought experiment, not a peer-reviewed dataset) except the modern-human
trophic level of 2.21, which is a real figure from published research.

Full script, reproducible with `pandas` + `matplotlib`:
[`scripts/food_economy_tracker.py`](https://github.com/jt630/jt630.github.io/blob/main/scripts/food_economy_tracker.py)

```bash
python3 scripts/food_economy_tracker.py
# writes hfet-timeline.png, hfet-trophic-map.png, hfet-flow.png
# to static/images/brain/
```
