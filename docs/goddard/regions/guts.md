# Region: guts

The guts region holds Goddard's internal consumable tanks and waste containment.
These are not tools that reach out and act on the world — they are the supplies
and the cleanup that make every other action possible. Nothing in guts moves
against the environment; everything in guts supports the organs that do.

Three organs live here today:

- **guts_filament_tank** — swappable PLA cartridge that feeds arm_3d_printer.
  Reports `filament_remaining_g`, which arm_3d_printer checks as a precondition
  before accepting any print job.
- **guts_water_tank** — refillable clean-water reservoir for light cleaning,
  humidifier assist, and pet-bowl top-up. Reports `water_volume_ml` and a
  `refill_needed` flag so a caregiver is never surprised mid-task.
- **guts_waste_bay** — sealed intake bay for vacuum debris, print support scraps,
  and handled disposables. Stays locked between service cycles; reports fill level.

## Interfaces with

- **arm** — guts_filament_tank feeds arm_3d_printer via a PTFE bowden path that
  terminates at the active-tool slot. The arm region does not manage filament
  inventory; it reads `filament_remaining_g` from this region's output.
- **skin** — skin_vacuum deposits collected material into guts_waste_bay via the
  one-way intake valve. The waste bay does not know the vacuum exists; it only
  knows material has arrived.
- **core** — all three organs report resource levels (`filament_remaining_g`,
  `water_volume_ml`, `waste_bay_fill_pct`) that core_storage_budget should
  account for and surface to the caregiver dashboard. Low-supply and full-bay
  alerts route through core's bus.
- **brain** — scheduled refill reminders and service-cycle prompts originate in
  brain_intent_queue; guts organs do not schedule their own alerts.

## Key design decisions

**Swappable cartridges, not hard-wired supplies.** All three guts bays use
removable or refillable units. A caregiver — not a technician — can swap a
filament cartridge or refill the water tank. The service interaction is designed
to be familiar: like changing a printer cartridge or refilling a water filter.

**Waste sealing is non-negotiable.** The waste bay door locks during normal
operation. No odor, no spill, no unsanitary exposure inside the home. A seal
breach detected at service triggers a maintenance lockout until the gasket is
confirmed intact.

**All guts organs are `owned_by: jarvis`.** These are planned, managed resources,
not reflexive. Filament and water levels update on the planner's cadence; waste
intake is event-driven but still mediated through the planner's intent queue.

**`voice_interruptible: true` on all three.** A caregiver or resident can verbally
halt a dispense, pause an intake, or trigger a swap confirmation at any point.

## Open questions

- **Cross-region storage accounting.** `core_storage_budget.yaml` exists but
  this lane has not confirmed how guts bays are registered against it. Requesting
  a handoff spec from the core lane: should each guts organ push its
  `storage_volume_cm3` to a running total, or does core scan all manifests at
  boot?
- **Water tank refill workflow.** The current design assumes manual top-up by a
  caregiver. A future version could include an auto-refill dock interface — but
  this is v2 territory and should not block v1 manifest work.
- **Filament humidity sensor.** `humidity_pct` is reported by guts_filament_tank
  but no organ currently consumes it. Should core_safety_monitor add a humidity
  threshold check, or is this advisory-only for now?
