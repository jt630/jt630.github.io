# Open Questions

Cross-lane interfaces and architectural ambiguities surfaced during Wave 1
region scaffolding. Goddard reviews and adjudicates here before lanes hard-code
assumptions. Entries are resolved by editing this file (mark RESOLVED with the
decision) or promoted into the owning region's manifest once answered.

## Q1 — Balance sub-loop state shape (legs ↔ core) — RESOLVED

Resolved via the modular `sub_loop:` block + uniform `sub_loop_report`
envelope. Goddard is modular (ISS-style): not every configuration has legs,
and the schema must tolerate that. Fixing a single `proprioception_state`
shape on `core_reflex_loop.inputs` would have forced every config to ship a
balance loop.

**Decision:**

- Any organ that runs an inner loop declares it in a manifest-level
  `sub_loop:` block: `{id, hz, criticality, payload_shape}`.
- Core reads a uniform `sub_loop_report` envelope keyed by id on every main
  tick: `{id, hz_actual, missed_ticks, healthy, payload}`. Empty map is
  valid.
- The command module (core) supervises: any `criticality: safety` sub-loop
  with `healthy: false` raises a precondition failure for every skill that
  depends on it, until recovery.
- `proprioception_v1` is the first named payload shape: `pitch_deg, roll_deg,
  yaw_rate_dps, per_leg_contact[4], com_offset_cm[2], corrections_n, stable,
  joint_saturation`. New shapes are proposed by PR and promoted into
  SCHEMA.md.

Edits shipped in this resolution: `docs/goddard/SCHEMA.md` (§ Sub-loops + §
Named payload shapes), `data/robots/organs/leg_walk.yaml` (adds `sub_loop:`
block), `data/robots/organs/core_reflex_loop.yaml` (swaps
`proprioception_state: required` → `sub_loop_reports: optional`),
`docs/goddard/regions/legs.md`, `docs/goddard/regions/core.md`.

**Commit:** `e7d0cc1`

## Q2 — Shoulder handshake (core/thighs ↔ arm)

`arm_manipulator` mounts at `shoulder-mount` against the core chassis. The
physical + electrical handshake isn't specified: power pin-out, bus connector,
alignment key for installation and (future) hot-swap.

**Decision needed:** pin-out, connector part, keyed orientation, max continuous
current at the shoulder.

**Owners:** core (chassis interface), arm (consumer), possibly thighs if
high-current routing shares a rail.

## Q3 — Wrist handshake (arm ↔ hands/tools)

`arm_manipulator` exposes an `active-tool` slot at the wrist. Today every
hand/tool declares `slot: wrist-interface` (or similar) but there's no formal
spec: locking mechanism, signal protocol, weight budget, force/torque lines.

**Decision needed:** mount-bay protocol doc — mechanical latch, electrical
pin-out, weight envelope, F/T signal path.

**Owners:** arm (provides), hands + arm-mounted tools (consume).

## Q4 — Hip load and thermal dissipation (thighs ↔ skin/chassis)

`thigh_joint` needs a chassis-weight-plus-payload estimate to calibrate torque
scaling, and a thermal path for 32 W peak across four joints. Neither is
currently owned.

**Decision needed:**
- Expected chassis-plus-payload load for torque planning.
- Thermal interface at the hip housing — passive sink through chassis vs.
  active air path through a skin vent.

**Owners:** thighs (consumer), skin/chassis (provider of both answers).

## Q5 — Storage-budget accounting model (core ↔ all regions)

`core_storage_budget` is the "one-car garage" accountant. Two open pieces:

1. **Discovery model:** push-register (each non-embedded organ calls in at
   boot) vs. boot-scan (core reads every manifest's `storage_volume_cm3`
   directly). Boot-scan is simpler and matches the skill-registry pattern.
2. **Separate buckets:** skin bay (embedded gadgets, tier 1) is separate
   from the main garage per SKILL-DIRECTORY.md — guts bays add a third
   bucket (internal consumables). Should all three roll up to a single cap,
   or be enforced independently?

**Owners:** core (accountant), every region with `storage_volume_cm3`.

## Q6 — Speech-to-text path (skin ↔ brain)

`skin_mic` captures raw audio and flags `voice_command_pending`, but the
path from raw audio to normalized intents on `brain_intent_queue` has no
named organ. Likely candidates: `brain_compute` (absorb the STT workload)
or a new `brain_stt` manifest.

**Decision needed:** own STT in a new organ, or fold it into `brain_compute`'s
scope.

**Owners:** brain.

## Q7 — `brain_compute` group fit — RESOLVED

`group: sensing` on `brain_compute` was a pragmatic stretch — compute is
substrate, not sensing. Going forward the functional axis has nine groups
with `infrastructure` covering substrate organs (compute, runtime
supervision, storage accounting, inter-organ bus). "Infrastructure" is the
honest category and future-proofs for other plumbing without adding more
group-of-one labels later.

**Decision:**

- Add `infrastructure` as the ninth group in `data/robots/skill_groups.yaml`
  (description: substrate that other groups depend on; callable pattern
  `infrastructure(action, scope)`; `owned_by: goddard`).
- `brain_compute.yaml` moves from `group: sensing` → `group: infrastructure`.
- `docs/goddard/SCHEMA.md` updated: groups list now 9, validation rule reads
  "one of the 9 functional groups."
- Other core substrate organs (`core_reflex_loop`, `core_safety_monitor`,
  `core_power_bus`, `core_storage_budget`) are *not* reassigned in this
  commit — their current groups (sensing/power/sequence_reading) work well
  enough, and a bulk reassignment deserves its own review. Captured as a
  possible future follow-up, not blocking.

**Commit:** `<pending>`

## Q8 — Compute topology: centralized SBC vs. per-organ autonomy — RAISED

Surfaced while resolving Q7. Today every brain organ names
`brain_compute_online: true` as a precondition, which implies a single head-
unit SBC runs everything. But the MVP framing is "Goddard's core is a
portable substrate that plugs into modules that may bring their own
compute." That pushes back on the single-substrate assumption.

Three topologies to consider:

1. **Centralized (current).** One SBC runs the reflex loop, planner, and
   every brain organ. Simple, cheap. Weakness: a manufacturer who wants to
   dock Goddard's core into a module with its own MCU-driven balance loop
   or vision pipeline has to disable their silicon and route everything
   through Goddard's SBC.

2. **Per-organ autonomy.** Each organ declares its own `compute_runtime:`
   (on-board MCU vs. host-SBC vs. external hub) and the registry schedules
   accordingly. Organs with `compute_runtime: on_board` run their inner
   loops on local silicon and only post results to core via the bus.
   Flexible, but means every organ manifest carries a runtime block.

3. **Hybrid (the "maybe both" option).** Goddard's MVP ships as a
   centralized SBC by default, but the schema allows organs to opt-in to
   local autonomy via a `compute_runtime: on_board` declaration. Wave 1
   organs stay centralized; future modules can declare otherwise without a
   schema break. This is the same modular primitive as Q1's `sub_loop:`
   block — declare what you own, core discovers.

**Decision needed:** which topology to bake into the MVP schema. Likely
(3) given the Q1 precedent, but needs explicit curator adjudication before
any organ starts declaring `compute_runtime:`.

**Dependencies:** touches every brain organ's preconditions
(`brain_compute_online: true`), SCHEMA.md (new optional manifest block),
and possibly a new sub-group of the `infrastructure` group.

**Owners:** Goddard (schema), brain region (primary consumer).
