---
title: "Robot Organs"
date: 2026-04-19
description: "Theorizing robot design — organs as skills, physical + logical, with a Goddard brain that reads YAML manifests"
draft: false
---

Robots are the most important design project to work on right now. Product design,
program design, workflow design — robots are where all three converge and where
the future actually gets paved. This page is the running theory doc.

**Brain before body.** It's strange that we built AI before we built useful
robots, but it actually tracks: the brain has to exist before the form around
it makes sense. You design the organism mind-first, then grow the body that
fits it. Agentic AI is the nervous system. Hardware is scaffolding we hang
on it.

So we build **the brain first** — a skill library the robot can call into —
and the chassis comes after.

## Thesis

**A robot is a hardware interface over an agentic AI skill library.**

Every skill an agent has in software (search, summarize, fetch, write) has a
physical analog in a robot: locomote, grasp, fabricate, sense. The skills folder
pattern — discrete, callable, documented — is the same pattern. Robots just
give skills a body.

So: **organs = skills**. Each organ has
- a **physical design** (hardware that executes it)
- a **logical design** (the skill manifest that governs it, matching the agentic skill spec)

## Meet Goddard

The robot is **Goddard.** One name, one character, one assistant.

Internally Goddard has three layers, but only one of them talks to me:

1. **Curator (me)** — taste, context, direction. I say what matters.
2. **Goddard** — the whole robot. Reads my intent, plans, calls skills, acts.
   Has an internal planner (the thing other stacks call "Jarvis") and an
   internal reflex loop (balance, obstacle avoid, battery, heartbeat) — but
   they're not separate personalities. They're just Goddard's subsystems.
3. **The skill library** — the brain content. YAML manifests that describe
   every organ Goddard can invoke. This is the artifact we build first.

Collapsing Jarvis into Goddard matters: one character, one voice, one body.
The planner is a component, not a co-star.

## The brain: a YAML skill library

The skill library lives in `data/robots/`. Every organ is a YAML manifest.
Goddard reads the registry at boot and knows what it can do.

The manifest schema mirrors the Claude Code skill card pattern (`id`,
`description` with trigger rules, hardware analog of `allowed-tools`) and
adds hardware-specific fields so the same file drives both AI dispatch and
physical execution:

```yaml
id: 3d_printer_arm
name: 3D Printer Arm
group: fabrication

description: |
  Extrudes thermoplastic filament into arbitrary 3D shapes.
  TRIGGER when the robot needs a small rigid object (<15x15x20cm, <2kg)
  that isn't on hand and can be printed in under ~10 min.
  SKIP for metal, food-contact, or load-bearing parts.

hardware:
  slot: arm-primary
  power_w: 45
  deploy_time_ms: 1200
  consumables: [pla_filament]
  envelope_cm: [15, 15, 20]

preconditions:
  - battery_pct >= 20
  - ambient_temp_c: {min: 15, max: 35}

inputs:
  model_stl: {type: path, required: true}
  infill_pct: {type: number, default: 20}

composes_with:
  - heat_mold
  - vacuum
  - lighter

safety:
  - no flammables within 30cm during 60s cooldown
```

The `description` block is a routing prompt — Goddard reads it to decide
when to call the skill, exactly the way an LLM reads a skill card.

The `composes_with` list is the superpower: skills reference other skills
by id, and a composed skill (see `heat_mold.yaml`) is just a manifest that
runs a sequence. No bespoke code per combination.

### Current registry

- **`skill_groups.yaml`** — the organ taxonomy (movement, manipulation,
  fabrication, sensing, sequence_reading, power, communication, gadgets)
- **`sci_fi_catalog.yaml`** — canonical sci-fi robots tagged by skill group,
  used to find gaps in the design space
- **`organs/3d_printer_arm.yaml`** — on-demand fabrication
- **`organs/lighter.yaml`** — flick-out flame gadget
- **`organs/vacuum.yaml`** — retractable suction gadget
- **`organs/heat_mold.yaml`** — composed skill (lighter + printer) that
  reshapes printed parts after extrusion

### Organ groups

- **movement** — walking legs, wheeled legs, climbing legs, hovering, swimming
- **manipulation** — grasp, press, twist, fine-motor
- **fabrication** — 3D print, weld, cut, assemble, heat+mold
- **sensing** — vision, audio, thermal, chemical, proprioception
- **sequence_reading** — the spinal cord. Dispatch + planner + skill registry.
  The callable library itself is here.
- **power** — charge, scavenge, solar, battery
- **communication** — speak, signal, network
- **gadgets** — concealed single-purpose tools that flick out (Q-branch layer)

## Sci-fi catalog — finding gaps

Tagged canon lives in `sci_fi_catalog.yaml`. Early observations:

- Very few canonical robots treat **fabrication** as a primary organ.
  R2-D2 and Wall-E gesture at it; nobody lives there. Our spy-cat with the
  3D-printer arm + heat-mold skill is in open territory.
- The **gadgets** group is dominated by R2-D2. Huge design space wide open.
- **Soft-body** (Baymax) is an underused chassis. Worth borrowing from.

## Form factor (chassis comes later)

Sketch for when the brain is ready:

Many-legged, asymmetric locomotion. One leg walks, one leg wheels. Spider-scorpion
chassis, low and stable, can climb. Abstract the vibe toward **cat, not dog.**
Independent, curious, doesn't need constant approval.

**Style: James Bond gadget cat.** Q-branch, not Boston Dynamics. Organs as
concealed gadgets, not visible appendages. Every tool lives flush with the
body until called.

Starter gadget loadout:
- Flick-out **lighter** — localized controlled flame
- Retractable **vacuum** — cleanup, sampling, adhesion
- **3D printer arm** — extrude polymer on demand
- **Heat + mold** — composes lighter + printer to reshape extrusions into
  forms the printer alone can't make

## Open questions

- What's the minimum viable organ set for a useful house robot?
- How does the composed-skill runtime actually execute a manifest? Sequential
  by default with explicit handoff steps? A DAG?
- Is the reflex loop inside Goddard a skill group (`movement` + `power` +
  `sensing` owned_by: goddard) or a separate runtime that sits under the
  skill registry?
- How do I version hardware the way I version skills? Swappable attachments
  that ship their own manifest?
- What's the smallest end-to-end demo? Maybe: Goddard reads one manifest,
  plans one call, fires one actuator. Everything after that is scale.

## Why this matters

I'm learning to use AI tools by building real things. Robot design is the
long-arc version of the same workflow: specs, skill libraries, tool-calling
agents, human-in-the-loop curation. If I can design Goddard's brain as a
YAML skill library that an AI operates, I've internalized the agentic
pattern at a level deeper than any chatbot project can teach.

Brain first. Library first. The body fits itself around a mind that already
knows what to do.
