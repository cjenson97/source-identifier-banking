from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import pandas as pd
import requests


GDELT_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
DATA_DIR = Path("data")
OUTPUT_DIR = DATA_DIR / "output"
SEEN_SOURCES_FILE = DATA_DIR / "seen_sources.csv"
CURRENT_SOURCES_FILE = DATA_DIR / "current_sources.txt"
CONFIG_FILE = Path("discovery_config.json")

DEFAULT_CONFIG = {
    "check_interval_hours": 6,
    "lookback_days": 7,
    "max_records_per_term": 80,
    "min_relevance_score": 2,
    "min_articles_per_domain": 1,
    "terms": [
        "banking compliance",
        "anti money laundering",
        "prudential regulation",
        "bank enforcement action",
        "financial crime controls",
        "payment systems regulation",
        "cybersecurity banking",
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
        "stress testing bank supervision",
        "beneficial ownership bank compliance",
        "suspicious activity report bank",
        "consumer protection financial regulation",
        "ESG sustainable finance bank",
        "know your customer KYC bank",
        "bank capital buffer requirement",
    ],
    "relevance_terms": [
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
    ],
    "high_trust_tlds": [".gov", ".gob", ".gc.ca", ".eu", ".int", ".org"],
    "regulator_hints": [
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
    ],
}

SOURCE_TYPE_RULES = [
    ("Regulator", ["fca", "sec", "finra", "fma", "fsa", "bank", "centralbank", "supervision", "authority", "prudential"]),
    ("Legislation", ["parliament", "legislation", "gazette", "congress", "senate", "assembly", "laws", "bill"]),
    ("Enforcement", ["enforcement", "sanction", "penalty", "attorneygeneral", "justice", "cease-desist", "revocation"]),
    ("FIU/AML", ["fiu", "aml", "moneylaundering", "fintrac", "fincen", "uif", "uaf", "fatf"]),
    ("Industry", ["association", "bankingassociation", "trade", "chamber", "federation"]),
    ("Media", ["news", "media", "press", "reuters", "law", "blog"]),
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


def ensure_paths() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
        return DEFAULT_CONFIG

    raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    merged = DEFAULT_CONFIG.copy()
    merged.update(raw)
    return merged


def normalize_domain(url: str) -> str:
    parsed = urlparse(url)
    domain = parsed.netloc.lower().strip()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def extract_urls_from_text(text: str) -> list[str]:
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


def domain_is_known(domain: str, known_domains: set[str]) -> bool:
    candidate = domain.lower().strip()
    if not candidate:
        return False

    for known in known_domains:
        reference = str(known).lower().strip()
        if not reference:
            continue

        # Treat parent/child domains as covered to avoid resurfacing known sources.
        if candidate == reference:
            return True
        if candidate.endswith(f".{reference}"):
            return True
        if reference.endswith(f".{candidate}"):
            return True

    return False


def load_current_source_domains() -> set[str]:
    if not CURRENT_SOURCES_FILE.exists():
        return set()
    text = CURRENT_SOURCES_FILE.read_text(encoding="utf-8", errors="ignore")
    return set(domains_from_urls(extract_urls_from_text(text)))


def load_seen_sources() -> pd.DataFrame:
    if not SEEN_SOURCES_FILE.exists():
        return pd.DataFrame(columns=["domain", "first_seen", "last_seen", "times_seen"])
    df = pd.read_csv(SEEN_SOURCES_FILE)
    expected = {"domain", "first_seen", "last_seen", "times_seen"}
    if set(df.columns) != expected:
        return pd.DataFrame(columns=["domain", "first_seen", "last_seen", "times_seen"])
    return df


def update_seen_sources(existing: pd.DataFrame, domains: Iterable[str]) -> pd.DataFrame:
    now_utc = datetime.now(timezone.utc).isoformat()
    domain_counts = pd.Series(list(domains)).value_counts()

    if existing.empty:
        seeded = pd.DataFrame(
            {
                "domain": domain_counts.index,
                "first_seen": now_utc,
                "last_seen": now_utc,
                "times_seen": domain_counts.values,
            }
        )
        return seeded.sort_values(by="times_seen", ascending=False).reset_index(drop=True)

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


def relevance_score(text: str, terms: Iterable[str]) -> int:
    lowered = text.lower()
    return sum(1 for term in terms if term in lowered)


def tld_trust_score(domain: str, high_trust_tlds: Iterable[str]) -> int:
    lowered = domain.lower()
    if any(lowered.endswith(tld) for tld in high_trust_tlds):
        return 2
    if lowered.endswith(".com"):
        return 0
    return 1


def regulator_hint_score(domain: str, title: str, regulator_hints: Iterable[str]) -> int:
    haystack = f"{domain} {title}".lower()
    return 2 if any(hint in haystack for hint in regulator_hints) else 0


def priority_score(max_relevance: float, article_count: float, trust: float, regulator: float) -> float:
    return (max_relevance * 2.0) + (min(article_count, 5) * 1.25) + (trust * 1.5) + (regulator * 1.5)


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
    response = requests.get(GDELT_ENDPOINT, params=params, timeout=40)
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
                        })
            else:
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
                        })
        except Exception:  # noqa: BLE001
            pass

    return articles


def run_discovery(config: dict) -> pd.DataFrame:
    rows: list[dict] = []

    # --- Direct regulator/authority RSS feeds (fetched once, independent of search terms) ---
    try:
        reg_items = fetch_regulator_rss_articles()
    except Exception:  # noqa: BLE001
        reg_items = []

    print(f"[INFO] Regulator RSS feeds returned {len(reg_items)} articles")

    for item in reg_items:
        url = item.get("url", "")
        source_url = item.get("sourceurl", "")
        domain = normalize_domain(source_url or url)
        if not url or not domain:
            continue
        title = item.get("title", "")
        score = relevance_score(f"{title}", config["relevance_terms"])
        rows.append({
            "search_term": "regulator_feed",
            "title": title,
            "url": source_url or url,
            "domain": domain,
            "seen_date": item.get("seendate", ""),
            "source_country": "",
            "language": "en",
            "relevance_score": score,
        })

    terms = config["terms"]
    for term in terms:
        articles: list[dict] = []
        try:
            articles.extend(
                fetch_gdelt_articles(
                    term,
                    int(config["lookback_days"]),
                    int(config["max_records_per_term"]),
                )
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] GDELT failed: {term} | {exc}")

        try:
            articles.extend(
                fetch_google_news_rss_articles(
                    term,
                    int(config["lookback_days"]),
                    int(config["max_records_per_term"]),
                )
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] Google News RSS failed: {term} | {exc}")

        if not articles:
            continue

        for item in articles:
            url = item.get("url", "")
            source_url = item.get("sourceurl", "")
            domain = normalize_domain(source_url or url)
            if not url or not domain:
                continue
            title = item.get("title", "")
            score = relevance_score(f"{title} {item.get('seendate', '')}", config["relevance_terms"])
            rows.append(
                {
                    "search_term": term,
                    "title": title,
                    "url": source_url or url,
                    "domain": domain,
                    "seen_date": item.get("seendate", ""),
                    "source_country": item.get("sourcecountry", ""),
                    "language": item.get("language", ""),
                    "relevance_score": score,
                }
            )

    if not rows:
        return pd.DataFrame(
            columns=[
                "search_term",
                "title",
                "url",
                "domain",
                "seen_date",
                "source_country",
                "language",
                "relevance_score",
            ]
        )

    df = pd.DataFrame(rows).drop_duplicates(subset=["url"]).reset_index(drop=True)
    df["seen_date"] = pd.to_datetime(df["seen_date"], errors="coerce")
    return df.sort_values(by=["relevance_score", "seen_date"], ascending=[False, False])


def build_domain_rollup(discovery_df: pd.DataFrame, known_domains: set[str], config: dict) -> pd.DataFrame:
    if discovery_df.empty:
        return pd.DataFrame(
            columns=[
                "domain",
                "article_count",
                "avg_relevance",
                "max_relevance",
                "latest_seen_date",
                "sample_title",
                "sample_url",
                "source_type",
                "trust_score",
                "regulator_score",
                "priority_score",
                "is_new_source",
            ]
        )

    grouped = (
        discovery_df.groupby("domain", as_index=False)
        .agg(
            article_count=("url", "count"),
            avg_relevance=("relevance_score", "mean"),
            max_relevance=("relevance_score", "max"),
            latest_seen_date=("seen_date", "max"),
            sample_title=("title", "first"),
            sample_url=("url", "first"),
        )
        .sort_values(by=["article_count", "max_relevance"], ascending=[False, False])
    )

    grouped["avg_relevance"] = grouped["avg_relevance"].round(2)
    grouped["trust_score"] = grouped["domain"].apply(
        lambda d: tld_trust_score(str(d), config["high_trust_tlds"])
    )
    grouped["regulator_score"] = grouped.apply(
        lambda r: regulator_hint_score(str(r["domain"]), str(r["sample_title"]), config["regulator_hints"]),
        axis=1,
    )
    grouped["source_type"] = grouped.apply(
        lambda r: classify_source_type(str(r["domain"]), str(r["sample_title"])),
        axis=1,
    )
    grouped["priority_score"] = grouped.apply(
        lambda r: priority_score(
            float(r["max_relevance"]),
            float(r["article_count"]),
            float(r["trust_score"]),
            float(r["regulator_score"]),
        ),
        axis=1,
    ).round(2)
    grouped["is_new_source"] = ~grouped["domain"].apply(
        lambda d: domain_is_known(str(d), known_domains)
    )
    return grouped


def update_compiled_master(candidates: pd.DataFrame, run_time: str) -> pd.DataFrame:
    master_file = OUTPUT_DIR / "compiled_new_sources.csv"
    cols = [
        "domain",
        "first_detected",
        "last_detected",
        "detection_count",
        "max_priority_score",
        "max_relevance",
        "max_articles",
        "sample_title",
        "sample_url",
    ]

    if master_file.exists():
        master = pd.read_csv(master_file)
    else:
        master = pd.DataFrame(columns=cols)

    incoming = candidates.copy()
    if incoming.empty:
        master.to_csv(master_file, index=False)
        return master

    existing_domains = set(master["domain"].astype(str).tolist())
    for _, row in incoming.iterrows():
        domain = str(row["domain"])
        if domain in existing_domains:
            mask = master["domain"] == domain
            master.loc[mask, "last_detected"] = run_time
            master.loc[mask, "detection_count"] = master.loc[mask, "detection_count"].astype(int) + 1
            master.loc[mask, "max_priority_score"] = master.loc[mask, "max_priority_score"].astype(float).clip(
                lower=float(row["priority_score"])
            )
            master.loc[mask, "max_relevance"] = master.loc[mask, "max_relevance"].astype(float).clip(
                lower=float(row["max_relevance"])
            )
            master.loc[mask, "max_articles"] = master.loc[mask, "max_articles"].astype(int).clip(
                lower=int(row["article_count"])
            )
        else:
            master = pd.concat(
                [
                    master,
                    pd.DataFrame(
                        [
                            {
                                "domain": domain,
                                "first_detected": run_time,
                                "last_detected": run_time,
                                "detection_count": 1,
                                "max_priority_score": float(row["priority_score"]),
                                "max_relevance": float(row["max_relevance"]),
                                "max_articles": int(row["article_count"]),
                                "sample_title": str(row["sample_title"]),
                                "sample_url": str(row["sample_url"]),
                            }
                        ]
                    ),
                ],
                ignore_index=True,
            )

    master = master.sort_values(by=["max_priority_score", "last_detected"], ascending=[False, False]).reset_index(drop=True)
    master.to_csv(master_file, index=False)
    return master


def write_latest_update_report(
    run_time: str,
    discovery_df: pd.DataFrame,
    new_sources: pd.DataFrame,
    candidates: pd.DataFrame,
) -> None:
    report_file = OUTPUT_DIR / "latest_update.txt"
    lines = [
        "Banking Compliance Source Monitor Update",
        "======================================",
        f"Run time (UTC): {run_time}",
        f"Articles fetched: {len(discovery_df)}",
        f"Net-new domains found: {len(new_sources)}",
        f"New sources worth monitoring: {len(candidates)}",
        "",
        "Top 20 new sources worth monitoring:",
    ]

    top = candidates.head(20)
    if top.empty:
        lines.append("- None in this run")
    else:
        for _, row in top.iterrows():
            lines.append(
                "- "
                + f"{row['domain']} | priority={row['priority_score']}"
                + f" | relevance={row['max_relevance']} | articles={row['article_count']}"
            )

    lines.extend(
        [
            "",
            "Generated files:",
            "- data/output/latest_new_sources_worth_monitoring.csv",
            "- data/output/latest_all_net_new_sources.csv",
            "- data/output/latest_source_overview.csv",
            "- data/output/latest_article_matches.csv",
            "- data/output/compiled_new_sources.csv",
        ]
    )

    report_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_latest_daily_digest(run_time: str, candidates: pd.DataFrame) -> None:
    digest_file = OUTPUT_DIR / "latest_daily_digest.txt"
    lines = [
        "Daily Digest: New Banking Compliance Sources",
        "===========================================",
        f"Generated at (UTC): {run_time}",
        "",
    ]

    if candidates.empty:
        lines.append("No high-priority new sources were found in the latest run.")
        digest_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    type_counts = candidates["source_type"].value_counts().to_dict()
    lines.append("Source types identified:")
    for source_type, count in type_counts.items():
        lines.append(f"- {source_type}: {count}")

    lines.extend(["", "Top sources to review:"])
    for _, row in candidates.head(15).iterrows():
        lines.append(
            "- "
            + f"{row['domain']} ({row['source_type']})"
            + f" | priority={row['priority_score']}"
            + f" | sample={row['sample_title']}"
        )

    digest_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_single_check() -> None:
    ensure_paths()
    config = load_config()
    run_time = datetime.now(timezone.utc).isoformat()

    seen_sources = load_seen_sources()
    seen_domains = set(seen_sources["domain"].astype(str).tolist())
    baseline_domains = load_current_source_domains()
    known_domains = seen_domains.union(baseline_domains)

    if seen_sources.empty and baseline_domains:
        seeded = update_seen_sources(seen_sources, baseline_domains)
        seeded.to_csv(SEEN_SOURCES_FILE, index=False)
        seen_sources = seeded
        seen_domains = set(seeded["domain"].astype(str).tolist())
        known_domains = seen_domains.union(baseline_domains)

    discovery_df = run_discovery(config)
    rollup = build_domain_rollup(discovery_df, known_domains, config)
    new_sources = rollup[rollup["is_new_source"]].copy()
    candidates = new_sources[
        (new_sources["max_relevance"] >= int(config["min_relevance_score"]))
        & (new_sources["article_count"] >= int(config["min_articles_per_domain"]))
    ].copy()
    candidates = candidates.sort_values(
        by=["priority_score", "max_relevance", "article_count", "latest_seen_date"],
        ascending=[False, False, False, False],
    )
    candidates["run_time_utc"] = run_time

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    discovery_df.to_csv(OUTPUT_DIR / "latest_article_matches.csv", index=False)
    rollup.to_csv(OUTPUT_DIR / "latest_source_overview.csv", index=False)
    new_sources.to_csv(OUTPUT_DIR / "latest_all_net_new_sources.csv", index=False)
    candidates.to_csv(OUTPUT_DIR / "latest_new_sources_worth_monitoring.csv", index=False)
    candidates.to_csv(OUTPUT_DIR / f"new_sources_worth_monitoring_{ts}.csv", index=False)

    update_compiled_master(candidates, run_time)
    write_latest_update_report(run_time, discovery_df, new_sources, candidates)
    write_latest_daily_digest(run_time, candidates)

    updated_seen = update_seen_sources(seen_sources, candidates["domain"].tolist())
    updated_seen.to_csv(SEEN_SOURCES_FILE, index=False)

    print(f"[INFO] Run complete at {run_time}")
    print(f"[INFO] Articles fetched: {len(discovery_df)}")
    print(f"[INFO] Net-new domains: {len(new_sources)}")
    print(f"[INFO] Candidates worth monitoring: {len(candidates)}")
    print(f"[INFO] Output folder: {OUTPUT_DIR.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run automated banking compliance source checks.")
    parser.add_argument("--once", action="store_true", help="Run one check and exit.")
    args = parser.parse_args()

    if args.once:
        run_single_check()
        return

    config = load_config()
    interval_hours = float(config.get("check_interval_hours", 6))
    sleep_seconds = int(interval_hours * 3600)
    print(f"[INFO] Starting scheduler loop, interval={interval_hours} hours")

    while True:
        try:
            run_single_check()
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] Scheduled run failed: {exc}")
        print(f"[INFO] Sleeping for {interval_hours} hours")
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()