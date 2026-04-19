# The CD-Changer — Mount-Bays, Magazines, and Call Priority

Arms are expensive. Every useful skill cannot have a dedicated copy of its
hardware. So Goddard shares hardware via a **CD-changer pattern** —
borrowed from CNC tool carousels and 90s car stereos.

This file defines the mechanic and, crucially, how it becomes a **call-time
priority system** the planner uses to pick the cheapest path to an intent.

## The physical mechanic

- **Mount-bay** — a standardized physical + electrical interface on an arm
  (e.g. `arm-mount-v1`). The ISS docking port analog. An arm organ
  declares what mount-bay type(s) it exposes and how many slots.
- **Tool** — any organ whose `requires_mount` matches a mount-bay type.
  Tools live idle in storage, dock into mount-bays on demand.
- **Magazine** — the arm's local tool carousel. Capacity = a few tools
  (`magazine_slots: N` on the arm organ). Fast swap between magazine and
  active slot.
- **Active slot** — the one tool currently in use per arm.
- **Storage (the "one-car garage")** — offboard storage with a bounded
  `storage_volume_cm3` budget. Tools in storage are available but far.

## Call priority — the tiers

At skill-call time Goddard's planner ranks candidates by how expensive
they are to reach. Four tiers, cheapest first:

| Tier | State | Example | Access cost |
|---|---|---|---|
| **1. Embedded** | Fixed-install, always on-body | `skin_lighter`, `skin_vacuum` | 0 (always ready) |
| **2. Mounted (active)** | Currently in an arm's active slot | Whatever tool is docked right now | 0 (already active) |
| **3. Magazine** | On-body but needs tool_change | Tools in the arm's carousel | `tool_change_time_s` |
| **4. Storage** | In the garage, needs retrieve + change | Tools in long-term storage | retrieve_time_s + tool_change_time_s |

**Rule**: the planner prefers lower-tier options when they satisfy the intent.
A `skin_lighter` (tier 1) beats a magazine-resident butane torch (tier 3)
for the same heat task unless the magazine tool has better-fitting inputs.

**Rule**: the planner may decline tier-4 calls if the total access cost
exceeds the intent's time budget. Composed skills inherit the *max* tier
of their sub-skills.

## Storage budget

The whole robot has a hard `storage_volume_cm3` cap. This is the
"one-car garage" — finite, shared across all tiers 3 and 4.

- Each organ declares its `storage_volume_cm3`
- Core region owns the accounting (`core_storage_budget.yaml`, future)
- Adding a tool that exceeds the budget forces an eject — the planner
  picks the least-recently-used tool in storage to drop
- Embedded (tier 1) skills count against the skin region's local bay
  budget, not the main garage

## Arm organ fields (the bay side)

Arms that expose mount-bays declare:

```yaml
id: arm_shoulder
name: Primary Arm
region: arm
group: manipulation

hardware:
  slot: right-shoulder
  mount_bays:
    - type: arm-mount-v1
      count: 1                   # 1 active slot
  magazine_slots: 4              # 4 tools ready on-arm
  # ... rest of schema
```

Tool organs match the bay type via `requires_mount: arm-mount-v1`.

## Tool change as a first-class organ

`arm_tool_change.yaml` (to be written by the arm scaffolding lane) is a
composed skill:

1. Retrieve target tool from magazine (or storage if tier 4)
2. Stow current active tool to magazine
3. Dock target tool to active slot
4. Verify handshake

The planner budgets this into any multi-step task that switches tools.

## Why this matters

Without priority tiers, the planner would treat every skill as equally
cheap. That's wrong — a lighter embedded in the skin is fundamentally
different from a torch sitting in a storage crate. The CD-changer makes
the cost explicit in the YAML, so the planner's choices stay honest and
Goddard never promises a capability it can't reach in time.

The pattern also means we can afford MANY skills in the library — only a
few need to be resident. The rest live in the garage until called.
