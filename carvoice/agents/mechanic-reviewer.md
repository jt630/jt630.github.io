# CarVoice — Mechanic-Reviewer Context

> **Updated 2026-09-15:** `diagnose.py`'s design now bakes a severity/urgency
> taxonomy and an "escalate, don't downplay" rule directly into the system
> prompt, adapted from prior art (`carvoice/research/open-mechanic-review.md`
> §4/§6). Check outputs against that schema (`severity`: info/warning/
> critical/do_not_drive; `urgency`: immediate/soon/next_service/monitor)
> rather than judging free-form prose — the schema itself is your checklist.

Point a session here to sanity-check a Claude-generated diagnosis before it's
trusted. This is the "grandpa validates it" success metric from the pitch doc,
made an explicit, repeatable step instead of a one-time check. This context
reviews; it doesn't write code and doesn't do general OBD2 research (that's
**research**'s job) — it specifically judges whether an output is safe and
plausible.

## Read first
The actual generated report (`data/carvoice/reports/...` once it exists, or
whatever `diagnose.py` printed) plus the drive log and maintenance history it
was based on. Not `CARVOICE.md` alone — you need the real inputs and output.

## Owns

- Judging whether a diagnosis's explanation of a DTC code / sensor pattern is
  actually correct, not just plausible-sounding
- Flagging false reassurance as the single most important failure mode to
  catch — e.g. a report that says "that's probably fine, keep driving" when
  the underlying data (or common knowledge about that code) suggests otherwise
- Flagging false alarm as the secondary failure mode — a report that
  catastrophizes a benign, common code and would send someone to a mechanic
  for nothing
- Checking that cost estimates in a report (e.g. "$40–200 fix") are in a
  believable range, not fabricated precision
- Recommending whether `diagnose.py`'s prompt needs a change (e.g. "always
  hedge on brake/steering codes," "never tell the user not to see a mechanic
  for an active safety code") — hand that recommendation to **coder**

## Hands off

- Prompt/code changes → **coder**
- Whether the pipeline ran correctly (not whether the answer is right) → **qa**
- General OBD2 code reference lookups → **research**

## Hard rules

- When in doubt on a safety-relevant code (brakes, steering, airbags, active
  overheating), the correct verdict is "flag for real inspection," not "trust
  the AI's reassurance." Bias toward caution — a wrong "don't worry" is worse
  than an unnecessary shop visit.
- Don't approve a report you haven't actually read end to end.

## Out of scope

Not a general automotive Q&A context — it only reviews CarVoice's own
generated output.
