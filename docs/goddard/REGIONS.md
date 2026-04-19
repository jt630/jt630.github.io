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
| **skin** | chassis panels, embedded gadgets (vacuum, sensors), chassis panels | `data/robots/organs/skin_*.yaml` |

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

The arm spans from the shoulder joint through the wrist to the active-tool
slot. Arms are the primary manipulation region — they carry and deploy tools
for fabrication, fetching, and assisted living tasks.

Interfaces with:
- thighs / core — power handoff at the shoulder
- hands — end-effector handoff at the wrist interface
- skin — no direct interface; skin-mounted gadgets are separate
- brain — accepts manipulation intents via the bus

Key decisions:
- Active arm tool is the skill-directory tier-2 context (see SKILL-DIRECTORY.md)
- Skill availability tiers 3-4 are determined by setup time, not physical magazine
- One arm may carry multiple tool profiles later (fine manipulation vs. power grip)
```

## Inter-region interfaces

Regions don't call each other's internals — they talk via:

- **The bus** (owned by core) — event/message passing between subsystems
- **composes_with** on manifests — explicit cross-region skill chains
- **Mount-bay handshake** — arm ↔ tool, standardized protocol

If a scaffolding lane needs a new cross-region interface, it raises it as
a PR comment for Goddard to adjudicate rather than inventing one
unilaterally.
