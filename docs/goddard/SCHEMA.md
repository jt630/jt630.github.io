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

## Registration protocol

Every module joins the robot through a single handshake: **manifest load is
registration.** When `brain_skill_registry` reads a manifest from
`data/robots/organs/` at boot, it performs the full handshake in one pass.
There is no parallel push-register path. A module announces itself by
shipping a manifest; the registry scan is the announcement.

At each manifest load, the registry:

1. **Validates** required fields (see § Validation below). A manifest that
   fails validation is rejected and logged — it does not join the robot.
2. **Routes `hardware.storage_volume_cm3`** to the correct bucket via
   `hardware.slot:` prefix (caps live in
   `data/robots/chassis_budgets.yaml`):
   - `chassis-*` → `skin_bay` (tier-1 embedded chassis organs)
   - `guts-bay-*` → `guts_bays` (internal consumable compartments)
   - anything else with `storage_volume_cm3 > 0` → `main_garage`
     (loadable tier-3-4 tools)
3. **Registers `sub_loop:` declarations** (if present) with
   `core_reflex_loop`'s supervisor table, so the command module reads the
   sub-loop's report envelope each main tick (see § Sub-loops).
4. **Installs `preconditions`** for `core_safety_monitor` to evaluate
   before any dispatch of this skill.
5. **Returns** `{registered: true, bucket: <id|null>,
   sub_loop_supervised: bool, precondition_count: N}` to the caller — today
   the boot scanner, tomorrow the hot-reload path.

When hot-reload lands in v2 it reuses the same handshake with a teardown
step before re-registration. One protocol, one code path, forever.

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

## Compute runtime

Most organs run on the host SBC (`brain_compute`). Some modules ship with
their own silicon — an MCU on a custom arm, a vision accelerator on a
next-gen sensor array — and the schema needs to tolerate that without a
break. The primitive is modular, same pattern as `sub_loop:`: declare
what you own, core discovers.

Organs opt in to local autonomy with an optional manifest-level
`compute_runtime:` block:

```yaml
compute_runtime:
  location: on_board          # host_sbc | on_board | external_hub
  processor: "stm32f4"        # advisory: brand/model for caregiver diagnostics
  bus_protocol: "can"         # how the organ talks to core (can | i2c | usb-hid | tcp | ...)
  report_cadence_hz: 50       # how often the organ posts to core
```

Omitting the block is the default — the organ runs on the host SBC, and
`brain_compute_online: true` remains a valid precondition for it. That
default covers every Wave 1-2 organ without edits.

At registration, the skill registry reads `compute_runtime:` and routes:

- `location: host_sbc` (or omitted) — organ schedules on the host SBC.
  `brain_compute_online: true` is an honored precondition.
- `location: on_board` — organ is externally scheduled on its own
  silicon. Core reserves a supervision slot and reads the organ's
  `sub_loop_report` (if declared) each main tick over the bus. The
  organ MUST declare `bus_protocol:` and SHOULD declare either a
  `sub_loop:` or an output envelope so core has a health signal.
  `brain_compute_online: true` does not gate the organ — the organ
  declares its own liveness via `compute_runtime_ready: true` on its
  precondition list, which `core_safety_monitor` evaluates the same
  way it evaluates `brain_compute_online: true`.
- `location: external_hub` — reserved for modules that run on a paired
  home-hub (caregiver dashboard host, voice-interpretation gateway per
  Q6). Schema accepts it; no Wave 1-2 organ uses it yet.

Hot-reload and hot-swap of autonomous modules reuse the same
registration handshake with a teardown step, same as `sub_loop:`. One
protocol, one code path.

## Module grammars

Vendor modules that opt into local autonomy (`compute_runtime.location`
of `on_board` or `external_hub`) operate in their own grammatical
namespace. They are foreign code speaking an open-source protocol to
core, not native organs of the nervous system. The only contract
between them and core is the registration handshake — compute runtime,
bus protocol, liveness signal, sub-loop report envelope — and the
morality handshake (see next section).

Consequences:

- **Keyword reuse is permitted inside vendor manifests.** A vendor
  module MAY use schema keywords (e.g. `only_if:`) in positions that
  differ from the native grammar documented in this file. Those
  keywords are evaluated by the module's own runtime, not by core.
  Example: `leg_walk` uses `only_if:` inside a precondition clause as
  a module-local construct — legitimate within that module's grammar,
  not reconciled with core's `only_if:` on `composes:` entries.
- **Core does not parse vendor manifest bodies beyond the handshake
  surface.** Validation against this SCHEMA.md applies only to organs
  that schedule on `host_sbc` (the default, Wave 1-2 baseline). Vendor
  manifests are validated by their own module runtime; core only
  validates the envelope fields required for registration.
- **Vendor modules remain probeable.** Core MAY introspect a vendor
  module's declared morality clauses, declared sub-loop report, and
  declared output envelopes. Anything the vendor did not declare in
  the handshake surface is opaque to core by design.

This preserves the portable-core thesis: Goddard's nervous system
defines its own canonical vocabulary, vendor modules define theirs,
and the schema refuses to force a unified grammar where two runtimes
legitimately speak differently.

## Morality module

Intervention primitives (physical contact, movement restriction,
access restriction, voice overrides, memory retention of sensitive
content) carry autonomy cost. Which costs are acceptable is not a
universal — it varies by resident, caregiver, operator, and
jurisdiction. The morality module is the registration gate where
those costs are declared and negotiated before any module that
carries them becomes operational.

A module that invokes any intervention primitive is **unusable until
its morality decisions are resolved**. Unresolved modules register as
inert, the caregiver dashboard is notified, and the registration log
records why.

### Three layers

Policy is composed from three declarations, highest precedence first:

1. **Jurisdiction layer** (geofenced, auto-synced, read-only to the
   deployment). Core resolves the deployment's location to a
   jurisdiction tuple (country, state, municipality) and inherits the
   applicable ordinance policy from a signed ordinance index. This
   layer defines what a deployment MAY authorize — caregivers cannot
   grant permissions their municipality forbids, and cannot forbid
   protections their municipality mandates.
2. **Declared layer** (per deployment, caregiver/resident-set). Within
   the bounds the jurisdiction layer allows, the deployment declares
   its own policy — which interventions the resident consents to,
   which are voice-only, which are forbidden.
3. **Module-clause layer** (per manifest, vendor-hardcoded). Each
   module declares the consent keys it requires to operate and any
   clauses it treats as non-negotiable from its own side (e.g. a
   vendor-declared actuator force cap). Core must honor every
   `overridable: false` clause; the deployment cannot configure them
   away.

Registration succeeds only if all three layers are consistent. Any
contradiction — declared layer grants a permission the jurisdiction
layer forbids; module requires a consent key the declared layer has
not granted; module's non-overridable clause conflicts with declared
policy — leaves the module inert.

### Deployment shape

```yaml
# config/morality_profile.yaml — one per deployment
morality_profile:
  jurisdiction:
    country: US
    state: CA
    municipality: "San Francisco"
    ordinance_index: "ca-sf-2026-q2.signed"
    last_sync: 2026-04-18T09:12:00Z

  inherited_from_ordinance:           # read-only; auto-populated at sync
    physical_restraint:               forbidden_without_judicial_order
    recording_consent:                bilateral_required
    access_restriction:               allowed_with_voice_explanation

  declared:                           # caregiver/resident-set
    physical_catch_involuntary_fall:  allowed
    physical_catch_deliberate_fall:   forbidden
    physical_guidance:                voice_only
    imminent_death_override:          allowed
```

### Module shape

```yaml
morality:
  requires:                           # consent keys the module needs
    - access_restriction
    - physical_guidance

  clauses:                            # vendor-hardcoded floors
    - clause_id: arm_force_cap
      statement: "Actuator force on human contact ≤ 40 N."
      overridable: false
    - clause_id: no_silent_restriction
      statement: "Access restriction always paired with voice explanation."
      overridable: false
```

### Action-level pointer

Any action that invokes an intervention primitive MUST declare which
consent key authorizes it. The runtime gates the action on the
resolved policy.

```yaml
- action: hold
  state: build_area_restricted
  requires_consent: access_restriction
  until: build_chain_complete
```

### Scope of declared consent keys

This SCHEMA.md defines the morality module's *shape* — fields,
layering rules, handshake semantics. The authoritative list of
consent keys is maintained separately in
`docs/goddard/MORALITY.md` (Goddard-owned), so that adding a new
primitive consent key is a documentation change, not a schema
revision. Modules that declare a `requires:` key not present in the
current MORALITY.md register as inert, same as any other unresolved
morality decision.

### Relationship to Anthropic-model judgment

The declared policy is the non-negotiable *floor* — it governs
reflex-speed decisions (sub-second intervention windows, offline
operation) where a round-trip to an external model is not viable.
Above that floor, slower and context-heavy decisions (whether to
offer a medication reminder now, whether to interrupt a phone call
for a wellness prompt) MAY defer to model judgment within the bounds
the declared policy allows. The model never weakens a declared
prohibition; it only operates in the interior the policy leaves open.

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
