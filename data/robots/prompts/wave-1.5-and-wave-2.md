# Goddard session — Wave 1.5 (adjudicate open questions) then Wave 2 (composed skills)

You are Goddard. Two phases, in order. Phase A is curator-in-the-loop; Phase
B fans out parallel Sonnet Agents. Do not start Phase B until Phase A is
clean (or the curator explicitly defers the rest).

## Load first — strict order, before anything else

1. `GODDARD.md` at repo root — your identity and voice
2. `docs/goddard/SCHEMA.md` — note the `kind: composed` section; Wave 2 lives here
3. `docs/goddard/SKILL-DIRECTORY.md` — tier inheritance rule: composed skills
   inherit the *max* tier of their sub-skills
4. `docs/goddard/REGIONS.md` — region ownership
5. `docs/goddard/WORKFLOW.md` — session types, dispatch, review checklist
6. `docs/goddard/OPEN-QUESTIONS.md` — **your Phase A worklist (Q1–Q7)**
7. `docs/goddard/regions/*.md` — Wave 1 region docs (responsibility, interfaces, decisions, open questions per region)
8. `content/brain/goddard-core-functions.md` — Wave 0 decisions
9. `data/robots/organs/arm_3d_printer.yaml` + `skin_vacuum.yaml` — canonical atoms
10. Glob the 26 `data/robots/organs/*.yaml` so the `composes_with` graph is in context

## State at session start

- Wave 1 is merged to `main`. 26 organs across 8 regions, 8 region docs,
  `OPEN-QUESTIONS.md` capturing 7 cross-lane interface questions.
- No composed skills exist yet — the `kind: composed` pattern in
  `SCHEMA.md` has zero instances in the registry.
- Branch off `main` fresh: `claude/goddard-wave-2-<SUFFIX>`. Do NOT reuse
  the Wave 1 branch — it was deleted on merge.
- `hugo --minify` is green. Keep it that way at every step.

## Phase A — adjudicate OPEN-QUESTIONS.md (Type 1, curator-in-the-loop)

For each question Q1–Q7 in order:

1. Re-read the question and open every manifest it touches.
2. Propose at most three concrete resolutions with tradeoffs. Recommend one.
3. Curator picks. Implement:
   - Edit affected manifests (e.g. Q1 adds an `outputs:` block with
     explicit field types to `leg_walk`; `core_reflex_loop`'s `inputs:`
     mirrors it)
   - If the resolution needs a schema edit (e.g. Q7 may promote a new
     `group` value), update `SCHEMA.md` and `data/robots/skill_groups.yaml`
     in the same commit
   - Mark the question **RESOLVED** in-place in `OPEN-QUESTIONS.md` with
     the decision and commit hash
4. Run `hugo --minify` after every change. Green or don't commit.
5. One commit per resolved question: `Q<n>: <one-line decision>`.

Priorities (if curator deprioritizes, skip and note why in the file):
- **Q1 (balance sub-loop shape)** and **Q7 (`brain_compute` group)** first —
  both touch schema and block downstream clarity.
- **Q5 (storage-budget accounting)** next — unblocks any future Wave 3
  magazine/storage organ design.
- Q2, Q3 (shoulder/wrist handshakes) can stay as open questions until
  hardware prototyping begins; they're prose interfaces.
- Q4 (hip load + thermal) same — defer unless curator has numbers in mind.
- Q6 (STT path) — decide between a new `brain_stt` organ vs. folding into
  `brain_compute`. Small but self-contained.

## Phase B — Wave 2: composed skills (Type 2, Agent fan-out)

Once Phase A is complete (or curator signals "go"), fan out composed skills
using `kind: composed` per `SCHEMA.md`. The Wave 1 atoms are rich enough to
compose real elderly-care scenarios.

Scenario clusters (one lane each, no cross-file collisions):

| Lane | Cluster | Candidate composed skills |
|---|---|---|
| A | fabrication chains | `arm_print_and_clean` (promote the SCHEMA illustrative example), `arm_print_on_demand` (memory → registry → printer → vacuum) |
| B | fetch / retrieval | `fetch_object` (walk → manipulator → paw), `retrieve_dropped` (sensor → walk cautious → pincer), `hand_from_shelf` |
| C | safety / care | `spill_cleanup` (sensor → walk → vacuum), `fall_response` (sensor → walk cautious_approach → speaker → intent_queue), `medication_reminder` (memory → speaker → mic → intent_queue) |
| D | daily routines | `morning_routine`, `evening_routine`, `check_in` — each a scheduled chain pulling from `brain_memory` |

Each lane writes composed manifests as files in `data/robots/organs/` named
by the lane's lead region (e.g. `arm_print_and_clean.yaml`, `leg_fetch_object.yaml`).
Every composed manifest MUST:

- Set `kind: composed`
- Live in the region of the lead organ in the `composes:` list
- Resolve every `composes:` sub-skill id (validator in the Wave 1 commit
  message — reuse it)
- Include a `fallback:` branch where failure could strand the resident
  (e.g. fall_response has no silent-failure mode — escalate to caregiver)
- Inherit the max tier of its sub-skills (see SKILL-DIRECTORY.md)
- Carry elderly-care TRIGGER/SKIP in `description`
- Include `voice_interruptible: true` in `safety`

Lane prompts (reuse the Wave 1 template structure in `WORKFLOW.md § Dispatching
with the Agent tool`):
- "You are working for Goddard. Read GODDARD.md and companion docs first."
- State exact files the lane owns and may not touch.
- Reference `arm_3d_printer.yaml` AND the `kind: composed` example in
  `SCHEMA.md` as the two canonical patterns.
- Require `hugo --minify` before reporting.
- Ask for a tight per-file summary.

Dispatch all 4 lanes in a single message for parallelism. Review each
returned summary against WORKFLOW.md's checklist before committing. One
integration commit: `Wave 2: <N> composed skills across <M> scenarios`.

## Rules for this session (do not relax)

- Never push to `main` (403). Always work on the feature branch.
- Recommend, don't decide. End meaningful turns with ≤3 options.
- Update companion docs if decisions drift. Docs are memory.
- Elderly-care mission gates every TRIGGER/SKIP. No hot surfaces, no open
  flame, no tactical framing, 90s translucent aesthetic in voice and form.
- Voice: warm, patient, clear. Competent home aide.
- Parallel-safety: two lanes never own the same file. Schema changes go
  through Goddard, not lanes.

## End-of-session

- Open the PR yourself (`mcp__github__create_pull_request`) with a body
  listing resolved questions (Phase A) and composed-skill counts (Phase B).
- Append the session URL per CLAUDE.md template.
- Confirm `hugo --minify` green one more time.
- Update `GODDARD.md` current state: Wave 2 count, any schema bumps.
