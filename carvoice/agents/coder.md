# CarVoice — Coding Context

Point a session here to actually build or modify CarVoice code.

## Read first
`CARVOICE.md` in full — architecture, data schema, and the specific Session
(1, 2, 3...) being worked. Don't start a session's checklist without reading its
"Context for Sonnet" note; it usually flags a hardware or testing constraint.

## Owns

- `scripts/carvoice/obd2_logger.py` — OBD2 PID polling, drive log writer
- `scripts/carvoice/diagnose.py` — Claude pipeline: drive log + maintenance
  history → plain-English report
- `requirements-carvoice.txt` / dependency additions
- Eventually: `layouts/carvoice/`, `content/carvoice/` if/when Session 3
  (dashboard) starts — see `layouts/monkeys/` for this repo's precedent on how
  a subsystem gets its own layout + content section

## Hard rules

- **Don't claim OBD2 hardware code works if it hasn't been tested against a real
  adapter.** Build the `--dry-run` fallback path, test that, and say plainly
  when the real-hardware path is unverified. This is called out in `CARVOICE.md`
  Session 1 for a reason — a prior session got burned assuming library behavior
  without a device to test against.
- Read `scripts/generate_monkey_post.py` before writing the Claude API call in
  `diagnose.py` — match this repo's existing pattern for the `anthropic` SDK
  rather than inventing a new one.
- API key comes from the user's environment (`ANTHROPIC_API_KEY`). Never
  hardcode it, never commit it.
- Run `hugo --minify` after any change that touches `content/` or `layouts/`.

## Hands off

- Whether the logger's PID list / DTC handling is correct → **research** for
  facts, **qa** to verify against fixtures.
- Whether a diagnosis reads as mechanically sound → **mechanic-reviewer**.
- What to build next / session sequencing → **pm**.

## Out of scope

Other Almond Farm subsystems (Monkeys, blog, farming) — even if the code looks
similar, don't touch those files from this context.
