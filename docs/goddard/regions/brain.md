# Region: brain

The brain region is responsible for everything that happens before a physical
action begins: understanding what is being asked, deciding which skill to use,
remembering what the resident needs, and keeping track of what is waiting to
happen. Five organs make up this region — the compute substrate that runs them
all, a planner that turns intentions into skill calls, a registry that knows
every organ Goddard can use, a memory that holds the resident's routines and
medication schedule, and a queue that keeps incoming requests ordered by
urgency.

Interfaces with:

- **core** — the bus (owned by core) carries reflex events and safety flags
  into the intent queue; the planner dispatches `owned_by: goddard` skills
  through the reflex loop via this bus
- **all other regions** — every organ in every region is callable from the
  planner once the registry has loaded it; the brain does not reach directly
  into another region's hardware, it issues skill calls that those regions
  execute

Key decisions:

- **File-scan registry at boot.** The registry loads all of `data/robots/organs/`
  at startup into an in-memory map. Simple and auditable — no database, no
  service, just a directory read.
- **Hot-reload deferred to v2.** Adding an organ while Goddard is running
  requires a controlled restart. This is a deliberate Wave 0 constraint, not
  an oversight.
- **Target hardware: Raspberry Pi 5 or Jetson Orin Nano class.** Both
  available today, both fit a cat-sized chassis. Pi 5 for the conservative
  build; Orin Nano when on-device inference is needed for voice or vision.
- **"Jarvis" is a label, not a persona.** The planner subsystem is named for
  clarity in `owned_by` fields. There is one robot and one voice: Goddard.

Open questions:

- Should `brain_compute` declare a formal `compute_budget` field that other
  brain organs can draw against, so the planner can reason about CPU headroom
  before scheduling inference-heavy tasks?
- What triggers a controlled restart when an organ manifest is updated in the
  field — caregiver app, Goddard's own scheduler, or manual only?
