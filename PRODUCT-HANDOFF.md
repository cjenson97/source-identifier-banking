# Banking Compliance Source Finder - Product Handoff

## Purpose
This product helps analysts find viable new sources for the Banking vertical.
It focuses on source discovery, not update tracking.
It runs a web-wide open-source trace scan across public feeds and article indexes.

## Who It Is For
- Regulatory intelligence analysts
- Product managers overseeing source coverage
- Operations teams maintaining monitoring universe quality

## Core User Outcome
A user runs one scan and receives a source-level list of net-new domains worth monitoring, with CSV export and history access.

## Current Experience (Chrome Extension)
- Run Now button triggers a web-wide open-source trace scan.
- Findings table shows source-level results only.
- Export Findings CSV downloads results.
- Completion notification can be enabled.
- Scan History lets users reopen prior result sets.
- Current Banking Sources tab shows covered domains currently excluded from findings.

## Source-First Design Principles
- The system evaluates source relevance, not article novelty.
- Existing covered domains are excluded as a hard rule.
- Parent/subdomain matching is applied so known source families are not resurfaced.
- UI language and columns are source-centric.

## Findings Table (Current)
- Source Domain
- Source Type
- Source Relevance
- Banking Update Cadence

## What Was Removed by Design
- Example Headline column
- Recent Mentions column
- Last Seen column
- Visible editable covered-domain field (hidden from UI)

## Hard Exclusion Rule
A hard blocked covered-source set is embedded and always excluded from findings.
This includes the large source list provided by the business.

## Relevance and Cadence
- Source Relevance is banded: Very Strong, Strong, Moderate, Early Signal.
- Banking Update Cadence is estimated from source activity volume in the scan window.

## User History
- Each user has local scan history in browser extension storage.
- Users can load prior runs and re-export from history.
- History is local to that browser profile.

## Notifications
- Optional completion notification confirms when a scan has finished.

## Branding and UX
- Blue/green branded visual system.
- Compact analyst workflow with low friction.
- Tabs separate discovery outputs from current covered sources.

## Current Constraints
- Discovery breadth is still bounded by upstream provider response limits.
- The scan is broad web coverage, not a literal crawl of every page on the internet.
- Extension storage is local, not centralized across users.

## Success Criteria
- Analysts only see net-new candidate sources.
- Known covered sources do not reappear.
- Scan and export are usable in one pass.
- Users can revisit prior run outputs without rescanning.

## Recommended Next Product Steps
1. Add organization-wide shared covered-source management.
2. Add analyst feedback actions (Keep, Reject, Already Covered).
3. Add source quality scoring (authority, recency stability, regulatory density).
4. Add team-wide cloud history and audit trail.
5. Add scheduled scan mode with daily digest summary.
