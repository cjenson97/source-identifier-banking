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
DEFAULT_LOOKBACK_DAYS = 7
DEFAULT_MAX_RECORDS = 80

DEFAULT_TERMS = [
    "banking compliance",
    "anti money laundering",
    "prudential regulation",
    "consumer duty bank",
    "bank enforcement action",
    "know your customer",
    "financial crime controls",
    "capital requirements bank",
    "Basel III capital adequacy",
    "DORA digital operational resilience",
    "sanctions screening compliance",
    "open banking PSD2 regulation",
    "crypto asset regulation bank",
    "climate risk financial disclosure",
    "FATF money laundering recommendations",
    "fintech regulatory supervision",
    "CBDC central bank digital currency",
    "correspondent banking regulation",
    "bank resolution recovery planning",
    "payment services regulation",
    "stress testing bank supervision",
    "beneficial ownership bank compliance",
    "suspicious activity report bank",
]

RELEVANCE_TERMS = [
    "compliance",
    "regulation",
    "regulatory",
    "supervision",
    "supervisory",
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
    "financial stability",
    "monetary",
    "resolution",
    "stress test",
    "buffer",
    "dora",
    "basel",
    "fintech",
    "cbdc",
    "crypto",
    "open banking",
    "payment",
    "beneficial ownership",
    "suspicious activity",
    "correspondent",
    "terrorist financing",
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
    "fincen",
    "fatf",
    "fsb",
    "esma",
    "eiopa",
    "eba",
    "apra",
    "mas",
    "hkma",
    "osfi",
    "cfpb",
    "fdic",
    "occ",
    "bis",
    "bcbs",
    "enforcement",
    "compliance",
]

REGULATOR_RSS_FEEDS: list[str] = [
    # UK
    "https://www.fca.org.uk/news/rss.xml",
    "https://www.bankofengland.co.uk/rss/publications",
    # EU
    "https://www.eba.europa.eu/rss/press-releases",
    "https://www.esma.europa.eu/rss/press-news.xml",
    "https://www.eiopa.europa.eu/rss/press-news_en.xml",
    # International
    "https://www.fsb.org/feed/",
    "https://www.bis.org/rss/bcbspubl.rss",
    "https://www.bis.org/rss/fsi_papers.rss",
    "https://www.fatf-gafi.org/en/media/news/rss.xml",
    # US
    "https://www.federalreserve.gov/feeds/press_all.xml",
    "https://www.occ.gov/rss/rss-news.xml",
    "https://www.fdic.gov/resources/rss.xml",
    "https://www.consumerfinance.gov/about-us/newsroom/activity-feed.xml",
    "https://www.sec.gov/rss/litigation/litreleases.xml",
    "https://www.fincen.gov/rss.xml",
    # Asia-Pacific
    "https://www.mas.gov.sg/news/rss",
    "https://www.hkma.gov.hk/eng/rss/_rss_press-releases.xml",
    # Canada
    "https://www.osfi-bsif.gc.ca/en/news-communications/feed",
    # Industry / global news
    "https://feeds.reuters.com/reuters/businessNews",
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


def relevance_band(score: float) -> str:
    if score >= 4:
        return "Very Strong"
    if score >= 3:
        return "Strong"
    if score >= 2:
        return "Moderate"
    return "Early Signal"


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


def fetch_regulator_rss_articles() -> list[dict]:
    """Fetch articles directly from curated banking/compliance regulator RSS and Atom feeds."""
    articles: list[dict] = []
    ATOM_NS = "http://www.w3.org/2005/Atom"

    for feed_url in REGULATOR_RSS_FEEDS:
        try:
            resp = requests.get(
                feed_url,
                timeout=15,
                headers={"User-Agent": "Mozilla/5.0 (compatible; BankingComplianceMonitor/1.0)"},
            )
            if resp.status_code != 200:
                continue
            root = ET.fromstring(resp.content)

            if ATOM_NS in root.tag:
                # Atom 1.0 feed
                for entry in root.findall(f"{{{ATOM_NS}}}entry")[:30]:
                    title = (entry.findtext(f"{{{ATOM_NS}}}title") or "").strip()
                    link_elem = entry.find(f"{{{ATOM_NS}}}link[@rel='alternate']")
                    if link_elem is None:
                        link_elem = entry.find(f"{{{ATOM_NS}}}link")
                    link = link_elem.get("href", "") if link_elem is not None else ""
                    pub = (
                        entry.findtext(f"{{{ATOM_NS}}}published")
                        or entry.findtext(f"{{{ATOM_NS}}}updated")
                        or ""
                    )
                    if link:
                        articles.append({
                            "title": title,
                            "url": link,
                            "sourceurl": link,
                            "sourcename": normalize_domain(feed_url),
                            "seendate": pub,
                            "sourcecountry": "",
                            "language": "en",
                            "socialimage": "",
                        })
            else:
                # RSS 2.0 feed
                for item in root.findall("./channel/item")[:30]:
                    title = (item.findtext("title") or "").strip()
                    link = (item.findtext("link") or "").strip()
                    pub = item.findtext("pubDate") or ""
                    if link:
                        articles.append({
                            "title": title,
                            "url": link,
                            "sourceurl": link,
                            "sourcename": normalize_domain(feed_url),
                            "seendate": pub,
                            "sourcecountry": "",
                            "language": "en",
                            "socialimage": "",
                        })
        except Exception:  # noqa: BLE001
            pass

    return articles


def run_discovery(config: DiscoveryConfig) -> pd.DataFrame:
    records: list[dict] = []

    # --- Fetch directly from curated regulator RSS/Atom feeds (once, no search term filter) ---
    try:
        reg_items = fetch_regulator_rss_articles()
    except Exception:  # noqa: BLE001
        reg_items = []

    for item in reg_items:
        url = item.get("url", "")
        source_url = item.get("sourceurl", "")
        domain = normalize_domain(source_url or url)
        if not domain:
            continue
        title = item.get("title", "")
        score = relevance_score(title, RELEVANCE_TERMS)
        records.append({
            "search_term": "regulator_feed",
            "title": title,
            "url": source_url or url,
            "domain": domain,
            "source_country": "",
            "language": "en",
            "seen_date": item.get("seendate", ""),
            "social_image": "",
            "relevance_score": score,
        })

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
                "example_headline",
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
            example_headline=("title", "first"),
        )
        .sort_values(by=["article_count", "max_relevance"], ascending=[False, False])
    )

    grouped["is_new_source"] = ~grouped["domain"].isin(known_domains)
    grouped["avg_relevance"] = grouped["avg_relevance"].round(2)
    grouped["trust_score"] = grouped["domain"].apply(tld_trust_score)
    grouped["regulator_score"] = grouped.apply(
        lambda r: regulator_hint_score(str(r["domain"]), str(r["example_headline"])),
        axis=1,
    )
    grouped["source_type"] = grouped.apply(
        lambda r: classify_source_type(str(r["domain"]), str(r["example_headline"])),
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
    grouped["relevance_band"] = grouped["max_relevance"].apply(relevance_band)
    return grouped


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def inject_ui_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700;800&display=swap');

        :root {
            --vixio-red: #d92d27;
            --vixio-red-dark: #a81d19;
            --vixio-ink: #0f172a;
            --vixio-slate: #334155;
            --vixio-bg: #f8fafc;
            --vixio-card: #ffffff;
        }

        .stApp {
            font-family: 'Manrope', sans-serif;
            background:
                radial-gradient(circle at top right, rgba(217, 45, 39, 0.10), transparent 30%),
                radial-gradient(circle at top left, rgba(15, 23, 42, 0.06), transparent 28%),
                linear-gradient(180deg, #ffffff 0%, var(--vixio-bg) 100%);
            color: var(--vixio-ink);
        }
        .hero {
            padding: 1.6rem 1.8rem;
            border-radius: 24px;
            background: linear-gradient(130deg, var(--vixio-ink) 0%, #1e293b 52%, #334155 100%);
            color: #ffffff;
            box-shadow: 0 20px 44px rgba(15, 23, 42, 0.26);
            margin-bottom: 1.2rem;
        }
        .hero h1 {
            margin: 0;
            font-size: 2.1rem;
            font-weight: 800;
            letter-spacing: 0.2px;
        }
        .hero p {
            margin: 0.45rem 0 0 0;
            font-size: 1rem;
            opacity: 0.94;
        }
        .panel {
            background: var(--vixio-card);
            border: 1px solid rgba(15, 23, 42, 0.10);
            border-radius: 18px;
            padding: 1rem 1.1rem;
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
            margin-bottom: 1rem;
        }
        .panel h3 {
            margin-top: 0;
            margin-bottom: 0.35rem;
            color: var(--vixio-ink);
        }
        .panel p {
            margin-bottom: 0;
            color: var(--vixio-slate);
        }
        .kpi-note {
            font-size: 0.9rem;
            color: var(--vixio-slate);
            margin-bottom: 0.6rem;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 0.35rem;
            border-bottom: 2px solid rgba(15, 23, 42, 0.10);
        }
        .stTabs [data-baseweb="tab"] {
            color: var(--vixio-slate) !important;
            font-weight: 700;
            background: transparent;
            border-radius: 10px 10px 0 0;
            padding: 0.65rem 0.9rem;
        }
        .stTabs [aria-selected="true"] {
            color: var(--vixio-red) !important;
            border-bottom: 3px solid var(--vixio-red) !important;
        }

        .stMarkdown, .stText, .stCaption, .stDataFrame, .stAlert, .stMetric, label, p, h1, h2, h3, h4 {
            color: var(--vixio-ink);
        }

        .stButton > button {
            border-radius: 10px;
            border: 1px solid rgba(15, 23, 42, 0.18);
        }
        .stButton > button[kind="primary"] {
            background: var(--vixio-red);
            border-color: var(--vixio-red-dark);
            color: #ffffff;
        }
        .stButton > button[kind="primary"]:hover {
            background: var(--vixio-red-dark);
        }

        .stSpinner > div {
            color: var(--vixio-ink);
            font-weight: 600;
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
            <p>Open the app and it automatically scans for net-new compliance sources your team does not yet monitor.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def run_live_discovery(
    all_terms: list[str],
    seen_sources: pd.DataFrame,
    current_source_domains: set[str],
    strict_mode: bool,
    max_records: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    discovery_df = run_discovery(
        DiscoveryConfig(
            terms=all_terms,
            lookback_days=DEFAULT_LOOKBACK_DAYS,
            max_records_per_term=max_records,
        )
    )

    seen_domains = set(seen_sources["domain"].astype(str).tolist())
    known_domains = seen_domains.union(current_source_domains)
    domain_rollup = build_domain_rollup(discovery_df, known_domains)
    new_sources = domain_rollup[domain_rollup["is_new_source"]].copy()

    if strict_mode:
        monitor_candidates = new_sources[
            new_sources["relevance_band"].isin(["Very Strong", "Strong"])
        ].copy()
    else:
        monitor_candidates = new_sources[
            new_sources["relevance_band"].isin(["Very Strong", "Strong", "Moderate"])
        ].copy()

    monitor_candidates = monitor_candidates.sort_values(
        by=["priority_score", "max_relevance", "article_count", "latest_seen_date"],
        ascending=[False, False, False, False],
    )
    return discovery_df, domain_rollup, monitor_candidates


def format_source_table(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    formatted = df.copy()
    if "latest_seen_date" in formatted.columns:
        formatted["latest_seen_date"] = pd.to_datetime(formatted["latest_seen_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    rename_map = {
        "domain": "Source Domain",
        "source_type": "Source Type",
        "relevance_band": "Relevance",
        "article_count": "Recent Mentions",
        "latest_seen_date": "Last Seen",
        "example_headline": "Example Headline",
    }
    keep_cols = [
        "domain",
        "source_type",
        "relevance_band",
        "article_count",
        "latest_seen_date",
        "example_headline",
    ]
    keep_cols = [c for c in keep_cols if c in formatted.columns]
    return formatted[keep_cols].rename(columns=rename_map)


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
        st.header("Scan Preferences")
        selected_defaults = st.multiselect(
            "Focus Topics",
            options=DEFAULT_TERMS,
            default=DEFAULT_TERMS,
        )
        custom_terms_raw = st.text_area(
            "Optional extra topics (one per line)",
            placeholder="Basel 3.1\nPSD3 banking\nfraud controls bank",
        )
        strict_mode = st.toggle("Show only Strong matches", value=True)
        max_records = st.slider("Scan depth", min_value=20, max_value=250, value=DEFAULT_MAX_RECORDS, step=10)
        manual_refresh = st.button("Refresh Scan", type="primary")

    custom_terms = [t.strip() for t in custom_terms_raw.splitlines() if t.strip()]
    all_terms = list(dict.fromkeys(selected_defaults + custom_terms))
    if not all_terms:
        all_terms = DEFAULT_TERMS

    should_scan = manual_refresh or ("last_scan" not in st.session_state)
    if should_scan:
        with st.spinner("Scanning for new sources..."):
            discovery_df, domain_rollup, monitor_candidates = run_live_discovery(
                all_terms=all_terms,
                seen_sources=seen_sources,
                current_source_domains=current_source_domains,
                strict_mode=strict_mode,
                max_records=max_records,
            )
        st.session_state["last_scan"] = {
            "discovery_df": discovery_df,
            "domain_rollup": domain_rollup,
            "monitor_candidates": monitor_candidates,
            "scan_time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "strict_mode": strict_mode,
        }

    scan_state = st.session_state.get("last_scan", {})
    discovery_df = scan_state.get("discovery_df", pd.DataFrame())
    domain_rollup = scan_state.get("domain_rollup", pd.DataFrame())
    monitor_candidates = scan_state.get("monitor_candidates", pd.DataFrame())
    scan_time = scan_state.get("scan_time", "Not scanned yet")
    strict_mode_used = scan_state.get("strict_mode", strict_mode)

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
            st.markdown(f"<div class='kpi-note'>Latest scan: {scan_time} | Mode: {'Strong only' if strict_mode_used else 'Broad'}</div>", unsafe_allow_html=True)

            live_col1, live_col2 = st.columns(2)
            if live_col1.button("Run Background Scan Now", use_container_width=True, type="primary"):
                with st.spinner("Running background scan..."):
                    ok, message = run_live_scan_now()
                if ok:
                    st.success("Background scan finished and files updated.")
                    if message:
                        st.text_area("Scan log", value=message, height=160)
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
            st.dataframe(format_source_table(latest_candidates_df.head(50)), use_container_width=True, hide_index=True)

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
        st.markdown(
            """
            <div class="panel">
                <h3>Live Discovery Results</h3>
                <p>This scan runs automatically when the app opens. Use Refresh Scan in the sidebar at any time.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        new_sources = domain_rollup[domain_rollup["is_new_source"]].copy() if not domain_rollup.empty else pd.DataFrame()

        col1, col2, col3 = st.columns(3)
        col1.metric("Articles", int(discovery_df.shape[0]))
        col2.metric("Unique Domains", int(domain_rollup.shape[0]))
        col3.metric("New Domains", int(monitor_candidates.shape[0]))

        st.subheader("New Sources Worth Monitoring")
        st.caption("Only sources not already in your monitored baseline are listed here.")
        st.dataframe(format_source_table(monitor_candidates), use_container_width=True, hide_index=True)

        st.subheader("All Net-New Sources")
        st.dataframe(format_source_table(new_sources), use_container_width=True, hide_index=True)

        st.subheader("Source Overview")
        st.dataframe(format_source_table(domain_rollup), use_container_width=True, hide_index=True)

        with st.expander("View matching articles"):
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