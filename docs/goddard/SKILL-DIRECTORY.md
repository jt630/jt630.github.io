# The Skill Directory — Call-Priority Tiers and Storage Budget

## Aesthetic note

The CD-changer motif lives on visually. Goddard's chassis leans 90s translucent
plastic — iMac G3, Gameboy Color, Tamagotchi. Colorful, see-through, approachable,
friendly to anyone who grew up before all tech went matte-black. This aesthetic is
part of the elderly-care mission: nothing about Goddard should look tactical or
intimidating. A scared grandma should see a cheerful translucent companion, not
a piece of military hardware.

## What this is

The skill directory is a **logical priority system**, not a physical tool magazine.
There is no carousel spinning inside the robot. Instead, the planner consults
directory-priority tiers when it resolves which skill to fire — giving each skill
an ordering hint that reflects how quickly it can be made ready.

Think of it like a filesystem with search-path precedence: the planner looks in
the cheapest tier first. If it finds a skill there that satisfies the intent, it
uses that one. The "CD-changer" name captures the intuition (some skills are
immediately ready, some need a moment to set up) without implying a physical swap
mechanism.

## The four tiers

| Tier | State | Example | Planner cost |
|---|---|---|---|
| **1. Embedded** | Always active, fixed in the chassis | `skin_vacuum` | 0 — always ready |
| **2. Mounted (active)** | Loaded and ready in the active context | Session's primary tool | 0 — already active |
| **3. Magazine** | Available but requires brief setup | Additional arm tools | setup_time_s |
| **4. Storage** | Available but requires retrieval + setup | Infrequently used tools | retrieve_time_s + setup_time_s |

**Rule**: the planner prefers lower-tier options when they satisfy the intent.
An embedded skin skill (tier 1) beats a stored arm tool (tier 4) for the same
task unless the stored tool is a substantially better fit.

**Rule**: the planner may decline tier-4 calls if total access cost exceeds the
intent's time budget. Composed skills inherit the *max* tier of their sub-skills.

## What this means in YAML

The tier a skill occupies is inferred from context, not declared as a numeric
field. The planner determines tier from:

- `hardware.slot: chassis-panel-*` → tier 1 (embedded, always active)
- Active context tracking in the runtime → tier 2 (mounted-active)
- Everything else is tier 3 or 4 depending on `storage_volume_cm3`

A large `storage_volume_cm3` is a signal that the tool is bulky and likely stored
away — this is an advisory hint to the planner, not a hard rule.

## Storage budget

Storage is split across three physically-separate buckets, each with its own
cap. Caps live in `data/robots/chassis_budgets.yaml` — one file, one truth,
overridable per chassis variant.

| Bucket | What lives here | Routing rule (on `hardware.slot:`) | Default cap |
|---|---|---|---|
| `main_garage` | Loadable tier-3-4 tools | anything not prefixed `chassis-` or `guts-bay-`, volume > 0 | 8000 cm³ |
| `skin_bay` | Tier-1 embedded chassis organs | prefix `chassis-` | 1000 cm³ |
| `guts_bays` | Internal consumable compartments | prefix `guts-bay-` | 5000 cm³ |

`core_storage_budget` computes per-bucket `declared_cm3`, `loaded_cm3`, and
`available_cm3`, plus a rolled-up `chassis_total_loaded_cm3` as an umbrella
advisory. Only `main_garage` has a swappable subset — `skin_bay` and
`guts_bays` organs are always loaded by definition, so declared equals loaded
for those buckets.

A large `storage_volume_cm3` on a main_garage-routed organ is a signal that
the tool is bulky and likely stored away — the planner uses this as an
ordering hint, not a hard rule. The hard rule is the per-bucket cap.

Routing happens at the registration protocol (see SCHEMA.md § Registration):
the registry reads `hardware.slot:`, picks the bucket, and hands the
advisory to `core_storage_budget`. No per-organ declaration of which bucket
they live in — the slot prefix is the answer.

## Why this matters

Without priority tiers, the planner would treat every skill as equally available.
That's wrong — a vacuum nozzle embedded in the skin is fundamentally different
from a specialized tool that takes 30 seconds to deploy. The directory makes the
cost difference explicit in YAML so the planner's choices stay honest.

The pattern also means we can carry a large skill library — only a few skills need
to be immediately resident. The rest are available at a cost, and the planner
accounts for that cost transparently.
