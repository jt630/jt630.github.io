# API Data Map — Developer Tickets

Each ticket is a self-contained unit of work. Complete them in order —
each one depends on the previous being merged to `main`.

To hand a ticket to Sonnet: start a new session and say
**"Read `TODO-API-MAP-PROMPTS.md` and execute Ticket N."**

---

## Ticket 1 — Build the YAML data catalog

**Status:** done — `data/api_map.yaml` exists, validates, 11 clusters
**Depends on:** nothing
**Branch:** new branch off `main`

### Context

The API map page is data-driven. All API data lives in `data/api_map.yaml`
and is read by the Hugo template at build time — same pattern as
`data/calendar_events.yaml` and `data/seasons.yaml`. This ticket creates
the data file. No layout work yet.

### Spec

Read `API-DATA-MAP.md` section "2. Data file" — it contains the full YAML
schema, field definitions, valid enum values, and a complete example cluster.

### Deliverables

- `data/api_map.yaml` — the complete catalog

### Requirements

- All 11 clusters from the table in `API-DATA-MAP.md` section 2
- Every cluster has: `name`, `icon`, `texture`, `description`, `apis`
- Every API entry has: `name`, `url`, `shape`, `auth`, `notes`, `status`
- `rate_limit` and `project_ideas` are optional — include where known, omit where not
- `auth` must be exactly one of: `none`, `free_key`, `free_tier`
- `status` must be exactly one of: `idea`, `planned`, `built`, `live`
- All entries use `status: idea` except FRED which uses `status: built`
- No placeholder comments like `# ... etc` — every API in the table is fully written

### Acceptance criteria

- [ ] `python3 -c "import yaml; yaml.safe_load(open('data/api_map.yaml'))"` exits without error
- [ ] File has exactly 11 top-level clusters
- [ ] Every API entry has all required fields
- [ ] No `auth` value outside the allowed enum
- [ ] FRED entry has `status: built`, everything else has `status: idea`

### Do not

- Do not create any layout files yet
- Do not modify any existing files

### Commit message

`data: add api_map.yaml — full catalog of 11 clusters, ~60 free APIs`

---

## Ticket 2 — Build the Hugo layout template

**Status:** done — `/apis/` renders from `layouts/page/apis.html`
**Depends on:** Ticket 1
**Branch:** new branch off `main`

### Context

The layout reads `data/api_map.yaml` and renders it as collapsible
`<details>/<summary>` panels — one per cluster. Uses no JavaScript.
The visual pattern follows `layouts/page/markets.html` (read it as reference).

### Spec

Read `API-DATA-MAP.md` sections "1. Content file" and "3. Layout".
Section 3 has the exact Hugo template — copy it, do not rewrite it.

### Deliverables

- `content/apis.md` — front matter only, exact content in spec section 1
- `layouts/page/apis.html` — Hugo template, exact structure in spec section 3

### Requirements

- `content/apis.md` front matter: `layout: "apis"`, `type: "page"` — exactly as in spec
- Template uses `{{ range $i, $cluster := .Site.Data.api_map.clusters }}`
- First cluster has `open` attribute: `{{ if eq $i 0 }}open{{ end }}`
- All external links have `target="_blank" rel="noopener"`
- Optional fields (`rate_limit`, `project_ideas`) wrapped in `{{ with }}` blocks
- `data-auth` and `data-status` attributes on each `.api-card` div

### Acceptance criteria

- [ ] `hugo --minify` exits with 0 errors
- [ ] `localhost:1313/apis/` renders without a blank page or Hugo error
- [ ] All 11 cluster names appear on the page
- [ ] First cluster is open by default, rest collapsed
- [ ] Clicking a cluster summary toggles it open/closed
- [ ] API names are clickable links opening in a new tab
- [ ] No hardcoded API data in the template — all rendered from YAML

### Do not

- Do not add CSS yet — unstyled is fine, that's Ticket 3
- Do not modify `layouts/index.html` yet — that's Ticket 4
- Do not modify `assets/css/main.css`

### Commit message

`feat: add /apis/ layout — collapsible cluster panels from api_map.yaml`

---

## Ticket 3 — Style the API map page

**Status:** done — `API DATA MAP PAGE` section present in `assets/css/main.css`
**Depends on:** Ticket 2
**Branch:** new branch off `main`

### Context

The page exists and renders but has no custom styles. This ticket adds the
CSS. All new styles are appended to the bottom of `assets/css/main.css`
under a clearly-labelled section header. No existing styles are modified.

### Spec

Read `API-DATA-MAP.md` section "4. CSS additions" — it has the exact CSS
block to add, including class names and property values. Copy it exactly.

Also read `CUNTY-THEME-GUIDE.md` to understand the design system variables
(`--pink`, `--gold`, `--black-card`, etc.) before making any adjustments.

### Deliverables

- `assets/css/main.css` — new section appended at the bottom

### Requirements

- CSS is appended after the last existing rule — do not insert into the middle
- Section header comment matches: `/* === API DATA MAP PAGE / /apis/ === */`
- Class names match exactly what the template uses (they're in `layouts/page/apis.html`)
- Auth badge colors: `none` = green (`#00C864`), `free_key` = gold, `free_tier` = orange
- Status badge colors: `idea` = dim, `planned` = gold, `built` = pink, `live` = green
- Uses CSS variables from `:root` — no hardcoded hex except the two greens not in the palette
- Texture badge hidden on mobile, visible at 600px+

### Acceptance criteria

- [ ] `hugo --minify` exits with 0 errors
- [ ] `localhost:1313/apis/` — page looks styled (not plain HTML)
- [ ] Cluster headers are gold, monospace, uppercase
- [ ] API names are pink and underline on hover
- [ ] Auth badges are color-coded (green/gold/orange)
- [ ] Status badges visible next to each API name
- [ ] First cluster open and readable, remaining clusters show summary row
- [ ] No existing page is broken (check homepage and `/markets/`)

### Do not

- Do not modify any existing CSS rules
- Do not change class names in the template to match different CSS — adjust CSS to match template
- Do not add a `<style>` block to the layout file — all CSS goes in `main.css`

### Commit message

`style: add api-map CSS — cluster panels, api cards, auth/status badges`

---

## Ticket 4 — Add the homepage card

**Status:** done — API Map card present on `/`
**Depends on:** Ticket 3
**Branch:** new branch off `main`

### Context

Every section on the site has a card on the homepage. The API Map needs one.
This is a single `<a>` block added to `layouts/index.html`. Nothing else changes.

### Spec

Read `API-DATA-MAP.md` section "5. Homepage card" — it has the exact HTML.

### Deliverables

- `layouts/index.html` — one `<a>` block added

### Requirements

- Exact HTML from spec section 5
- Placed inside `.section-cards`, immediately after the Markets card
  (the `<a href="/markets/" ...>` block)
- Uses `&#128506;` as the card icon (globe with meridians)

### Acceptance criteria

- [ ] `hugo --minify` exits with 0 errors
- [ ] Homepage at `localhost:1313/` shows an "API Map" card
- [ ] Clicking the card navigates to `/apis/`
- [ ] No other cards are shifted or broken

### Do not

- Do not change any other part of `layouts/index.html`
- Do not add CSS for the card — it inherits `.section-card` styles

### Commit message

`feat: add API Map card to homepage`

---

## Ticket 5 — Add project ideas to every API

**Status:** done — all 74 APIs have `project_ideas`
**Depends on:** Ticket 4
**Branch:** new branch off `main`

### Context

The YAML has `project_ideas` as an optional field. Most entries currently
have none. This ticket fills them in — every API gets 1-2 ideas specific
to Almond Farm. These show up as a `→ idea` list under each API card.

### Requirements

- Every API gets at least 1 `project_ideas` entry
- Ideas are specific to Almond Farm — not generic "you could build a dashboard"
- Ideas reference existing sections where possible:
  `blog`, `cooking`, `farming`, `music`, `books`, `gallery`, `gaming`, `art`,
  `movies`, `drinks`, `brain`, `body`, `gadgets` — or propose a new section
- Priority connections to fill empty sections: `gaming`, `art`, `movies`,
  `drinks`, `body`, `gadgets`
- Keep each idea under 12 words
- Do not change any other field in the YAML

### Acceptance criteria

- [ ] `python3 -c "import yaml; yaml.safe_load(open('data/api_map.yaml'))"` exits without error
- [ ] Every API entry has a `project_ideas` list with at least 1 item
- [ ] No idea is a generic placeholder
- [ ] `hugo --minify` exits with 0 errors
- [ ] Ideas render on the page at `localhost:1313/apis/`

### Commit message

`data: add project_ideas to all APIs in api_map.yaml`

---

## Ticket 6 — Add vanilla JS filter bar

**Status:** done — `assets/js/api-map.js` exists, filter bar wired into the page
**Depends on:** Ticket 5
**Branch:** new branch off `main`

### Context

The page currently shows all clusters at once. A filter bar lets the user
narrow by auth level or search by name. The page already works without JS
(progressive enhancement) — filters are additive.

### Deliverables

- `assets/js/api-map.js` — new file, all filter logic
- `layouts/page/apis.html` — add filter bar HTML + script tag
- `assets/css/main.css` — append filter bar styles

### Filter bar HTML to add inside `.api-map-page`, before the first cluster

```html
<div class="api-filter-bar" id="api-filter-bar">
  <select id="api-filter-auth" class="api-filter-select">
    <option value="">all auth levels</option>
    <option value="none">no key</option>
    <option value="free_key">free key</option>
    <option value="free_tier">free tier</option>
  </select>
  <select id="api-filter-status" class="api-filter-select">
    <option value="">all status</option>
    <option value="idea">idea</option>
    <option value="planned">planned</option>
    <option value="built">built</option>
    <option value="live">live</option>
  </select>
  <input type="search" id="api-filter-search" class="api-filter-input"
         placeholder="search APIs...">
  <button id="api-filter-clear" class="api-filter-clear">clear</button>
</div>
```

### JS behavior requirements

- Filters apply on `input`/`change` events — no submit button
- Auth filter: hide `.api-card` elements where `data-auth` does not match
- Status filter: hide `.api-card` elements where `data-status` does not match
- Search filter: hide `.api-card` where the API name (`.api-card-name` text) does not
  contain the search string (case-insensitive)
- After filtering, if a cluster has 0 visible cards, collapse it (`details.open = false`)
  and add class `api-cluster--empty`; remove when filters are cleared
- Clear button resets all three controls and shows everything
- Store filter state in URL hash as `#auth=none&search=foo` so filtered views are
  shareable. Restore state from hash on page load.
- No external libraries. Vanilla JS only. No `eval`. No `innerHTML` for user input.

### Acceptance criteria

- [ ] `hugo --minify` exits with 0 errors
- [ ] Filter bar appears above the clusters
- [ ] Auth dropdown hides/shows cards correctly
- [ ] Status dropdown hides/shows cards correctly
- [ ] Search box filters by API name as you type
- [ ] Empty clusters collapse automatically
- [ ] Clear button restores all cards
- [ ] URL hash updates as filters change; loading the URL with a hash restores filters
- [ ] Page works identically with JS disabled (clusters still expand/collapse)

### Commit message

`feat: add filter bar to /apis/ — auth, status, search with URL hash state`

---

## Ticket 7 — Build 3 live data integrations

**Status:** partial (2026-08-16 audit) — CocktailDB is done: `scripts/fetch_cocktails.py`
exists, `data/cocktails.yaml` is populated, `/drinks/` renders it. TMDB and Open
Library were never run: no `data/movies.yaml`, no `data/books.yaml`, both still
`status: idea` in `api_map.yaml`, and there is no `TMDB_KEY` repo secret configured
(`gh secret list` only shows `FRED_API_KEY` and `OWM_API_KEY`). `/movies/` currently
renders empty since its template ranges over `.Site.Data.movies`, which doesn't exist.
Remaining work: get a TMDB key, add it as a repo secret, run
`fetch_movies.py` and `fetch_book_covers.py`, flip both statuses to `built`.
**Depends on:** Ticket 6
**Branch:** new branch off `main`

### Context

The API map page shows what could be built. This ticket builds three of them,
filling three currently-empty sections of the site. Each integration follows
the same pattern already used by `data/calendar_events.yaml`:
**fetch script writes YAML → Hugo template reads YAML → page renders.**

### Integrations to build

**A. CocktailDB → `/drinks/`**
- API: `https://www.thecocktaildb.com/api/json/v1/1/` (no key needed)
- Script: `scripts/fetch_cocktails.py` — fetches 12–20 cocktails, writes `data/cocktails.yaml`
- Schema: `[ { name, glass, category, instructions, ingredients: [str], thumb_url } ]`
- Layout: `layouts/drinks/list.html` — grid of cocktail cards with name, glass type, ingredient list
- Content: `content/drinks/_index.md` (if it doesn't exist)

**B. TheMovieDB (TMDB) → `/movies/`**
- API: `https://api.themoviedb.org/3/` (free key required — use `data/keys.yaml` or env var)
- Script: `scripts/fetch_movies.py` — fetches "now popular" movies, writes `data/movies.yaml`
- Schema: `[ { title, year, overview, poster_path, tmdb_id, vote_average } ]`
- Layout: `layouts/movies/list.html` — poster grid with title, year, rating
- Poster URL pattern: `https://image.tmdb.org/t/p/w300{poster_path}`
- Content: `content/movies/_index.md` (if it doesn't exist)

**C. Open Library → `/books/`**
- API: `https://openlibrary.org/api/` (no key needed)
- The existing `content/books.md` may already have a reading list — read it first
- Script: `scripts/fetch_book_covers.py` — for each book in `data/books.yaml`,
  fetch cover URL from Open Library by ISBN or title, add `cover_url` field
- Layout: update `layouts/_default/single.html` or create a books-specific layout
  to show cover images if `cover_url` is present

### For each integration

1. Create the fetch script in `scripts/`
2. Run it once manually to generate the YAML in `data/`
3. Create or update the layout to render the data
4. Update the API's `status` in `data/api_map.yaml` to `built`
5. Verify the page renders at the correct URL

### Acceptance criteria

- [ ] `scripts/fetch_cocktails.py` runs and writes `data/cocktails.yaml`
- [ ] `/drinks/` renders cocktail cards with name, glass, ingredients
- [ ] `scripts/fetch_movies.py` runs and writes `data/movies.yaml`
- [ ] `/movies/` renders a movie grid with posters and titles
- [ ] `scripts/fetch_book_covers.py` runs and enriches `data/books.yaml` with cover URLs
- [ ] `/books/` renders book covers where available
- [ ] All three APIs have `status: built` in `data/api_map.yaml`
- [ ] `hugo --minify` exits with 0 errors
- [ ] All three pages look consistent with the site theme

### Do not

- Do not hardcode the TMDB API key — read it from an environment variable `TMDB_KEY`
  or from `data/keys.yaml` (gitignored file the user creates locally)
- Do not commit API keys to the repo
- Do not fetch more than 20 items per script — keep data files small
- Do not build a backend — fetch runs locally, output is static YAML

### Commit message

`feat: live data — cocktails (CocktailDB), movies (TMDB), book covers (Open Library)`

---

## Ticket 8 — GitHub Actions cron: auto-refresh data

**Status:** partial (2026-08-16 audit) — `.github/workflows/refresh-data.yml` exists
but is missing the required `schedule: - cron: '0 6 * * *'` trigger (currently
`workflow_dispatch` only, so it never runs automatically). It also has a latent bug:
the commit step runs `git add data/cocktails.yaml data/movies.yaml data/books.yaml`,
and since the latter two files don't exist yet (see Ticket 7), that `git add` will
fail the first time this workflow actually runs. Fix depends on Ticket 7 landing first.
**Depends on:** Ticket 7
**Branch:** new branch off `main`

### Context

The fetch scripts run manually now. This ticket schedules them to run
automatically every day so the data stays fresh without manual intervention.
A GitHub Actions workflow runs the scripts, commits updated YAML, and triggers
the existing deploy.

### Deliverables

- `.github/workflows/refresh-data.yml` — new workflow file

### Requirements

Read the existing `.github/workflows/deploy.yml` before writing anything.
The new workflow must not modify or replace it.

```yaml
# Structure of refresh-data.yml

name: Refresh API data
on:
  schedule:
    - cron: '0 6 * * *'   # daily at 6am UTC
  workflow_dispatch:        # allow manual trigger from GitHub Actions UI

jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install requests pyyaml
      - run: python scripts/fetch_cocktails.py
      - run: python scripts/fetch_movies.py
        env:
          TMDB_KEY: ${{ secrets.TMDB_KEY }}
      - name: Commit updated data
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/cocktails.yaml data/movies.yaml data/books.yaml
          git diff --cached --quiet || git commit -m "data: auto-refresh [skip ci]"
          git push
```

- `[skip ci]` in the commit message prevents the data commit from triggering
  another deploy cycle — but the deploy workflow should already be watching
  for pushes to `main` and will fire on the next push that doesn't skip CI
- `TMDB_KEY` is stored as a GitHub Actions secret — document this in the PR description
- Do not run `fetch_book_covers.py` on cron — it enriches a hand-curated list,
  not a feed. Run it manually when the books list changes.

### Acceptance criteria

- [ ] `.github/workflows/refresh-data.yml` exists and is valid YAML
- [ ] Workflow appears in GitHub Actions tab
- [ ] Manual trigger (`workflow_dispatch`) runs successfully
- [ ] After a manual run, `data/cocktails.yaml` and `data/movies.yaml` are updated
- [ ] No API keys appear in the workflow file — only `secrets.*` references
- [ ] `[skip ci]` present in the auto-commit message

### Commit message

`ci: add daily data refresh workflow for cocktails and movies`

---

## Summary

| Ticket | What gets built | Status |
|--------|----------------|-----------|
| 1 | `data/api_map.yaml` | ✅ done |
| 2 | `layouts/page/apis.html` + `content/apis.md` | ✅ done |
| 3 | CSS for the page | ✅ done |
| 4 | Homepage card | ✅ done |
| 5 | Project ideas in YAML | ✅ done |
| 6 | JS filter bar | ✅ done |
| 7 | 3 live integrations | ⚠ partial — CocktailDB/`/drinks/` done; TMDB/`/movies/` and Open Library/`/books/` not started |
| 8 | Cron workflow | ⚠ partial — file exists, missing daily schedule, has a bug that will fail on first real run (depends on Ticket 7) |

Audited 2026-08-16 against the live repo state, not just this doc's prior claims.
