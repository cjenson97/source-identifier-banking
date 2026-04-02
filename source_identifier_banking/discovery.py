import uuid
from urllib.parse import urlparse
import requests
import yaml
import structlog

from source_identifier_banking.url_utils import extract_domain, normalize_domain
from source_identifier_banking.feeds import detect_feeds
from source_identifier_banking.search import get_provider
from source_identifier_banking.crawler import LinkExpansionCrawler
from source_identifier_banking.scoring import (
    FS_TAXONOMY_KEYWORDS,
    score_candidate,
    apply_policy_filters,
    recommend_action,
)

logger = structlog.get_logger()

_MAX_QUERIES = 9  # cap: 3 jurisdictions × 3 regimes × 1 template per combination


class DiscoveryRunner:
    """Orchestrates the full source discovery pipeline."""

    def __init__(self, search_config_path: str, existing_sources_path: str) -> None:
        """
        Initialise with paths to config files.

        Args:
            search_config_path: Path to search_config.yaml.
            existing_sources_path: Path to existing_sources.yaml.
        """
        with open(search_config_path) as fh:
            self.config = yaml.safe_load(fh)
        with open(existing_sources_path) as fh:
            existing = yaml.safe_load(fh)

        self.existing_domains: set[str] = {
            normalize_domain(s["domain"])
            for s in existing.get("sources", [])
            if s.get("domain")
        }
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "SourceIdentifierBot/1.0"})

    def _generate_queries(self) -> list[str]:
        """Generate search queries from templates × jurisdictions × regimes (capped)."""
        templates = self.config.get("query_templates", [])
        jurisdictions = self.config.get("jurisdictions", [])[:3]
        regimes = self.config.get("regimes", [])[:3]
        queries = []
        for jurisdiction in jurisdictions:
            for regime in regimes:
                for template in templates:
                    q = template.format(jurisdiction=jurisdiction, regime=regime)
                    queries.append(q)
                    if len(queries) >= _MAX_QUERIES * len(templates):
                        return queries
        return queries

    def _collect_search_urls(self) -> list[dict]:
        """Run search queries and collect candidate URL + metadata dicts."""
        provider = get_provider(self.config)
        queries = self._generate_queries()
        seen_urls: set[str] = set()
        candidates = []

        for query in queries[:_MAX_QUERIES]:
            results = provider.search(query)
            for r in results:
                url = r.get("url", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                domain = extract_domain(url)
                parsed = urlparse(url)
                homepage = f"{parsed.scheme}://{parsed.netloc}"
                candidates.append({
                    "homepage_url": homepage,
                    "source_name": r.get("title", domain),
                    "description": r.get("description", ""),
                    "evidence_samples": [{"url": url, "title": r.get("title", "")}],
                })
        return candidates

    def _collect_crawler_urls(self) -> list[dict]:
        """Run link expansion crawler and return candidate dicts."""
        seed_urls = self.config.get("seed_urls", [])
        delay = self.config.get("rate_limit_delay_seconds", 2.0)
        timeout = self.config.get("request_timeout_seconds", 10)
        crawler = LinkExpansionCrawler(seed_urls, delay=delay, timeout=timeout)
        urls = crawler.crawl()
        candidates = []
        for url in urls:
            domain = extract_domain(url)
            candidates.append({
                "homepage_url": url,
                "source_name": domain,
                "description": "",
                "evidence_samples": [{"url": url, "title": domain}],
            })
        return candidates

    def _build_candidate(self, raw: dict) -> dict:
        """Enrich a raw candidate dict into the full candidate format."""
        url = raw["homepage_url"]
        domain = extract_domain(url)

        feed_urls = []
        try:
            feed_urls = detect_feeds(url, self._session, timeout=self.config.get("request_timeout_seconds", 10))
        except Exception as exc:
            logger.warning("feed_detection_failed", url=url, error=str(exc))

        feed_url = feed_urls[0] if feed_urls else None

        text = " ".join([raw.get("source_name", ""), raw.get("description", "")]).lower()
        tags = [kw for kw in FS_TAXONOMY_KEYWORDS if kw.lower() in text]

        candidate = {
            "candidate_id": str(uuid.uuid4()),
            "source_name": raw.get("source_name", domain),
            "homepage_url": url,
            "feed_url": feed_url,
            "jurisdiction": "Unknown",
            "source_type": "unknown",
            "fs_coverage_tags": tags,
            "evidence_samples": raw.get("evidence_samples", []),
            "description": raw.get("description", ""),
            "confidence_score": 0.0,
            "recommended_action": "reject",
            "reason": "",
        }
        return candidate

    def run(self) -> list[dict]:
        """
        Execute the full discovery pipeline.

        Returns a list of scored and sorted candidate dicts.
        """
        logger.info("discovery_start", existing_domains=len(self.existing_domains))

        raw_candidates: list[dict] = []
        raw_candidates.extend(self._collect_search_urls())
        raw_candidates.extend(self._collect_crawler_urls())

        seen_domains: set[str] = set()
        unique_raws: list[dict] = []
        for r in raw_candidates:
            domain = normalize_domain(extract_domain(r.get("homepage_url", "")))
            if domain and domain not in seen_domains:
                seen_domains.add(domain)
                unique_raws.append(r)

        logger.info("discovery_raw_candidates", count=len(unique_raws))

        results = []
        for raw in unique_raws:
            candidate = self._build_candidate(raw)

            keep, reason = apply_policy_filters(candidate, self.config)
            if not keep:
                logger.debug("candidate_filtered", url=candidate["homepage_url"], reason=reason)
                continue

            score = score_candidate(candidate, self.existing_domains, self.config)
            candidate["confidence_score"] = score
            candidate["recommended_action"] = recommend_action(score, self.config)
            candidate["reason"] = reason or f"Score: {score:.2f}"

            results.append(candidate)

        results.sort(key=lambda c: c["confidence_score"], reverse=True)
        logger.info("discovery_complete", candidates=len(results))
        return results
