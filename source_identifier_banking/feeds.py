import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import structlog

logger = structlog.get_logger()

COMMON_FEED_PATHS = [
    "/feed", "/feed.xml", "/feed.rss", "/rss", "/rss.xml", "/rss.rss",
    "/atom.xml", "/atom", "/feeds/all.rss", "/feeds/all.atom",
    "/news/feed", "/news/rss", "/blog/feed", "/blog/rss",
    "/?feed=rss2", "/?feed=atom",
]


def detect_feeds(url: str, session: requests.Session, timeout: int = 10) -> list[str]:
    """
    Detect RSS/Atom feed URLs for a given homepage URL.

    Parses HTML link tags, tries common feed paths, and checks sitemap.xml.
    Returns a deduplicated list of feed URLs.
    """
    feeds = []
    base = _base_url(url)

    # 1. Parse HTML for <link rel="alternate"> tags
    try:
        resp = session.get(url, timeout=timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup.find_all("link", rel="alternate"):
            tag_type = tag.get("type", "")
            if tag_type in ("application/rss+xml", "application/atom+xml"):
                href = tag.get("href", "")
                if href:
                    feeds.append(urljoin(url, href))
    except Exception as exc:
        logger.warning("feed_html_fetch_failed", url=url, error=str(exc))

    # 2. Try common feed paths
    for path in COMMON_FEED_PATHS:
        candidate = urljoin(base, path)
        if candidate in feeds:
            continue
        try:
            r = session.head(candidate, timeout=timeout, allow_redirects=True)
            if r.status_code == 200:
                feeds.append(candidate)
        except Exception:
            pass

    # 3. Try sitemap.xml for sub-sitemaps / feed hints
    try:
        sitemap_url = urljoin(base, "/sitemap.xml")
        r = session.get(sitemap_url, timeout=timeout)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "lxml-xml")
            for loc in soup.find_all("loc"):
                loc_text = loc.get_text(strip=True)
                if "feed" in loc_text.lower() or "rss" in loc_text.lower():
                    feeds.append(loc_text)
    except Exception:
        pass

    # Deduplicate preserving order
    seen = set()
    result = []
    for f in feeds:
        if f not in seen:
            seen.add(f)
            result.append(f)
    return result


def _base_url(url: str) -> str:
    """Return scheme + host of a URL."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"
