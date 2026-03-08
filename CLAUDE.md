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

`gh` CLI is **not available** in this environment. PRs must be created through the GitHub web UI.

**After pushing your branch**, open a PR immediately:

1. Go to **[github.com/jt630/jt630.github.io/compare](https://github.com/jt630/jt630.github.io/compare)**
2. Set **base:** `main` ← **compare:** `claude/your-branch-name`
3. Click **"Create pull request"**
4. Fill in the template below, then **submit**
5. Merge when ready — the deploy workflow fires automatically on merge to `main`

**Shortcut:** after pushing, GitHub usually shows a yellow
**"Compare & pull request"** banner at the top of the repo — click it.

### PR description template

```markdown
## Summary
- bullet points of what changed

## Test plan
- [ ] hugo build passes
- [ ] checked in browser at localhost:1313
- [ ] no layout breakage on mobile

https://claude.ai/code/session_[SESSION_ID]
```

> **Note:** Always include the session URL at the bottom of the PR body.
> It links this PR to the Claude session that made the changes.

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
