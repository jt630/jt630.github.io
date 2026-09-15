---
title: "CarVoice - AI Car Assistant"
date: 2026-09-14
author: ""
description: "A personal, open-source project: read your own car's OBD2 diagnostics and have Claude explain them in plain English, using your own API key."
tags: ["invention", "ai", "automotive", "open-source"]
---

## The Problem

Most car owners treat vehicle diagnostics as a black box. A warning light comes on. They panic, or they ignore it. A mechanic can tell them what's wrong, but the diagnosis itself costs money, and the owner has no way to independently verify it or track the story of their car over time.

Cars are the second-largest purchase most people make, and most owners are information-asymmetry victims: the mechanic knows what's wrong, the owner doesn't, and that gap breeds distrust on both sides.

This project doesn't try to fix that industry-wide. It's a personal tool: read my own car's diagnostics, have Claude explain what they mean, check that against what my grandpa (and a real mechanic) says. If it's useful, the code's open — take it.

---

## The Concept

Plug a Bluetooth OBD2 adapter into a car built 1996 or later. A local script reads the diagnostic stream and sends it — through my own Claude API key — to plain-English answers: *Is this real? Should I worry? What's next?*

| Parameter | Spec |
|---|---|
| Hardware | Off-the-shelf Bluetooth OBD2 adapter (not custom hardware) |
| Connection | OBD2 port → laptop (Bluetooth) → Claude API → plain-English report |
| Intelligence | Claude API, my own key — no vendor sees the data or the AI bill |
| Constraint | Standard OBD2 only, works on any 1996+ car, no proprietary firmware |

No cloud backend, no dashboard-as-a-service, no company. Everything runs locally and the data stays in this repo.

---

## Planned Capabilities

| Feature | Description |
|---|---|
| **OBD2 Data Collection** | Reads car diagnostics during a drive — RPM, temps, speed, engine load, error codes |
| **Maintenance Tracking** | A YAML log of oil changes, tire rotations, repairs, tracked against mileage |
| **AI Diagnostics** | Claude reads sensor data + maintenance history and answers plain questions about what's going on |
| **Predictive Maintenance** | Once there's enough logged history — "your fuel trim is drifting, look at this before it throws a real code" |
| **Code Translation** | Turns a DTC into something useful — "P0300 = cylinder misfire, likely a spark plug or coil, common $40–200 fix" — instead of just a scary light |

Not planned: a hosted dashboard, a subscription, or hardware for sale. If a simple local dashboard turns out to be worth building later because I'm actually using this day to day, that's a "maybe," not a roadmap item.

---

## Technical Stack

- **Hardware:** off-the-shelf Bluetooth Classic OBD2 adapter (WiFi and BLE-only adapters ruled out — see Prior Art / build notes for why)
- **Logger:** a Python script (`python-obd`) that polls a fixed PID set and writes one drive's data to a local file
- **Diagnose pipeline:** a Python script that reads a drive log + the maintenance YAML and calls the Claude API directly
- **Storage:** plain YAML/JSONL files in this repo — no database, no server

---

## Prior Art

Before building this, I looked at what already exists. It's more crowded than it looks:

- **OBDAI**, **LAUNCH AIOBD**, and **MECH AI** all already ship "plug in an OBD2 adapter, get an AI explanation of your codes" as real commercial products today.
- **SPARQ Diagnostics** is a funded, press-covered startup with almost this exact pitch — including marketing language uncomfortably close to "give your car a voice."
- **[open-mechanic](https://github.com/speed785/open-mechanic)** (GitHub, MIT-licensed, ~33 stars) is the closest thing to prior art for the specific mechanism here: `python-obd` + a user's own Claude API key, no vendor-hosted backend. It's a hobby project with no product around it — which is basically what this is too.

None of the commercial products let you bring your own API key — they all host the AI themselves behind a subscription. That's a real, unclaimed gap, but I'm not chasing it as a business. The honest reason to build this anyway: it's genuinely useful for one car and one household, the code is worth having whether or not it's "differentiated," and there's no reason not to open-source it once it exists.

---

## What to Build First

The whole plan, realistically:

1. Grab a Bluetooth OBD2 adapter and get raw PIDs streaming off the Subaru
2. Log a handful of real drives — cold start, highway, city stop-and-go
3. Build a small Claude API pipeline that takes the logged data + maintenance history and answers plain questions about it
4. Compare Claude's read against what a real mechanic (and grandpa) says is going on

That's it. No phase 2 launch, no beta users, no billing. Full build plan and session-by-session notes live in `CARVOICE.md` at the repo root, alongside the research that led to the choices above.

---

## Success Metrics

- Claude catches a real car issue the OBD reader itself misses
- Grandpa validates that the AI's mechanical reasoning holds up
- It's simple enough that I actually keep using it after the novelty wears off
- I can say: *"My car finally makes sense"*
