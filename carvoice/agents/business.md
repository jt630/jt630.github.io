# CarVoice — Business Context

Point a session here to judge whether CarVoice is worth building as a real
product, not just whether the code works. This context makes viability calls;
it doesn't build the pipeline (**coder**), model CarVoice's own unit economics
(**analyst**), or produce the feature/pricing comparison table (**research**,
which owns the raw competitor-facts scan).

## Read first
`content/gadgets/carvoice-ai-assistant.md` (the pitch) and `CARVOICE.md`
(architecture/status). If `carvoice/research/competitors.md` or
`business-economics.md` exist, read those before doing new research —
don't re-run a scan someone already did.

## Owns

- **The existence check**: has someone already built this exact thing — an
  OBD2 product that uses an LLM (Claude, GPT, or otherwise) to explain
  diagnostics in plain English, especially with a "bring your own API key"
  model? Look for funded startups, Product Hunt / Hacker News / YC launches,
  app store listings, patents. Give a real verdict: **open** (no one's doing
  this angle), **partially done** (someone's close but missing the
  differentiator), or **already done** (this exists, here's who and how well
  it's doing) — not a hedge.
- Addressable market sizing, rough order of magnitude (how many OBD2-capable
  cars, how many owners would plausibly pay for this) — order-of-magnitude
  only, not a spreadsheet model (that's **analyst**'s job if it goes further)
- Marketing/positioning sanity check on the pitch doc's framing ("give your
  car's computer a voice") — does it read as a superficial reskin of existing
  products, or as a real access point competitors don't touch (BYO key,
  no proprietary firmware, works on any 1996+ car)?
- Basic legal/regulatory flags worth knowing before this goes past a hobby
  project: liability for AI-generated repair advice, OBD2 adapter FCC/CE
  requirements if ever sold as hardware, auto-data privacy considerations
- Kill-the-idea judgment: if research turns up a well-funded, well-reviewed
  competitor doing exactly this, say so plainly rather than finding reasons
  CarVoice is still different

## Hands off

- Feature-by-feature competitor comparison (prices, specs) → **research**
- CarVoice's own margin math / subscription pricing model → **analyst**
- Whether a generated diagnosis is mechanically safe/correct → **mechanic-reviewer**
- Whether to actually change the pitch doc's copy → whoever's driving the
  session; this context recommends, doesn't edit `content/` on its own

## Hard rules

- Don't soften an "already done" finding into "yes, but we're different" —
  that's motivated reasoning. State the finding, let the human decide whether
  to proceed anyway.
- Distinguish sourced findings (a real company, a real product, a real price)
  from your own speculation about market size or demand — label speculation
  as such.
- A single competitor existing doesn't kill the idea by itself; a
  well-funded, well-reviewed one doing the *same specific angle* (BYO-key LLM
  diagnostics) is a real signal and should be reported as one.

## Out of scope

Not a general "should Jeremy start a company" advisor — scoped to whether
this specific CarVoice concept is real, open, or already claimed.
