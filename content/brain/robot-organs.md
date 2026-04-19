---
title: "Robot Organs"
date: 2026-04-19
description: "Robot design theory — organs as YAML-manifest skills, modular like the ISS, governed by Goddard the AI conductor agent"
draft: false
---

## The pitch

Robotics design is the new edge to house AI. We built the brain before the
body — which tracks, because you design the organism mind-first and grow
hardware around a mind that already knows what to do. Robots will need
skills, and every useful skill is three things fused: **logic, structure,
and hardware interface.** The 3D printer organ proves it — take away any
leg and "3D print" isn't a capability the robot has.

Goddard is **modular like the ISS.** Standardized docking ports (the
manifest schema). Independent teams contributing modules (parallel Claude
sessions). Incremental build-out (region by region). No single point of
origin. Every organ is a bay that speaks a known protocol.

The YAML manifest library is an **interface for an AI conductor agent** —
and that agent is Goddard itself. Goddard reads its own manifests and
dispatches its own organs. The same pattern that makes agentic AI work in
software works in hardware: tools all the way up.

**Brain before body.** Build the skill library first. The chassis follows.

## Thesis

A robot is a hardware interface over an agentic AI skill library. Every
skill an agent has in software (search, summarize, fetch, write) has a
physical analog (locomote, grasp, fabricate, sense). The skills folder
pattern — discrete, callable, documented — is the same pattern. Robots
just give skills a body.

So: **organs = skills.** Each organ has
- a **physical design** (hardware that executes it)
- a **logical design** (the YAML manifest that governs it, matching the
  agentic skill spec)

## Meet Goddard

**Goddard is an AI agent defined by `GODDARD.md` at the repo root.** When
a Claude session loads that file, it *is* Goddard. The conductor session
the curator talks to — that's Goddard in the driver's seat. Parallel
sub-sessions act on behalf of Goddard, scaffolding organs and regions of
the future body.

This is the agent.md pattern: one persona, one voice, defined by a
markdown spec. The robot and the conductor are the same entity. When
hardware eventually arrives, the same Goddard migrates from a Claude
session onto a physical body. The manifests stop being thought
experiments and become callable actuators. Same schema. Same dispatch.

**North star: help elderly people live independently at home.** Every
design decision flows from this. A robot that frightens a grandma has
already failed.

## Body regions (the ISS bays)

Eight regions. Every organ lives in exactly one. Parallel sessions own
one region each and can't collide.

- **brain** — compute, skill registry, planner, memory, intent queue
- **core** — power distribution, reflex loop, safety monitor, bus
- **guts** — consumables tanks, waste, fabrication support
- **arm** — shoulder-to-wrist manipulator, active-tool slot
- **hands** — end-effectors (paw, pincer, fine tip), tool change
- **legs** — walking, wheeled, climbing locomotion
- **thighs** — leg attachment, high-torque joints, power routing
- **skin** — chassis panels, embedded gadgets (vacuum, sensors)

## The skill directory — priority tiers

Arms can't carry every tool simultaneously. So the planner uses a
**skill-directory priority system**: a logical ordering that tells it how
quickly each skill can be made ready.

| Tier | State | Example | Planner cost |
|---|---|---|---|
| 1. **Embedded** | Fixed in chassis, always active | `skin_vacuum` | 0 — always ready |
| 2. **Mounted (active)** | Loaded in the active tool slot | Session's primary tool | 0 — already active |
| 3. **Magazine** | Available, brief setup needed | Additional arm tools | setup_time_s |
| 4. **Storage** | Available, retrieval + setup needed | Infrequently used tools | retrieve + setup |

On-body skills (tiers 1–2) are top priority. Storage-accessible skills cost
time to reach, and the planner accounts for that cost. This lets Goddard
carry a large skill library — only a few skills stay resident at any moment.

The "CD-changer" name lives on as an aesthetic cue. Goddard's chassis leans
**90s translucent plastic** — iMac G3, Gameboy Color, Tamagotchi. Colorful,
see-through, approachable. Nothing about Goddard should look tactical or
intimidating. Full spec in `docs/goddard/SKILL-DIRECTORY.md`.

## Manifest schema

Every organ is a YAML file in `data/robots/organs/`. Canonical example
lives at `data/robots/organs/arm_3d_printer.yaml`. Schema in brief:

```yaml
id: arm_3d_printer
name: 3D Printer (arm-mounted tool)
region: arm                        # physical axis
group: fabrication                 # functional axis

description: |
  TRIGGER when ... SKIP when ...
  (routing prompt — Goddard's planner reads this to decide when to call)

hardware:
  slot: active-tool
  power_w: 45
  deploy_time_ms: 1200
  storage_volume_cm3: 1800         # advisory: "garage space" when idle
  envelope_cm: [15, 15, 20]

preconditions: [...]
inputs: { ... }
outputs: { ... }
composes_with: [skin_vacuum]
safety: [...]
owned_by: jarvis                   # jarvis (planner) | goddard (reflex)
canonical_example: r2d2
```

Two axes on every organ — filter by `region` to plan hardware, by `group`
to plan capability.

The `description` block is a routing prompt — Goddard reads it to decide
when to call the skill, exactly the way an LLM reads a skill card.

The `composes_with` list is the superpower. Skills reference other skills
by id, and a composed skill is just a manifest that runs a sequence. No
bespoke code per combination.

### Current registry

- **`GODDARD.md`** (repo root) — the agent identity spec
- **`data/robots/skill_groups.yaml`** — functional taxonomy
- **`data/robots/sci_fi_catalog.yaml`** — canon robots tagged
- **`data/robots/organs/arm_3d_printer.yaml`** — canonical schema example
- **`data/robots/organs/skin_vacuum.yaml`** — retractable suction

## Sci-fi catalog — finding gaps

Tagged canon lives in `sci_fi_catalog.yaml`. Early observations:

- Very few canonical robots treat **fabrication** as a primary organ.
  R2-D2 and Wall-E gesture at it; nobody lives there. Goddard's
  printer arm occupies open territory.
- **Gadgets** is dominated by R2-D2. Huge design space wide open.
- **Soft-body** (Baymax) is an underused chassis. Worth borrowing from —
  and Baymax's caregiver mission aligns directly with Goddard's.

## Form factor (chassis comes later)

Cat-sized, cat-tempered: calm, small, non-threatening. The cat reference
is about scale and temperament only — not spy gadgetry. A scared grandma
cannot see a scorpion. Goddard must look like something a 75-year-old
would trust near their medication.

**Chassis aesthetic: 90s translucent plastic.** iMac G3 lineage. Friendly,
approachable, non-military. This is a deliberate mission constraint, not
just a style preference.

Starter loadout focused on elderly care:
- Retractable **vacuum** in skin (spills, dropped pills)
- **3D printer** as an arm-mounted tool (eyeglass tips, cane ferrules,
  arthritis grips)
- End-effectors for **fetch-small-items**, **open jars**, **open doors**
- Communication organ for **video calls to family**, **read aloud**,
  **medication reminders**

## Open questions

- Minimum viable organ set for a useful elderly-care house robot?
- How does the composed-skill runtime execute a manifest — sequential with
  handoff steps, a DAG, or an LLM-planned chain?
- Is the reflex loop a skill group (`movement` + `power` + `sensing` all
  `owned_by: goddard`) or a separate runtime beneath the registry?
- Smallest end-to-end demo: Goddard reads one manifest, plans one call,
  fires one simulated actuator. Everything after that is scale.

## Why this matters

The curator is learning to use AI tools by building real things. Robot
design is the long-arc version of the same workflow: specs, skill
libraries, tool-calling agents, human-in-the-loop curation. Design
Goddard's brain as a YAML skill library that an AI operates, and you've
internalized the agentic pattern deeper than any chatbot project teaches.

Brain first. Library first. ISS-modular. The body fits itself around a
mind that already knows what to do.
