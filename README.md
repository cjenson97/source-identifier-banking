# source-identifier-banking

A Financial Services horizon scanning **source discovery** system that automatically finds, scores, and recommends new regulatory and authoritative sources for monitoring.

---

## Overview

`source-identifier-banking` discovers new financial-services regulatory sources by:

1. **Searching** (DuckDuckGo or Serper API) using configurable query templates across jurisdictions and regulatory regimes.
2. **Crawling** seed URLs (e.g. FSB, IOSCO, BIS) to follow outgoing links and surface linked authority domains.
3. **Detecting feeds** (RSS/Atom) for each candidate homepage.
4. **Scoring** each candidate on four dimensions: authority, relevance, frequency, and usability.
5. **Filtering** duplicates and policy-excluded domains.
6. **Outputting** ranked candidates as JSON for human review, with a decisions CSV workflow to approve/reject.

---

## Requirements

- Python 3.10+
- Git

---

## Setup

```bash
git clone <repo-url>
cd source-identifier-banking
pip install -e .
```

---

## Configuration

### `config/search_config.yaml`

Controls the search provider, query templates, jurisdictions, regimes, seed URLs, scoring weights, and policy filters.

Key fields:

| Field | Description |
|---|---|
| `provider` | `duckduckgo` (default) or `serper` |
| `api_key_env` | Env var name for Serper API key (default: `SERPER_API_KEY`) |
| `max_results_per_query` | Results per search query |
| `rate_limit_delay_seconds` | Pause between requests |
| `request_timeout_seconds` | HTTP timeout |
| `recommend_add_threshold` | Score ≥ this → `add` |
| `recommend_watchlist_threshold` | Score ≥ this → `watchlist`, else `reject` |
| `scoring_weights` | Weights for authority, relevance, frequency, usability, uniqueness |
| `query_templates` | Templates using `{jurisdiction}` and `{regime}` placeholders |
| `jurisdictions` | List of jurisdiction strings to search across |
| `regimes` | List of regulatory regime strings |
| `seed_urls` | URLs to crawl for link expansion |
| `policy_filters.exclude_domain_patterns` | Domain substrings to exclude |
| `policy_filters.us_legislation_trackers` | Exact domains to always exclude |

### `config/existing_sources.yaml`

Lists already-known sources (by `domain`). Any candidate matching an existing domain is scored 0 and excluded from output.

---

## CLI Commands

### `discover` — Run the discovery pipeline

```bash
python -m source_identifier_banking discover \
  --config config/search_config.yaml \
  --existing config/existing_sources.yaml \
  --output artifacts/candidate_sources.json \
  --max-candidates 50
```

| Flag | Default | Description |
|---|---|---|
| `--config` | `config/search_config.yaml` | Path to search config YAML |
| `--existing` | `config/existing_sources.yaml` | Path to existing sources YAML |
| `--output` | `artifacts/candidate_sources.json` | Output JSON path |
| `--max-candidates` | `50` | Maximum candidates to write |

Writes `artifacts/candidate_sources.json` and an `artifacts/decisions.csv` template.

### `apply-decisions` — Apply human decisions

Fill in `artifacts/decisions.csv` with `add` or `reject` for each `candidate_id`, then run:

```bash
python -m source_identifier_banking apply-decisions \
  --decisions artifacts/decisions.csv \
  --candidates artifacts/candidate_sources.json \
  --approved config/approved_sources.yaml \
  --rejected config/rejected_sources.yaml
```

| Flag | Default | Description |
|---|---|---|
| `--decisions` | `artifacts/decisions.csv` | Decisions CSV |
| `--candidates` | `artifacts/candidate_sources.json` | Candidates JSON |
| `--approved` | `config/approved_sources.yaml` | Approved sources YAML output |
| `--rejected` | `config/rejected_sources.yaml` | Rejected sources YAML output |

---

## Output Format

`artifacts/candidate_sources.json` is a JSON array, sorted by `confidence_score` descending:

```json
[
  {
    "candidate_id": "uuid",
    "source_name": "European Securities and Markets Authority",
    "homepage_url": "https://www.esma.europa.eu",
    "feed_url": "https://www.esma.europa.eu/rss.xml",
    "jurisdiction": "Unknown",
    "source_type": "unknown",
    "fs_coverage_tags": ["regulatory", "securities", "MiFID"],
    "evidence_samples": [{"url": "...", "title": "..."}],
    "description": "...",
    "confidence_score": 0.82,
    "recommended_action": "add",
    "reason": "Score: 0.82"
  }
]
```

---

## Scoring Methodology

Each candidate receives a composite score between 0 and 1 from five components:

| Component | Weight | Description |
|---|---|---|
| **Authority** | 0.30 | `.gov`, `.europa.eu`, `.int` TLDs score highly; `.org` scores moderately; authority keywords in name/description add bonus |
| **Relevance** | 0.30 | Count of Financial Services taxonomy keyword matches (banking, AML, GDPR, crypto, ESG, etc.) in name + description |
| **Frequency** | 0.15 | Number of evidence samples collected; more mentions = higher score |
| **Usability** | 0.15 | Has a feed URL (+0.7) and uses HTTPS (+0.3) |
| **Uniqueness** | 0.10 | Always 1.0 (candidate not already in existing sources) |

Weights are configurable via `scoring_weights` in `search_config.yaml`.

---

## How to Extend

### Adding a new search provider

1. Subclass `SearchProvider` in `source_identifier_banking/search.py`.
2. Implement `search(self, query: str) -> list[dict]` returning dicts with `title`, `url`, `description`.
3. Add a new branch in `get_provider()`.

### Adding taxonomy keywords

Add strings to `FS_TAXONOMY_KEYWORDS` in `source_identifier_banking/scoring.py`. These are used for both relevance scoring and `fs_coverage_tags` tagging.

### Adding authority TLDs

Add to `_AUTHORITY_TLDS` in `source_identifier_banking/scoring.py`.

---

## GitHub Actions Workflow

`.github/workflows/discover.yml` runs the discovery pipeline:

- **Schedule**: Every Monday at 07:00 UTC.
- **Manual trigger**: `workflow_dispatch` with optional `config_path` input.
- **Steps**: Checkout → Install → Run discovery → Upload `artifacts/` as a workflow artifact.
- **Secret**: Set `SERPER_API_KEY` in repository secrets to use the Serper provider.

---

## Running Tests

```bash
pip install -e ".[dev]"  # or: pip install pytest pytest-mock responses
python -m pytest tests/ -v
```

