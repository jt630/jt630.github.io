# Morality Registry

Authoritative list of the consent keys, resident-facing hold states, and
module clauses the robot's morality module recognizes. Companion to the
schema: this file says *which names exist*; `docs/goddard/SCHEMA.md`
§ [Morality module](SCHEMA.md#morality-module) says *what shape they take*
and how the three-layer handshake resolves them at registration.

The morality module is the registration gate where intervention primitives
(physical contact, movement restriction, access restriction, voice
overrides, sensitive-memory retention) declare their autonomy cost and get
matched against what the deployment, jurisdiction, and vendor have each
agreed to. A module whose `requires:` names a consent key not present in
this file registers as inert, same as any other unresolved morality
decision. Adding a new primitive consent key is therefore a documentation
change against this registry, not a schema revision.

For the layering rules (jurisdiction → declared → module-clause), the
deployment and module shapes, and the `requires_consent:` pointer grammar,
see SCHEMA.md § [Morality module](SCHEMA.md#morality-module).

## Consent keys

Consent keys are named by modules in their `morality.requires:` list and
named by deployments in `data/robots/morality_profile.yaml` under
`declared:`. They are the shared vocabulary both sides negotiate in.

| Key                                | Primitive governed                                                                                  |
|------------------------------------|------------------------------------------------------------------------------------------------------|
| `access_restriction`               | Enforcing a keep-out zone or movement restriction on the resident's environment (e.g. a build-area cordon around a warm 3D-printer plate). |
| `physical_guidance`                | Deliberate contact to steer the resident's motion — a hand at an elbow on uneven flooring, a light touch to redirect a turn.               |
| `physical_catch_involuntary_fall`  | Interposing the chassis to break an unplanned fall. The resident has not chosen to go to the floor; the robot arrests the descent.        |
| `physical_catch_deliberate_fall`   | Physically intervening when the resident is lowering themselves intentionally (sitting onto the floor, kneeling). Distinct from involuntary because autonomy is not in question. |
| `imminent_death_override`          | Overriding a narrower declared policy when sensor evidence indicates imminent death without intervention (unconscious-in-water, prolonged absence of respiration). |

Only `access_restriction` is currently asserted by any manifest
(`arm_print_on_demand`, `arm_print_and_clean`). The other four are named so
that deployments can declare positions on them up front and modules
shipped in later waves can reference them without a schema change.

## Resident-facing hold states

`hold: <state>` actions split into two flavors per SCHEMA.md
§ [`hold:` / `until:`](SCHEMA.md#hold--until--pause-in-a-declared-safe-state):
robot-self holds (no autonomy cost; state ids are free-form and not
registry-tracked) and resident-facing holds (intervention primitive; MUST
carry `requires_consent:`). This table is the authoritative list of the
resident-facing states.

| `hold:` state            | Consent key          | Asserted by                                      |
|--------------------------|----------------------|--------------------------------------------------|
| `build_area_restricted`  | `access_restriction` | `arm_print_on_demand` (1), `arm_print_and_clean` (2) |

Robot-self hold states currently in use — `station_at_nearest_safe_pose`,
`station_at_nearest_dry_pose` (both in `leg_fall_response`),
`station_outside_personal_space_bubble` (`brain_check_in`) — are listed
here for orientation only. They are not part of this registry because
they do not constrain the resident.

## Module clauses

Modules MAY publish vendor-hardcoded floors in their `morality.clauses:`
list. Each clause has a `clause_id:`, a human-readable `statement:`, and
`overridable: true|false`. Core must honor every `overridable: false`
clause; the deployment cannot configure it away. Clauses are how a vendor
takes on their own moral exposure in the open-protocol ecosystem — a
published floor the caregiver can audit at registration.

The named clauses currently defined by the schema:

| `clause_id:`               | Statement (summary)                                                   | Overridable | Asserted by                                      |
|----------------------------|-----------------------------------------------------------------------|-------------|--------------------------------------------------|
| `arm_force_cap`            | Actuator force on human contact ≤ 40 N.                               | `false`     | `arm_manipulator`                                |
| `no_silent_restriction`    | Access restriction always paired with a voice explanation.            | `false`     | `arm_print_on_demand`, `arm_print_and_clean`     |

Both clauses are now asserted in the manifests listed above. `arm_force_cap`
is the vendor-published ceiling on the arm's actuator force — reinforcing
(not replacing) the operational limits already enforced in `arm_manipulator`'s
`safety:` block (back-drive on unexpected contact force > 12 N) and its
`inputs.force_limit_n` range. `no_silent_restriction` formalizes the rule
that both fabrication manifests already follow in code: every
`build_area_restricted` hold is preceded in the recovery list by a
`skin_speaker` utterance explaining the cordon in warm-home-aide register,
per SCHEMA.md § [Voice lines → Relationship to the morality module](SCHEMA.md#voice-lines).

## Deployment profiles

The three-layer handshake only resolves once a real deployment takes
positions on the consent keys above. That per-deployment artifact is the
**morality profile**. Its shape is defined in SCHEMA.md
§ [Deployment shape](SCHEMA.md#deployment-shape): a jurisdiction tuple, a
read-only `inherited_from_ordinance:` block, and a `declared:` block with
one position (`allowed | forbidden | voice_only`) per consent key.

The canonical reference profile lives at
[`data/robots/morality_profile.yaml`](../../data/robots/morality_profile.yaml).
It is the first concrete instantiation of the module — the resident is
Mrs. Alvarez (early-80s, lives alone, mild balance decline post-hip
replacement; the same persona named in `arm_fetch_object`'s elderly-care
example), the jurisdiction is US / CA / San Francisco, and every declared
position carries a one-line caregiver-rationale comment so the audit trail
is inline with the decision.

Per-deployment is per-file. Each new deployment gets its own
`morality_profile.yaml` at the same path in its own repo / config bundle,
not a template directory here — multi-tenancy is a future concern. Future
profiles SHOULD mirror the reference file's shape: a persona blurb at the
top, the jurisdiction tuple, the ordinance-inherited block, one declared
position per consent key with reasoning, and a registration-outcomes walk
at the bottom so a reader can trace each asserting manifest through the
three layers.

A new profile MUST NOT reference consent keys, hold states, or module
clauses that are not present in this registry. If a persona seems to
need new vocabulary, the registry is updated first (see the add-a-new-entry
workflow below) and the profile pulls from the updated registry — the
profile never invents names the registry has not blessed.

## Add-a-new-entry workflow

### Adding a new consent key

1. Open a PR that edits **this file** — add a row to § Consent keys with
   the key's name and a one-line description of the primitive it governs.
   Consent-key names are snake_case, singular, action-noun (what is being
   consented to, not who consents).
2. Point the intervention action at it via `requires_consent: <key>` on
   the action line in the module that needs it, per
   SCHEMA.md § [Action-level pointer](SCHEMA.md#action-level-pointer).
3. If the new key corresponds to a primitive that deployments will want
   to declare positions on, add it to the deployment example in
   SCHEMA.md § [Deployment shape](SCHEMA.md#deployment-shape) so the
   example stays illustrative. Not all keys need to appear there — only
   ones a deployment might realistically set to `allowed | forbidden |
   voice_only`.
4. `hugo --minify` green. Standard PR review.

### Adding a new resident-facing hold state

1. Add a row to § Resident-facing hold states with the state id, the
   consent key that authorizes it, and the asserting manifests.
2. Every site that enters the state MUST carry
   `requires_consent: <key>` on the same `hold:` action; registration
   rejects a resident-facing hold without it.
3. Every site SHOULD be preceded in its recovery list by a voice-line
   explaining the hold in warm-home-aide register (SCHEMA.md
   § [Voice lines](SCHEMA.md#voice-lines)). A module that asserts
   `no_silent_restriction` MUST pair the hold with an utterance.
4. Pair each entry with an `until:` condition that has a realistic
   release path. Forever-holds are invalid per SCHEMA.md.

Robot-self hold states do not go in this registry. They stay local to
the manifest that declares them and are free-form snake_case state ids.

### Adding a new module clause

1. Add a row to § Module clauses with the `clause_id:`, a one-line
   statement, `overridable:` value, and the asserting manifests.
2. Assert the clause in the module's `morality.clauses:` list exactly as
   named here. A clause asserted under a name not in this registry is
   treated as unresolved at registration.
3. `overridable: false` is a publishing commitment — once shipped, the
   vendor cannot weaken it without a clause-version bump and a
   deprecation path. Prefer `overridable: true` for clauses that
   deployments might legitimately need to tune.
