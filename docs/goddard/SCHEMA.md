# Organ Manifest Schema

Every organ is a YAML file in `data/robots/organs/`. Canonical example:
`data/robots/organs/arm_3d_printer.yaml`. Open that before authoring.

## Two axes

Every organ has both:

- `region` — physical axis: `brain | core | guts | arm | hands | legs | thighs | skin`
- `group` — functional axis: `movement | manipulation | fabrication | sensing |
  sequence_reading | power | communication | gadgets`

Filter by region to plan hardware. Filter by group to plan capability.

## Full schema

```yaml
id: arm_3d_printer                 # unique, lowercase, underscores
name: 3D Printer (arm-mounted tool)
region: arm
group: fabrication

# "kind: composed" for skills that chain other skills (see heat_mold).
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
  storage_volume_cm3: 1800         # "garage space" consumed when idle

requires_mount: arm-mount-v1       # (tools only) docks into matching mount-bay
tool_change_time_s: 4              # (tools only) magazine -> active slot time

preconditions:
  - battery_pct >= 20
  - ambient_temp_c: {min: 15, max: 35}
  - clearance_cm >= 25
  - currently_mounted: true        # (tools only) must be docked first

inputs:
  model_stl: {type: path, required: true}
  infill_pct: {type: number, default: 20, range: [5, 100]}
  color: {type: enum, values: [black, white, red], default: black}

outputs:
  object: physical
  print_time_s: number
  filament_used_g: number

composes_with:                     # other organs that chain with this one
  - heat_mold
  - skin_vacuum
  - skin_lighter

safety:
  - no flammables within 30cm during 60s cooldown
  - surface must be level within 5deg

owned_by: jarvis                   # jarvis (planner) | goddard (reflex loop)
canonical_example: r2d2            # nearest sci-fi robot in sci_fi_catalog.yaml
```

## Composed skills

A composed skill uses `kind: composed` + a `composes:` block instead of raw
hardware fields. Example (`heat_mold.yaml`):

```yaml
id: heat_mold
kind: composed
region: arm         # composed skill lives in the region of its lead organ
group: fabrication

composes:
  - skill: skin_lighter
    with: {duration_s: 4, flame_height_mm: 10}
  - skill: arm_3d_printer
    role: press_tool

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

## Validation

Before merging a PR, Goddard runs these checks:
- All required fields present
- `region` is one of the 8 regions
- `group` is one of the 8 functional groups
- Every id in `composes_with` resolves to an existing organ
- `requires_mount` (if present) matches a known mount-bay type
- `hugo --minify` passes (build health)

Schema drift (new fields introduced by a lane) must be proposed — Goddard
promotes, renames, or rejects during PR review.
