# API Data Map — Session Prompts

Each prompt below is a self-contained task you can hand to Sonnet in a new
session. They're ordered — do them in sequence. Copy-paste the prompt into a
new Claude Code session and let it run.

---

## Prompt 1: Build the YAML data file

> Read `API-DATA-MAP.md` for the full project spec. Create the file
> `data/api_map.yaml` following the schema defined in that doc. Include all
> 11 clusters with every API listed in the spec. For each API, include:
> name, url, shape, auth (none / free_key / free_tier), and a one-line
> `notes` field. Leave `project_ideas` as an empty list for now — we'll
> fill those in later. Validate the YAML with `python3 -c "import yaml;
> yaml.safe_load(open('data/api_map.yaml'))"`. Commit and push.

**What this teaches:** Data-driven content pattern — separating data (YAML)
from presentation (layout). Same pattern used by music.md, books.md, and
the monkey registry.

---

## Prompt 2: Build the layout template

> Read `API-DATA-MAP.md` for the project spec and `layouts/page/markets.html`
> for the visual precedent. Create `layouts/page/apis.html` that renders
> `data/api_map.yaml` as collapsible `<details>/<summary>` panels. Each
> cluster is a panel. Inside each panel, render each API as a card showing
> name (linked to url), shape, auth badge, and notes. Use the Markets page
> panel styling as a starting point — pink headers, black card backgrounds,
> gold accents. Also create `content/apis.md` with front matter:
> `title: "API Data Map"`, `layout: "apis"`, `type: "page"`,
> `description: "The data manifold"`. Run `hugo server` and verify the
> page renders at localhost:1313/apis/. Commit and push.

**What this teaches:** Hugo's `$.Site.Data` lookup pattern for rendering YAML
through templates. The `<details>/<summary>` pattern for no-JS interactivity.

---

## Prompt 3: Style the API map page

> Read `API-DATA-MAP.md` for the spec and look at the current state of
> `layouts/page/apis.html`. Add CSS to `assets/css/main.css` for the API
> map components. Key classes needed: `.api-map-page`, `.api-cluster`
> (the details/summary panel), `.api-card` (individual API entry),
> `.api-texture-badge` (small pill showing data shape like "time-series"),
> `.api-auth-badge` (green for no key, gold for free key, orange for free
> tier). Follow the theme guide in `CUNTY-THEME-GUIDE.md` — hot pink
> headers, black backgrounds, gold accents, outset borders. The first
> cluster should render open, the rest collapsed. Verify in browser,
> commit and push.

**What this teaches:** Working within an existing design system. CSS-only
interactive components. Reading a theme guide as a constraint doc.

---

## Prompt 4: Add the homepage card

> Add an "API Map" card to `layouts/index.html` in the section-cards grid.
> Use the globe emoji (&#128506;) as the icon, "API Map" as the title,
> "The data manifold" as the subtitle. Place it after the Markets card.
> Verify the homepage renders correctly with `hugo server`. Commit and push.

**What this teaches:** Small, surgical edits to shared templates. Keeping
changes minimal to avoid breaking other parts of the page.

---

## Prompt 5: Add project ideas to each API

> Read `data/api_map.yaml`. For each API entry, add 1-2 `project_ideas` —
> short descriptions of what you could build on Almond Farm using that API.
> Ideas should be specific to the site (not generic). Examples:
> - Open-Meteo → "7-day orchard forecast widget on the Farming page"
> - USGS Earthquake → "California seismic activity map in Brain section"
> - MusicBrainz → "Auto-populate the Music page from a YAML playlist"
> - TMDB → "Now-watching list for the Movies section"
> - Open Library → "Auto-fetch cover art for the Books reading list"
> Think about which existing empty sections (gaming, art, movies, drinks,
> body, gadgets) each API could fill. Validate YAML, commit and push.

**What this teaches:** Thinking about data as a resource that maps to product
features. Connecting APIs to actual use cases rather than collecting them
abstractly.

---

## Prompt 6: Add integration status tracking

> Read `data/api_map.yaml`. Add a `status` field to each API entry with
> one of: `idea` (not started), `planned` (spec written), `built` (code
> exists), `live` (deployed on site). For now, everything is `idea` except:
> - FRED → `built` (Markets page uses FRED data)
> Update `layouts/page/apis.html` to show a small status badge next to each
> API name. Colors: idea=dim gray, planned=gold, built=pink, live=green.
> This turns the API map into a project tracker — you can see at a glance
> what's wired up and what's still a possibility. Commit and push.

**What this teaches:** Using data fields as state machines. Evolving a
static catalog into a living project dashboard.

---

## Prompt 7: Connect the map to existing sections

> Read `API-DATA-MAP.md` and look at the "Relationship to existing sections"
> table. In `layouts/page/apis.html`, add a new section at the top of the
> page — a "Connections" panel that shows which APIs are linked to which
> site sections. Render it as a simple two-column grid: left column is the
> site section (linked), right column lists the APIs that could power it.
> Pull this data from a new top-level key in `api_map.yaml` called
> `connections`. Commit and push.

**What this teaches:** Cross-referencing data structures. Building navigation
that connects different parts of a site.

---

## Prompt 8: Add vanilla JS filters

> Read the current `layouts/page/apis.html`. Add a filter bar at the top
> of the page with three controls:
> 1. Texture dropdown (time-series, graph, corpus, spatial, event-stream)
> 2. Auth dropdown (any, no key, free key, free tier)
> 3. Text search box
> Implement in vanilla JS (no frameworks). Filters should show/hide API
> cards and auto-collapse empty clusters. Store filter state in the URL
> hash so you can link directly to a filtered view (e.g., `/apis/#texture=
> time-series`). Keep the JS in a separate file: `assets/js/api-map.js`.
> Commit and push.

**What this teaches:** Progressive enhancement — the page works without JS,
filters add interactivity. URL hash state for shareable views. Vanilla JS
DOM manipulation.

---

## Prompt 9: Pick 3 APIs and build data layers

> This is the payoff prompt. Pick 3 APIs from `data/api_map.yaml` that
> would fill empty sections on the site. For each one:
> 1. Write a fetch script in `scripts/` that pulls data and writes it to
>    a YAML file in `data/`
> 2. Create or update the layout to render that data
> 3. Update the API's status to `built` in `api_map.yaml`
>
> Good candidates:
> - **TMDB** → fill the Movies section with a "now watching" list
> - **Open Library** → fill the Books page with cover art + metadata
> - **CocktailDB** → fill the Drinks section with cocktail recipes
>
> For each, the pattern is: script fetches → YAML stores → template renders.
> Same pattern as the existing music/books/calendar data-driven pages.
> Commit and push.

**What this teaches:** The full data pipeline — fetch, store, render. This is
the core pattern for every future data integration on the site. Once you've
done it three times, you can do it for any API.

---

## Prompt 10: Write the live-update system

> Currently the Markets page uses static demo data. Design and implement a
> GitHub Actions workflow (`.github/workflows/update-data.yml`) that runs
> on a cron schedule (daily at 6am UTC) and:
> 1. Runs the fetch scripts from `scripts/` to pull fresh data
> 2. Commits updated YAML files to `main`
> 3. Triggers a Hugo rebuild + deploy
>
> Read the existing deploy workflow at `.github/workflows/deploy.yml` for
> patterns. The new workflow should be additive — don't modify the existing
> deploy flow. Use GitHub Secrets for any API keys (reference them as
> `${{ secrets.FRED_KEY }}` etc). Update `API-DATA-MAP.md` to document
> the automation. Commit and push.

**What this teaches:** CI/CD as a data pipeline. Cron-triggered workflows.
The pattern of "fetch → commit → deploy" that turns a static site into a
live dashboard without a backend server.

---

## How to use these prompts

1. Start a new Claude Code session
2. Copy-paste one prompt
3. Let Sonnet execute it
4. Review the PR, merge to main
5. Move to the next prompt

Each prompt builds on the previous one, but they're designed to be
independently mergeable — if prompt 3 needs tweaks, you can fix it
without redoing prompt 4.

The first 4 prompts give you a working page. Prompts 5-7 enrich it.
Prompt 8 adds interactivity. Prompts 9-10 are where it becomes a
real data platform.
