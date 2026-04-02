from urllib.parse import urlparse, urlunparse


def canonicalize_url(url: str) -> str:
    """Normalize a URL: lowercase scheme+host, prefer https, strip www, remove trailing slash."""
    parsed = urlparse(url)
    scheme = "https" if parsed.scheme in ("http", "https") else parsed.scheme
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path.rstrip("/") if parsed.path != "/" else ""
    return urlunparse((scheme, host, path, parsed.params, parsed.query, parsed.fragment))


def extract_domain(url: str) -> str:
    """Extract the domain from a URL, stripping www."""
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def is_same_domain(url1: str, url2: str) -> bool:
    """Return True if both URLs share the same domain."""
    return extract_domain(url1) == extract_domain(url2)


def normalize_domain(domain: str) -> str:
    """Lowercase and strip www. from a domain string."""
    domain = domain.lower().strip()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain
