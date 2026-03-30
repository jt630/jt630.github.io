# Unlikely Correlations Engine — Build Plan

An open-source, multi-agent research platform that surfaces hidden
correlations between health outcomes and environmental, occupational,
and geographic factors.

**Repository:** `jt630/Huh-Really-`
**Stack:** Python, Claude API, Streamlit, PySAL, pandas, folium
**Demo case:** Parkinson's disease / pesticide exposure / golf course proximity

---

## Architecture

```
Input: hypothesis OR discovery mode
         |
         v
+---------------------+
|  Data Ingestion     |  20+ public data source adapters
+--------+------------+
         |
         v
+---------------------+
|  Correlation Agent  |  Pairwise + sweep + LISA spatial clustering
+--------+------------+
         |  Significant associations found?
         |  No -> Report -> END
         |  Yes v
         v
+---------------------+
|  Literature Agent   |  PubMed search + Claude synthesis [CO-DESIGN]
+--------+------------+
         |
         v
+---------------------+
|  Causation Agent    |  Bradford Hill + confounders + alternatives [CO-DESIGN]
+--------+------------+
         |
         v
+---------------------+
|  Study Design Agent |  Investigation brief + full proposal [CO-DESIGN]
+--------+------------+
         |
         v
      Streamlit UI (tabbed: correlation, literature, causation, study design)
```

**Design principle — Facts vs. Analysis:** All agent output separates
verifiable evidence (exact statistics, verbatim citations) from AI
interpretation (labeled explicitly, with stated confidence levels).

---

## Ordered Prompt List

Each prompt below is a self-contained session with Claude Sonnet.
Run them in order. Each session should produce working, tested code
before moving to the next.

---

### Prompt 0: Project Skeleton

**Prerequisites:** Create an empty repo `jt630/unlikely-correlations` on GitHub.

```
Create the project skeleton for "unlikely-correlations" — an open-source
multi-agent research platform that detects hidden associations between
health outcomes and environmental, occupational, or geographic factors.

Set up:
- pyproject.toml with dependencies: anthropic, streamlit, pandas, scipy,
  numpy, requests, folium, plotly, pydantic, pysal, geopandas, shapely
- src/agents/ directory with empty modules: correlation.py, literature.py,
  causation.py, study_design.py
- src/data/ directory with empty modules for each data source adapter
  (see list below)
- src/pipeline.py — orchestrator entry point
- src/config.py — pydantic settings model loading from .env
- app.py — Streamlit UI entry point
- cases/parkinsons_golf.yaml — demo case definition with parameters:
    outcome: "parkinsons_mortality_rate"
    outcome_source: "cdc_wonder"
    outcome_icd10: "G20"
    exposures: ["paraquat_kg", "rotenone_kg", "chlorpyrifos_kg",
                "golf_course_density"]
    confounders: ["median_age", "median_income", "pct_rural",
                  "healthcare_access"]
- .env.example listing: ANTHROPIC_API_KEY, NCBI_API_KEY (optional),
  CENSUS_API_KEY (optional)
- .gitignore (include data/cache/, results/, .env, __pycache__)
- README.md explaining:
  - What the project does (2-3 sentences)
  - The four-agent pipeline architecture
  - How to install and run
  - How to configure API keys
  - The demo case (Parkinson's/pesticide)
  - License: MIT
- tests/ directory with conftest.py

Data source adapter modules to create (empty, with docstrings only):
  src/data/cdc_wonder.py
  src/data/cdc_places.py
  src/data/cms_chronic.py
  src/data/county_health_rankings.py
  src/data/epa_tri.py
  src/data/epa_pesticides.py
  src/data/epa_superfund.py
  src/data/epa_ejscreen.py
  src/data/epa_aqs.py
  src/data/epa_sdwis.py
  src/data/usgs_pesticide_use.py
  src/data/usgs_nwis.py
  src/data/usgs_nlcd.py
  src/data/usda_cropscape.py
  src/data/osm_features.py
  src/data/census_acs.py
  src/data/census_cbp.py
  src/data/cdc_svi.py
  src/data/openfda_faers.py
  src/data/pubmed.py
  src/data/semantic_scholar.py

Each module should have a docstring explaining its data source, what
fields it provides, and the API endpoint or download URL. Use pydantic
BaseModel for all data schemas. No implementation yet.
```

---

### Prompt 1: Data Ingestion — Priority Sources

```
In the unlikely-correlations project, implement the priority data source
adapters needed for the Parkinson's/pesticide demo case.

## src/data/cdc_wonder.py
Fetch county-level mortality data for a given ICD-10 code.
- CDC Wonder uses a POST-based query interface. Implement the request
  format for the Underlying Cause of Death dataset.
- Return DataFrame: county_fips, county_name, state, deaths, population,
  age_adjusted_rate, year
- Cache responses in data/cache/ to avoid re-fetching during development.
- If the WONDER API is too restrictive for automation, implement a
  fallback that reads from pre-downloaded compressed mortality files
  (document where to obtain them in the module docstring).

## src/data/cms_chronic.py
Fetch CMS Chronic Conditions prevalence by county.
- Use the data.cms.gov Socrata API (SODA).
- Filter for specific conditions (Parkinson's, Alzheimer's, etc.)
- Return DataFrame: county_fips, condition, prevalence_pct,
  beneficiary_count, year

## src/data/usgs_pesticide_use.py
Fetch USGS estimated annual agricultural pesticide use by county.
- Download tab-delimited files from USGS Pesticide National Synthesis
  Project.
- Filter by compound list (paraquat, rotenone, chlorpyrifos, maneb).
- Return DataFrame: county_fips, compound, kg_applied, year

## src/data/osm_features.py
Query OpenStreetMap for geographic features by county.
- Use Overpass API to count features tagged leisure=golf_course.
- Accept any OSM tag for extensibility (e.g., landuse=industrial).
- Return DataFrame: county_fips, feature_type, count,
  density_per_sq_km
- Use US Census county boundary data for spatial joins.
- Implement rate limiting and batch queries by state to stay within
  Overpass API limits.

## src/data/census_acs.py
Fetch demographic confounders from American Community Survey.
- Use Census API (requires API key, free instant registration).
- Variables: median age, median household income, percent rural,
  total population, percent below poverty.
- Return DataFrame: county_fips, variable_name, value, year

## src/data/county_health_rankings.py
Load County Health Rankings annual dataset.
- Download the national CSV from countyhealthrankings.org.
- Parse relevant measures: premature death rate, poor health days,
  primary care physician rate, uninsured rate.
- Return DataFrame: county_fips, measure, value, year

All modules must:
- Use pydantic models for output schemas.
- Include a __main__ block that fetches sample data and prints it.
- Handle rate limiting with exponential backoff.
- Log progress so the user can monitor long-running fetches.
- Raise clear errors when API keys are missing or endpoints are down.
```

---

### Prompt 2: Data Ingestion — Extended Sources

```
In the unlikely-correlations project, implement the remaining data
source adapters. Follow the same patterns established in the priority
sources (pydantic models, caching, rate limiting, __main__ test block).

Implement these modules:
- src/data/cdc_places.py — CDC PLACES chronic disease estimates via
  Socrata/SODA API
- src/data/epa_tri.py — Toxics Release Inventory via Envirofacts API
- src/data/epa_superfund.py — NPL site locations via Envirofacts
- src/data/epa_ejscreen.py — Environmental justice indicators
  (bulk download)
- src/data/epa_aqs.py — Air quality monitoring data via AQS API
  (requires API key)
- src/data/epa_sdwis.py — Drinking water violations via Envirofacts
- src/data/usgs_nwis.py — Water quality measurements via NWIS REST API
- src/data/usda_cropscape.py — Crop-specific land cover via CropScape
  API
- src/data/census_cbp.py — County Business Patterns (establishment
  counts by industry) via Census API
- src/data/cdc_svi.py — Social Vulnerability Index (bulk CSV download)
- src/data/openfda_faers.py — FDA adverse event reports via openFDA API
- src/data/pubmed.py — PubMed search via NCBI E-utilities
  (ESearch + EFetch, XML parsing)
- src/data/semantic_scholar.py — Academic paper search + citation data

Also create:
- src/data/registry.py — A DataSourceRegistry class that:
  - Auto-discovers all available data source modules
  - Reports which sources are configured (API keys present)
  - Provides a unified interface: registry.load(source_name, **params)
  - Returns a standardized DataFrame with county_fips as index
  - Lists all available variables across all sources
```

---

### Prompt 3: Correlation Agent

```
Build the Correlation Agent for the unlikely-correlations project.

## src/agents/correlation.py

Takes health outcome data and exposure/environmental data (both as
DataFrames indexed by county FIPS) and surfaces statistically
significant associations.

### Capabilities:

1. Pairwise correlation:
   - Pearson r + p-value
   - Spearman rank correlation + p-value
   - Partial correlation controlling for specified confounders
   - Report number of counties with data for both variables

2. Correlation sweep:
   - Given ONE outcome and a LIST of exposure variables, test all
   - Rank by statistical significance
   - Apply Bonferroni correction for multiple comparisons
   - Return top N results

3. Outlier detection:
   - Flag counties >2 SD above mean on BOTH variables
   - These are candidate "hot spot" counties

4. Map generation (folium):
   - Choropleth of health outcome by county
   - Exposure intensity overlay
   - Hot-spot county markers with popups

### Geospatial analysis (PySAL):
5. Global Moran's I — is the variable spatially clustered?
6. Local Moran's I (LISA) — which counties are in clusters?
   - HH (hot spot), LL (cold spot), HL, LH classifications
7. Bivariate Local Moran's I — spatial co-clustering of two variables
8. LISA cluster map (folium) — hot spots in red, cold spots in blue

### Data models (pydantic):
- CorrelationRequest, CorrelationResult, SweepReport, SpatialResult

Use scipy.stats for statistical tests. Use PySAL (esda module) for
spatial analysis. Cache the county spatial weights matrix (Queen
contiguity from Census TIGER/Line shapefiles).

Requires: county boundary GeoJSON or shapefile for spatial analysis.
Download Census TIGER/Line county boundaries in __main__ setup.
```

---

### Prompt 4: Literature Agent

**Note:** This module is flagged for co-design with a domain expert.
Build the working prototype; it will be refined in a later session.

```
Build the Literature Agent for the unlikely-correlations project.

## src/agents/literature.py

Takes a hypothesis (from the Correlation Agent's findings) and searches
biomedical literature for supporting evidence, contradictions, and gaps.

### Capabilities:

1. Hypothesis-to-query generation:
   - Use Claude to convert a natural language hypothesis into 3-5
     PubMed search queries (MeSH terms + keyword variants)

2. PubMed search:
   - NCBI E-utilities API (ESearch + EFetch)
   - De-duplicate across queries
   - Fetch abstracts, authors, year, journal, MeSH terms, DOI
   - Configurable max results (default: 50)
   - Respect rate limits (3 req/sec without key, 10 with)
   - Cache raw API responses in data/cache/

3. Claude synthesis — structured prompt producing:
   - Evidence summary (N supporting, N contradicting, weight)
   - Key findings with specific citations (Author, Year)
   - Contradictions with analysis of why studies may differ
   - Dose-response evidence assessment
   - Evidence gaps
   - Suggested follow-up queries

4. Iterative deepening (optional):
   - If gaps are identified, generate follow-up queries
   - Require user confirmation before running additional rounds
   - Track depth level

### Design principle:
All output must separate EVIDENCE (verbatim findings with citations)
from ANALYSIS (AI interpretation, labeled as such). Never paraphrase
source material in the evidence section.

### Data models (pydantic):
- LiteratureRequest, Paper, LiteratureSynthesis, LiteratureResult
```

---

### Prompt 5: Causation Agent

**Note:** Flagged for co-design with domain expert.

```
Build the Causation Agent for the unlikely-correlations project.

## src/agents/causation.py

Receives correlation results and literature synthesis. Produces a
structured causal assessment.

### Capabilities:

1. Bradford Hill criteria assessment:
   For each of the 9 criteria (strength, consistency, specificity,
   temporality, biological gradient, plausibility, coherence,
   experiment, analogy):
   - Rating: Strong / Moderate / Weak / Insufficient data
   - Evidence: Specific data points and citations
   - Gaps: What evidence is missing

2. Confounder analysis:
   - For each available confounder, compute partial correlation
   - Report whether association survives adjustment
   - Use Claude to identify domain-specific confounders not in dataset
   - Output table: confounder, unadjusted_r, adjusted_r, pct_change

3. Alternative explanations:
   - Ecological fallacy, selection bias, information bias,
     reverse causation, shared upstream cause
   - Assess plausibility of each alternative

4. Overall causal assessment:
   - Rating: Probable / Possible / Insufficient / Likely non-causal
   - Confidence: High / Moderate / Low
   - Top 3 supporting points, top 3 uncertainties
   - Recommended next steps

### Design principle:
Facts vs. Analysis separation throughout. Never use "prove" in
relation to observational data. Use "support," "consistent with,"
"suggest." Bradford Hill criteria are guidelines, not a checklist.
Ecological fallacy warning in every assessment.

### Data models (pydantic):
- CausationRequest, BradfordHillCriterion, ConfounderAssessment,
  AlternativeExplanation, CausationResult
```

---

### Prompt 6: Study Design Agent

**Note:** Flagged for co-design with domain expert.

```
Build the Study Design Agent for the unlikely-correlations project.

## src/agents/study_design.py

Receives full pipeline output and generates research proposals that
directly address the key uncertainties identified by the Causation Agent.

### Two output modes:

MODE 1 — Rapid Investigation Brief:
- 1-2 page operational document for decision-makers
- Sections: Finding Summary, Evidence Assessment (table), Affected
  Populations, Current Activity, Recommended Actions (tiered:
  immediate/short-term/long-term), Cost of Inaction, Limitations
- Footer: "Generated proposal — requires expert review and independent
  verification before informing policy decisions."

MODE 2 — Full Research Proposal:
- 5-10 page academic document
- Sections: Title, Study Type (with justification), Hypothesis,
  Population (with sample size rationale), Exposure Assessment,
  Outcome Assessment, Confounders/Covariates, Analysis Plan,
  Limitations, Ethical Considerations, Timeline/Resources
- Include precedent study citations from literature results
- 2-3 alternative study designs with trade-off comparison table

### For both modes:
- Gap resolution table: each uncertainty from CausationResult mapped
  to how the proposed study addresses it
- Exportable as Markdown and PDF
- Label clearly: "Generated proposal — requires expert review and
  institutional adaptation before submission."

### Data models (pydantic):
- StudyDesignRequest, GapResolution, StudyProposal,
  AlternativeDesign, StudyDesignResult
```

---

### Prompt 7: Orchestrator + Streamlit UI

```
Build the pipeline orchestrator and Streamlit UI for the
unlikely-correlations project.

## src/pipeline.py

class Pipeline:
    def run_hypothesis(exposure, outcome, confounders, output_mode)
        -> PipelineResult
    def run_discovery(outcome, top_n, confounders, output_mode)
        -> list[PipelineResult]

- Chain: Data -> Correlation -> Literature -> Causation -> Study Design
- Emit progress events for UI display
- Cache intermediate results to results/{run_id}/
- Interruptible — user can stop after any stage
- Each run gets a unique run_id

## app.py — Streamlit UI

SIDEBAR:
- Mode: "Test Hypothesis" / "Discovery Mode"
- Dropdowns for outcome and exposure (populated from DataSourceRegistry)
- Confounder checklist
- Output format: "Investigation Brief" / "Full Research Proposal"
- "Run Pipeline" button
- "Run Demo" button (pre-loads Parkinson's/pesticide case)
- Previous runs list

MAIN AREA (6 tabs):
- Overview: progress indicator + summary card
- Correlation: choropleth map, LISA cluster map, statistics table
- Literature: evidence synthesis, paper list, contradictions, gaps
- Causation: Bradford Hill table, confounder table, alternatives
- Study Design: brief or proposal, alternatives table, export button
- Raw Data: facts-only view, downloadable CSV/JSON

UI requirements:
- AI analysis sections display header: "AI Analysis — Verify
  Independently"
- Evidence sections display: "Source Data — Cited and Verifiable"
- All maps interactive (zoom, click for county detail)
- Complete report export (Markdown + PDF)
```

---

## Co-Design Sessions

Phases 3, 4, and 5 are flagged for co-design with a domain expert
in global health policy. Each module has a working prototype from the
prompts above, but the expert should review and reshape:

- **Literature Agent:** Search strategy, source selection, synthesis
  format, contradiction handling, iterative deepening behavior
- **Causation Agent:** Bradford Hill implementation, confounder
  prioritization, alternative explanation framework, language
  constraints
- **Study Design Agent:** Proposal structure, investigation brief
  format, ethical considerations, feasibility assessment criteria

A dedicated onboarding prompt for the co-design session is available
in the project documentation.

---

## Data Sources Reference

### Disease & Health Outcomes
| # | Source | Free | County-Level | Access |
|---|--------|------|-------------|--------|
| 1 | CDC Wonder | Yes | Yes | POST API |
| 2 | CDC PLACES | Yes | Yes | REST (Socrata) |
| 3 | CMS Chronic Conditions | Yes | Yes | CSV + Socrata |
| 4 | County Health Rankings | Yes | Yes | CSV download |
| 5 | IHME Global Burden of Disease | Registration | Yes | CSV download |
| 6 | State Cancer Profiles | Yes | Yes | Web export |

### Environmental Exposure
| # | Source | Free | County-Level | Access |
|---|--------|------|-------------|--------|
| 7 | USGS Pesticide Use | Yes | Yes | Bulk download |
| 8 | EPA Toxics Release Inventory | Yes | Yes (facility) | REST + CSV |
| 9 | EPA Superfund Sites | Yes | Yes | REST API |
| 10 | EPA EJScreen | Yes | Yes | REST + CSV |

### Air & Water Quality
| # | Source | Free | County-Level | Access |
|---|--------|------|-------------|--------|
| 11 | EPA Air Quality (AQS) | API key | Yes | REST API |
| 12 | EPA Drinking Water (SDWIS) | Yes | Partial | REST API |
| 13 | USGS Water Quality (NWIS) | Yes | Yes (site) | REST API |

### Land Use & Geography
| # | Source | Free | County-Level | Access |
|---|--------|------|-------------|--------|
| 14 | USDA CropScape | Yes | Yes | REST API |
| 15 | OpenStreetMap Overpass | Yes | Yes (spatial) | REST API |

### Demographic / Socioeconomic
| # | Source | Free | County-Level | Access |
|---|--------|------|-------------|--------|
| 16 | Census ACS | API key | Yes | REST API |
| 17 | USDA County-Level Datasets | Yes | Yes | CSV download |
| 18 | CDC Social Vulnerability Index | Yes | Yes | CSV download |

### Pharmaceutical & Literature
| # | Source | Free | County-Level | Access |
|---|--------|------|-------------|--------|
| 19 | openFDA (FAERS) | Yes | No | REST API |
| 20 | PubMed E-utilities | API key | N/A | REST API |
