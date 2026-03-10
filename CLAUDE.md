# Almond Farm — Claude Code Guide

A Hugo static site deployed to GitHub Pages at [almondfarm.us](https://almondfarm.us).

## Stack

- **Hugo 0.139.0 extended** — static site generator
- **Single CSS file** — `assets/css/main.css` (~900 lines, no framework)
- **Vanilla JS** — only a hamburger menu toggle in `baseof.html`
- **GitHub Actions** — auto-deploys on push to `main` (`.github/workflows/deploy.yml`)

## Key commands

```bash
hugo server          # local dev server at localhost:1313
hugo --minify        # production build → ./public/
hugo new content/blog/my-post.md   # scaffold a post (or use /new-post)
```

## Content structure

```
content/
├── blog/       ← narrative posts
├── cooking/    ← recipes
├── farming/    ← farm dispatches
├── music.md    ← rendered from data/music.yaml
├── books.md    ← rendered from data/books.yaml
├── gallery.md  ← scans static/images/gallery/
├── about.md    ← rendered from data/contributors.yaml
└── gaming/ art/ movies/ drinks/ brain/ body/ gadgets/  ← empty, fill freely
```

Data-driven sections (music, books) get their content from `data/`. Gallery pulls
from `static/images/gallery/`. Everything else is markdown in `content/`.

### Monkeys subsystem

The Infinite Monkey Theorem project lives under `content/monkeys/`. Full design
spec, architecture, and build plan are in **`MONKEYS.md`** — read it before any
monkeys session.

Key files:
- `MONKEYS.md` — project spec, design decisions, and session build plans
- `data/monkey_registry.yaml` — one entry per language (name, coins, progress)
- `data/dictionaries/{lang}.txt` — word lists per language *(to be built)*
- `data/hamlet/{lang}.txt` — Hamlet plaintext per language *(to be built)*
- `scripts/generate_monkey_post.py` — mint script *(to be built)*
- `scripts/hamlet_scan.py` — Hamlet n-gram scanner *(to be built)*
- `content/monkeys/{lang}_{YYYYMMDD}.md` — individual coin posts
- `layouts/monkeys/` — coin display templates

## Layouts

- `layouts/_default/baseof.html` — master shell (nav, marquee ticker, footer)
- `layouts/index.html` — homepage (hero + 14 section cards + latest posts)
- `layouts/_default/single.html` — individual post
- `layouts/_default/list.html` — section list pages
- `layouts/brain/list.html` — custom Brain Lab page (design experiments)
- `layouts/partials/` — nav, footer, post-card, contributors

## Theme

Hot pink (`#FF2D8A`) · Black (`#0A0A0A`) · Gold (`#D4AF37`). See `CUNTY-THEME-GUIDE.md`
for the full palette and component reference.

Current 2000s additions: crosshair cursor, Impact hero font, outset card borders,
marquee ticker, blinking NEW! badge, visitor counter in footer.

---

## Git workflow

### Branch naming

All work goes on a feature branch. Branch names must follow this pattern:

```
claude/[short-description]-[SESSION_ID_SUFFIX]
```

Example: `claude/2000s-style-updates-K4Nh1`

The session ID suffix is provided in your system prompt at the start of each session.
**Never push directly to `main`** — it's protected and will return a 403.

### Day-to-day flow

```bash
# 1. Create or switch to your feature branch
git checkout -b claude/my-feature-AbCdE
# or if it already exists:
git checkout claude/my-feature-AbCdE

# 2. Make changes, then commit
git add <specific files>
git commit -m "Short description of what and why"

# 3. Push
git push -u origin claude/my-feature-AbCdE
```

### Opening a Pull Request

`gh` CLI is not available in this environment. Open PRs through the GitHub web UI:

1. Push your branch (step 3 above)
2. Go to **github.com/jt630/jt630.github.io**
3. GitHub will show a **"Compare & pull request"** banner for your recently pushed branch — click it
4. Or go to **Pull requests → New pull request** and select your branch as the compare branch
5. Set base branch to `main`
6. Write a title + summary, then **Create pull request**
7. Merge when ready — the deploy workflow fires automatically on merge to `main`

### PR description template

```
## Summary
- bullet points of what changed

## Test plan
- [ ] hugo build passes
- [ ] checked in browser at localhost:1313
- [ ] no layout breakage on mobile
```

### Checking build before pushing

```bash
hugo --minify
# If it exits cleanly the deploy will work.
# Build output goes to ./public/ (gitignored).
```

---

## Slash commands

| Command | What it does |
|---------|-------------|
| `/new-post` | Scaffolds a new Hugo post — asks for section, title, description |
| `/mint` | Mint a monkey coin — picks language, runs generation, commits *(planned)* |

## Claude Code best practices for this project

These patterns apply across sessions. Follow them.

### Parallel agents for research
When a task requires looking up multiple independent things (baby names for 10
countries, dictionaries for 10 languages, checking 10 files), use **parallel
Agent calls** — launch them all in one message. Don't research sequentially.

### Worktree isolation for risky experiments
When trying something that might break the site (new layout, big CSS refactor,
theme experiment), use `isolation: "worktree"` on the Agent tool. This gives
you a throwaway copy of the repo. If it works, merge it. If not, it disappears.

### Build verification
Always run `hugo --minify` after making changes and before committing. The
session-start hook checks this automatically, but you should verify after
each significant change too.

### Read MONKEYS.md first
Before any monkeys session, read `MONKEYS.md`. It contains design decisions,
front matter schema, naming conventions, and the session build plan. Without
it you'll make decisions that conflict with prior work.
