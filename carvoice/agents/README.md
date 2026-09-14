# CarVoice Agent Roster

Eight role-context files, one per concern. These are plain markdown, not
registered Claude Code subagents — point a session at one (or paste its
contents in) when the work fits that role, instead of re-explaining scope
each time.

| File | Role | One-line scope |
|---|---|---|
| [`research.md`](research.md) | Research | OBD2/PID/DTC reference, library docs, competitor feature/pricing facts — no verdicts |
| [`coder.md`](coder.md) | Coding | Builds `scripts/carvoice/*.py`, eventually `layouts/carvoice/` |
| [`hardware.md`](hardware.md) | Hardware | Adapter selection, vehicle compatibility, connection troubleshooting |
| [`pm.md`](pm.md) | PM | Keeps `CARVOICE.md` Status/Session Log/Build Plan accurate; sequences work |
| [`qa.md`](qa.md) | QA | Verifies scripts/data actually run and parse before anything is "done" |
| [`mechanic-reviewer.md`](mechanic-reviewer.md) | Mechanic reviewer | Judges whether a generated diagnosis is safe and correct — the "grandpa validates it" step |
| [`analyst.md`](analyst.md) | Analyst | Crunches CarVoice's own drive-log trends, health-score math, unit economics |
| [`business.md`](business.md) | Business | Is this already done by someone else, is it worth building — viability verdict |

All eight read `CARVOICE.md` first. None of them cover other Almond Farm
content (blog, farming, Monkeys) — each file says so explicitly.
