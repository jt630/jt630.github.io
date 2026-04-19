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

## Q7 — `brain_compute` group fit

`brain_compute` currently uses `group: sensing` as the best available fit
for an always-on SBC substrate. It's a stretch — compute is neither sensing
nor any other listed group. Groups are a functional axis, and the SBC is
infrastructure.

**Decision needed:** leave as-is (pragmatic), promote a new `group:
infrastructure`, or add `compute` as a ninth group. Affects
`data/robots/skill_groups.yaml`.

**Owners:** Goddard (schema).
