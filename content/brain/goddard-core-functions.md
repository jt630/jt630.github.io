---
title: "Goddard — Core Functions"
date: 2026-04-19
description: "Wave 0 decisions: what Goddard's core actually does — reflex loop, safety monitor, skill registry"
draft: false
---

## Mission

**Help elderly people live independently and safely at home.** This is the
non-negotiable priority above every other design goal. Hardware choices,
voice, form factor, skill prioritization, safety rules — all of it flows
from this mission. When two designs are otherwise equal, pick the one that
a 75-year-old living alone would trust more.

## Reflex loop

Goddard runs two loops simultaneously:

**10 Hz main loop** — proprioception, battery and thermal monitoring,
safety flag evaluation, intent queue drain, and firing of `owned_by:
goddard` skills (movement, power, sensing). This is the heartbeat of the
robot. At each tick it checks: is anything wrong? is there an intent to
act on? do the safety flags permit acting?

**100 Hz balance sub-loop** — dedicated to leg control. Faster than the
main loop because stability can't wait. The sub-loop feeds into the main
loop's state but runs on its own cadence.

**Target hardware: Raspberry Pi 5 or Jetson Orin Nano class SBC.** These
numbers are achievable on real hardware today. 10 Hz main and 100 Hz
balance sub-loop are both well within reach. We're not speculating about
future silicon — we're designing to what exists.

## Safety monitor

The safety monitor lives in core and runs on every reflex tick. It has
three powers:

1. **Pre-call precondition check.** Before any skill fires, the safety
   monitor evaluates the skill's `preconditions:` block. If a condition
   fails, the call is refused and Goddard reports why. No exceptions.

2. **Mid-call interrupt.** While a skill is running, the safety monitor
   watches for flag changes. If a flag trips (obstacle appears, thermal
   limit exceeded, voice command received), the monitor aborts the running
   skill and transitions to the safe state.

3. **Hard stop.** Emergency halt: Goddard drops to safe pose immediately.
   Triggered by a fall-detection event, a panic button, or an unrecoverable
   safety flag. Motion stops before anything else.

**Elderly-care rules (non-negotiable):**
- No fast motion near humans. Speed caps when any person is within range.
- Thermal limits enforced. No surface accessible to touch may exceed safe
  skin-contact temperature.
- Voice-interruptible always. Any spoken command can halt or redirect
  Goddard mid-action. The person is always in control.
- Obstacle-aware for walkers and canes. Goddard's path planning must
  account for mobility aids — not just the person, but their equipment.
- Never expose hot surfaces within human reach. The 3D printer nozzle
  cools before any proximate motion. No open flame. No exposed heating
  elements.

## Skill registry

At boot, Goddard file-scans `data/robots/organs/` and builds the registry
from every YAML manifest it finds. The registry is the planner's menu of
callable skills.

**Hot-reload is a v2 feature.** We're not implementing it now. But the
schema is designed to tolerate it: every manifest has a stable `id` and
will eventually carry a `version` field. Adding hot-reload later doesn't
require changing the schema, just adding a file-watcher.

**The registry is just a directory of YAML manifests.** No database. No
service. A file-scan at boot, loaded into memory. Simple enough to reason
about, robust enough to ship.

The skill-directory priority tiers (see `docs/goddard/SKILL-DIRECTORY.md`)
give the planner an ordering hint — embedded skills first, stored tools
last — but the registry itself doesn't enforce tiers. That's the planner's
job.

## Owned-by boundaries

Every manifest declares `owned_by: goddard` or `owned_by: jarvis`.

- **goddard (reflex)** owns: `movement`, `power`, `sensing`. These run on
  the 10 Hz main loop and 100 Hz balance sub-loop. The reflex loop fires
  them directly without planner mediation.

- **jarvis (planner)** owns: `manipulation`, `fabrication`,
  `communication`, `gadgets`, `sequence_reading`. These are intent-driven
  and mediated through the planner's intent queue.

"Jarvis" is a subsystem name, not a separate persona. Internally, there is
no "Jarvis" character — it's a label for the planner subsystem of Goddard.
One robot, one voice. The distinction is purely architectural: which loop
fires the skill.

## Aesthetic

**90s translucent plastic.** iMac G3, Gameboy Color, Tamagotchi. Colorful,
see-through, approachable, friendly to anyone who grew up before all tech
went matte-black. Nothing about Goddard looks tactical, military, or
intimidating.

This is not incidental. The chassis aesthetic is part of the elderly-care
mission. A robot that looks like a weapon — or a spider, or a spy device —
has failed before it enters the room. Goddard should look like something
a person would be glad to see when they wake up alone.
