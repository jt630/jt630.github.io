# Body Regions

Eight regions. Every organ lives in exactly one. Parallel scaffolding
sessions own one region each so they never collide on files.

## The regions

| Region | Scope | Owns files matching |
|---|---|---|
| **brain** | compute, skill registry, planner, memory, intent queue | `data/robots/organs/brain_*.yaml` |
| **core** | power distribution, reflex loop, safety monitor, inter-organ bus, storage budget accounting | `data/robots/organs/core_*.yaml` |
| **guts** | consumables tanks (filament, butane, water), waste, fabrication support | `data/robots/organs/guts_*.yaml` |
| **arm** | shoulder-to-wrist manipulator, arm-mounted tools and gadgets | `data/robots/organs/arm_*.yaml` |
| **hands** | end-effectors (paw, pincer, fine tip), tool change | `data/robots/organs/hand_*.yaml` |
| **legs** | walking, wheeled, climbing locomotion | `data/robots/organs/leg_*.yaml` |
| **thighs** | leg attachment, high-torque joints, power routing to legs | `data/robots/organs/thigh_*.yaml` |
| **skin** | chassis panels, embedded gadgets (lighter, vacuum), sensors on skin | `data/robots/organs/skin_*.yaml` |

Every organ filename starts with its region prefix. Goddard rejects
manifests in the wrong file or without a `region:` field.

## Region docs

Each region gets a short markdown doc at `data/robots/regions/<region>.md`
authored by its scaffolding lane. The doc covers:

1. What the region is responsible for
2. What the region interfaces with (which other regions, via what)
3. Key design decisions specific to the region
4. Open questions for the region

Example (illustrative):

```markdown
# Region: arm

The arm spans from the shoulder joint through the wrist to the mount-bay
where tools dock. Arms are the CD-changer chassis — they expose bays and
manage the magazine carousel.

Interfaces with:
- thighs / core — power handoff at the shoulder
- hands — tool-change protocol at the mount-bay
- skin — no direct interface; skin-mounted gadgets are separate
- brain — accepts manipulation intents via the bus

Key decisions:
- Mount-bay type v1 uses a 6-pin electrical + mechanical quick-release
- Magazine holds 4 tools; tier-3 swap budget is ~4 seconds
- One arm may expose multiple bay types later (tight tools vs. coarse tools)
```

## Inter-region interfaces

Regions don't call each other's internals — they talk via:

- **The bus** (owned by core) — event/message passing between subsystems
- **composes_with** on manifests — explicit cross-region skill chains
- **Mount-bay handshake** — arm ↔ tool, standardized protocol

If a scaffolding lane needs a new cross-region interface, it raises it as
a PR comment for Goddard to adjudicate rather than inventing one
unilaterally.
