# Region: skin

The skin region is Goddard's outermost layer — the chassis panels that face the
world and everything embedded in them. In a home setting, the skin is the part
a resident sees first and most often. It carries the organs that let Goddard
hear, see, and speak, and the small embedded gadgets (like skin_vacuum) that
deploy from panel slots without needing the arm.

Four organs live here today:

- **skin_mic** — beamforming microphone array on the top panel. The primary input
  channel for all voice interaction. Continuously active from boot; feeds
  `voice_command_pending` directly to core_safety_monitor on every reflex tick.
- **skin_speaker** — front-panel speaker calibrated for speech intelligibility
  with older ears: clear, unhurried, lower-pitched, gentle onset for alerts.
- **skin_sensor_array** — the full exteroceptive suite: RGB-D cameras, short-range
  LIDAR, and capacitive touch across the chassis ring. Maintains the `obstacle_clear`
  flag that gates every motion skill.
- **skin_vacuum** — retractable suction nozzle from a side panel. Cleanup,
  sampling, surface adhesion. See `skin_vacuum.yaml` (canonical example) for the
  full manifest.

## Interfaces with

- **core** — skin_mic and skin_sensor_array both publish hard-interrupt flags
  (`voice_command_pending`, `obstacle_clear`, `human_proximity_cm`,
  `mobility_aid_detected`) directly to core_safety_monitor. These are not
  advisory — the safety monitor reads them on every tick and acts immediately.
- **brain** — skin_mic routes recognized speech through brain_intent_queue;
  skin_speaker receives all utterances via the planner and, for urgent messages,
  directly from core_safety_monitor bypassing the queue.
- **guts** — skin_vacuum deposits material into guts_waste_bay via the one-way
  intake valve. The skin region initiates deposit; the guts region confirms receipt
  and tracks fill level.
- **legs** — skin_sensor_array's `obstacle_clear` output is a required precondition
  for leg_walk. No motion skill should bypass this gate.

## Key design decisions

**Tier 1 embedded, all of them.** Every organ in the skin region today uses
`slot: chassis-panel-*` — they are always active, zero deploy cost. The planner
sees them as immediately available with no setup step. Their `storage_volume_cm3`
values count against the skin bay budget, not the main garage.

**Mic failure is a motion-halt event, not a degraded-mode event.** If skin_mic
goes offline, core_safety_monitor halts all non-reflex motion immediately. A
robot that cannot hear "stop" must not move. This is a deliberate hard rule, not
a soft preference. The region doc enshrines it here so future sessions don't soften
it without a conscious decision.

**Speaker calibration is part of the mission.** Volume levels, pitch response,
and alert onset timing are tuned at first-run setup and stored in a caregiver
profile. The default favors slightly lower pitch and moderate pace — both are
research-backed for older-ear intelligibility. Loudness can be adjusted down by
caregiver profile but never raised without consent.

**Chassis aesthetic informs sensor placement.** The 90s translucent plastic
chassis is not just decorative — the translucency means sensor apertures are
visible, not hidden. A resident can see where the camera is. Goddard does not
look like it is watching covertly; it looks like it is doing exactly what it is
doing. This supports trust.

## Open questions

- **Voice stack ownership across brain and skin.** skin_mic captures audio and
  emits `voice_command_pending`; brain_intent_queue normalizes recognized speech
  into intents. The speech recognition step between these two is unassigned — it
  presumably lives in brain_compute, but no manifest claims it yet. Requesting
  brain lane clarification.
- **Skin bay budget accounting.** Current `storage_volume_cm3` totals across
  skin organs: skin_mic 12, skin_speaker 30, skin_sensor_array 480,
  skin_vacuum 170 = 692 cm³. No formal skin bay budget cap has been declared.
  Requesting a cap number from core lane (or confirmation that core_storage_budget
  tracks skin separately from the main garage).
- **Multi-panel slot collision.** skin_sensor_array uses `slot: chassis-panel-ring-1`
  (full circumference). If a future organ needs a panel slot on the ring, there
  may be a conflict. A panel map showing which slots are occupied would prevent
  this — could live in this doc once the hardware spec firms up.
