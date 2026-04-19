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

## Body regions (the ISS bays)

Eight regions. Every organ lives in exactly one. Parallel sessions own
one region each and can't collide.

- **brain** — compute, skill registry, planner, memory, intent queue
- **core** — power distribution, reflex loop, safety monitor, bus
- **guts** — consumables tanks, waste, fabrication support
- **arm** — shoulder-to-wrist manipulator, mount-bays for tools
- **hands** — end-effectors (paw, pincer, fine tip), tool change
- **legs** — walking, wheeled, climbing locomotion
- **thighs** — leg attachment, high-torque joints, power routing
- **skin** — chassis panels, gadget bays, embedded sensors

## The CD-changer — mount-bays, magazines, and call priority

Arms are expensive. We can't give every arm a dedicated copy of every
fabrication or gadget tool. So arms share hardware via a **CD-changer
pattern**, borrowed from CNC machines and 90s car stereos.

- **Mount-bay** — standardized physical + electrical interface on an arm
  (e.g. `arm-mount-v1`). The ISS docking port analog.
- **Tool** — any organ whose `requires_mount` matches a mount-bay. Tools
  live idle in storage and swap into the active slot on demand.
- **Magazine** — the arm's local tool carousel. Fast swap.
- **Storage budget** — the "one-car garage." The whole robot has a
  bounded `storage_volume_cm3` across idle tools. Hard cap.

But the CD-changer isn't just a physical mechanic — it's a **call-priority
system.** At skill-call time Goddard's planner ranks candidates by how
expensive they are to reach:

| Tier | State | Access cost |
|---|---|---|
| 1. **Embedded** | Fixed on skin (lighter, vacuum) | 0 — always ready |
| 2. **Mounted (active)** | Already docked in an arm slot | 0 — already active |
| 3. **Magazine** | On-arm carousel, needs tool_change | a few seconds |
| 4. **Storage** | In the garage, retrieve + change | longer, may be declined |

On-body skills (tiers 1-2) are top priority. Storage-accessible skills are
lower priority because they cost time to reach. This lets us carry a HUGE
library of skills — only a few stay resident; the rest live in the garage
until called. Full spec in `data/robots/CD-CHANGER.md`.

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
  storage_volume_cm3: 1800         # "garage space" when idle
  envelope_cm: [15, 15, 20]

requires_mount: arm-mount-v1       # docks into any arm with this bay
tool_change_time_s: 4

preconditions: [...]
inputs: { ... }
outputs: { ... }
composes_with: [heat_mold, skin_vacuum, skin_lighter]
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
bespoke code per combination. See `heat_mold.yaml` for the canonical
composed example.

### Current registry

- **`GODDARD.md`** (repo root) — the agent identity spec
- **`data/robots/skill_groups.yaml`** — functional taxonomy
- **`data/robots/sci_fi_catalog.yaml`** — canon robots tagged
- **`data/robots/organs/arm_3d_printer.yaml`** — canonical schema example
- **`data/robots/organs/skin_lighter.yaml`** — flick-out flame
- **`data/robots/organs/skin_vacuum.yaml`** — retractable suction
- **`data/robots/organs/heat_mold.yaml`** — composed (lighter + printer)

## Sci-fi catalog — finding gaps

Tagged canon lives in `sci_fi_catalog.yaml`. Early observations:

- Very few canonical robots treat **fabrication** as a primary organ.
  R2-D2 and Wall-E gesture at it; nobody lives there. Goddard's
  printer arm + heat-mold occupies open territory.
- **Gadgets** is dominated by R2-D2. Huge design space wide open.
- **Soft-body** (Baymax) is an underused chassis. Worth borrowing from.

## Form factor (chassis comes later)

Many-legged, asymmetric locomotion. One leg walks, one leg wheels.
Spider-scorpion chassis, low and stable, can climb. Abstract toward
**cat, not dog.** Independent, curious, doesn't need constant approval.

**Style: James Bond gadget cat.** Q-branch, not Boston Dynamics. Organs
as concealed gadgets. Every tool lives flush with the body until called.

Starter loadout:
- Flick-out **lighter** in skin
- Retractable **vacuum** in skin
- **3D printer** as an arm-mounted tool
- **Heat + mold** composed skill
- Magazine of additional arm tools (pincer, fine-tip, laser pointer,
  grappling hook — TBD by the arm scaffolding lane)

## Open questions

- Minimum viable organ set for a useful house robot?
- How does the composed-skill runtime execute a manifest — sequential with
  handoff steps, a DAG, or an LLM-planned chain?
- Is the reflex loop a skill group (`movement` + `power` + `sensing` all
  `owned_by: goddard`) or a separate runtime beneath the registry?
- How is hardware versioned — swappable attachments shipping their own
  manifest? Who adjudicates mount-bay compatibility?
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
