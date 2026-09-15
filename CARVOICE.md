# CarVoice — Project Plan

## Summary

CarVoice is an OBD2 adapter + Claude pipeline that turns raw car diagnostics into
plain-English answers: *is this real, should I worry, what's next.*

This file is the internal build/architecture doc — read it before any CarVoice
session. For the pitch and full feature spec, see
[`content/gadgets/carvoice-ai-assistant.md`](content/gadgets/carvoice-ai-assistant.md).

Registries: `data/carvoice/vehicles.yaml`, `data/carvoice/maintenance_log.yaml`

## Status

**Phase 1 (Prototype) — code written, unverified against real hardware or a
real API call.** `obd2_logger.py` and `diagnose.py` exist (2026-09-15),
adapted from open-mechanic. Verified so far: `--dry-run` logging produces
valid JSONL; `diagnose.py`'s drive-log parsing, summarization, and prompt
formatting all run correctly against a dry-run log. **Not yet verified:**
connecting to a real OBD2 adapter (none owned yet), and the actual Claude
API call in `diagnose()` (no `ANTHROPIC_API_KEY` in this environment — that's
by design, it's the user's own key, not something this session should have).
No vehicle registered in `data/carvoice/vehicles.yaml` yet. Nothing in this
repo has touched a real car.

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
OBD2 adapter (USB) → laptop → obd2_logger.py → drive log (.jsonl)
                                                          ↓
                              maintenance_log.yaml → diagnose.py → Claude API → structured diagnosis
```

The user's own Claude API key does the analysis. No proprietary firmware access,
no cloud backend required to prove the concept — that's Phase 2.

**Hard out-of-scope boundary: the ECU's actual firmware/ROM.** CarVoice reads
only standard OBD2 — Mode 01 (live PIDs) and Mode 03/04 (DTCs) via
`python-obd`, the interface legally mandated on every 1996+ US car
specifically for diagnostic access. It does not, and should never, touch ECU
firmware extraction, flashing, or tuning (J2534 pass-thru, chip access,
manufacturer proprietary tools). That's a different legal regime (DMCA
1201's vehicle-repair exemption covers standard diagnostics, not firmware
extraction/modification) and a different risk category (emissions-tampering
law applies to firmware changes, not to reading OBD2 sensor data) — and
nothing CarVoice's pitch promises requires it anyway.

---

## Data Files

### `data/carvoice/vehicles.yaml`
Registry, one entry per tracked vehicle. Schema and template are in the file header.

### `data/carvoice/maintenance_log.yaml`
Maintenance history, one entry per service event, keyed by `vehicle_id`. This is
the ground truth the diagnose pipeline reads alongside live sensor data — a
misfire code reads differently if the plugs were just changed vs. 60k miles ago.

### `data/carvoice/dtc_codes.json`
522-code offline DTC reference, vendored from open-mechanic (MIT) — see
`carvoice/THIRD_PARTY_NOTICES.md`. `{code, description, severity, category}` per entry.

### `data/carvoice/drives/{vehicle_id}_{YYYYMMDD}.jsonl`
Raw OBD2 PID samples from one drive session, written by `obd2_logger.py`. One
JSON object per line: timestamp + PID readings (RPM, coolant temp, speed, engine
load, fuel level, plus a few extras) + active DTCs. Directory is empty until a
real (or `--dry-run`) session writes to it.

### `data/carvoice/reports/{vehicle_id}_{YYYYMMDD}.md`
Output of `diagnose.py --save` — the structured diagnosis report for one drive log.

---

## Key Files

- `CARVOICE.md` — this file
- `data/carvoice/vehicles.yaml` — vehicle registry
- `data/carvoice/maintenance_log.yaml` — maintenance history
- `data/carvoice/dtc_codes.json` — 522-code DTC reference, vendored from open-mechanic
- `data/carvoice/drives/` — raw OBD2 session logs (empty until a session runs)
- `data/carvoice/reports/` — generated diagnosis reports (empty until `--save` is used)
- `scripts/carvoice/obd2_logger.py` — reads OBD2 PIDs + DTCs, writes drive logs
  (dry-run path tested; real-hardware path untested, no adapter owned yet)
- `scripts/carvoice/diagnose.py` — drive log + maintenance history → Claude →
  structured diagnosis (local logic tested; the actual API call is untested —
  needs the user's own `ANTHROPIC_API_KEY`)
- `requirements-carvoice.txt` — `obd`, `pyserial`, `anthropic`, `pyyaml`
- `carvoice/THIRD_PARTY_NOTICES.md` — MIT attribution for code/data adapted from open-mechanic
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

**Done (2026-09-15):**
- [x] Vendor `data/carvoice/dtc_codes.json` from open-mechanic (with NOTICE/attribution
      in `carvoice/THIRD_PARTY_NOTICES.md`)
- [x] `scripts/carvoice/obd2_logger.py`, adapted from open-mechanic's connection.py + reader.py + dtc.py:
  - Connect via `python-obd` over USB serial (OBDLink EX), `OBD_PROTOCOL=6` set explicitly
  - Poll a fixed PID set: RPM, coolant temp, vehicle speed, engine load, fuel level, active DTCs (plus a few extras)
  - Write one JSON line per sample to `data/carvoice/drives/{vehicle_id}_{YYYYMMDD}.jsonl`
  - `--dry-run` flag that generates fake but plausible readings, no hardware required
- [x] Tested with `--dry-run`: produces valid JSONL, all sensor keys present, confirmed parseable
- [x] Added `obd`, `pyserial`, `anthropic`, and `pyyaml` to `requirements-carvoice.txt`

**Not done — needs real hardware:**
- [ ] Add a `data/carvoice/vehicles.yaml` entry for the target vehicle (year/make/model
      required, VIN and adapter model optional) — no vehicle owned/confirmed yet
- [ ] Connect to a real OBD2 adapter and confirm `OBDConnection`/PID polling/DTC
      reading actually work against a live car — **the real-hardware path in
      `obd2_logger.py` is code adapted from a tested reference, but has not
      itself been run against any adapter or vehicle. Treat it as unverified
      until it is.**

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

**Done (2026-09-15):**
- [x] `scripts/carvoice/diagnose.py`, adapted from open-mechanic's ai/prompts.py + ai/diagnose.py:
  - Loads a drive log (`data/carvoice/drives/...`) and the vehicle's entries from
    `data/carvoice/maintenance_log.yaml`
  - System prompt enforces the structured JSON schema (severity/urgency/cost
    range/diy_feasible/disclaimer); user message assembles vehicle context +
    DTCs + sensor snapshot + maintenance history
  - Disclaimer injected by the function itself unconditionally, not left to
    the caller or the model's own copy
  - `--save` flag to also write `data/carvoice/reports/{vehicle_id}_{YYYYMMDD}.md`
- [x] Verified without an API key: drive-log parsing, DTC/sensor summarization, and
      prompt formatting all run correctly against a `--dry-run` log from Session 1

**Not done — needs the user's own `ANTHROPIC_API_KEY`:**
- [ ] Actually call the Claude API and confirm the JSON response is parsed correctly
      (this environment has no `ANTHROPIC_API_KEY` — by design, it's the user's own
      key, not something a CarVoice dev session should have)
- [ ] Sanity-check the tone and usefulness of a real diagnosis against a `--dry-run` log
- [ ] Once run against a real drive: compare Claude's read against what a real
      mechanic says is going on (this is the core success metric from the pitch doc)

### Session 3: Dashboard (Phase 2)

**Goal:** simple web view of car health — car score, next maintenance due, history.

Not started — blocked on Session 1 and 2 producing output worth displaying first.
When this starts, follow the pattern in `layouts/monkeys/` for how this repo
builds a custom section (own `layouts/carvoice/` templates, own `content/carvoice/`
section) rather than inventing a new convention.

---

## Backlog / Later

Not scheduled into a session yet — don't act on these until they're pulled in.

- **Contribute P0128 and P0230 back to open-mechanic.** Our own research
  (`carvoice/research/obd2-reference.md`) documents two DTC codes missing from
  their vendored 522-code database. Proposed entries: `P0128` (Coolant
  Thermostat, `warning`/`engine`) and `P0230` (Fuel Pump Primary Circuit
  Malfunction, `critical`/`fuel`) — reasoning and convention cross-checks are
  in this session's chat log. **Wait until there's real hardware/vehicle data**
  so the contribution can honestly say what it was confirmed on (their own
  `CONTRIBUTING.md` has an optional "vehicles confirmed on" field — don't
  fabricate it). Two paths: open a GitHub issue on their DTC-addition template,
  or fork + PR directly.
- **Mine more open DTC/PID reference sources to expand `data/carvoice/dtc_codes.json`.**
  The formal standards (SAE J1979 for PIDs, SAE J2012 for DTC format) are paid,
  copyrighted SAE specifications — not open source. But the practical code
  meanings are widely and freely republished (Wikipedia, obd-codes.com,
  `python-obd`'s own decoder tables, open-mechanic's MIT-licensed JSON).
  Generic P0xxx codes are standardized and safe to treat as common knowledge;
  manufacturer-specific P1xxx/P3xxx codes are proprietary per-brand and need
  per-manufacturer sourcing if this is ever pursued. **Track the license/source
  of anything pulled in** — don't lump "freely republished" and "open source"
  together when actually vendoring more codes.

---

## Session Log

*(Append one entry per work session — date, what shipped, what's next.)*

### 2026-09-15 — Research fan-out, prior-art review, Session 1+2 code

Ran five parallel research passes (OBD2 reference, competitors, hardware
options, business economics, business viability) → verdict PARTIALLY DONE,
decided to stay a personal open-source project, rewrote the public pitch
accordingly. Then cloned and read `speed785/open-mechanic` (MIT) directly
instead of trusting the earlier search-summary — it's field-tested on a
real vehicle, not a toy. Adapted its connection/reader/DTC-reading code and
its diagnosis JSON schema into `scripts/carvoice/obd2_logger.py` and
`diagnose.py`, and vendored its 522-code DTC database. Flipped the hardware
recommendation from Bluetooth (OBDLink MX+) to USB (OBDLink EX) to match
what was actually field-tested.

**Verified:** `--dry-run` logging produces valid JSONL; `diagnose.py`'s
drive-log parsing, DTC/sensor summarization, and prompt formatting all run
correctly against a dry-run log; both scripts compile cleanly.

**Not verified — next session's job:** the real-hardware connection path (no
adapter owned), and the actual Claude API call in `diagnose()` (no
`ANTHROPIC_API_KEY` in this environment, by design). No vehicle registered
in `vehicles.yaml` yet — household is still shopping for the Subaru
(`scripts/car_buy_math.py`/`car_finder.py`), nothing to register yet.

**Next session:** once there's a real vehicle and an OBDLink EX (or similar
USB adapter) in hand, register the vehicle in `vehicles.yaml`, run
`obd2_logger.py` for real, then run `diagnose.py` with a real
`ANTHROPIC_API_KEY` and compare the output against a real mechanic's read.
