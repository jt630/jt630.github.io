# API Data Map — Technical Specification

A page at `/apis/` that catalogs free public APIs, organized into clusters by
domain. Serves as both a reference for the site owner and a planning tool for
deciding which data to integrate next.

---

## Files

| Action | Path |
|--------|------|
| CREATE | `content/apis.md` |
| CREATE | `data/api_map.yaml` |
| CREATE | `layouts/page/apis.html` |
| MODIFY | `assets/css/main.css` — append new classes at end of file |
| MODIFY | `layouts/index.html` — add one card to the section-cards grid |

---

## 1. Content file — `content/apis.md`

Exact front matter, nothing else in the file:

```yaml
---
title: "API Data Map"
description: "Free APIs organized by data domain — the starting point for any new data integration"
layout: "apis"
type: "page"
tabTitle: "API Map"
---
```

The layout is `apis`, type is `page`. Hugo resolves this to
`layouts/page/apis.html`.

---

## 2. Data file — `data/api_map.yaml`

### Schema

Every field is required unless marked optional.

```yaml
clusters:
  - name: string           # Display name of the cluster
    icon: string           # Single emoji
    texture: string        # Comma-separated data shape tags (see valid values below)
    description: string    # One sentence — what kind of data this cluster contains
    apis:
      - name: string           # API name as commonly known
        url: string            # Link to the API docs homepage
        shape: string          # What the data looks like (free text, 1 line)
        auth: enum             # One of: none | free_key | free_tier
        rate_limit: string     # optional — e.g. "10k/day", "60/min", "public"
        notes: string          # One sentence — what makes this API notable
        status: enum           # One of: idea | planned | built | live
        project_ideas:         # optional list — site-specific use cases
          - string
```

**Valid `auth` values:**
- `none` — no account, no key, just call the URL
- `free_key` — free account + API key required
- `free_tier` — freemium, key required, limited calls

**Valid `status` values:**
- `idea` — noted, not started
- `planned` — spec written somewhere in the repo
- `built` — code exists but not deployed
- `live` — deployed and working on the site

**Valid `texture` tags** (use comma-separated from this list):
`time-series` · `geographic` · `event-stream` · `graph` · `corpus` ·
`image-stream` · `spatial` · `taxonomy`

### Full example — one cluster

```yaml
clusters:
  - name: "Sky & Earth"
    icon: "🌍"
    texture: "time-series, geographic, event-stream"
    description: "The physical world instrumented — weather, climate, seismic, air quality"
    apis:
      - name: "Open-Meteo"
        url: "https://open-meteo.com/en/docs"
        shape: "hourly/daily forecast grids, historical climate"
        auth: "none"
        rate_limit: "10k/day"
        notes: "No key needed. Best free weather API. Historical back to 1940."
        status: "idea"
        project_ideas:
          - "7-day orchard forecast panel on the Farming page"
          - "Historical frost date chart for almond bloom risk"
      - name: "OpenWeatherMap"
        url: "https://openweathermap.org/api"
        shape: "current conditions, 5-day/3-hour forecast"
        auth: "free_key"
        rate_limit: "60/min"
        notes: "Most-used weather API. Free tier sufficient for a site widget."
        status: "idea"
      - name: "NOAA Climate Data Online"
        url: "https://www.ncdc.noaa.gov/cdo-web/webservices/v2"
        shape: "historical climate records, station data, normals"
        auth: "free_key"
        notes: "Authoritative US climate archive. Good for long-run farm analysis."
        status: "idea"
      - name: "USGS Earthquake Hazards"
        url: "https://earthquake.usgs.gov/fdsnws/event/1/"
        shape: "real-time seismic events, GeoJSON"
        auth: "none"
        notes: "All global earthquakes, updated every minute. No key needed."
        status: "idea"
      - name: "AirNow"
        url: "https://docs.airnowapi.org/"
        shape: "US air quality index by zip/location"
        auth: "free_key"
        notes: "EPA AQI data. Useful for farm air quality or wildfire smoke context."
        status: "idea"
      - name: "OpenAQ"
        url: "https://docs.openaq.org/"
        shape: "global air quality sensor readings"
        auth: "none"
        notes: "Community sensor network, global coverage, no key for basic queries."
        status: "idea"
      - name: "Sunrise-Sunset"
        url: "https://sunrise-sunset.org/api"
        shape: "sunrise/sunset/golden hour times by lat/lon"
        auth: "none"
        notes: "Simple, reliable. No key. Good for farm light-hour displays."
        status: "idea"
```

### All 11 clusters to populate

Build the full file with all APIs listed under each cluster. Do not skip any.

| # | Cluster | APIs to include |
|---|---------|----------------|
| 1 | Sky & Earth | Open-Meteo, OpenWeatherMap, NOAA CDO, USGS Earthquake, AirNow, OpenAQ, Sunrise-Sunset |
| 2 | Space | NASA APOD, NASA EONET, NASA Mars Rover Photos, NASA NEO, SpaceX API (r-spacex), Open Notify (ISS), Le Système Solaire |
| 3 | Living Things | iNaturalist, GBIF, Open Food Facts, USDA FoodData Central, TheDogAPI, TheCatAPI, PokeAPI |
| 4 | Culture & Knowledge | Open Library, Google Books, MusicBrainz, Last.fm, Discogs, TheMovieDB (TMDB), Open Trivia DB, Wikidata, Wikipedia REST, Harvard Art Museums, Met Museum (no key), Rijksmuseum |
| 5 | Words & Language | Datamuse, Free Dictionary API, Wordnik, PoetryDB, Project Gutenberg, Quotable |
| 6 | Civic & Government | US Census Bureau, Data.gov, Congress.gov API, Open States, FEC, BLS, FRED (St. Louis Fed), World Bank, UN Comtrade |
| 7 | Sports | MLB Stats API, NBA Stats (unofficial), TheSportsDB, Football-data.org, ESPN (unofficial) |
| 8 | Maps & Place | OpenStreetMap/Overpass, Nominatim, Open Elevation, GeoNames, REST Countries, IP-API |
| 9 | Money & Markets | Alpha Vantage, CoinGecko, ExchangeRate.host, Open Exchange Rates, Yahoo Finance (unofficial) |
| 10 | Transit & Infrastructure | Transit.land, Transport for London, WMATA, OpenSky Network, ADS-B Exchange |
| 11 | Dev & Social | GitHub REST, HackerNews, Lichess, Chess.com, CocktailDB |

All entries start with `status: idea`. The one exception: FRED gets `status: built`
because `layouts/page/markets.html` already references FRED data.

---

## 3. Layout — `layouts/page/apis.html`

### Hugo data access pattern

```html
{{ range .Site.Data.api_map.clusters }}
  <!-- cluster fields: .name .icon .texture .description .apis -->
  {{ range .apis }}
    <!-- api fields: .name .url .shape .auth .notes .status .project_ideas -->
  {{ end }}
{{ end }}
```

### Full template structure

```html
{{ define "main" }}
<div class="page-wrap">
  <div class="api-map-page">

    <div class="api-map-header">
      <h1>API DATA MAP</h1>
      <p class="api-map-subtitle">the data manifold — {{ len .Site.Data.api_map.clusters }} clusters</p>
    </div>

    {{ range $i, $cluster := .Site.Data.api_map.clusters }}
    <details class="api-cluster" {{ if eq $i 0 }}open{{ end }}>
      <summary class="api-cluster-summary">
        <span class="api-cluster-icon">{{ $cluster.icon }}</span>
        <span class="api-cluster-name">{{ $cluster.name }}</span>
        <span class="api-texture-badge">{{ $cluster.texture }}</span>
        <span class="api-cluster-count">{{ len $cluster.apis }}</span>
      </summary>
      <p class="api-cluster-desc">{{ $cluster.description }}</p>
      <div class="api-cards">
        {{ range $cluster.apis }}
        <div class="api-card" data-auth="{{ .auth }}" data-status="{{ .status }}">
          <div class="api-card-header">
            <a href="{{ .url }}" class="api-card-name" target="_blank" rel="noopener">{{ .name }}</a>
            <span class="api-auth-badge api-auth-{{ .auth }}">{{ .auth }}</span>
            <span class="api-status-badge api-status-{{ .status }}">{{ .status }}</span>
          </div>
          <p class="api-card-shape">{{ .shape }}</p>
          <p class="api-card-notes">{{ .notes }}</p>
          {{ with .rate_limit }}<p class="api-card-rate">rate: {{ . }}</p>{{ end }}
          {{ with .project_ideas }}
          <ul class="api-card-ideas">
            {{ range . }}<li>{{ . }}</li>{{ end }}
          </ul>
          {{ end }}
        </div>
        {{ end }}
      </div>
    </details>
    {{ end }}

  </div>
</div>
{{ end }}
```

### Key template decisions

- `{{ if eq $i 0 }}open{{ end }}` — first cluster open, rest collapsed, no JS needed
- `data-auth` and `data-status` attributes on each card — hooks for the JS filter (Ticket 8)
- `target="_blank" rel="noopener"` on all external links — security requirement
- `{{ with .rate_limit }}` — optional field, only renders if present
- `{{ with .project_ideas }}` — optional field, only renders if list is non-empty

---

## 4. CSS additions — append to `assets/css/main.css`

Add a clearly-labelled section at the bottom of the file. Do not modify existing
styles. Class names below are exact — the template uses them.

```css
/* ===========================
   API DATA MAP PAGE
   /apis/
   =========================== */

.api-map-page {
  max-width: 860px;
  margin: 0 auto;
  padding: 2rem 1.5rem;
}

.api-map-header {
  margin-bottom: 2rem;
}

.api-map-header h1 {
  font-family: 'Courier New', Courier, monospace;
  font-size: 2rem;
  font-weight: bold;
  color: var(--pink);
  text-transform: uppercase;
  letter-spacing: 0.15em;
  text-shadow: 0 0 20px var(--pink-glow);
}

.api-map-subtitle {
  font-size: 0.85rem;
  color: var(--white-dim);
  letter-spacing: 0.08em;
  margin-top: 0.25rem;
}

/* Cluster (details/summary) */

.api-cluster {
  background: var(--black-card);
  border: 1px solid rgba(212, 175, 55, 0.15);
  border-top: 2px solid var(--gold);
  border-radius: var(--radius);
  margin-bottom: 0.75rem;
}

.api-cluster-summary {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.9rem 1.25rem;
  cursor: pointer;
  list-style: none;
  user-select: none;
}

.api-cluster-summary::-webkit-details-marker { display: none; }

.api-cluster-summary:hover {
  background: var(--black-elevated);
}

.api-cluster[open] .api-cluster-summary {
  border-bottom: 1px solid rgba(212, 175, 55, 0.12);
}

.api-cluster-icon {
  font-size: 1.1rem;
}

.api-cluster-name {
  font-family: 'Courier New', Courier, monospace;
  font-size: 0.8rem;
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 0.15em;
  color: var(--gold);
  text-shadow: 0 0 8px rgba(212,175,55,0.6);
  flex: 1;
}

.api-cluster-count {
  font-size: 0.75rem;
  color: var(--white-faint);
  font-family: 'Courier New', Courier, monospace;
}

.api-cluster-desc {
  font-size: 0.82rem;
  color: var(--white-dim);
  padding: 0.5rem 1.25rem 0.25rem;
  font-style: italic;
}

/* Texture badge */

.api-texture-badge {
  font-size: 0.68rem;
  color: var(--white-faint);
  letter-spacing: 0.04em;
  font-family: 'Courier New', Courier, monospace;
  display: none; /* show on wider screens */
}

@media (min-width: 600px) {
  .api-texture-badge { display: inline; }
}

/* API cards grid */

.api-cards {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0;
  padding: 0.5rem 1.25rem 1rem;
}

.api-card {
  padding: 0.75rem 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.api-card:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.api-card-header {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.2rem;
}

.api-card-name {
  font-size: 0.92rem;
  font-weight: 600;
  color: var(--pink);
  text-decoration: none;
  letter-spacing: 0.02em;
}

.api-card-name:hover {
  text-decoration: underline;
  text-shadow: 0 0 8px var(--pink-glow);
}

.api-card-shape {
  font-size: 0.8rem;
  color: var(--white-dim);
  margin-bottom: 0.15rem;
}

.api-card-notes {
  font-size: 0.78rem;
  color: var(--white-faint);
}

.api-card-rate {
  font-size: 0.72rem;
  color: var(--white-faint);
  font-family: 'Courier New', Courier, monospace;
  margin-top: 0.15rem;
}

.api-card-ideas {
  margin-top: 0.35rem;
  padding-left: 1rem;
  list-style: none;
}

.api-card-ideas li::before {
  content: "→ ";
  color: var(--gold);
}

.api-card-ideas li {
  font-size: 0.78rem;
  color: var(--white-dim);
  margin-bottom: 0.1rem;
}

/* Auth badges */

.api-auth-badge {
  font-size: 0.65rem;
  font-family: 'Courier New', Courier, monospace;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 0.1rem 0.4rem;
  border-radius: 2px;
  white-space: nowrap;
}

.api-auth-none {
  background: rgba(0, 200, 100, 0.15);
  color: #00C864;
  border: 1px solid rgba(0, 200, 100, 0.3);
}

.api-auth-free_key {
  background: rgba(212, 175, 55, 0.1);
  color: var(--gold);
  border: 1px solid rgba(212, 175, 55, 0.25);
}

.api-auth-free_tier {
  background: rgba(255, 140, 0, 0.1);
  color: #FF8C00;
  border: 1px solid rgba(255, 140, 0, 0.25);
}

/* Status badges */

.api-status-badge {
  font-size: 0.6rem;
  font-family: 'Courier New', Courier, monospace;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 0.1rem 0.35rem;
  border-radius: 2px;
  white-space: nowrap;
}

.api-status-idea    { color: rgba(245,240,235,0.25); border: 1px solid rgba(245,240,235,0.1); }
.api-status-planned { color: var(--gold); border: 1px solid rgba(212,175,55,0.3); }
.api-status-built   { color: var(--pink); border: 1px solid rgba(255,45,138,0.3); }
.api-status-live    { color: #00FF41; border: 1px solid rgba(0,255,65,0.3); }
```

---

## 5. Homepage card — modify `layouts/index.html`

In `layouts/index.html`, add one `<a>` block inside the `.section-cards` div,
**after** the Markets card (the one with `href="/markets/"`):

```html
<a href="/apis/" class="section-card apis">
  <span class="card-icon">&#128506;</span>
  <h3>API Map</h3>
  <p>The data manifold</p>
</a>
```

That is the only change to `layouts/index.html`.

---

## 6. Build verification

After all files are created, run:

```bash
hugo --minify
```

Expected: exits with 0 errors. If it fails, fix before committing.

Also check:
- `hugo server` → visit `localhost:1313/apis/` — page renders
- First cluster is open, rest collapsed
- All cluster names appear in the summary rows
- No broken links in nav or homepage card grid
- `python3 -c "import yaml; yaml.safe_load(open('data/api_map.yaml'))"` exits cleanly

---

## Out of scope for initial build

These are tracked in `TODO-API-MAP-PROMPTS.md` as later tickets:

- Vanilla JS filter bar (texture/auth/search)
- `connections` panel linking APIs to site sections
- Fetch scripts for live data
- GitHub Actions cron workflow

Do not build these in the initial pass. Get the static catalog working first.
