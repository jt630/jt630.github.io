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
either pasted into a new session or saved to `docs/robots/prompts/`.

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
- `storage_volume_cm3` present on any tool that's not embedded (advisory)
- No edits to files outside the lane's region ownership
- No schema drift — new fields promoted, renamed, or rejected
- Voice check: region docs written in the Goddard voice (warm, patient,
  clear — competent home aide tone, no spy-gadget framing)
- Safety check: no hot-surface or open-flame skills; motion skills include
  elderly-care preconditions (obstacle_clear, voice_interruptible)

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

Shared session prompts live at `docs/robots/prompts/`. Two formats
coexist:

- `.yaml` — current canonical shape. Use for any new prompt that
  another session or sub-agent should be able to load cold and execute.
- `.md` — older free-form prompts kept for historical reference
  (`wave-1.5-and-wave-2.md`). Don't write new ones in this format.

### When to write one

- **End-of-session handoff.** When the conductor session is wrapping
  up and the next wave is well-defined. Save as
  `docs/robots/prompts/wave-N-<short-slug>.yaml`. The next conductor
  session loads it as its brief — no need to re-explain prior state.
- **Parallel-lane dispatch.** When fanning out work to multiple Type-2
  (Agent) or Type-3 (separate-session) lanes. Save as
  `docs/robots/prompts/lane-<batch>-<region-or-task>.yaml`. The
  conductor pastes the same file into each lane's launching prompt so
  every lane starts from the same brief and only diverges on its
  task-specific section.

### Why YAML

- Predictable shape across waves — `read_first`, `task.pieces`,
  `do_not`, `branch`, `success_criteria`, `learning_angle`,
  `runners_up`. The loading session can navigate by keys instead of
  skimming prose.
- Forces the prompt author to separate context from task, mandatory
  from optional, asserted-must from deferred-shouldn't. Markdown lets
  those slip together; YAML doesn't.
- One schema covers both end-of-session handoffs and parallel-lane
  dispatches — only the scope of `task.pieces` differs.

### Schema (worked example)

`docs/robots/prompts/wave-8-morality-profile.yaml` is the canonical
example. Top-level keys:

- `wave:` — number, if numbered. Omit for ad-hoc lane prompts.
- `title:` — one-line goal.
- `session_suffix_placeholder:` — the literal string the next session
  replaces with its own session-id suffix when constructing the
  branch name.
- `context:` — multi-line block: prior state, what the last waves
  did, why this one matters now.
- `read_first:` — list of `{path:, section:}` pairs, in load order.
- `task:` — `{artifact:, shape_reference:, pieces: [...]}`. Each
  piece has `id:`, `title:`, `description:`.
- `do_not:` — list of `{rule:, reason:}` pairs. Scope guards.
- `branch:` — `{start_from:, bootstrap:, name_pattern:, notes:}`.
- `success_criteria:` — list of one-line completion checks.
- `learning_angle:` — multi-line block: the generalizable AI-workflow
  lesson this wave teaches.
- `runners_up:` — list of `{title:, reason_not_picked:}` pairs.
  Documents the alternatives that were considered, so the next
  curator can override.

### YAML gotchas

Strings containing `:` followed by a space (like `utterance_ref:` or
`when:/action:/utterance:`) get parsed as nested mappings even when
they appear inside what should be a scalar value. Quote them:

```yaml
- rule:  "Don't migrate utterance_ref:"     # quoted — colon at end is fine
- title: "utterance_ref: migration"          # quoted — would parse as map otherwise
```

If `python3 -c "import yaml; yaml.safe_load(open('<file>'))"` errors
with `mapping values are not allowed here`, that's almost always an
unquoted colon-in-value somewhere.
