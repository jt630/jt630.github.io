---
title: "Fermentation Press"
date: 2026-04-15
author: ""
description: "Design spec for a home fermentation vessel combining a French press plunger with an integrated one-way airlock."
tags: ["invention", "fermentation", "design"]
---

## The Problem

Home lacto-fermentation (sauerkraut, kimchi, pickles, hot sauce) has two persistent failure modes:

1. **Floating solids** — food rises above the brine and molds within days
2. **Oxygen intrusion** — air exposure causes spoilage; the vessel needs venting for CO₂ without letting O₂ back in

These are solved separately today. Fermenters use DIY weights (rocks, zip-lock bags full of water, glass discs) and bolt-on airlocks as two separate components. There is no integrated solution at meaningful scale.

---

## The Concept

A single vessel combining:

- **French press plunger** — a rod with a mesh plate at the bottom, pushed down through the lid to submerge solids, locked at depth
- **One-way valve** in the lid — CO₂ escapes, O₂ cannot enter

The plunger rod passes through a sealed grommet in the lid. The lid is airtight except for the valve. You push the plunger down until solids are submerged, twist to lock, and walk away.

---

## Specs

### Vessel
| Parameter | Spec |
|---|---|
| Capacity | 1 qt / 0.5 gal / 1 gal (three SKUs) |
| Material | Borosilicate glass |
| Mouth diameter | Wide mouth, ~86 mm (standard mason) |
| Base | Flat, stable |

### Lid Assembly
| Parameter | Spec |
|---|---|
| Material | Food-grade PP or 304 stainless |
| Seal | Silicone gasket, compression fit |
| Plunger grommet | Silicone, airtight around rod |
| Valve type | Silicone one-way flap (waterless) |
| Valve function | Opens at ~0.5 psi CO₂, seals on equalization |

### Plunger
| Parameter | Spec |
|---|---|
| Rod | 304 stainless, 8 mm diameter |
| Plate | 316 stainless mesh, ~80% open area |
| Lock mechanism | Bayonet twist — 90° locks at current depth |
| Lock positions | Continuous (any depth), not stepped |
| Plate diameter | 5 mm clearance from vessel walls |
| Handle | T-bar grip, sits above lid when locked |

### Operating Range
| Parameter | Spec |
|---|---|
| Max fill height | Lid gasket line |
| Min working depth | 2 cm below brine surface |
| Temperature | 35°F – 120°F (fridge to room temp) |
| Brine compatibility | Any salt concentration, vinegar, any pH |

---

## Prior Art

The core combination of **press + airlock** exists in [US20140116271](https://patents.google.com/patent/US20140116271) (Karen Wang Diggs, filed 2012, published 2014). That design uses:

- A compression **spring** (auto-press, fixed force) rather than a manual locking plunger
- A **water moat** airlock rather than a silicone one-way valve
- Mason jar scale only

Other products on the market:

- **Masontops Pickle Pipe** — airlock only, no submersion
- **Trellis + Co. PickleHelix** — spring-coil weight + waterless airlock lid, mason jar scale
- **Pickle Pusher** — combined weight-replacement + airlock, mason jar scale
- **North Mountain Supply kit** — spring weight + separate 2-piece airlock, mason jar scale

### Where novelty may exist

| Feature | Prior art | This design |
|---|---|---|
| Press mechanism | Spring (auto, fixed force) | Manual plunger, locks at depth |
| User control | None — spring decides | Full — set depth, twist to lock |
| Scale | Mason jar (half-gallon max) | Glass vessel up to 1 gallon |
| Airlock | Water moat or silicone flap | Silicone one-way flap |
| UX model | Novel mechanism | Familiar French press interaction |

The **locking manual plunger** through a sealed, valved lid is the potentially patentable claim. A spring presses; a plunger locks. That distinction drives predictable, user-controlled submersion depth — which matters for recipes with specific headspace requirements.

---

## Open Design Questions

- **Rod seal longevity** — silicone grommet around a moving rod will wear; what's the service life?
- **Disassembly for cleaning** — all contact surfaces must be reachable with a brush
- **Vessel material** — glass is ideal (inert, visible) but makes larger sizes heavy; PETG or Tritan for 1-gallon?
- **Pressure safety** — at what CO₂ pressure does the valve open? Needs calibration for hot sauce vs. sauerkraut (different gas rates)
- **Lock under pressure** — if CO₂ builds, will it push the plunger up? Rod needs to resist that force at the grommet

---

## What to Build First

A prototype using an existing wide-mouth jar:

1. 3D-print a lid with grommet channel and valve port
2. Cut a stainless mesh disc, press-fit to a stainless rod
3. Test the bayonet lock geometry in PLA first
4. Validate that silicone grommet holds seal through a full ferment (2–4 weeks)
