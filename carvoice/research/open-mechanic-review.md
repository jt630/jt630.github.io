# Code Review: open-mechanic (speed785/open-mechanic)

Cloned and read directly (not just the earlier web-search summary) on 2026-09-15.
MIT-licensed. This is more mature than the ~33-star "hobby project" framing in
`competitors.md` and `business-viability.md` suggested — it's tested against a
real vehicle, has full test coverage, CI, and cross-platform setup docs.

**Bottom line: don't write Session 1/2 from scratch. Adapt this.** It already
solved the boring, undifferentiated plumbing (serial connection handling, DTC
database, JSON-schema-constrained Claude prompting) and tested it on a real
car. CarVoice's actual differentiator (BYOK as a first-class feature, tied into
this repo's own `data/carvoice/maintenance_log.yaml`) is still worth building
fresh — the OBD2/AI plumbing underneath it is not.

---

## 1. Hardware recommendation changes

**open-mechanic uses a USB adapter, not Bluetooth** — specifically the
**OBDLink EX** (~$35, FTDI chip, works as a plain serial port on Linux/macOS/
Windows with zero pairing). This is a real, tested alternative to
`carvoice/research/hardware-options.md`'s Bluetooth Classic recommendation
(OBDLink MX+, ~$140), and it's arguably better for a first prototype:

- No Bluetooth pairing at all — it's just `/dev/ttyUSB0` (Linux),
  `/dev/cu.usbserial-*` (macOS), or `COM3` (Windows)
- Confirmed working in the field: 2018 Ford F-150, ISO 15765-4 CAN 11/500,
  115200 baud, on `/dev/ttyUSB0`
- Cheaper than the MX+ ($35 vs. $140) while still being a real chipset, not a clone
- Sidesteps the WiFi-adapter-disconnects-your-internet problem entirely — a
  wired USB connection has no effect on the laptop's network access

Tradeoff: the laptop has to be tethered to the car via USB cable during
logging, vs. Bluetooth being wireless. For a seated logging session (not
driving solo while also operating a laptop), this is a non-issue and arguably
simpler than dealing with OS Bluetooth pairing state.

**Updated recommendation: OBDLink EX (USB) for Session 1**, not the MX+.

## 2. Protocol tip (real, field-tested)

`python-obd`'s auto-detect protocol negotiation takes ~30s and can hang.
open-mechanic hardcodes `OBD_PROTOCOL=6` (ISO 15765-4 CAN 11/500 — covers
"most 2008+ cars," confirmed on their test Ford). Worth setting explicitly
for a Subaru Forester (2019+, CAN-bus) rather than relying on auto-detect.

## 3. Architecture worth adopting directly

```
connection.py   OBDConnection class — retry/backoff, cross-platform port
                detection, is_connected(), context-manager support
reader.py       SensorPoller — get_snapshot() one-shot read, start_polling()
                threaded loop with a callback; gracefully marks unsupported
                PIDs "N/A" instead of crashing
dtc.py          DTCReader — reads pending + confirmed DTCs, decodes against
                a local JSON database, clear_dtcs() gated behind an explicit
                confirmed=True (raises otherwise)
ai/prompts.py   Pure string formatting, zero API imports — format_diagnostic_
                prompt() assembles vehicle + DTCs + sensor snapshot into one
                user message; system prompt is a separate constant
ai/diagnose.py  DiagnosticEngine — wraps the anthropic client, 24h result
                cache keyed on (vehicle, DTCs, snapshot), strips markdown
                fences before json.loads, injects the safety disclaimer onto
                every result itself (never trusts the caller to add it)
db/models.py    SQLAlchemy: VehicleProfile, DiagnosticSession, SensorReading,
                DTCRecord, DiagnosisResult
```

This maps cleanly onto CarVoice's planned `obd2_logger.py` (connection.py +
reader.py + dtc.py) and `diagnose.py` (ai/prompts.py + ai/diagnose.py). The
`SensorPoller`/`DTCReader` split and the "unsupported PID → N/A, never crash"
handling are exactly the kind of thing that's easy to get subtly wrong writing
from scratch and this repo already got right, on a real car.

## 4. The diagnosis schema is better than what CARVOICE.md currently sketches

CARVOICE.md's Session 2 currently just says "plain-English report." open-mechanic's
system prompt forces strict JSON with a real taxonomy:

```json
{
  "severity": "<info|warning|critical|do_not_drive>",
  "summary": "...",
  "likely_causes": ["..."],
  "repair_steps": ["..."],
  "estimated_cost_usd": {"low": 0, "high": 0},
  "diy_feasible": true,
  "diy_difficulty": "<easy|moderate|hard|professional_only>",
  "urgency": "<immediate|soon|next_service|monitor>",
  "disclaimer": "..."
}
```

Plus a hardcoded rule: *"Be conservative: when in doubt, escalate severity
rather than downplay it."* That is the exact rule `carvoice/agents/
mechanic-reviewer.md` was written to enforce as a manual review step — here
it's baked into the system prompt itself, which is a stronger place for it to
live (defense at the source, review as a backstop, not the only line of
defense). **Recommend adopting this schema and rule directly** rather than a
looser "plain English" format — it also gives `qa.md` something concrete to
assert against (valid severity/urgency enum, cost range present, disclaimer
non-empty) instead of "didn't crash."

## 5. The DTC database is a real, reusable asset

`data/dtc_codes.json` — 522 codes, each `{code, description, severity, category}`,
offline, no API needed. CarVoice's own research (`obd2-reference.md`) only
hand-documented ~15 common codes. **Recommend vendoring this file** (MIT
permits it) into `data/carvoice/dtc_codes.json` rather than manually expanding
CarVoice's own list — it's already 35x more coverage and already used by a
tested `DTCReader` implementation we can adapt.

## 6. Safety guardrails worth copying as hard rules, not just prompt text

From `AGENTS.md`'s "CRITICAL CONSTRAINTS" — these are enforced in code, not
just asked for in a prompt:

- `clear_dtcs()` requires `confirmed=True` or raises — no accidental code clears
- The disclaimer is injected by `DiagnosticEngine` itself on every result,
  never left to the caller to remember
- Unsupported PIDs are skipped silently, never crash the poller
- API key only ever from env/`.env`, never hardcoded

These should become hard rules in `scripts/carvoice/diagnose.py` and
`obd2_logger.py` too, not just conventions in `CARVOICE.md` prose.

## 7. Licensing note

open-mechanic is MIT (`Copyright (c) 2026 open-mechanic contributors`).
Vendoring or adapting its code/data is permitted, but MIT requires keeping
the copyright notice and license text with any copy of the licensed
material. **If CarVoice vendors `dtc_codes.json` or adapts `connection.py`/
`reader.py`/`dtc.py`/`ai/prompts.py`/`ai/diagnose.py`, add a `NOTICE` or
top-of-file comment crediting open-mechanic and its MIT license**, and
carry that forward into CarVoice's own eventual LICENSE file (also MIT,
per `CARVOICE.md` Status — compatible).

## 8. What's not relevant yet

`api/`, `db/models.py` (SQLAlchemy + SQLite), the Vite/TypeScript `website/`,
and Phase 3/4 dashboard plans are all Phase-3-equivalent work — CarVoice's
own Session 3 (dashboard) is exactly where `db/models.py`'s schema shape
(VehicleProfile / DiagnosticSession / SensorReading / DTCRecord /
DiagnosisResult) becomes a useful reference again, but there's no reason to
adopt SQLAlchemy/SQLite for Session 1/2's flat-file, no-server local prototype.
