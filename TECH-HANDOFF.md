# Banking Compliance Source Finder - Technical Handoff

## Scope
This document describes the current architecture and implementation state across:
- Chrome extension UI and scan logic
- Python discovery engine scripts
- Standalone desktop app path

## Repository Areas
- chrome-extension: active extension UI and discovery client
- scheduled_checks.py: Python discovery runner and reporting pipeline
- desktop_app.py: native desktop UI (Tkinter)
- app.py: desktop launcher entrypoint

## Primary Runtime (Current Focus)
Chrome extension under chrome-extension.

## Chrome Extension Architecture
### Files
- manifest.json: extension metadata, permissions, popup entry
- popup.html: UI layout and tabs
- popup.css: brand styling
- popup.js: scan workflow, filtering, scoring, export, history, notifications
- README.md: load and usage instructions

### Permissions
- storage
- notifications
- host permissions for public discovery endpoints

### Discovery Flow
1. User clicks Run Now.
2. Run a web-wide trace scan across indexed public sources.
3. Fetch regulator RSS/Atom feeds.
4. Fetch GDELT + Google News RSS per banking terms.
5. Normalize and deduplicate source URLs.
6. Aggregate by domain.
7. Apply hard covered-source exclusion.
8. Score and classify source relevance.
9. Render findings table.
10. Persist run to local scan history.
11. Optional completion notification.

## Covered Source Exclusion
### Rule Model
- Hard-rule covered sources are embedded in popup.js.
- Default covered sources are merged with hard-rule list.
- Matching includes:
  - exact domain
  - child subdomain of known domain
  - parent domain of known domain

### UI Behavior
- Covered source editor is hidden from UI.
- Current Banking Sources tab provides read-only visibility of excluded domains.

## Scoring and Classification
### Relevance
Term-based relevance scoring against configured banking/regulatory terms.

### Priority Score
Computed from:
- max relevance
- article count contribution
- trust score by TLD
- regulator hint score

### Source Type
Rule-based tagging:
- Regulator
- Legislation
- Enforcement
- FIU/AML
- Industry
- Media
- Other

### Banking Update Cadence
Derived from aggregated mention volume in the current scan window.

## UI Data Model (Findings)
Current findings object fields include:
- sourceDomain
- sourceType
- sourceRelevance
- updateCadence
- mentionCount
- priorityScore

Note: mentionCount is retained internally for ranking but not shown in table.

## Export
CSV export columns:
- Source Domain
- Source Type
- Source Relevance
- Banking Update Cadence
- Priority Score

## History
Stored in local extension storage key scanHistory.
- Saved per run with id, timestamp, count, findings payload
- Retains last 30 entries
- User can load selected historical run

## No Local Cap Policy
Local slices on feed/article lists were removed where possible.
Current practical limit is provider-side API response constraints.
GDELT request uses maxrecords=250.
This provides web-wide trace coverage over indexed/public endpoints, not an exhaustive crawl of every live web page.

## Desktop/Python Path (Still Present)
### scheduled_checks.py
- Full Python runner for repeated checks and output files
- Includes Google RSS fallback and source-type classification
- Contains CSV and digest output generation under data/output

### desktop_app.py
- Tkinter desktop client with Run Now and CSV export
- Uses scheduled_checks.py functions

### app.py
- Launches desktop_app.main()

## Build and Run
### Chrome extension
1. Open chrome://extensions
2. Enable Developer mode
3. Load unpacked folder chrome-extension

### Python checks
- Run one cycle: python scheduled_checks.py --once

## Known Technical Risks
- Public endpoint latency and occasional timeouts
- Browser CORS behavior variability by endpoint
- Local storage size growth if history payloads are large
- Hard-rule list currently code-embedded, not externalized

## Recommended Engineering Next Steps
1. Move hard-rule covered sources into versioned JSON file.
2. Add source-list checksum and validation on load.
3. Add retry/backoff and per-source telemetry in popup.js.
4. Add unit tests for domain normalization and exclusion matching.
5. Add pipeline for signed extension package builds.
