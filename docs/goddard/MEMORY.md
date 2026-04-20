# Memory Registry

Authoritative list of the canonical keys stored in `brain_memory` — the
persistent store of the resident's routines, preferences, schedules, and
daily rhythms. Companion to the schema: this file says *which keys exist
and what fields they carry*; `docs/goddard/SCHEMA.md`
§ [Memory-key conventions](SCHEMA.md#memory-key-conventions) says *what
shapes and naming rules apply* and how organs access them.

Memory is dignity infrastructure. A resident who has to re-explain her
medication routine every morning has lost something. These keys encode
those routines once — confirmed by the resident or her caregiver — and
Goddard carries them forward. A manifest that reads or writes a key not
present in this file registers as inert, same handshake rule that
governs unresolved consent keys (see
[`docs/goddard/MORALITY.md`](MORALITY.md)).

For the three-category partition (config / log / token-backed), the
`query:` / `update:` access grammar, and the `caregiver_auth:` rule, see
SCHEMA.md § [Memory-key conventions](SCHEMA.md#memory-key-conventions).

## Config keys

Caregiver-authored, organ-read. Hold the resident's preferences,
schedules, and thresholds. Singular-noun snake_case. Writes to these
keys SHOULD declare `caregiver_auth: true` — caregivers are the
authoritative source.

| Key                      | Read by                                  | Known fields                                                                                            |
|--------------------------|------------------------------------------|---------------------------------------------------------------------------------------------------------|
| `morning_preferences`    | `brain_morning_routine`                  | `preferred_name`, `greeting_style`, `wake_tolerance_min`, `morning_medication_scheduled`                |
| `evening_preferences`    | `brain_evening_routine`                  | `preferred_name`, `announcement_style`, `evening_medication_scheduled`, `typical_bedside_requests`      |
| `welfare_check_profile`  | `brain_check_in`                         | `preferred_name`, `quiet_threshold_min`, `last_known_location`, `do_not_disturb_active`, `nap_pattern`  |
| `medication_schedule`    | `brain_medication_reminder`              | `drug_name`, `dose`, `scheduled_time`, `preferred_name`, `tone_preference`                              |
| `approved_parts_list`    | `arm_print_on_demand`                    | list-valued; accessed via `match: candidate_part_id` lookup                                             |

Field-naming conventions applied above and expected for new fields:

- Plain snake_case nouns for scalars (`preferred_name`, `drug_name`).
- Booleans end in `_active` or `_scheduled`
  (`do_not_disturb_active`, `morning_medication_scheduled`).
- Durations end in `_min` or `_s`
  (`wake_tolerance_min`, `quiet_threshold_min`).

## Log keys

Organ-authored, caregiver-read. Named `<domain>_log`. Append-style
per-day records of what happened. Writes to log keys are default
`caregiver_auth: false` — the caregiver reviews them after the fact,
does not authorize them in advance.

| Key               | Written by                                                        | Known fields (with enum values observed)                                                                                                                                                                                                                                                         |
|-------------------|-------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `daily_log`       | `brain_morning_routine`, `brain_evening_routine`, `brain_check_in` | `morning_checkin` (`captured_response` \| `no_response_captured`), `morning_retreat_reason` (`resident_declined`), `evening_routine` (`completed` \| `no_response_captured`), `evening_retreat_reason` (`resident_declined`), `welfare_checkin` (`captured_outcome` \| `skipped_do_not_disturb` \| `resident_ok` \| `no_response_alert_filed`) |
| `medication_log`  | `brain_medication_reminder`                                        | `last_acknowledgment` (record: `drug_name`, `timestamp`, `ack_phrase`), `missed_acknowledgments` (record: `drug_name`, `timestamp`, `reason`), `declined_doses` (record: `drug_name`, `timestamp`, `resident_phrase`)                                                                              |

Log-key field conventions:

- Log fields are snake_case nouns describing *what is being logged*
  (`morning_checkin`, `welfare_checkin`).
- Log-value enums are snake_case describing *the outcome*
  (`captured_response`, `resident_declined`, `no_response_captured`).
- Keep the enum small per field — caregiver dashboards render these
  verbatim and a sprawling enum becomes noise.
- A log field MAY also be a record (multi-field value) when the event
  warrants structured capture, as `medication_log` does.

## Token-backed keys

Single scalar values referenced by `voice_lines:` substitution tokens.
Token `[snake_case]` in an utterance resolves to
`brain_memory.snake_case` at fire time. A token referencing an
unregistered key causes the organ to register as inert.

| Key                   | Token          | Used in                                                                       |
|-----------------------|----------------|-------------------------------------------------------------------------------|
| `resident_name`       | `[name]`       | `brain_morning_routine`, `brain_evening_routine`, `brain_check_in`, `brain_medication_reminder` |
| `current_medication`  | `[drug_name]`  | `brain_medication_reminder`                                                   |

Token-backed keys and their tokens share the same snake_case root by
convention; adding `[foo]` means registering `foo` here.

## Add-a-new-key workflow

### Add a new config key

1. Add a row to § Config keys with the key name, the organ(s) that read
   it, and the field list.
2. Use singular-noun snake_case for the key itself. Use the field-naming
   rules above for every field inside:
   - booleans → `_active` or `_scheduled` suffix
   - durations → `_min` or `_s` suffix
   - otherwise plain snake_case nouns
3. Organ manifests access the key via `query:` on `brain_memory` (see
   SCHEMA.md § [Access grammar](SCHEMA.md#access-grammar)). Writes from
   caregiver-facing flows declare `caregiver_auth: true`.
4. `hugo --minify` green. Standard PR review.

### Add a new log key

1. Add a row to § Log keys with the key name (must end `_log`), the
   organ(s) that write it, and the field list with observed enum values.
2. Each field is a snake_case noun describing what is being logged.
   Values are snake_case enums or small structured records. Keep enums
   short — the caregiver dashboard renders them as-is.
3. Writes use `update:` on `brain_memory` with
   `caregiver_auth: false` (the default on log-key writes). Reviewable
   after the fact; not caregiver-gated in advance.

### Add a new token-backed key

1. Pick a snake_case name. The `[token]` used inside an utterance MUST
   be the same snake_case string.
2. Add a row to § Token-backed keys with the key name, the token, and
   the manifests that use it.
3. Wire the key's value source — `brain_memory` will need a real backing
   for it (often an alias over a config-key field like
   `morning_preferences.preferred_name` for `resident_name`). Record
   the backing mechanism in a PR comment until the memory organ's
   internal schema stabilizes.
4. Any `voice_lines:` entry referencing the token before the key lands
   will register as inert — ship the registry entry in the same PR as
   the token's first use.
