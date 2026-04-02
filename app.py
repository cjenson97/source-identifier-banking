from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
from typing import Iterable
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import pandas as pd
import requests
import streamlit as st


GDELT_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
DATA_DIR = Path("data")
SEEN_SOURCES_FILE = DATA_DIR / "seen_sources.csv"
CURRENT_SOURCES_FILE = DATA_DIR / "current_sources.txt"
OUTPUT_DIR = DATA_DIR / "output"
LATEST_UPDATE_FILE = OUTPUT_DIR / "latest_update.txt"
LATEST_DIGEST_FILE = OUTPUT_DIR / "latest_daily_digest.txt"
RUN_CHECK_CMD_FILE = Path("run_check_once.cmd")
DEFAULT_TASK_NAME = "BankingComplianceSourceCheck"

DEFAULT_TERMS = [
    "banking compliance",
    "anti money laundering",
    "prudential regulation",
    "consumer duty bank",
    "bank enforcement action",
    "know your customer",
    "financial crime controls",
    "capital requirements bank",
]

RELEVANCE_TERMS = [
    "compliance",
    "regulation",
    "regulatory",
    "supervision",
    "aml",
    "anti money laundering",
    "kyc",
    "sanctions",
    "prudential",
    "capital",
    "conduct",
    "enforcement",
    "risk",
    "governance",
    "bank",
    "banking",
]

SOURCE_TYPE_RULES = [
    ("Regulator", ["fca", "sec", "finra", "fma", "fsa", "bank", "centralbank", "supervision", "authority", "prudential"]),
    ("Legislation", ["parliament", "legislation", "gazette", "congress", "senate", "assembly", "laws", "bill"]),
    ("Enforcement", ["enforcement", "sanction", "penalty", "attorneygeneral", "justice", "cease-desist", "revocation"]),
    ("FIU/AML", ["fiu", "aml", "moneylaundering", "fintrac", "fincen", "uif", "uaf"]),
    ("Industry", ["association", "bankingassociation", "trade", "chamber", "federation"]),
    ("Media", ["news", "media", "press", "reuters", "law", "blog"]),
]

HIGH_TRUST_TLDS = [".gov", ".gob", ".gc.ca", ".eu", ".int", ".org"]
REGULATOR_HINTS = [
    "bank",
    "centralbank",
    "fca",
    "finra",
    "sec",
    "prudential",
    "supervision",
    "ministry",
    "treasury",
    "parliament",
    "gazette",
    "regulator",
    "authority",
]


@dataclass
class DiscoveryConfig:
    terms: list[str]
    lookback_days: int
    max_records_per_term: int


def normalize_domain(url: str) -> str:
    parsed = urlparse(url)
    domain = parsed.netloc.lower().strip()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def extract_urls_from_text(text: str) -> list[str]:
    # Captures standard URL formats and strips trailing punctuation from copied lists.
    matches = re.findall(r"https?://[^\s\]\[\)\(\'\"<>]+", text)
    cleaned = [m.rstrip(".,;:)") for m in matches]
    return list(dict.fromkeys(cleaned))


def domains_from_urls(urls: Iterable[str]) -> list[str]:
    domains: list[str] = []
    for url in urls:
        domain = normalize_domain(url)
        if domain:
            domains.append(domain)
    return list(dict.fromkeys(domains))


def relevance_score(text: str, terms: Iterable[str]) -> int:
    lowered = text.lower()
    return sum(1 for term in terms if term in lowered)


def tld_trust_score(domain: str) -> int:
    lowered = domain.lower()
    if any(lowered.endswith(tld) for tld in HIGH_TRUST_TLDS):
        return 2
    if lowered.endswith(".com"):
        return 0
    return 1


def regulator_hint_score(domain: str, title: str) -> int:
    haystack = f"{domain} {title}".lower()
    return 2 if any(hint in haystack for hint in REGULATOR_HINTS) else 0


def calculate_priority_score(
    max_relevance: float,
    article_count: float,
    trust_score: float,
    regulator_score: float,
) -> float:
    return (
        (max_relevance * 2.0)
        + min(article_count, 5) * 1.25
        + trust_score * 1.5
        + regulator_score * 1.5
    )


def classify_source_type(domain: str, title: str) -> str:
    haystack = f"{domain} {title}".lower().replace(" ", "")
    for label, hints in SOURCE_TYPE_RULES:
        if any(hint in haystack for hint in hints):
            return label
    return "Other"


def fetch_gdelt_articles(search_term: str, lookback_days: int, max_records: int) -> list[dict]:
    params = {
        "query": f'"{search_term}"',
        "mode": "ArtList",
        "format": "json",
        "maxrecords": str(max_records),
        "timespan": f"{lookback_days} days",
        "sort": "DateDesc",
    }
    response = requests.get(GDELT_ENDPOINT, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()
    return payload.get("articles", [])


def fetch_google_news_rss_articles(search_term: str, lookback_days: int, max_records: int) -> list[dict]:
    params = {
        "q": f'{search_term} when:{lookback_days}d',
        "hl": "en-GB",
        "gl": "GB",
        "ceid": "GB:en",
    }
    response = requests.get("https://news.google.com/rss/search", params=params, timeout=30)
    response.raise_for_status()

    root = ET.fromstring(response.content)
    articles: list[dict] = []
    for item in root.findall("./channel/item")[:max_records]:
        source = item.find("source")
        articles.append(
            {
                "title": item.findtext("title", default=""),
                "url": item.findtext("link", default=""),
                "sourceurl": source.get("url", "") if source is not None else "",
                "sourcename": source.text if source is not None else "",
                "seendate": item.findtext("pubDate", default=""),
                "sourcecountry": "",
                "language": "en",
                "socialimage": "",
            }
        )
    return articles


def run_discovery(config: DiscoveryConfig) -> pd.DataFrame:
    records: list[dict] = []

    for term in config.terms:
        articles: list[dict] = []
        try:
            articles.extend(
                fetch_gdelt_articles(
                    search_term=term,
                    lookback_days=config.lookback_days,
                    max_records=config.max_records_per_term,
                )
            )
        except Exception as exc:  # noqa: BLE001
            st.warning(f"GDELT search failed for term '{term}': {exc}")

        try:
            articles.extend(
                fetch_google_news_rss_articles(
                    search_term=term,
                    lookback_days=config.lookback_days,
                    max_records=config.max_records_per_term,
                )
            )
        except Exception as exc:  # noqa: BLE001
            st.warning(f"Google News RSS search failed for term '{term}': {exc}")

        if not articles:
            continue

        for item in articles:
            url = item.get("url", "")
            source_url = item.get("sourceurl", "")
            domain = normalize_domain(source_url or url)
            title = item.get("title", "")
            snippet = item.get("seendate", "")
            score = relevance_score(f"{title} {snippet}", RELEVANCE_TERMS)

            records.append(
                {
                    "search_term": term,
                    "title": title,
                    "url": source_url or url,
                    "domain": domain,
                    "source_country": item.get("sourcecountry", ""),
                    "language": item.get("language", ""),
                    "seen_date": item.get("seendate", ""),
                    "social_image": item.get("socialimage", ""),
                    "relevance_score": score,
                }
            )

    if not records:
        return pd.DataFrame(
            columns=[
                "search_term",
                "title",
                "url",
                "domain",
                "source_country",
                "language",
                "seen_date",
                "social_image",
                "relevance_score",
            ]
        )

    df = pd.DataFrame(records)
    df = df[df["url"].str.len() > 0]
    df = df[df["domain"].str.len() > 0]
    df = df.drop_duplicates(subset=["url"]).reset_index(drop=True)
    df["seen_date"] = pd.to_datetime(df["seen_date"], errors="coerce")
    return df.sort_values(by=["relevance_score", "seen_date"], ascending=[False, False])


def load_seen_sources() -> pd.DataFrame:
    if not SEEN_SOURCES_FILE.exists():
        return pd.DataFrame(columns=["domain", "first_seen", "last_seen", "times_seen"])

    df = pd.read_csv(SEEN_SOURCES_FILE)
    expected_cols = {"domain", "first_seen", "last_seen", "times_seen"}
    if set(df.columns) != expected_cols:
        return pd.DataFrame(columns=["domain", "first_seen", "last_seen", "times_seen"])
    return df


def load_current_source_urls() -> list[str]:
    if not CURRENT_SOURCES_FILE.exists():
        return []
    text = CURRENT_SOURCES_FILE.read_text(encoding="utf-8", errors="ignore")
    return extract_urls_from_text(text)


def save_current_source_urls(urls: Iterable[str]) -> None:
    unique_urls = list(dict.fromkeys(urls))
    CURRENT_SOURCES_FILE.write_text("\n".join(unique_urls) + "\n", encoding="utf-8")


def update_seen_sources(existing: pd.DataFrame, domains: Iterable[str]) -> pd.DataFrame:
    now_utc = datetime.now(timezone.utc).isoformat()
    domain_counts = pd.Series(list(domains)).value_counts()

    if existing.empty:
        updated = pd.DataFrame(
            {
                "domain": domain_counts.index,
                "first_seen": now_utc,
                "last_seen": now_utc,
                "times_seen": domain_counts.values,
            }
        )
        return updated.sort_values(by="times_seen", ascending=False).reset_index(drop=True)

    updated = existing.copy()
    existing_domains = set(updated["domain"].astype(str).tolist())

    for domain, count in domain_counts.items():
        if domain in existing_domains:
            mask = updated["domain"] == domain
            updated.loc[mask, "last_seen"] = now_utc
            updated.loc[mask, "times_seen"] = updated.loc[mask, "times_seen"].astype(int) + int(count)
        else:
            updated = pd.concat(
                [
                    updated,
                    pd.DataFrame(
                        [
                            {
                                "domain": domain,
                                "first_seen": now_utc,
                                "last_seen": now_utc,
                                "times_seen": int(count),
                            }
                        ]
                    ),
                ],
                ignore_index=True,
            )

    return updated.sort_values(by="times_seen", ascending=False).reset_index(drop=True)


def build_domain_rollup(df: pd.DataFrame, known_domains: set[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=[
                "domain",
                "article_count",
                "avg_relevance",
                "max_relevance",
                "latest_seen_date",
                "sample_title",
                "is_new_source",
            ]
        )

    grouped = (
        df.groupby("domain", as_index=False)
        .agg(
            article_count=("url", "count"),
            avg_relevance=("relevance_score", "mean"),
            max_relevance=("relevance_score", "max"),
            latest_seen_date=("seen_date", "max"),
            sample_title=("title", "first"),
        )
        .sort_values(by=["article_count", "max_relevance"], ascending=[False, False])
    )

    grouped["is_new_source"] = ~grouped["domain"].isin(known_domains)
    grouped["avg_relevance"] = grouped["avg_relevance"].round(2)
    grouped["trust_score"] = grouped["domain"].apply(tld_trust_score)
    grouped["regulator_score"] = grouped.apply(
        lambda r: regulator_hint_score(str(r["domain"]), str(r["sample_title"])),
        axis=1,
    )
    grouped["source_type"] = grouped.apply(
        lambda r: classify_source_type(str(r["domain"]), str(r["sample_title"])),
        axis=1,
    )
    grouped["priority_score"] = grouped.apply(
        lambda r: calculate_priority_score(
            float(r["max_relevance"]),
            float(r["article_count"]),
            float(r["trust_score"]),
            float(r["regulator_score"]),
        ),
        axis=1,
    ).round(2)
    return grouped


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def inject_ui_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(196, 224, 255, 0.7), transparent 28%),
                linear-gradient(180deg, #f7fbff 0%, #eef4f7 100%);
        }
        .hero {
            padding: 1.4rem 1.6rem;
            border-radius: 20px;
            background: linear-gradient(135deg, #12344d 0%, #1d587b 58%, #2d88a8 100%);
            color: #ffffff;
            box-shadow: 0 18px 42px rgba(18, 52, 77, 0.18);
            margin-bottom: 1rem;
        }
        .hero h1 {
            margin: 0;
            font-size: 2rem;
            font-weight: 700;
        }
        .hero p {
            margin: 0.45rem 0 0 0;
            font-size: 1rem;
            opacity: 0.92;
        }
        .panel {
            background: rgba(255, 255, 255, 0.86);
            border: 1px solid rgba(18, 52, 77, 0.09);
            border-radius: 18px;
            padding: 1rem 1.1rem;
            box-shadow: 0 10px 24px rgba(18, 52, 77, 0.08);
            margin-bottom: 1rem;
        }
        .panel h3 {
            margin-top: 0;
            margin-bottom: 0.35rem;
            color: #12344d;
        }
        .panel p {
            margin-bottom: 0;
            color: #35556b;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    st.markdown(
        """
        <div class="hero">
            <h1>Banking Compliance Source Finder</h1>
            <p>Run live scans, schedule automatic checks, and review new sources worth monitoring in one place.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def latest_update_text() -> str:
    if not LATEST_UPDATE_FILE.exists():
        return "No update has been generated yet. Run a live scan or wait for the scheduled task to complete."
    return LATEST_UPDATE_FILE.read_text(encoding="utf-8", errors="ignore")


def latest_digest_text() -> str:
    if not LATEST_DIGEST_FILE.exists():
        return "No digest has been generated yet. Run a live scan or background check to generate a digest."
    return LATEST_DIGEST_FILE.read_text(encoding="utf-8", errors="ignore")


def latest_monitor_candidates() -> pd.DataFrame:
    latest_candidates = OUTPUT_DIR / "latest_new_sources_worth_monitoring.csv"
    if not latest_candidates.exists():
        return pd.DataFrame()
    return pd.read_csv(latest_candidates)


def task_exists(task_name: str = DEFAULT_TASK_NAME) -> bool:
    result = subprocess.run(
        ["schtasks.exe", "/Query", "/TN", task_name],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def query_task_status(task_name: str = DEFAULT_TASK_NAME) -> str:
    result = subprocess.run(
        ["schtasks.exe", "/Query", "/TN", task_name, "/FO", "LIST", "/V"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return "Not scheduled"

    for line in result.stdout.splitlines():
        if "Status:" in line:
            return line.split(":", 1)[1].strip()
    return "Scheduled"


def create_or_update_task(interval_hours: int, task_name: str = DEFAULT_TASK_NAME) -> tuple[bool, str]:
    start_time = (datetime.now() + pd.Timedelta(minutes=2)).strftime("%H:%M")
    cmd_path = str(RUN_CHECK_CMD_FILE.resolve())
    result = subprocess.run(
        [
            "schtasks.exe",
            "/Create",
            "/TN",
            task_name,
            "/SC",
            "HOURLY",
            "/MO",
            str(interval_hours),
            "/ST",
            start_time,
            "/TR",
            f'"{cmd_path}"',
            "/F",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Task registration failed."
        return False, message
    return True, f"Scheduled checks every {interval_hours} hours. First start time: {start_time}."


def delete_task(task_name: str = DEFAULT_TASK_NAME) -> tuple[bool, str]:
    result = subprocess.run(
        ["schtasks.exe", "/Delete", "/TN", task_name, "/F"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Task deletion failed."
        return False, message
    return True, "Scheduled background checks removed."


def run_scheduled_task_now(task_name: str = DEFAULT_TASK_NAME) -> tuple[bool, str]:
    result = subprocess.run(
        ["schtasks.exe", "/Run", "/TN", task_name],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Could not start scheduled task."
        return False, message
    return True, "Scheduled task started in the background."


def run_live_scan_now() -> tuple[bool, str]:
    if not RUN_CHECK_CMD_FILE.exists():
        return False, f"Missing launcher file: {RUN_CHECK_CMD_FILE}"

    result = subprocess.run(
        ["cmd.exe", "/c", str(RUN_CHECK_CMD_FILE)],
        capture_output=True,
        text=True,
        check=False,
        timeout=360,
    )
    output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
    if result.returncode != 0:
        return False, output.strip() or "Live scan failed."
    return True, output.strip() or "Live scan completed."


def main() -> None:
    st.set_page_config(page_title="Banking Compliance Source Finder", layout="wide")

    ensure_data_dir()
    inject_ui_styles()
    render_hero()

    seen_sources = load_seen_sources()
    current_source_urls = load_current_source_urls()
    current_source_domains = set(domains_from_urls(current_source_urls))

    if seen_sources.empty and current_source_domains:
        seeded = update_seen_sources(pd.DataFrame(columns=["domain", "first_seen", "last_seen", "times_seen"]), current_source_domains)
        seeded.to_csv(SEEN_SOURCES_FILE, index=False)
        seen_sources = seeded

    control_tab, discovery_tab, baseline_tab = st.tabs(["Control Center", "Live Discovery", "Baseline Sources"])

    with st.sidebar:
        st.header("Discovery Settings")
        selected_defaults = st.multiselect(
            "Baseline search terms",
            options=DEFAULT_TERMS,
            default=DEFAULT_TERMS[:4],
        )
        custom_terms_raw = st.text_area(
            "Custom search terms (one per line)",
            placeholder="Basel 3.1\nPSD3 banking\nfraud controls bank",
        )
        lookback_days = st.slider("Lookback window (days)", min_value=1, max_value=30, value=7)
        max_records = st.slider("Max records per term", min_value=10, max_value=250, value=60, step=10)
        min_relevance = st.slider("Minimum relevance score", min_value=0, max_value=8, value=2)
        min_articles = st.slider("Minimum articles per domain", min_value=1, max_value=10, value=1)

        run = st.button("Run Discovery", type="primary")

    with control_tab:
        status_col, schedule_col = st.columns([1.1, 1])

        with status_col:
            st.markdown(
                """
                <div class="panel">
                    <h3>Background Monitor</h3>
                    <p>Use this area to run immediate scans and manage the automatic background schedule.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            task_status = query_task_status()
            summary_col1, summary_col2, summary_col3 = st.columns(3)
            summary_col1.metric("Baseline URLs", len(current_source_urls))
            summary_col2.metric("Baseline Domains", len(current_source_domains))
            summary_col3.metric("Schedule Status", task_status)

            live_col1, live_col2 = st.columns(2)
            if live_col1.button("Run Live Scan Now", use_container_width=True, type="primary"):
                with st.spinner("Running live scan..."):
                    ok, message = run_live_scan_now()
                if ok:
                    st.success("Live scan finished.")
                    if message:
                        st.text_area("Scan log", value=message, height=160)
                    st.rerun()
                else:
                    st.error(message)

            if live_col2.button("Run Scheduled Task Now", use_container_width=True):
                ok, message = run_scheduled_task_now()
                if ok:
                    st.success(message)
                else:
                    st.error(message)

        with schedule_col:
            st.markdown(
                """
                <div class="panel">
                    <h3>Scheduling</h3>
                    <p>Set automatic background checks so analysts do not need to touch scripts or Task Scheduler.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            schedule_interval = st.selectbox(
                "Run checks every",
                options=[1, 2, 3, 4, 6, 8, 12, 24],
                index=4,
                format_func=lambda hours: f"{hours} hours",
            )
            schedule_col1, schedule_col2 = st.columns(2)
            if schedule_col1.button("Save Background Schedule", use_container_width=True):
                ok, message = create_or_update_task(schedule_interval)
                if ok:
                    st.success(message)
                else:
                    st.error(message)
            if schedule_col2.button("Remove Schedule", use_container_width=True):
                ok, message = delete_task()
                if ok:
                    st.success(message)
                else:
                    st.error(message)

        st.subheader("Latest Update")
        st.text_area("Most recent background summary", value=latest_update_text(), height=300)

        st.subheader("Daily Digest")
        st.text_area("Analyst-friendly digest", value=latest_digest_text(), height=260)

        latest_candidates_df = latest_monitor_candidates()
        st.subheader("Latest New Sources Worth Monitoring")
        if latest_candidates_df.empty:
            st.info("No saved live-scan results yet.")
        else:
            st.dataframe(latest_candidates_df.head(50), use_container_width=True, hide_index=True)

    with baseline_tab:
        st.markdown(
            """
            <div class="panel">
                <h3>Current Monitored Sources</h3>
                <p>Paste your current source universe here so the app only flags truly new domains worth watching.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        baseline_text = st.text_area(
            "Paste monitored source URLs (one or many lines)",
            value="\n".join(current_source_urls),
            height=260,
        )

        uploaded = st.file_uploader(
            "Or upload a .txt/.csv URL list",
            type=["txt", "csv"],
            accept_multiple_files=False,
        )

        if uploaded is not None:
            uploaded_text = uploaded.getvalue().decode("utf-8", errors="ignore")
            baseline_text = f"{baseline_text}\n{uploaded_text}".strip()

        if st.button("Update Baseline Sources", type="primary"):
            baseline_urls = extract_urls_from_text(baseline_text)
            baseline_domains = domains_from_urls(baseline_urls)
            save_current_source_urls(baseline_urls)
            updated_seen = update_seen_sources(seen_sources, baseline_domains)
            updated_seen.to_csv(SEEN_SOURCES_FILE, index=False)
            st.success(f"Stored {len(baseline_urls)} baseline URLs and {len(baseline_domains)} baseline domains.")
            st.rerun()

        st.subheader("Known Sources")
        st.dataframe(seen_sources, use_container_width=True, hide_index=True)

    with discovery_tab:
        custom_terms = [t.strip() for t in custom_terms_raw.splitlines() if t.strip()]
        all_terms = list(dict.fromkeys(selected_defaults + custom_terms))

        st.markdown(
            """
            <div class="panel">
                <h3>Live Discovery Workspace</h3>
                <p>Use this tab for analyst-led ad hoc scans. Background monitoring can keep running separately.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if not run:
            st.info("Adjust the filters in the sidebar and click Run Discovery for an analyst-led live scan.")
            return

        if not all_terms:
            st.warning("Select at least one search term.")
            return

        with st.spinner("Running discovery..."):
            discovery_df = run_discovery(
                DiscoveryConfig(
                    terms=all_terms,
                    lookback_days=lookback_days,
                    max_records_per_term=max_records,
                )
            )

        seen_domains = set(seen_sources["domain"].astype(str).tolist())
        known_domains = seen_domains.union(current_source_domains)
        domain_rollup = build_domain_rollup(discovery_df, known_domains)
        new_sources = domain_rollup[domain_rollup["is_new_source"]].copy()
        monitor_candidates = new_sources[
            (new_sources["max_relevance"] >= min_relevance)
            & (new_sources["article_count"] >= min_articles)
        ].copy()
        monitor_candidates = monitor_candidates.sort_values(
            by=["priority_score", "max_relevance", "article_count", "latest_seen_date"],
            ascending=[False, False, False, False],
        )

        col1, col2, col3 = st.columns(3)
        col1.metric("Articles", int(discovery_df.shape[0]))
        col2.metric("Unique Domains", int(domain_rollup.shape[0]))
        col3.metric("New Domains", int(monitor_candidates.shape[0]))

        st.subheader("New Sources Worth Monitoring")
        st.caption("Filtered to domains not in baseline and meeting your relevance/article thresholds.")
        st.dataframe(monitor_candidates, use_container_width=True, hide_index=True)

        st.subheader("All Net-New Sources")
        st.dataframe(new_sources, use_container_width=True, hide_index=True)

        st.subheader("Source Overview")
        st.dataframe(domain_rollup, use_container_width=True, hide_index=True)

        st.subheader("Article Matches")
        st.dataframe(discovery_df, use_container_width=True, hide_index=True)

        articles_csv = discovery_df.to_csv(index=False).encode("utf-8")
        sources_csv = domain_rollup.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download Article Matches CSV",
            data=articles_csv,
            file_name="banking_compliance_article_matches.csv",
            mime="text/csv",
        )
        st.download_button(
            label="Download Source Overview CSV",
            data=sources_csv,
            file_name="banking_compliance_source_overview.csv",
            mime="text/csv",
        )
        monitor_csv = monitor_candidates.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download New Sources Worth Monitoring CSV",
            data=monitor_csv,
            file_name="banking_compliance_new_sources_worth_monitoring.csv",
            mime="text/csv",
        )

        if st.button("Save New Sources To History"):
            updated_seen = update_seen_sources(seen_sources, monitor_candidates["domain"].tolist())
            updated_seen.to_csv(SEEN_SOURCES_FILE, index=False)
            st.success(f"Saved {len(monitor_candidates)} domains to {SEEN_SOURCES_FILE}.")


if __name__ == "__main__":
    main()