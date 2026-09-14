# CarVoice — Project Plan

## Summary

CarVoice is an OBD2 adapter + Claude pipeline that turns raw car diagnostics into
plain-English answers: *is this real, should I worry, what's next.*

This file is the internal build/architecture doc — read it before any CarVoice
session. For the pitch and full feature spec, see
[`content/gadgets/carvoice-ai-assistant.md`](content/gadgets/carvoice-ai-assistant.md).

Registries: `data/carvoice/vehicles.yaml`, `data/carvoice/maintenance_log.yaml`

## Status

**Phase 1 (Prototype) — not started.** No OBD2 hardware acquired yet. No vehicle
registered. Nothing in this repo touches a real car yet.

---

## Architecture

Phase 1 is entirely local — no backend, no dashboard, just a logger + a Claude call:

```
OBD2 adapter → laptop (BLE/WiFi) → obd2_logger.py → drive log (.jsonl)
                                                          ↓
                              maintenance_log.yaml → diagnose.py → Claude API → plain-English report
```

The user's own Claude API key does the analysis. No proprietary firmware access,
no cloud backend required to prove the concept — that's Phase 2.

---

## Data Files

### `data/carvoice/vehicles.yaml`
Registry, one entry per tracked vehicle. Schema and template are in the file header.

### `data/carvoice/maintenance_log.yaml`
Maintenance history, one entry per service event, keyed by `vehicle_id`. This is
the ground truth the diagnose pipeline reads alongside live sensor data — a
misfire code reads differently if the plugs were just changed vs. 60k miles ago.

### `data/carvoice/drives/{vehicle_id}_{YYYYMMDD}.jsonl` *(to be built)*
Raw OBD2 PID samples from one drive session, written by the logger script. One
JSON object per line: timestamp + PID readings (RPM, coolant temp, speed, engine
load, fuel level, active DTCs).

### `data/carvoice/reports/{vehicle_id}_{YYYYMMDD}.md` *(to be built)*
Output of the diagnose pipeline — the plain-English report for one drive log.

---

## Key Files

- `CARVOICE.md` — this file
- `data/carvoice/vehicles.yaml` — vehicle registry
- `data/carvoice/maintenance_log.yaml` — maintenance history
- `data/carvoice/drives/` — raw OBD2 session logs *(to be built)*
- `data/carvoice/reports/` — generated diagnosis reports *(to be built)*
- `scripts/carvoice/obd2_logger.py` — reads live OBD2 PIDs, writes drive logs *(to be built)*
- `scripts/carvoice/diagnose.py` — drive log + maintenance history → Claude → plain-English report *(to be built)*
- `content/gadgets/carvoice-ai-assistant.md` — public pitch/spec post

---

## Build Plan

### Session 1: Register the vehicle + OBD2 logger

**Goal:** get real PID data off a car onto disk.

**Context for Sonnet:** This needs actual OBD2 hardware to test against — a cheap
ELM327 Bluetooth/WiFi adapter. `python-obd` (`pip install obd`) is the standard
library for talking to ELM327 adapters. If no adapter is plugged in this session,
build the script with a `--dry-run` mode that fakes plausible readings, and say
plainly that the real-hardware path is untested — don't claim it works against a
car you haven't connected to.

- [ ] Add a `data/carvoice/vehicles.yaml` entry for the target vehicle (year/make/model
      required, VIN and adapter model optional — fill in what's known)
- [ ] `scripts/carvoice/obd2_logger.py`:
  - Connect via `python-obd`
  - Poll a fixed PID set: RPM, coolant temp, vehicle speed, engine load, fuel level, active DTCs
  - Write one JSON line per sample to `data/carvoice/drives/{vehicle_id}_{YYYYMMDD}.jsonl`
  - `--dry-run` flag that generates fake but plausible readings, no hardware required
- [ ] Test with `--dry-run`, confirm the output file format is something Session 2 can parse
- [ ] Add `obd` and `pyyaml` to a `requirements-carvoice.txt`

### Session 2: Diagnose pipeline

**Goal:** turn one drive log + maintenance history into a plain-English report.

**Context for Sonnet:** `scripts/generate_monkey_post.py` already shows this repo's
pattern for calling the `anthropic` Python SDK — read it first rather than
reinventing the client setup. The API key comes from the user's own environment
(`ANTHROPIC_API_KEY`), never hardcoded.

- [ ] `scripts/carvoice/diagnose.py`:
  - Load a drive log (`data/carvoice/drives/...`) and the vehicle's entries from
    `data/carvoice/maintenance_log.yaml`
  - Build a prompt: raw sensor summary + maintenance context + "explain what's
    going on, plain English, flag anything that needs attention soon"
  - Call the Claude API, print the report to stdout
  - `--save` flag to also write `data/carvoice/reports/{vehicle_id}_{YYYYMMDD}.md`
- [ ] Run it against a `--dry-run` drive log from Session 1, sanity-check the tone
      and usefulness of the output
- [ ] Once run against a real drive: compare Claude's read against what a real
      mechanic says is going on (this is the core success metric from the pitch doc)

### Session 3: Dashboard (Phase 2)

**Goal:** simple web view of car health — car score, next maintenance due, history.

Not started — blocked on Session 1 and 2 producing output worth displaying first.
When this starts, follow the pattern in `layouts/monkeys/` for how this repo
builds a custom section (own `layouts/carvoice/` templates, own `content/carvoice/`
section) rather than inventing a new convention.

---

## Session Log

*(Append one entry per work session — date, what shipped, what's next. Empty so far — no session has run yet.)*
