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

**Viability verdict: PARTIALLY DONE** (see `carvoice/research/business-viability.md`
for full findings). "OBD2 + LLM explains your codes" is already shipped by at least
four real products (OBDAI, LAUNCH AIOBD, MECH AI, and funded startup SPARQ
Diagnostics) — that framing alone is not a differentiator anymore. The one gap none
of them fill is **bring-your-own-API-key** (no vendor markup on AI cost, no vendor
custody of diagnostic data) — the only prior art there is `open-mechanic`, a ~33-star
open-source hobby project with no company or users behind it.

**Decision (2026-09-15): personal project, not a business.** Given the viability
verdict, this is staying scoped to personal use on the household's own car(s) —
no hardware sales, no subscription, no dashboard-as-a-service. The code will be
open-sourced once it exists (nothing in `scripts/carvoice/` yet — add a LICENSE,
MIT suggested, once Session 1 actually produces code, not before). The pitch in
`content/gadgets/carvoice-ai-assistant.md` has been rewritten to reflect this —
no pricing, no business model, an honest "Prior Art" section, and the tagline
moved away from "give your car's computer a voice" (too close to SPARQ's own ad
campaign). The `business` and `analyst` role contexts are now mostly dormant;
day-to-day work is research/hardware/coder/qa/pm/mechanic-reviewer.

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
- `carvoice/agents/` — role-context briefs (research, coder, hardware, pm, qa,
  mechanic-reviewer, analyst, business) — point a session at one instead of
  re-explaining scope each time; see `carvoice/agents/README.md`
- `carvoice/research/` — findings written by research sessions (OBD2
  reference, competitor scan, hardware options, business economics/viability,
  and a full code review of prior art `open-mechanic` — read that one before
  Session 1 or 2, it changes the plan)

---

## Build Plan

### Session 1: Register the vehicle + OBD2 logger

**Goal:** get real PID data off a car onto disk.

**Context for Sonnet:** Don't write this from scratch. Read
`carvoice/research/open-mechanic-review.md` first — `speed785/open-mechanic`
(MIT-licensed, cloned and reviewed on 2026-09-15) already solved this exact
plumbing and tested it on a real vehicle. Adapt its `connection.py`
(`OBDConnection`, retry/backoff, cross-platform port detection), `reader.py`
(`SensorPoller`, unsupported-PID-never-crashes handling), and `dtc.py`
(`DTCReader`, gated `clear_dtcs(confirmed=True)`) into
`scripts/carvoice/obd2_logger.py` rather than re-deriving the same design.
Vendor its `data/dtc_codes.json` (522 codes) into
`data/carvoice/dtc_codes.json` instead of hand-writing a short DTC list — add
a `NOTICE` crediting open-mechanic's MIT license wherever code or data is
copied (see the review file §7).

**Hardware pivot:** earlier research (`hardware-options.md`) recommended a
Bluetooth adapter (OBDLink MX+). open-mechanic's field-tested choice is
**USB** instead — the **OBDLink EX** (~$35, FTDI chip, plain serial port on
every OS, zero Bluetooth pairing, confirmed working on a real 2018 F-150).
Cheaper and simpler than Bluetooth for a laptop-tethered logging session; use
this unless there's a specific reason to need wireless. Set `OBD_PROTOCOL=6`
(ISO 15765-4 CAN 11/500) explicitly rather than relying on ~30s auto-detect —
covers the Subaru Forester (2019+, CAN-bus) per `hardware-options.md`'s
compatibility notes.

If no adapter is plugged in this session, build the script with a `--dry-run`
mode that fakes plausible readings, and say plainly that the real-hardware
path is untested — don't claim it works against a car you haven't connected to.

- [ ] Add a `data/carvoice/vehicles.yaml` entry for the target vehicle (year/make/model
      required, VIN and adapter model optional — fill in what's known)
- [ ] Vendor `data/carvoice/dtc_codes.json` from open-mechanic (with NOTICE/attribution)
- [ ] `scripts/carvoice/obd2_logger.py`, adapted from open-mechanic's connection.py + reader.py + dtc.py:
  - Connect via `python-obd` over USB serial (OBDLink EX), `OBD_PROTOCOL=6` set explicitly
  - Poll a fixed PID set: RPM, coolant temp, vehicle speed, engine load, fuel level, active DTCs
  - Write one JSON line per sample to `data/carvoice/drives/{vehicle_id}_{YYYYMMDD}.jsonl`
  - `--dry-run` flag that generates fake but plausible readings, no hardware required
- [ ] Test with `--dry-run`, confirm the output file format is something Session 2 can parse
- [ ] Add `obd`, `pyserial`, and `pyyaml` to a `requirements-carvoice.txt`

### Session 2: Diagnose pipeline

**Goal:** turn one drive log + maintenance history into a structured diagnosis.

**Context for Sonnet:** Read `carvoice/research/open-mechanic-review.md` §4
and §6 first. `scripts/generate_monkey_post.py` shows this repo's own pattern
for calling the `anthropic` SDK, but for the *prompt/schema design* adapt
open-mechanic's `ai/prompts.py` + `ai/diagnose.py` instead of inventing a
"plain English report" format from scratch — their JSON schema
(`severity`: info/warning/critical/do_not_drive, `urgency`, `estimated_cost_usd`
range, `diy_feasible`, always-injected `disclaimer`) is a better design and
gives `qa.md` and `mechanic-reviewer.md` something concrete to check against.
Bake in their hard rules as code, not just prompt text: the diagnostic
function itself must inject the disclaimer onto every result — never trust
the caller to add it — and the system prompt must include "when in doubt,
escalate severity rather than downplay it." The API key comes from the
user's own environment (`ANTHROPIC_API_KEY`), never hardcoded.

- [ ] `scripts/carvoice/diagnose.py`, adapted from open-mechanic's ai/prompts.py + ai/diagnose.py:
  - Load a drive log (`data/carvoice/drives/...`) and the vehicle's entries from
    `data/carvoice/maintenance_log.yaml`
  - System prompt enforces the structured JSON schema above (adapt, don't
    reinvent); user message assembles vehicle context + DTCs (decoded via
    `data/carvoice/dtc_codes.json`) + sensor snapshot + maintenance history
  - Call the Claude API, print the structured result to stdout
  - Disclaimer injected by the function itself, not left to the caller
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
