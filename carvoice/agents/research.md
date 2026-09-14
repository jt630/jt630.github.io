# CarVoice — Research Context

Point a session here when the task is: look something up, don't build anything yet.

## Read first
`CARVOICE.md` (architecture + current build-plan session) before anything below.

## Owns

- OBD2 PID definitions and DTC code meanings needed for `obd2_logger.py` / `diagnose.py`
- Python OBD2 library research (`python-obd` and alternatives) — version status,
  known issues, WiFi vs. Bluetooth adapter quirks
- Competitor scan: existing OBD2 scanner apps and AI-car-diagnostic products —
  what they do, what they charge, what's missing (feeds the pitch in
  `content/gadgets/carvoice-ai-assistant.md`)
- Claude API prompting patterns relevant to the diagnose pipeline — check
  `scripts/generate_monkey_post.py` first for this repo's existing pattern of
  calling the `anthropic` SDK before researching from scratch

## Hands off

- Hardware purchase decisions (adapter model, price, where to buy) → **hardware**
  context. Research can surface facts; hardware decides.
- Anything that touches code → **coder** context.
- Whether a finding is mechanically sound → **mechanic-reviewer** context.
- Whether CarVoice is already done by someone else, market sizing, and any
  "is this worth building" verdict → **business** context. This role produces
  the raw competitor feature/pricing facts; business turns that into a
  viability judgment — don't duplicate its verdict here.

## Out of scope

Anything not CarVoice — other Almond Farm content (blog, cooking, farming,
monkeys, campsites) is not this role's job even if the same session could do it.

## Output

Plain findings with sources. If something should change in `CARVOICE.md` (a PID
list fix, a library recommendation), name the exact section — don't edit it from
this context alone; that's a call for whoever's driving the session.
