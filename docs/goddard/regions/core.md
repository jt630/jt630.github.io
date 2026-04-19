# Region: core

Core is the autonomic backbone of the robot. It runs continuously, below the
planner's awareness, and cannot be suspended. If brain is the mind, core is
the heartbeat and nervous system — the part that keeps the body safe when
everything else is still thinking.

## Responsibility

Core owns four always-on systems and one planner-consulted accountant:

- **Reflex loop** — 10 Hz main loop. Proprioception, safety-flag evaluation,
  intent-queue drain, and dispatch of `owned_by: goddard` skills.
- **Safety monitor** — runs on every reflex tick. Pre-call precondition check,
  mid-call interrupt, and hard stop. Non-override-able by any other organ.
- **Power bus** — routes battery capacity to every region header. Enforces
  brown-out priority cuts (core and brain stay live longest; gadgets cut first).
- **Battery** — the chassis energy store. Reports state-of-charge, thermal
  state, and time-to-empty to both the reflex loop and the power bus.
- **Storage budget** — the "one-car garage" accountant. Tracks
  `storage_volume_cm3` across non-embedded organs and advises the planner
  when a tool-swap is needed before a new tool can load.

## Interfaces

- **All regions** — every organ receives power via the power bus, which core
  owns. The bus is the backbone; core sees every tick.
- **Brain** — the reflex loop drains brain's intent queue each tick. Brain
  stays live under brown-out so it can issue graceful-degradation messages.
- **Legs / thighs** — the legs region owns the 100 Hz balance sub-loop; that
  sub-loop reports its state into the reflex loop each main tick. Core does not
  own the sub-loop cadence — legs do.
- **Skin** — embedded (tier-1) organs count against the skin region's local
  bay budget, not the core garage budget.

## Key decisions

- **Target hardware: Raspberry Pi 5 or Jetson Orin Nano.** 10 Hz main loop
  and 100 Hz balance sub-loop are both achievable on current silicon. No
  speculative hardware.
- **10 Hz main / 100 Hz balance split.** Balance cannot wait for a full main
  tick. The sub-loop cadence is owned by the legs region and feeds into core's
  state — not the other way around.
- **Safety monitor is non-override-able.** No organ, planner intent, or voice
  command can bypass it. Voice commands halt motion; they do not disable safety
  checks.
- **`owned_by: goddard` vs. `owned_by: jarvis`.** Skills the reflex loop fires
  directly (movement, power, sensing) are `goddard`. Skills that enter the
  planner's intent queue (manipulation, fabrication, gadgets) are `jarvis`.
  Core-region organs are all `goddard` except `core_storage_budget`, which is
  planner-consulted.
- **Brown-out priority.** Core and brain are never cut. Legs before arm before
  skin before guts. Motion capability is preserved over gadget capability —
  a resident depending on Goddard mid-task must not find the robot stranded.

## Open questions

- How does brown-out priority interact with in-flight composed skills? If a
  composed skill is mid-execution and skin (gadget) power is cut, does the
  composed skill abort, pause, or degrade gracefully? The power bus and reflex
  loop need a shared protocol for this.
- The 100 Hz balance sub-loop interface between legs and core is described in
  words but not yet formal in either region's schema. The legs lane should
  define the state shape that feeds back into the reflex loop; core will consume
  it. Cross-lane interface request pending.
- `core_storage_budget` garage cap defaults to 8000 cm³ (config). Where does
  that config live? It should be a named constant the planner can inspect, not
  a hardcoded number buried in firmware.
