#!/usr/bin/env python3
"""
Historical Food Economy Tracker (HFET)

Tracks, ranks, and visualizes the "apexness" of ten landmark species across
Earth's history using energy economics rather than raw caloric intake:

  - Trophic Production Cost (TPC): TPC = 10 ** (trophic_level - 1)
    Plant calories required to produce one calorie of the target species.
  - Market Share: the % of a local ecosystem's energy throughput one
    species captures.
  - Era Duration: how long (Myr) that species held its position.

Run:
    python3 scripts/food_economy_tracker.py

Outputs three PNGs to static/images/brain/:
    hfet-timeline.png   Plot A - "King of the Hill" longevity timeline
    hfet-trophic-map.png Plot B - "Where We Are Today" trophic quadrant
    hfet-flow.png        Graphic 3 - the ecological pyramid / flow diagram
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ── Theme (matches Almond Farm's Cunty Theme: assets/css/main.css) ──────────
BG = "#0A0A0A"
CARD = "#141414"
TEXT = "#F5F0EB"
TEXT_DIM = "#9A968F"
GOLD = "#D4AF37"
PINK = "#FF2D8A"
GRID = "#2A2A2A"

# Categorical epoch colors: dark-mode slots from the validated 8-hue
# palette (blue, orange, aqua, gold), adjacent-pair CVD-checked. "Other"
# (Megalodon, outside the four headline epochs) gets neutral gray rather
# than a 5th hue, per the "fold rare categories to Other" rule.
EPOCH_COLORS = {
    "Cambrian Explosion": "#3987e5",
    "Jurassic/Cretaceous": "#d95926",
    "Pleistocene": "#199e70",
    "Holocene/Anthropocene": "#c98500",
    "Other (Neogene)": "#6b6b6b",
}

plt.rcParams.update({
    "figure.facecolor": BG,
    "axes.facecolor": BG,
    "savefig.facecolor": BG,
    "text.color": TEXT,
    "axes.labelcolor": TEXT,
    "xtick.color": TEXT_DIM,
    "ytick.color": TEXT_DIM,
    "axes.edgecolor": GRID,
    "font.family": "sans-serif",
    "font.size": 11,
})

# ── 1. Synthetic dataset ─────────────────────────────────────────────────
# Trophic levels, durations, and control % are illustrative estimates
# (some anchored to published figures — see notes) built for comparison,
# not a peer-reviewed dataset.
data = [
    # Species, Epoch, Era Duration (Myr), Trophic Level, Ecosystem Energy Control (%)
    ("Anomalocaris",              "Cambrian Explosion",     20.0, 3.5, 8.0),
    ("Tyrannosaurus rex",         "Jurassic/Cretaceous",     2.4, 4.7, 5.0),
    ("Megalodon",                 "Other (Neogene)",        19.4, 4.7, 4.0),
    ("Smilodon",                  "Pleistocene",              2.5, 4.3, 3.0),
    ("Homo erectus",              "Pleistocene",              1.8, 3.5, 1.0),
    ("Homo sapiens (Pleistocene)","Pleistocene",              0.28,3.7, 2.0),
    ("African Elephant",          "Holocene/Anthropocene",    5.0, 2.0, 1.5),
    ("Blue Whale",                "Holocene/Anthropocene",    1.5, 3.0, 2.0),
    ("Orca",                      "Holocene/Anthropocene",    6.0, 5.0, 3.0),
    # Modern trophic level ~2.21 is a real published estimate
    # (Bonhommeau et al., PNAS 2013) — comparable to a pig or anchovy.
    ("Homo sapiens (Modern)",     "Holocene/Anthropocene",    0.012,2.21,40.0),
]
df = pd.DataFrame(data, columns=[
    "Species", "Epoch", "Era Duration (Myr)", "Trophic Level",
    "Ecosystem Energy Control (%)",
])

# ── 2. Trophic Production Cost, computed programmatically ───────────────
df["TPC"] = 10 ** (df["Trophic Level"] - 1)

print(df.to_string(index=False))

# ── Plot A: "King of the Hill" longevity timeline ───────────────────────
fig, ax = plt.subplots(figsize=(9, 6))
sorted_df = df.sort_values("Era Duration (Myr)", ascending=True)
colors = [EPOCH_COLORS[e] for e in sorted_df["Epoch"]]
bars = ax.barh(sorted_df["Species"], sorted_df["Era Duration (Myr)"],
                color=colors, height=0.62)
ax.set_xscale("log")
ax.set_xlabel("Time spent at the top of the food economy — millions of years (log scale)")
ax.set_title("King of the Hill: Longevity Timeline", color=TEXT, fontsize=15,
             fontweight="bold", loc="left", pad=14)
ax.grid(axis="x", color=GRID, linewidth=0.6, which="both")
ax.set_axisbelow(True)
for spine in ["top", "right"]:
    ax.spines[spine].set_visible(False)

for bar, val in zip(bars, sorted_df["Era Duration (Myr)"]):
    label = f"{val:.3f} Myr" if val < 0.1 else f"{val:g} Myr"
    ax.text(bar.get_width() * 1.15, bar.get_y() + bar.get_height() / 2,
            label, va="center", ha="left", fontsize=9, color=TEXT_DIM)

ax.annotate(
    "Modern humans: 12,000 years on top —\na rounding error next to Anomalocaris'\n20 million, but already 40% of the\necosystem's energy throughput.",
    xy=(0.012, sorted_df["Species"].tolist().index("Homo sapiens (Modern)")),
    xytext=(0.02, 2.3), fontsize=8.5, color=PINK,
    arrowprops=dict(arrowstyle="->", color=PINK, lw=1.2),
)

legend_handles = [mpatches.Patch(color=c, label=e) for e, c in EPOCH_COLORS.items()]
ax.legend(handles=legend_handles, loc="lower right", frameon=False,
          fontsize=8, labelcolor=TEXT_DIM)

fig.tight_layout()
fig.savefig("static/images/brain/hfet-timeline.png", dpi=180)
plt.close(fig)

# ── Plot B: "Where We Are Today" trophic quadrant ────────────────────────
fig, ax = plt.subplots(figsize=(9, 7))
for epoch, color in EPOCH_COLORS.items():
    sub = df[df["Epoch"] == epoch]
    if sub.empty:
        continue
    ax.scatter(sub["Trophic Level"], sub["Ecosystem Energy Control (%)"],
               s=180, color=color, edgecolor=BG, linewidth=1.2,
               label=epoch, zorder=3)

# Halo ring on the human anomaly (secondary encoding, not a new hue)
human = df[df["Species"] == "Homo sapiens (Modern)"].iloc[0]
ax.scatter([human["Trophic Level"]], [human["Ecosystem Energy Control (%)"]],
           s=520, facecolor="none", edgecolor=PINK, linewidth=2, zorder=4)

for _, row in df.iterrows():
    dx, dy = 0.06, 1.0
    if row["Species"] == "Homo sapiens (Modern)":
        dx, dy = -0.05, -4.5
    ax.annotate(row["Species"], (row["Trophic Level"], row["Ecosystem Energy Control (%)"]),
                xytext=(row["Trophic Level"] + dx, row["Ecosystem Energy Control (%)"] + dy),
                fontsize=8.5, color=TEXT_DIM)

ax.axvspan(1.0, 2.5, color=GOLD, alpha=0.06, zorder=0)
ax.text(1.05, 42, "THE HUMAN\nAGRICULTURAL PIVOT", fontsize=9, color=GOLD,
        fontweight="bold", va="top")
ax.annotate("Low trophic level,\nfull ecosystem control —\nagriculture broke the\ntrophic-level/control link",
            xy=(human["Trophic Level"], human["Ecosystem Energy Control (%)"]),
            xytext=(3.3, 34), fontsize=8.5, color=PINK,
            arrowprops=dict(arrowstyle="->", color=PINK, lw=1.2))

ax.set_xlim(1.0, 5.5)
ax.set_ylim(0, 45)
ax.set_xlabel("Statistical Trophic Level")
ax.set_ylabel("Global Biomass / Ecosystem Control (%)")
ax.set_title("Where We Are Today: The Trophic Map", color=TEXT, fontsize=15,
             fontweight="bold", loc="left", pad=14)
ax.grid(color=GRID, linewidth=0.6)
ax.set_axisbelow(True)
for spine in ["top", "right"]:
    ax.spines[spine].set_visible(False)
ax.legend(loc="upper right", frameon=False, fontsize=8, labelcolor=TEXT_DIM)

fig.tight_layout()
fig.savefig("static/images/brain/hfet-trophic-map.png", dpi=180)
plt.close(fig)

# ── Graphic 3: The "Milkshake" flow diagram ──────────────────────────────
# Classic 10%-efficiency ecological pyramid, four tiers, sequential gold
# ramp (ordinal: order carries meaning, one hue, monotone lightness).
tiers = ["Primary producers", "Primary consumers", "Secondary consumers", "Apex predators"]
tier_pct = [100, 10, 1, 0.1]
tier_ramp = ["#f5d674", "#e0b94a", "#c98500", "#8a5c00"]  # light -> dark gold

fig, ax = plt.subplots(figsize=(9, 7.5))
y_positions = np.arange(len(tiers))[::-1]
max_width = 8.0
for y, pct, color, tier in zip(y_positions, tier_pct, tier_ramp, tiers):
    width = max_width * (pct / 100) ** 0.35  # perceptual width so 0.1% still reads
    ax.barh(y, width, left=-width / 2, height=0.55, color=color, zorder=3)
    ax.text(max_width * 0.62, y, f"{tier} — {pct:g}% of energy retained",
            ha="left", va="center", fontsize=9.5, color=TEXT, zorder=4)
    if y > 0:
        ax.annotate("", xy=(0, y - 0.72), xytext=(0, y - 0.32),
                    arrowprops=dict(arrowstyle="-|>", color=TEXT_DIM, lw=1.4))
        ax.text(0.55, y - 0.52, "~90% lost to metabolism,\nmovement, heat", fontsize=7.5,
                color=TEXT_DIM, va="center")

# The pivot: an arrow cutting straight from tier 1 to the human dot,
# bypassing three tiers of trophic loss. Placed in the headroom above the
# stack so it never collides with a tier label row.
ax.annotate("Homo sapiens (Modern): TL 2.21,\n~40% of throughput via agriculture —\nbypasses three tiers of trophic loss",
            xy=(max_width * 0.2, y_positions[0] + 0.28), xytext=(max_width * 0.55, y_positions[0] + 1.5),
            fontsize=8.5, color=PINK, fontweight="bold", ha="left",
            arrowprops=dict(arrowstyle="->", color=PINK, lw=1.6,
                             connectionstyle="arc3,rad=0.25"))

ax.set_xlim(-max_width * 0.9, max_width * 2.35)
ax.set_ylim(-0.9, len(tiers) + 0.9)
ax.axis("off")
ax.set_title('The "Milkshake" Flow: How Apex Species Absorb Underlying Capital',
             color=TEXT, fontsize=14, fontweight="bold", loc="left", pad=14)
ax.text(-max_width * 0.9, -0.55,
        "Each tier keeps ~10% of the energy below it (the 10% rule). Agriculture is humanity's straw\n"
        "into the bottom tier — it drinks the milkshake instead of climbing the pyramid.",
        fontsize=8, color=TEXT_DIM)

fig.tight_layout()
fig.savefig("static/images/brain/hfet-flow.png", dpi=180)
plt.close(fig)

print("\nWrote 3 charts to static/images/brain/")
