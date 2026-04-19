# Organ Manifest Schema

Every organ is a YAML file in `data/robots/organs/`. Canonical example:
`data/robots/organs/arm_3d_printer.yaml`. Open that before authoring.

## Two axes

Every organ has both:

- `region` — physical axis: `brain | core | guts | arm | hands | legs | thighs | skin`
- `group` — functional axis: `movement | manipulation | fabrication | sensing |
  sequence_reading | power | communication | gadgets | infrastructure`

Filter by region to plan hardware. Filter by group to plan capability.

## Full schema

```yaml
id: arm_3d_printer                 # unique, lowercase, underscores
name: 3D Printer (arm-mounted tool)
region: arm
group: fabrication

# "kind: composed" for skills that chain other skills.
# Omit for atomic skills that drive hardware.
# kind: composed

description: |
  TRIGGER when the robot needs a small rigid object (<15x15x20cm, <2kg)
  that isn't on hand and can be printed in under ~10 min.
  SKIP for metal, food-contact, load-bearing, or heat-resistant parts.

hardware:
  slot: active-tool                # named position on the robot
  power_w: 45
  deploy_time_ms: 1200
  consumables: [pla_filament]
  envelope_cm: [15, 15, 20]
  storage_volume_cm3: 1800         # advisory: "garage space" when not in use

preconditions:
  - battery_pct >= 20
  - ambient_temp_c: {min: 15, max: 35}
  - clearance_cm >= 25

inputs:
  model_stl: {type: path, required: true}
  infill_pct: {type: number, default: 20, range: [5, 100]}
  color: {type: enum, values: [black, white, red], default: black}

outputs:
  object: physical
  print_time_s: number
  filament_used_g: number

composes_with:                     # other organs that chain with this one
  - skin_vacuum

safety:
  - no flammables within 30cm during 60s cooldown
  - surface must be level within 5deg

owned_by: jarvis                   # jarvis (planner) | goddard (reflex loop)
canonical_example: r2d2            # nearest sci-fi robot in sci_fi_catalog.yaml
```

## Sub-loops

Some organs run inner loops faster than the main 10 Hz reflex tick. `leg_walk`'s
100 Hz balance sub-loop is the canonical example. Not every configuration has
one — a stationary countertop companion has no balance loop at all. Sub-loops
are therefore modular and discovered, not assumed.

An organ that owns an inner loop declares it in a manifest-level `sub_loop:`
block:

```yaml
sub_loop:
  id: balance                       # unique across the robot
  hz: 100                           # target cadence
  criticality: safety               # safety | performance | comfort
  payload_shape: proprioception_v1  # named shape (see below)
```

At boot the skill registry collects every `sub_loop:` declaration. On every
main tick `core_reflex_loop` reads a uniform report envelope from each
registered sub-loop:

```yaml
sub_loop_report:
  id: string
  hz_actual: number      # observed cadence, for health check
  missed_ticks: number   # cumulative since boot
  healthy: bool          # within cadence tolerance, no unhandled overruns
  payload: object        # shape determined by payload_shape
```

The command module (core) supervises. On every tick `core_reflex_loop` checks
the `healthy` flag for each report; `core_safety_monitor` treats any
`criticality: safety` sub-loop with `healthy: false` as a precondition failure
for every skill that depends on that sub-loop, until health is restored.
Configurations without a given sub-loop simply omit the id from
`sub_loop_reports`; an empty map is valid.

### Named payload shapes

Each `payload_shape:` is declared once and reused. Current shapes:

```yaml
# proprioception_v1 — emitted by leg_walk's 100 Hz balance sub-loop
pitch_deg: number
roll_deg: number
yaw_rate_dps: number
per_leg_contact: [bool, bool, bool, bool]
com_offset_cm: [number, number]   # x, y from chassis center, cm
corrections_n: number              # balance corrections absorbed since last main tick
stable: bool                       # rolled-up "upright and safe"
joint_saturation: bool             # any hip at >=90% max_torque
```

New payload shapes are proposed in a PR and promoted into this section by
Goddard. The `_v1` suffix reserves space for breaking changes later.

## Composed skills

A composed skill uses `kind: composed` + a `composes:` block instead of raw
hardware fields. Example (illustrative — a print-then-cleanup sequence):

```yaml
id: arm_print_and_clean
kind: composed
region: arm         # composed skill lives in the region of its lead organ
group: fabrication

composes:
  - skill: arm_3d_printer
    role: print
  - skill: skin_vacuum
    with: {mode: cleanup, duration_s: 10}

preconditions:
  - last_print_within_s <= 180
  - part_material: pla
```

The runtime resolves `composes:` into a sequential plan. Sub-skill failure
aborts the chain unless the composed skill declares a `fallback:` branch.

## Required fields

Every manifest MUST have:
- `id` (unique)
- `name`
- `region`
- `group`
- `description` (with TRIGGER and SKIP rules)
- `hardware` (or `composes:` for composed)
- `preconditions`
- `owned_by`

Optional but expected:
- `inputs`, `outputs`
- `composes_with`
- `safety`
- `canonical_example`
- `storage_volume_cm3` (advisory — omit for embedded/skin-panel organs)

## Validation

Before merging a PR, Goddard runs these checks:
- All required fields present
- `region` is one of the 8 regions
- `group` is one of the 9 functional groups
- Every id in `composes_with` resolves to an existing organ
- `hugo --minify` passes (build health)

Schema drift (new fields introduced by a lane) must be proposed — Goddard
promotes, renames, or rejects during PR review.
