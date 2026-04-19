# Session Workflow

Goddard (the conductor Opus session) orchestrates work. Sub-sessions and
sub-agents do the scaffolding. The curator sets direction and merges.

## Session types

### Type 1 — Curator + Goddard (this session, Opus)

Conversational. The curator and Goddard explore questions, make decisions,
and capture them to a decisions doc. No parallel sibling allowed — the
curator can only be in one conversation at a time.

Use for: Wave 0 (core functions), interface philosophy, safety/trust
model, learning loop, physical prototyping path, anything where judgment
matters more than output volume.

### Type 2 — Agent-tool sub-agents (Sonnet, parallel, dispatched from Goddard)

Goddard calls `Agent(subagent_type: general-purpose)` in parallel to
scaffold content without blocking the curator. Each call:

- Runs in the same repo working directory (no worktree)
- Does not hand the curator a separate window
- Returns a summary Goddard reviews before committing
- Can be launched concurrently — multiple Agent calls in a single message
  fan out

Use for: drafting organ manifests within one region, writing region docs,
running a focused search, summarizing prior art. Anything pattern-following
and bounded.

### Type 3 — Separate Claude sessions (Sonnet, parallel, ferried by the curator)

The curator opens a new Claude session (another terminal, another browser
tab), pastes a self-contained prompt, and ferries the output back. More
overhead than Agent calls — but useful when the work spans many tool
invocations, produces large context, or the curator wants to tweak the
prompt mid-flight.

Use for: long-horizon region scaffolding (all of arm + hands in one
session), drafting a full Hugo layout, prior-art research that needs many
web searches.

### Type 4 — Agent-authors-agent / Agent-authors-prompt (meta)

Goddard can call an Agent to produce a prompt for another Agent, or to
design a sub-agent definition. The output is reviewed then reused —
either pasted into a new session or saved to `data/robots/prompts/`.

Use for: generating lane prompts programmatically, refining prompts based
on observed output quality.

## Branch + PR protocol

- Scaffolding sessions branch off the current project branch (not `main`)
  as `claude/goddard-<region>-<suffix>`
- PRs target the project branch, NOT main
- Goddard reviews and merges
- After merge, Goddard pulls into the conductor branch so context stays
  fresh

## Goddard's review checklist

For every incoming PR (from Agent call or separate session):

- `hugo --minify` passes
- Every new organ has `id`, `region`, `group`, `description`
  (with TRIGGER + SKIP), `hardware`, `preconditions`, `owned_by`
- `region` matches filename prefix (e.g. `arm_*.yaml` has `region: arm`)
- `composes_with` ids all resolve to existing organs
- `requires_mount` (if present) matches a known mount-bay type
- `storage_volume_cm3` present on any tool that's not embedded
- No edits to files outside the lane's region ownership
- No schema drift — new fields promoted, renamed, or rejected
- Voice check: region docs written in the Goddard voice (tight, first
  person, no sub-personalities)

## Dispatching with the Agent tool

When Goddard fans out scaffolding work, the Agent prompt should:

1. Start with: *"You are working for Goddard. Read `GODDARD.md` and the
   companion docs listed there before anything else."*
2. State the exact files the agent owns and may not touch
3. Reference `data/robots/organs/arm_3d_printer.yaml` as the canonical
   schema example
4. Require the agent to run `hugo --minify` before reporting back
5. Ask for a tight summary of what was changed, by file

Goddard never says "based on your findings, implement it." Goddard
reviews findings and implements or commits the agent's output after check.

## Recommendation protocol

Goddard recommends next steps proactively. Every meaningful turn ends
with at most three concrete options the curator can pick from. Examples:

- "Open Wave 0 now (15 min convo) vs. dispatch the arm lane in parallel
  while we wait"
- "Commit the foundation now, or add REGIONS scaffolding first for a
  bigger commit"
- "Spawn Sonnet lanes for arm + legs concurrently, or do them serially
  so we can evolve the schema between them"

Recommendations are options, not decisions — the curator picks.

## Parallel-safety rules

- Two sub-agents must never own the same file
- Two sub-agents may read the same file freely
- Schema changes go through Goddard; lanes propose, Goddard promotes
- If two lanes need the same new cross-region interface, Goddard drafts
  it once and both consume it

## Prompt library

Shared session prompts live at `data/robots/prompts/<name>.md` —
version-controlled, evolves with the project. When Goddard writes a new
scaffolding prompt, it saves the reusable part here so the next session
(or the next curator) starts from the same place.
