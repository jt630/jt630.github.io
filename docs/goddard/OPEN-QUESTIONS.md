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

## Q5 — Storage-budget accounting model (core ↔ all regions) — RESOLVED

The "discovery" split dissolved — we define the protocol, and the protocol
is manifest load. One handshake for every module joining the robot. Storage
accounting, sub-loop announcement, and precondition installation all happen
in that single pass.

**Decision:**

1. **Registration protocol (new, documented in SCHEMA.md § Registration).**
   Manifest load IS the handshake. `brain_skill_registry`'s boot scan
   validates required fields, routes `storage_volume_cm3` to a bucket, hands
   sub_loop declarations to core's supervisor, and installs preconditions
   on the safety monitor — all in one pass. No parallel push-register path.
   Hot-reload (v2) reuses the same handshake with a teardown step.
2. **Three buckets, each independently capped:** `main_garage`, `skin_bay`,
   `guts_bays`. Routing rule at registration, based on `hardware.slot:`
   prefix:
   - `chassis-*` → `skin_bay`
   - `guts-bay-*` → `guts_bays`
   - anything else with `storage_volume_cm3 > 0` → `main_garage`
3. **Caps live in `data/robots/chassis_budgets.yaml`** (new file). Defaults:
   main_garage 8000, skin_bay 1000, guts_bays 5000. Override per chassis
   variant by editing that one file.
4. **`core_storage_budget` reports per-bucket declared / loaded /
   available** plus a rolled-up `chassis_total_loaded_cm3` advisory. Only
   `main_garage` has a swappable subset — embedded buckets are always
   loaded by definition.
5. **Registration handshake also announces sub-loops.** A module that ships
   a `sub_loop:` block is registered with core_reflex_loop's supervisor at
   the same moment its storage is routed. One protocol announces the loops
   it owns.

Shipped in this resolution: new `data/robots/chassis_budgets.yaml`, updated
`data/robots/organs/core_storage_budget.yaml` (bucketed outputs + routing
rule), updated `data/robots/organs/brain_skill_registry.yaml` (names the
handshake), new SCHEMA.md § Registration protocol, updated SKILL-DIRECTORY.md
§ Storage budget (three buckets), region docs core.md + skin.md.

**Commit:** `5d2be2a`

## Q6 — Voice interpretation path (skin ↔ brain) — DEFERRED (low priority)

`skin_mic` captures raw audio and flags `voice_command_pending`, but the
path from audio to normalized intents on `brain_intent_queue` has no named
organ.

**Framing for when this is picked back up:** modern multimodal LLMs (Claude
etc.) take audio bytes natively and return structured text. There is no
separate speech-to-text step to name; there is a *voice interpreter* that
calls an LLM with audio in, intent out. Likely shape: a new
`brain_voice_interpreter` manifest (region: brain, group: sensing,
owned_by: jarvis, composes_with: [skin_mic, brain_intent_queue,
brain_compute]) whose MVP implementation is one LLM call, later swappable
for an on-device model. Keeps the intent_queue as the uniform decoupling
point for voice / sensor / scheduled intents. Privacy posture matters —
caregiver opt-in gate required if audio leaves the device.

**Deferred rationale:** Wave 2 composed skills don't require voice
interpretation. They use `voice_interruptible` (any voice present → halt),
which skin_mic already provides. Full intent interpretation is only needed
once we wire up resident-initiated commands — not a Wave 2 blocker.

**Owners (when resumed):** brain.

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

**Commit:** `e4815bc`

## Q8 — Compute topology: centralized SBC vs. per-organ autonomy — RESOLVED

Resolved via the **hybrid / declared-autonomy** topology. The MVP stays
centralized by default (every Wave 1-2 organ schedules on the host SBC
and declares `brain_compute_online: true`), but the schema now carries
an optional `compute_runtime:` block so a future module can bring its
own silicon without a schema break. Same modular primitive shape as
Q1's `sub_loop:` — declare what you own, core discovers.

**Decision:**

- `compute_runtime:` is an optional manifest-level block with
  `location: host_sbc | on_board | external_hub`, plus advisory
  `processor:`, `bus_protocol:`, `report_cadence_hz:` fields.
- **Default (block omitted):** `location: host_sbc`. Honors
  `brain_compute_online: true` as a precondition. All 37 existing
  manifests remain valid without edits.
- **`location: on_board`:** organ is externally scheduled on its own
  silicon. Registry reserves a supervision slot; core reads the
  organ's `sub_loop_report` over the bus. Organ MUST declare a
  `bus_protocol:` and SHOULD declare either a `sub_loop:` or an output
  envelope. Organ declares its own liveness via a
  `compute_runtime_ready: true` precondition, which
  `core_safety_monitor` evaluates the same way as
  `brain_compute_online: true`.
- **`location: external_hub`:** reserved for caregiver-dashboard or
  voice-interpretation-gateway modules (see Q6 framing). Schema
  accepts it; no Wave 1-2 organ uses it yet.
- Hot-reload and hot-swap of autonomous modules reuse the same
  registration handshake from Q5 with a teardown step. One protocol,
  one code path.

Shipped in this resolution: new `## Compute runtime` section in
`docs/goddard/SCHEMA.md`. No manifest rewrites — Wave 1-2 organs are
host_sbc-by-default, which matches their existing
`brain_compute_online: true` preconditions exactly.

**Commit:** `1b35366`

## Q9 — Morality module: how is intervention consent declared and enforced? — RESOLVED

Raised and resolved in the same session as Q8, because the two
questions share a substrate: Q8 established that vendor modules can
bring their own silicon, and Q9 establishes that the nervous system
and those modules must also negotiate a shared moral contract before
any intervention primitive fires. Without Q9, the Phase B `hold:`
work would ship a schema that doesn't know whose morality it encodes.

**Framing.** Morality is not a universal the schema can hardcode —
different residents, caregivers, operators, and jurisdictions
legitimately hold different positions on physical intervention, voice
override, recording consent, and restraint. The schema therefore
encodes the *slots where morality gets declared*, not the morality
itself. Goddard ships the nervous system; deployment declares the
policy; vendor modules declare their floor; core refuses to operate
any combination that is internally inconsistent.

**Decision.**

- Add a manifest-level `morality:` block with `requires:` (consent
  keys the module needs) and `clauses:` (vendor-hardcoded floors,
  each with `overridable: true|false`).
- Add a deployment-level `config/morality_profile.yaml` with three
  layers:
  - `jurisdiction:` — geofenced, auto-synced from a signed ordinance
    index, read-only to the deployment.
  - `inherited_from_ordinance:` — auto-populated by the jurisdiction
    sync; defines the ceiling and floor the declared layer must
    respect.
  - `declared:` — caregiver/resident-set policy, bounded by
    `inherited_from_ordinance:`.
- Add a `requires_consent: <key>` pointer to every action that
  invokes an intervention primitive (`hold:`, catch reflexes, voice
  overrides, recording-on actions, physical-guidance actions).
- Registration handshake gates on consistency of all three layers.
  Modules whose morality decisions are unresolved register as inert,
  caregiver is notified, log records why.
- Authoritative list of consent keys lives in
  `docs/goddard/MORALITY.md` (Goddard-owned), so adding a primitive
  consent key is a documentation change, not a schema revision.
- Reflex-speed decisions are governed strictly by the declared policy
  (sub-second, offline). Slower decisions (medication reminders,
  wellness prompts) MAY defer to Anthropic-model judgment within the
  interior the declared policy leaves open. The model never weakens a
  declared prohibition.

**Why jurisdiction is first-class, not runtime-only.** Most declared
policy will inherit from geofenced municipal ordinances rather than
be authored from scratch per-deployment. Promoting
`inherited_from_ordinance:` into the schema makes the layering
auditable by caregivers, visible to vendor modules at registration,
and resilient to jurisdiction-sync failures (a module can refuse to
register if its `last_sync:` is stale beyond a clause-declared
threshold).

**Why modules carry non-overridable clauses.** Ecosystem trust. A
vendor publishing a module takes on their own moral exposure — an arm
manufacturer declaring a 40 N contact-force cap is publishing their
floor for residents and caregivers to audit at registration. The
nervous system respecting that floor is how the ecosystem stays
open-source-protocols-all-the-way-down rather than devolving into
each vendor negotiating bilaterally with Goddard.

**Shipped in this resolution:**
- New `## Module grammars` section in `SCHEMA.md` (Wave 3 Item 1,
  codifying the vendor-grammar silo).
- New `## Morality module` section in `SCHEMA.md` (Wave 3 Item 2,
  codifying the three-layer consent model).
- Phase B3 (`hold: <state>`) acquires a required `requires_consent:`
  pointer before it lands.
- Follow-up doc stub to create: `docs/goddard/MORALITY.md` —
  authoritative registry of consent keys, deferred to a later wave.

**Commit:** `PENDING`
