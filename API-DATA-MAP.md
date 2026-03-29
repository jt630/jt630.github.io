# API Data Map — Project Outline

A new section on Almond Farm: a visual catalog of free public APIs, organized as
a browsable "manifold" of data localities. Pick a cluster, see what's available,
and spin up a data-driven page from it.

## Why this page

The site already has data-driven sections (Markets, Calendar, Music, Books) but
choosing *which* data to build next requires knowing what's out there. This page
is both a reference for the site owner and a public resource — a curated map of
the free-data internet.

## Design

### Page location
- **Content:** `content/apis.md` (front matter only, like markets.md)
- **Data:** `data/api_map.yaml` (the full catalog)
- **Layout:** `layouts/page/apis.html` (custom template)
- **URL:** `/apis/`

### Homepage card
Add to `layouts/index.html`:
```html
<a href="/apis/" class="section-card apis">
  <span class="card-icon">&#128506;</span>  <!-- 🗺 -->
  <h3>API Map</h3>
  <p>The data manifold</p>
</a>
```

### Visual concept
Think of it as a dark terminal-style explorer. Each **cluster** (Sky & Earth,
Culture, Civic, etc.) is a collapsible panel — same aesthetic as the Markets
page panels. Inside each cluster:

- **API name** — bold, pink
- **Data shape** — what the data looks like (time-series, graph, corpus, etc.)
- **Auth** — no key / free key / free tier
- **Rate limit** — if notable
- **URL** — link to docs
- **Project ideas** — 1-2 sentence suggestions for what you could build

Each cluster also has a header badge showing the "texture" of the data
(time-series, spatial, graph, corpus) so you can scan the page by data shape.

### Data schema (`data/api_map.yaml`)

```yaml
clusters:
  - name: "Sky & Earth"
    icon: "🌍"
    texture: "time-series, geographic, sensor streams"
    description: "Weather, climate, seismic, air quality — the physical world instrumented"
    apis:
      - name: "Open-Meteo"
        url: "https://open-meteo.com/"
        shape: "time-series weather, forecast grids"
        auth: "none"
        rate_limit: "10k/day"
        notes: "Best free weather API. Historical + forecast. No key needed."
        project_ideas:
          - "Farm weather dashboard with 7-day forecast for the orchard"
          - "Historical frost date analysis for bloom planning"
      - name: "USGS Earthquake"
        url: "https://earthquake.usgs.gov/fdsnws/event/1/"
        shape: "real-time event stream, GeoJSON"
        auth: "none"
        notes: "All global seismic events. Updated every minute."
        project_ideas:
          - "Live earthquake map with magnitude filtering"
  # ... etc
```

### Layout structure (`layouts/page/apis.html`)

```
┌─────────────────────────────────────────┐
│  API DATA MAP                           │
│  the data manifold                      │
│                                         │
│  [filter by: texture ▾] [auth ▾]        │
├─────────────────────────────────────────┤
│  ▼ 🌍 Sky & Earth                       │
│    texture: time-series, geographic     │
│  ┌───────────────────────────────────┐  │
│  │ Open-Meteo         no key         │  │
│  │ time-series weather, forecast     │  │
│  │ → Farm weather dashboard          │  │
│  ├───────────────────────────────────┤  │
│  │ USGS Earthquake    no key         │  │
│  │ real-time GeoJSON events          │  │
│  │ → Live quake map                  │  │
│  └───────────────────────────────────┘  │
│                                         │
│  ▸ 🚀 Space (collapsed)                │
│  ▸ 🌿 Living Things (collapsed)        │
│  ...                                    │
└─────────────────────────────────────────┘
```

Collapsible panels use `<details>/<summary>` — no JS needed. First cluster
starts open, rest collapsed. Vanilla CSS handles the styling within the existing
theme (pink headers, gold accents, black cards).

### CSS additions (in `assets/css/main.css`)

Minimal additions — reuse `.markets-panel` patterns:

- `.api-map-page` — page wrapper
- `.api-cluster` — collapsible panel (details/summary)
- `.api-card` — individual API entry
- `.api-texture-badge` — small pill showing data shape
- `.api-auth-badge` — green (no key), yellow (free key), orange (free tier)

### Filters (stretch goal, JS)

Optional: a small vanilla JS filter bar at the top:
- Filter by texture (time-series, graph, corpus, spatial)
- Filter by auth level (no key, free key)
- Search box

This is a nice-to-have for v2. The page works without it.

---

## The Clusters

### 1. Sky & Earth
Weather, climate, air quality, earthquakes, sun/moon. Sensor data from the
physical world. Mostly time-series + geographic coordinates.

**APIs:** Open-Meteo, OpenWeatherMap, NOAA CDO, USGS Earthquake, AirNow,
Open AQ, Sunrise-Sunset

### 2. Space
NASA missions, Mars photos, near-Earth objects, solar events, ISS tracking,
SpaceX launches. Event logs + orbital data + image streams.

**APIs:** NASA (APOD, EONET, Mars Rover, NEO), SpaceX API, Open Notify,
Le Système Solaire

### 3. Living Things
Species observations, biodiversity, food/nutrition data. Taxonomies and
observation networks.

**APIs:** iNaturalist, GBIF, Open Food Facts, USDA FoodData Central,
TheDogAPI, TheCatAPI, PokeAPI

### 4. Culture & Knowledge
Books, music, movies, art, museums, trivia. The human creative record,
structured. Graph-shaped with rich relationships.

**APIs:** Open Library, Google Books, MusicBrainz, Last.fm, Discogs,
TheMovieDB, Open Trivia DB, Wikidata, Wikipedia, Harvard Art Museums,
Met Museum, Rijksmuseum

### 5. Words & Language
Dictionaries, thesauri, word relationships, poetry, full-text books, quotes.
Lexical graphs and text corpora.

**APIs:** Datamuse, Free Dictionary, Wordnik, PoetryDB, Project Gutenberg,
Quotable

### 6. Civic & Government
Census, legislation, elections, campaign finance, economic indicators.
Deep time-series + geographic hierarchies.

**APIs:** US Census, Data.gov, Congress.gov, Open States, FEC, BLS,
FRED, World Bank, UN Comtrade

### 7. Sports
Play-by-play, box scores, player stats, standings. Event logs + matrices.

**APIs:** MLB Stats API, NBA Stats, ESPN (unofficial), TheSportsDB,
Football-data.org

### 8. Maps & Place
Geocoding, elevation, place names, country data, geospatial queries.
Spatial graphs + polygon data.

**APIs:** OpenStreetMap/Overpass, Nominatim, Open Elevation, GeoNames,
REST Countries, IP-API

### 9. Money & Markets
Stock prices, crypto, forex, economic time-series. OHLCV + cross-correlations.

**APIs:** Alpha Vantage, CoinGecko, ExchangeRate.host, Yahoo Finance
(unofficial), Open Exchange Rates

### 10. Transit & Infrastructure
Public transport schedules, real-time vehicle positions, flight tracking.
Network topology + real-time streams.

**APIs:** Transit.land, Transport for London, WMATA, OpenSky Network,
ADS-B Exchange

### 11. Dev & Social
Repos, issues, discussions, news aggregation. Social graphs + text streams.

**APIs:** GitHub REST/GraphQL, HackerNews, Reddit, Lichess, Chess.com,
CocktailDB

---

## Relationship to existing sections

This page connects directly to existing and planned Almond Farm sections:

| API cluster | Existing section | Could power |
|-------------|-----------------|-------------|
| Sky & Earth | Farming | Orchard weather widget, frost alerts |
| Culture/Music | Music | Album data from MusicBrainz/Last.fm |
| Culture/Movies | Movies | Now-watching list from TMDB |
| Culture/Books | Books | Reading list from Open Library |
| Money/Markets | Markets | Live FRED data (already planned) |
| Living Things/Food | Cooking | Ingredient nutrition data |
| Sports | Gaming/new | Stats dashboards |
| Space | Brain/new | Daily APOD, ISS tracker |

---

## Build sequence

### Phase 1: Static catalog (this session or next)
1. Create `data/api_map.yaml` with all clusters and APIs
2. Create `content/apis.md` with front matter
3. Create `layouts/page/apis.html` with collapsible panels
4. Add CSS for the API map components
5. Add homepage card
6. Build-verify, commit, push

### Phase 2: Enrichment (future session)
7. Add project idea annotations to each API
8. Add "integration status" badges (planned / built / live)
9. Link to the site sections each API could power

### Phase 3: Filters (future session)
10. Add vanilla JS filter bar (by texture, auth level)
11. Add search box
12. Add URL hash state so you can link to a specific cluster

---

## Session prompts

See `TODO-API-MAP-PROMPTS.md` for a sequence of self-contained prompts
to build this out across multiple Sonnet sessions.
