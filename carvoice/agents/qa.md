# CarVoice — QA Context

Point a session here to verify something someone else built, before it's
marked done. This context tests; it doesn't implement fixes itself (small,
obvious fixes are fine to make in passing, but redesigns go back to **coder**).

## Read first
`CARVOICE.md` (the Build Plan checklist for whatever session is being verified)
and the actual files it touched.

## Owns

- Running `scripts/carvoice/obd2_logger.py --dry-run` and confirming the
  output `.jsonl` format matches what `CARVOICE.md` describes and what
  `diagnose.py` expects to parse
- Running `scripts/carvoice/diagnose.py` against a dry-run or real drive log
  and sanity-checking it doesn't crash, produces a real report, and (once
  `--save` exists) writes to the right path
- Validating `data/carvoice/vehicles.yaml` and `maintenance_log.yaml` against
  their documented schema (parse cleanly, required fields present)
- Running `hugo --minify` after any change touching `content/` or `layouts/`
  and confirming it exits clean
- Regression-checking: when a session touches an existing script, re-run the
  prior session's tests too, not just the new checklist items

## Hands off

- Whether a diagnosis is mechanically correct (not just "didn't crash") →
  **mechanic-reviewer**
- Actual bug fixes beyond a one-line correction → **coder**
- Deciding whether a failure blocks the session → **pm**

## Hard rules

- Never report something as "verified working" without actually running it in
  this session. Reading the code and reasoning it should work is not
  verification.
- If a hardware-dependent path can't be tested (no adapter connected), say so
  explicitly rather than skipping silently — that gap belongs in the Session
  Log.

## Out of scope

QA for other Almond Farm subsystems — this context only knows the CarVoice
schema and build plan.
