---
title: "CarVoice - AI Car Assistant"
date: 2026-09-14
author: ""
description: "Give your car's computer a voice: an OBD2 adapter that feeds your vehicle's diagnostics to Claude so you understand what's actually wrong before it costs you thousands."
tags: ["invention", "ai", "automotive", "design"]
---

## The Problem

Most car owners treat vehicle diagnostics as a black box. A warning light comes on. They panic, or they ignore it. A mechanic can tell them what's wrong, but the diagnosis itself costs money, and the owner has no way to independently verify it or track the story of their car over time.

Cars are the second-largest purchase most people make, and most owners are information-asymmetry victims: the mechanic knows what's wrong, the owner doesn't, and that gap breeds distrust on both sides.

---

## The Concept

CarVoice is a small OBD2 adapter that plugs into any car built 1996 or later. It reads the car's diagnostic stream continuously and pipes it — through the owner's own Claude API key — into plain-English answers: *Is this real? Should I worry? What's next?*

| Parameter | Spec |
|---|---|
| Form factor | Small OBD2 adapter (plug & play) |
| Connection | OBD2 port → WiFi/BLE → Cloud → Claude API → User Dashboard |
| User input | User's own Claude API key — they control their data |
| Price target | $79–129 hardware + freemium subscription |

The owner holds the keys, literally: their API key, their data, no proprietary firmware hacking, no dealership lock-in.

---

## Core Features (V1 Launch)

| Feature | Description |
|---|---|
| **OBD2 Data Collection** | Continuously reads car diagnostics — RPM, temps, pressures, error codes |
| **Maintenance Tracking** | User logs oil changes, tire rotations, repairs; CarVoice tracks them against mileage |
| **AI Diagnostics** | Claude analyzes sensor data + maintenance history and answers plain questions about what's going on |
| **Predictive Maintenance** | Patterns emerge over time — "your transmission fluid is degrading, change in 5k miles" |
| **Alert System** | Translates codes instead of causing panic — "P0300 = cylinder misfire, likely faulty spark plug, $40–200 fix" |
| **Simple Dashboard** | Car health score, next maintenance due, history, plain-English explanations |

### V2 (later)

- Multi-car / fleet support
- Mechanic reports (send your diagnosis to your mechanic)
- Resale value impact from maintenance history
- Cost projections for major repairs
- Community insights — compare your car to similar models

---

## Technical Stack

### Hardware
| Component | Spec |
|---|---|
| Base adapter | Cheap OBD2 Bluetooth/WiFi adapter (~$15 to manufacture) |
| Branded option | Case + WiFi module (~$30 total cost) |

### Software
| Layer | Choice |
|---|---|
| Backend | Python/Node.js API |
| Frontend | Simple web dashboard |
| Intelligence | Claude API (user's own key) |
| Database | Maintenance logs, error history, mileage |

### Architecture

OBD2 adapter → user's WiFi → CarVoice backend → Claude API → dashboard. The user's data flows through their own API key end to end — no proprietary firmware tuning required.

---

## Business Model

- **Hardware:** $79–129 per adapter, sold once, ~30% margin
- **Free tier:** basic diagnostics, error-code translations
- **Pro tier:** $9.99/month — predictive maintenance, full history, alerts

---

## Constraints

- No proprietary firmware tuning — standard OBD2 only
- No dealership lock-in — open ecosystem
- Works on any OBD2 car (1996+)
- Respects user privacy — their data, their API key

---

## MVP Roadmap

### Phase 1 — Prototype (2–3 weeks)
**Goal:** prove Claude can analyze real OBD2 data and make useful diagnoses.

- Python script reading OBD2 data from any cheap adapter
- Logs diagnostic data from real test drives
- Claude API pipeline analyzes the patterns
- Outputs actionable insights in plain English
- Validated on the Subaru — and by grandpa

### Phase 2 — Beta (4–6 weeks)
**Goal:** simple backend + dashboard for real users.

- Web dashboard for car health
- Maintenance log tracker
- Alert system for detected issues
- Test with 5–10 beta users

### Phase 3 — Product (Q3 2026)
**Goal:** branded hardware + polished software.

- Small plug-and-play device
- Production dashboard
- Subscription billing
- Market launch

---

## Success Metrics

- Claude catches a real car issue the OBD reader itself misses
- Grandpa validates that the AI's mechanical reasoning holds up
- The dashboard is simple enough for a non-technical person to use unassisted
- Predictive maintenance prevents at least one expensive repair
- Users say: *"My car finally makes sense"*

---

## What to Build First

Phase 1, concretely:

1. Grab a cheap OBD2 Bluetooth adapter and get raw PIDs streaming off the Subaru
2. Log a handful of real drives — cold start, highway, city stop-and-go
3. Build a small Claude API pipeline that takes the logged data + a maintenance history and answers plain questions about it
4. Compare Claude's read against what a real mechanic (and grandpa) says is going on
