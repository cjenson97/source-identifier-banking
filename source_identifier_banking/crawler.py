import time
import urllib.robotparser
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup
import structlog

from source_identifier_banking.url_utils import extract_domain

logger = structlog.get_logger()

_SOCIAL_DOMAINS = {
    "twitter.com", "facebook.com", "linkedin.com", "youtube.com",
    "instagram.com", "reddit.com", "tiktok.com", "pinterest.com",
}


class LinkExpansionCrawler:
    """Crawls seed URLs to discover linked authority/official domains."""

    def __init__(
        self,
        seed_urls: list[str],
        delay: float = 2.0,
        timeout: int = 10,
        max_links_per_seed: int = 20,
    ) -> None:
        """
        Initialise the crawler.

        Args:
            seed_urls: List of starting URLs to crawl.
            delay: Seconds to wait between requests.
            timeout: HTTP request timeout in seconds.
            max_links_per_seed: Maximum outgoing links to collect per seed.
        """
        self.seed_urls = seed_urls
        self.delay = delay
        self.timeout = timeout
        self.max_links_per_seed = max_links_per_seed
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "SourceIdentifierBot/1.0 (+https://github.com)"})

    def _robots_allowed(self, url: str) -> bool:
        """Check robots.txt to see if crawling is permitted."""
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        try:
            rp.read()
            return rp.can_fetch("*", url)
        except Exception:
            return True

    def _fetch_links(self, url: str) -> list[str]:
        """Fetch a page and return all hrefs found."""
        try:
            resp = self._session.get(url, timeout=self.timeout, allow_redirects=True)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            links = []
            for tag in soup.find_all("a", href=True):
                href = tag["href"].strip()
                if href.startswith("http"):
                    links.append(href)
                elif href.startswith("/"):
                    links.append(urljoin(url, href))
            return links
        except Exception as exc:
            logger.warning("crawler_fetch_failed", url=url, error=str(exc))
            return []

    def _is_candidate(self, url: str, seed_domains: set[str]) -> bool:
        """Return True if a URL looks like an official/authority page worth adding."""
        domain = extract_domain(url)
        if not domain:
            return False
        if domain in _SOCIAL_DOMAINS:
            return False
        if domain in seed_domains:
            return False
        return True

    def crawl(self) -> list[str]:
        """
        Crawl seed URLs and return candidate domain URLs.

        Returns a deduplicated list of candidate homepage URLs discovered
        via outgoing links from the seed pages.
        """
        seed_domains = {extract_domain(u) for u in self.seed_urls}
        candidates: dict[str, str] = {}

        for seed_url in self.seed_urls:
            if not self._robots_allowed(seed_url):
                logger.info("crawler_robots_disallowed", url=seed_url)
                continue

            links = self._fetch_links(seed_url)
            count = 0
            for link in links:
                if count >= self.max_links_per_seed:
                    break
                if not self._is_candidate(link, seed_domains):
                    continue
                domain = extract_domain(link)
                if domain and domain not in candidates:
                    parsed = urlparse(link)
                    homepage = f"{parsed.scheme}://{parsed.netloc}"
                    candidates[domain] = homepage
                    count += 1

            time.sleep(self.delay)

        return list(candidates.values())
