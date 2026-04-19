---
title: "Robot Organs"
date: 2026-04-19
description: "Theorizing robot design — organs as skills, physical + logical, with a Jarvis/Goddard control stack"
draft: false
---

Robots are the most important design project to work on right now. Product design,
program design, workflow design — robots are where all three converge and where
the future actually gets paved. This page is the running theory doc.

## Thesis

**A robot is a hardware interface over an agentic AI skill library.**

Every skill an agent has in software (search, summarize, fetch, write) has a
physical analog in a robot: locomote, grasp, fabricate, sense. The skills folder
pattern — discrete, callable, documented — is the same pattern. Robots just
give skills a body.

So: **organs = skills**. Each organ has
- a **physical design** (the hardware that executes it)
- a **logical design** (the skill that governs it, matching the agentic skill spec)

## The control stack

Three layers, borrowed from how I already work with AI:

1. **Curator (me)** — taste, context, direction. The operator that decides what
   matters. Not replaceable.
2. **Jarvis** — the tool-calling LLM. Receives my intent, plans, calls skills,
   reports back. This is the conversational surface.
3. **Goddard** — the basic cycling functionality. Heartbeat, balance, obstacle
   avoidance, battery management. Always running, never asks permission. This
   is the reflex / autonomic layer.

Jarvis plans. Goddard keeps the body alive. I decide what's worth doing.

## Skill groups (organ taxonomy)

Skills cluster by function. First pass:

- **Movement** — walking legs, wheeled legs, climbing legs, hovering, swimming
- **Manipulation** — grasp, press, twist, fine-motor
- **Fabrication** — 3D print, weld, cut, assemble
- **Sensing** — vision, audio, thermal, chemical, proprioception
- **Sequence reading** — the spinal cord. Main skills folder with callable
  skills that fit certain attachments, layouts, and supplies. This is where
  skill dispatch lives.
- **Power** — charge, scavenge, solar
- **Communication** — speak, signal, network

Each group is a folder. Each skill inside is a callable unit with hardware
requirements declared up front (like a skill's `allowed-tools`, but for
physical attachments).

## Form factor

Starting sketch: **many-legged, asymmetric locomotion.** One leg walks, one
leg wheels. Maybe four of each. Spider-scorpion chassis so the body is low,
stable, and can climb. Arms are separate — at least one arm is a 3D printer
so the robot can summon physical objects on demand.

Abstract the vibe toward **cat, not dog.** Independent, curious, doesn't need
constant approval. Goddard (Jimmy Neutron) is the reference point but cat-coded.

## Sci-fi assistant catalog

To design well I need to know the canon. Pull the reference robots, tag each
one by skills, see what clusters.

*TODO: build this table. Candidates to start:*

- Goddard (Jimmy Neutron) — loyalty, companion, compact utility
- Jarvis (Iron Man) — tool-caller, ambient assistant, no body
- R2-D2 — fabrication, hacking, sequence reading
- BB-8 — rolling locomotion, projection
- Wall-E — manipulation, scavenging, solo autonomy
- Baymax — sensing (medical), soft-body, single-purpose
- TARS / CASE (Interstellar) — modular locomotion, humor parameter
- EVE (Wall-E) — flight, sensing, fabrication-adjacent
- The Iron Giant — scale, defense, self-reassembly
- Data (Star Trek) — general intelligence, humanoid
- HK-47 (KOTOR) — combat, personality
- Chappie — learning, street-level
- Astro Boy — flight, strength, emotional range

Next pass: build the tag matrix. Which skills show up most? Which combos haven't
been tried?

## Open questions

- What's the minimum viable organ set for a useful house robot?
- How does a skill declare its hardware requirements? (Like a manifest — "needs
  arm-slot-A, power > 20W, clearance 30cm")
- Is Goddard one skill or a supervisor process that calls many?
- How do I version hardware the way I version code? Swappable attachments that
  declare their own capability?
- What does the "skills folder" actually look like on the robot? A literal
  filesystem? A capability registry? Both?

## Why this matters

I'm learning to use AI tools by building real things. Robot design is the
long-arc version of the same workflow: specs, skill libraries, tool-calling
agents, human-in-the-loop curation. If I can design a robot's organ stack,
I've internalized the agentic pattern at a level deeper than any chatbot
project can teach.

This is how we get from here to there — with this and that, and a clear map
of how the pieces compose.
