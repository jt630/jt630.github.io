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
# data/robots/morality_profile.yaml — one per deployment
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
consent keys, resident-facing hold states, and published module
clauses is maintained separately in
[`docs/goddard/MORALITY.md`](MORALITY.md) (Goddard-owned), so that
adding a new primitive consent key is a documentation change, not a
schema revision. Modules that declare a `requires:` key not present
in the current MORALITY.md register as inert, same as any other
unresolved morality decision.

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

### Conditional sub-skills — `only_if:`

Any entry in `composes:` MAY carry an optional `only_if:` field. The
sub-skill fires only when the expression evaluates true at the moment
the chain reaches that step; otherwise it is skipped and the chain
continues to the next entry.

```yaml
composes:
  - skill: brain_memory
    role: check_do_not_disturb
  - skill: leg_walk
    role: approach_last_known_location
    only_if: do_not_disturb_active == false AND quiet_threshold_exceeded == true
  - skill: skin_speaker
    role: apologize_and_retreat
    only_if: resident_responded_normally == true
```

**Semantics.**

- The expression is evaluated against the runtime's blackboard at the
  instant the step is reached, not at chain-plan time. A flag written
  by an earlier sub-skill in the same chain is visible.
- Skipping is not a failure. A skipped entry does not trigger
  `fallback:`; the chain continues with its success path.
- Expression grammar is the same as `preconditions:` — boolean
  comparisons against blackboard keys, joined by `AND`/`OR`. Keep
  expressions short; move complex gating into a dedicated check-skill
  earlier in the chain.
- `only_if:` on a composes entry is distinct from `only_if:` appearing
  inside a vendor module's precondition clause. The former is the core
  grammar documented here. The latter is vendor-local (see
  [Module grammars](#module-grammars)) and evaluated by that module's
  runtime, not by the core composer.

## Fallback and recovery

Any manifest MAY declare a `fallback:` block: a list of
`trigger: ... recovery: [...]` clauses evaluated in order. The first
trigger whose expression matches the current failure condition runs
its recovery list and the chain ends on whatever terminal action the
list reaches (`abort:`, a completed skill call, etc.).

```yaml
fallback:
  - trigger: <expression>
    recovery:
      - <recovery action>
      - <recovery action>
      - abort: true
```

Trigger expressions use the same grammar as `preconditions:` and
`only_if:` — boolean over blackboard keys, joined by `AND`/`OR`.
String membership via `contains` is permitted where the blackboard
key is a string (e.g. `resident_response contains "not yet"`).

### Recovery actions

A recovery list is heterogeneous. The currently-defined action types:

- **Skill invocation** — `skill: <id>` with the usual `role:` and
  `with:` fields. Executes a sub-skill as part of the recovery.
- **`reschedule:` — defer the parent intent.** See dedicated section
  below. (Wave 3 Phase B2.)
- **`hold:` / `until:` — pause in a declared safe state.** See
  dedicated section below. (Wave 3 Phase B3.)
- **`abort: true`** — terminate the chain; the runtime treats the
  recovery as complete and does not propagate the original failure
  upward.
- **`log: <key>`** — emit a structured log event under the given key
  for caregiver-tier review. Advisory only; does not terminate.
- **`enqueue:`** — place an intent on the brain's intent queue for
  later consideration. Shape:
  ```yaml
  - enqueue:
      intent: <intent_id>
      source: <sensor|schedule|caregiver|…>
      priority_hint: <scheduled|normal|elevated>
  ```
  Advisory; does not terminate. The intent queue organ decides when
  and whether to run the intent.

### `reschedule:` — defer the parent intent

`reschedule:` re-queues the manifest's own intent for a later
attempt. Used when the resident has soft-declined an interaction
(morning routine, evening routine, check-in) and the robot wants to
back off without giving up entirely.

```yaml
- reschedule:
    intent: morning_routine
    delay_min: 15
```

**Fields.**

- `intent:` (required) — the intent-queue key to re-enqueue. By
  convention, matches the parent manifest's primary intent id.
- `delay_min:` (required) — integer minutes to defer before the
  scheduler considers the intent again.

**Semantics.**

- `reschedule:` is non-terminal. The recovery list continues past it.
  Pair with a subsequent `abort: true` to end the current chain, as
  the two live sites do:
  ```yaml
  recovery:
    - skill: skin_speaker
      role: retreat_gently
      with: { utterance: "Of course. I will check back in a little while.", volume_pct: 40 }
    - reschedule: { intent: morning_routine, delay_min: 15 }
    - abort: true
  ```
- Reschedule stacking: if the intent queue already holds a pending
  instance of the named intent, `reschedule:` updates the scheduled
  time to the later of (existing, now + delay_min). The robot does
  not accumulate duplicate future attempts.
- `delay_min: 0` is valid but discouraged — it means "retry
  immediately," which is better expressed by omitting the
  `reschedule:` action and letting the chain's natural retry branch
  handle it.
- Ceiling: the intent queue organ MAY cap repeated reschedules of
  the same intent per day. That cap is an intent-queue policy, not a
  schema concern; manifests do not need to reason about it.

`reschedule:` is distinct from `enqueue:`. `enqueue:` places a *new*
intent on the queue (often a different intent than the parent).
`reschedule:` defers the *current* intent. Use `enqueue:` to hand off
to a different workflow; use `reschedule:` to back off and try again.

### `hold:` / `until:` — pause in a declared safe state

`hold: <state_id>` instructs the runtime to suspend forward motion of
the chain and place the robot — or the affected environment — in a
named safe state. The hold releases when the paired `until:` condition
evaluates true. Both fields are required together; one is meaningless
without the other.

```yaml
- hold: station_at_nearest_safe_pose
  until: caregiver_arrival OR obstacle_clear == true
```

**Two flavors, one grammar.** A hold state either acts on the robot
itself or acts on the resident / environment. The grammar is the
same; the morality implications differ.

**Robot-self holds** — the robot holds its own pose and does not
move. No autonomy cost to the resident. No `requires_consent:` needed.

```yaml
# leg_fall_response — robot stations itself out of the way until help arrives
- hold: station_at_nearest_safe_pose
  until: caregiver_arrival OR obstacle_clear == true

# brain_check_in — robot holds outside the resident's personal-space bubble
- hold: station_outside_personal_space_bubble
  until: caregiver_arrival OR resident_responds
```

**Resident-facing holds** — the robot enforces a keep-out zone,
movement restriction, or other access restriction on the resident's
environment. This is an intervention primitive and MUST carry a
`requires_consent: <key>` pointer (see [Morality module](#morality-module)).
Registration fails for any resident-facing hold that omits it.

```yaml
# arm_print_on_demand — keeps the resident clear of the warm build plate
- hold: build_area_restricted
  until: caregiver_ack
  requires_consent: access_restriction
```

**`until:` grammar.** Shares the boolean expression syntax of
`preconditions:`, `only_if:`, and `trigger:` — blackboard keys joined
by `AND`/`OR`, equality and comparison operators, `contains` for
string membership. Event-like keys (`caregiver_arrival`,
`caregiver_ack`, `resident_responds`) resolve true when the
corresponding event fires and remain true from that point onward in
the hold's scope.

**Expected pairings.** Every resident-facing hold SHOULD be preceded
in the recovery list by a voice-line explaining the hold in
warm-home-aide register (see [`voice_lines:`](#voice-lines)). The
Morality module's `no_silent_restriction` clause on fabrication-class
manifests hardens this convention from "should" to "must" at
registration time — a module asserting that clause cannot enter a
resident-facing hold without a paired utterance.

**Resident-facing hold state registry.** The authoritative mapping of
resident-facing hold states to consent keys lives in
[`docs/goddard/MORALITY.md`](MORALITY.md#resident-facing-hold-states)
(Goddard-owned). New resident-facing hold states are added there, not
by editing SCHEMA.md. Robot-self pose states are not registry-tracked
— they are free-form state ids local to the organ that declares them.

**No forever-holds.** `until: true` (an always-satisfied condition)
and `until:` omitted are both invalid. A hold without a release
condition is a stuck robot, not a safe state.

## Voice lines

Any manifest whose chain produces utterances MAY declare a top-level
`voice_lines:` block — a registry of the utterances the organ speaks
through `skin_speaker`. Keys are stable snake_case identifiers; values
are the utterance strings. The block is a sibling of `safety:`,
`fallback:`, and `composes:`.

```yaml
voice_lines:
  greeting:     "Good morning, Mrs. [name]. I hope you rested well."
  check_in:     "How did you sleep?"
  retreat:      "Of course. I will check back in a little while."
  soft_handoff: "I am going to ask your caregiver to double-check your
                 morning medicine today. Nothing for you to worry about."
```

### Purpose

`voice_lines:` is **reviewable copy**. Caregivers tune copy here
(through the caregiver app in production, through PRs today) without
touching chain logic. Putting utterances in one place makes the
organ's voice register auditable: anyone reading the manifest can see
every thing the robot might say, separated from the question of when
it says it.

### Register contract

Every entry in `voice_lines:` SHOULD sound like a warm neighbor poking
their head in, not a medical alarm. Per-organ comments (preamble
inside the `voice_lines:` block) describe the tonal target the
caregiver should preserve when tuning — e.g. *"a person saying it,
not a machine reading it,"* *"a neighbor poking their head in, not a
medical alarm."* These annotations are not schema-enforced but they
are the operational definition of the warm-home-aide register that
the broader system stakes itself on. Reviewers SHOULD push back on
copy that drifts toward clinical, corporate, or alarmist tone.

### Substitution tokens

Utterance strings MAY contain substitution tokens in
`[snake_case]` form. At fire time, the runtime resolves each token
against `brain_memory` using the token name as the memory key. The
currently-used tokens:

| Token          | Resolved from                        |
|----------------|--------------------------------------|
| `[name]`       | `brain_memory.resident_name`         |
| `[drug_name]`  | `brain_memory.current_medication`    |

New tokens are added by registering a key in `brain_memory` with the
same name and are documented in
[`docs/goddard/MEMORY.md`](MEMORY.md#token-backed-keys) (Goddard-owned).
Tokens referencing unregistered memory keys cause the organ to register
as inert, same as any other missing-dependency failure.

### Consumption pattern — current and forward

Sub-skill invocations today duplicate the utterance string verbatim
inside their `with: utterance: "..."` field. The `voice_lines:` block
serves as the canonical source; the duplication is known tech debt
from before this section existed.

Forward direction — not required in Wave 3 — is `utterance_ref:
<key>` on `skin_speaker` invocations, resolved at plan time to the
corresponding `voice_lines:` entry. The migration is deferred to a
later wave so existing manifests remain valid as-is; this section
documents the intent so the forward path is legible to future
authors.

### Relationship to the morality module

Resident-facing intervention primitives (notably resident-facing
`hold:` actions per [Morality module](#morality-module)) expect a
paired voice-line that explains the intervention in the organ's
declared register. A manifest asserting the
`no_silent_restriction` clause (fabrication-class organs) cannot
enter a resident-facing hold without a paired utterance; the registry
of utterances that satisfy that pairing lives in its own
`voice_lines:` block. Separating *what the robot says* from *when it
says it* lets caregivers tune one without risking the other.

## Memory-key conventions

Organs read and write shared state through `brain_memory`. The keys
involved are canonical — multiple organs reference the same key for
the same purpose, so naming drift fragments the caregiver's view of
the resident. This section defines the conventions so new organs and
new memory keys follow the existing shape.

### Key categories

Memory keys partition by who writes them and how organs consume
them.

- **Config keys** — caregiver-authored, organ-read. Singular-noun
  snake_case. Hold the resident's preferences, schedules, and
  thresholds that the caregiver tunes through the caregiver app.
  Currently in use: `morning_preferences`, `evening_preferences`,
  `welfare_check_profile`, `medication_schedule`,
  `approved_parts_list`.
- **Log keys** — organ-authored, caregiver-read. Named
  `<domain>_log`. Append-style per-day records of what happened.
  Currently in use: `daily_log`, `medication_log`.
- **Token-backed keys** — single scalar values referenced by
  `voice_lines:` substitution tokens. Token `[snake_case]` resolves
  to `brain_memory.snake_case`. Currently in use: `resident_name`
  (→ `[name]`), `current_medication` (→ `[drug_name]`).

### Access grammar

Sub-skill invocations of `brain_memory` use two `with:` shapes —
`query:` for reads, `update:` for writes.

**Read by field set:**

```yaml
- skill: brain_memory
  role: read_morning_profile
  with:
    query:
      key: morning_preferences
      fields: [preferred_name, greeting_style, wake_tolerance_min]
```

**Read by id match** (lookup within a list-valued key):

```yaml
- skill: brain_memory
  role: validate_part_is_approved
  with:
    query:
      key: approved_parts_list
      match: candidate_part_id
```

**Targeted write:**

```yaml
- skill: brain_memory
  role: log_checkin_outcome
  with:
    update:
      key: daily_log
      field: welfare_checkin
      value: captured_outcome
```

### Caregiver authority

Writes MAY declare `caregiver_auth: <bool>` alongside `update:`. When
`true`, the write is held in a pending queue until the caregiver
approves it via the caregiver app; when `false` (the current default
on log-key writes), the write lands immediately. Config-key writes
SHOULD declare `caregiver_auth: true` — caregivers are the
authoritative source for preferences, schedules, and thresholds.

### Field-level conventions

- Log-key fields are snake_case nouns describing what is being logged
  (`morning_checkin`, `evening_routine`, `welfare_checkin`,
  `morning_retreat_reason`).
- Log-key values are snake_case enums describing the outcome
  (`captured_response`, `resident_declined`, `no_response_captured`,
  `skipped_do_not_disturb`). Keep the enum small per field; caregiver
  dashboards render these verbatim.
- Config-key fields are snake_case nouns (`preferred_name`,
  `do_not_disturb_active`, `wake_tolerance_min`). Booleans end in
  `_active` or `_scheduled`. Durations end in `_min` or `_s`.

### Authoritative registry

The authoritative list of canonical memory keys, their category, and
their shape lives in [`docs/goddard/MEMORY.md`](MEMORY.md)
(Goddard-owned). New keys are added there, not by inventing them in
manifests. Manifests referencing unregistered keys register as inert
— same handshake rule that governs unresolved consent keys per the
morality module.

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

The canonical enforcement of this schema's rules is
**`scripts/validate_organs.py`** (Wave 13). Run it before merging any PR that
touches `data/robots/organs/` or the registries:

```bash
python3 scripts/validate_organs.py           # errors only
python3 scripts/validate_organs.py --strict  # warnings become errors (CI mode)
```

A CI step (`.github/workflows/validate.yml`) runs the validator on every push
and PR that touches organs or registries; failure blocks merge. The rules it
enforces are listed in the script's module docstring (R001–R018) with a
SCHEMA.md section anchor per rule.

**Adding a new rule:** every wave that adds a MUST/MUST NOT assertion to
SCHEMA.md MUST add a corresponding rule to `validate_organs.py` in the same PR.
A documented rule with no check function implies a guarantee that does not exist.

Goddard also runs these checks on every PR:
- All required fields present (R001)
- `region` is one of the 8 regions (R002)
- `group` is one of the 9 functional groups (R003)
- Every id in `composes_with` resolves to an existing organ (R004)
- `hugo --minify` passes (build health — separate from the validator)

Schema drift (new fields introduced by a lane) must be proposed — Goddard
promotes, renames, or rejects during PR review.
