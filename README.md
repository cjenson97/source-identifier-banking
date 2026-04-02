# Banking Compliance Source Identifier

This app helps analysts discover and track new online sources publishing about banking compliance.

It does three things:
- Pulls recent articles from public news data using banking compliance keyword searches.
- Groups results by source domain and scores relevance.
- Flags net-new domains not previously seen in your local source history.
- Lets you load your existing monitored source universe so discovery only surfaces true new candidates.

## Why this is useful

Regulatory intelligence teams need to continuously identify emerging source domains (publishers, legal blogs, regulator pages, law firms, trade outlets) discussing compliance themes. This app accelerates that discovery workflow and gives a repeatable way to track new sources over time.

## Features

- Multi-keyword discovery against recent news
- Domain-level source rollups
- Relevance scoring for compliance-focused terms
- New-source detection against persisted history
- One-click CSV exports for articles and sources
- Local source history management
- Baseline source list import via paste or .txt/.csv upload
- Priority scoring (relevance + trust + regulator hints)
- Automated 6-hour online checks with compiled net-new list output
- Non-technical control center for live scans and schedule management
- Fallback discovery via Google News RSS when GDELT is slow or unavailable
- Source-type labeling such as Regulator, Legislation, Enforcement, FIU/AML, Industry, and Media
- Daily digest text output for quick analyst review

## Quick start

1. Create and activate a virtual environment.
2. Install dependencies.
3. Run the app.

Windows PowerShell:

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py

## No-command launch for analysts

This project includes a double-click launcher and shortcut creator so non-technical users do not need to run terminal commands.

Files:

- Launch Banking Compliance Source Finder.vbs: hidden launcher (double-click this)
- Launch Banking Compliance Source Finder.cmd: starts the app server
- create_app_shortcuts.ps1: creates Desktop and Start Menu shortcuts
- enable_app_autostart.ps1: starts app automatically at Windows login
- disable_app_autostart.ps1: turns off Windows login auto-start

After shortcuts are created, analysts can launch from:

- Desktop icon: Banking Compliance Source Finder
- Start Menu: Banking Compliance Source Finder

## Auto-start at login (no command needed)

Run once:

./enable_app_autostart.ps1

On machines without Task Scheduler permissions, this automatically falls back to a per-user Startup shortcut.

To disable:

./disable_app_autostart.ps1

## How to use

1. Open the app and use the Control Center tab for everyday operations.
2. In Baseline Sources, paste or upload your current monitored URL list, then click Update Baseline Sources.
3. In Control Center, either:
   - click Run Live Scan Now for an immediate check, or
   - save a background schedule for automatic checks
4. In Live Discovery, analysts can run ad hoc manual scans using the sidebar filters.
5. Review:
	- New Sources Worth Monitoring (net-new and threshold-qualified)
	- All Net-New Sources (all discovered domains not in baseline)
	- Source Overview (all domains)
	- Article Matches (raw article-level results)
6. Export CSV files or Save New Sources To History.

## Data notes

- Article discovery uses the public GDELT DOC API.
- Source history is stored locally at data/seen_sources.csv.
- Baseline monitored URLs are stored at data/current_sources.txt.
- This app does not require external API keys for baseline use.

## Automated 6-hour monitoring

Use the runner script to execute online discovery checks and compile a master list of new sources worth monitoring.

The app now exposes this through the UI, so non-technical users do not need to work in PowerShell.

Run one check manually:

python scheduled_checks.py --once

Run continuously (every `check_interval_hours` from config):

python scheduled_checks.py

Configuration file:

- discovery_config.json

Key outputs (in data/output):

- latest_new_sources_worth_monitoring.csv
- latest_all_net_new_sources.csv
- latest_source_overview.csv
- latest_article_matches.csv
- compiled_new_sources.csv (master cumulative list)
- latest_update.txt (plain-English summary for analysts)
- latest_daily_digest.txt (short digest of the most important new sources)
- timestamped snapshot files for each run

### Windows Task Scheduler setup (every 6 hours)

PowerShell:

./setup_windows_task.ps1

This registers a scheduled task named `BankingComplianceSourceCheck` that runs:

python scheduled_checks.py --once

every 6 hours.

## Files

- app.py: Streamlit user interface and discovery logic
- scheduled_checks.py: automated discovery runner and compiled output generation
- setup_windows_task.ps1: registers a Windows scheduled task for 6-hour checks
- discovery_config.json: tuning for terms, thresholds, and interval
- requirements.txt: Python dependencies
- data/current_sources.txt: loaded monitored URL baseline (auto-created)
- data/seen_sources.csv: auto-created local source history

## Suggested enhancements

- Add regulator-specific feeds per jurisdiction
- Add analyst tagging and source quality ratings
- Add scheduled runs and email digests
- Add domain categorization model (regulator, law firm, media, etc.)
