from urllib.parse import urlparse
import structlog

from source_identifier_banking.url_utils import extract_domain, normalize_domain

logger = structlog.get_logger()

FS_TAXONOMY_KEYWORDS = [
    "banking", "bank", "financial", "finance", "credit", "lending", "mortgage",
    "investment", "securities", "capital", "liquidity", "prudential",
    "AML", "anti-money laundering", "KYC", "sanctions", "CTF",
    "consumer protection", "GDPR", "data protection", "privacy",
    "cybersecurity", "operational resilience", "DORA",
    "crypto", "digital asset", "CBDC", "stablecoin",
    "market abuse", "insider trading", "MiFID",
    "enforcement", "regulatory", "regulation", "compliance",
    "Basel", "FSB", "IOSCO", "FATF",
    "ESG", "climate", "sustainability", "disclosure",
    "AI", "artificial intelligence", "algorithm",
    "payment", "remittance", "fintech",
]

_AUTHORITY_KEYWORDS = [
    "regulator", "regulatory", "authority", "central bank", "ministry",
    "commission", "board", "supervisory", "supervisor", "oversight",
    "prudential", "financial authority",
]

_AUTHORITY_TLDS = (".gov", ".gov.uk", ".gov.au", ".gc.ca", ".europa.eu", ".int")


def _authority_score(candidate: dict) -> float:
    """Score 0-1 for how authoritative the source appears."""
    domain = extract_domain(candidate.get("homepage_url", ""))
    text = " ".join([
        candidate.get("source_name", ""),
        candidate.get("description", ""),
    ]).lower()

    score = 0.0
    for tld in _AUTHORITY_TLDS:
        if domain.endswith(tld):
            score = max(score, 0.9)
            break
    if ".org" in domain:
        score = max(score, 0.5)

    matches = sum(1 for kw in _AUTHORITY_KEYWORDS if kw in text)
    score = min(1.0, score + matches * 0.1)
    return score


def _relevance_score(candidate: dict) -> float:
    """Score 0-1 for financial-services relevance based on taxonomy keywords."""
    text = " ".join([
        candidate.get("source_name", ""),
        candidate.get("description", ""),
        " ".join(candidate.get("fs_coverage_tags", [])),
    ]).lower()

    matches = sum(1 for kw in FS_TAXONOMY_KEYWORDS if kw.lower() in text)
    return min(1.0, matches / 5.0)


def _frequency_score(candidate: dict) -> float:
    """Score 0-1 based on the number of evidence samples."""
    samples = len(candidate.get("evidence_samples", []))
    return min(1.0, samples / 5.0)


def _usability_score(candidate: dict) -> float:
    """Score 0-1 based on feed availability and URL stability."""
    score = 0.0
    if candidate.get("feed_url"):
        score += 0.7
    url = candidate.get("homepage_url", "")
    if url.startswith("https://"):
        score += 0.3
    return min(1.0, score)


def score_candidate(candidate: dict, existing_domains: set[str], config: dict) -> float:
    """
    Compute a composite 0-1 confidence score for a discovered candidate.

    Returns 0.0 immediately if the candidate's domain is already in existing_domains.

    Args:
        candidate: Candidate dict with homepage_url, source_name, description, etc.
        existing_domains: Set of already-known domains to filter duplicates.
        config: Search config dict containing scoring_weights.

    Returns:
        Float score between 0.0 and 1.0.
    """
    domain = extract_domain(candidate.get("homepage_url", ""))
    if normalize_domain(domain) in existing_domains:
        return 0.0

    weights = config.get("scoring_weights", {
        "authority": 0.30,
        "relevance": 0.30,
        "frequency": 0.15,
        "usability": 0.15,
        "uniqueness": 0.10,
    })

    authority = _authority_score(candidate)
    relevance = _relevance_score(candidate)
    frequency = _frequency_score(candidate)
    usability = _usability_score(candidate)
    uniqueness = 1.0

    score = (
        authority * weights.get("authority", 0.30)
        + relevance * weights.get("relevance", 0.30)
        + frequency * weights.get("frequency", 0.15)
        + usability * weights.get("usability", 0.15)
        + uniqueness * weights.get("uniqueness", 0.10)
    )
    return round(min(1.0, score), 4)


def apply_policy_filters(candidate: dict, config: dict) -> tuple[bool, str]:
    """
    Apply policy filters to a candidate.

    Returns:
        Tuple of (keep: bool, reason: str). keep=False means discard.
    """
    domain = extract_domain(candidate.get("homepage_url", ""))
    policy = config.get("policy_filters", {})

    exclude_patterns = policy.get("exclude_domain_patterns", [])
    for pattern in exclude_patterns:
        if pattern in domain:
            return False, f"Domain matches excluded pattern: {pattern}"

    us_trackers = policy.get("us_legislation_trackers", [])
    if domain in us_trackers:
        return False, f"Domain is a US legislation tracker: {domain}"

    return True, ""


def recommend_action(score: float, config: dict) -> str:
    """
    Map a numeric score to a recommended action string.

    Returns 'add', 'watchlist', or 'reject'.
    """
    add_threshold = config.get("recommend_add_threshold", 0.65)
    watchlist_threshold = config.get("recommend_watchlist_threshold", 0.35)

    if score >= add_threshold:
        return "add"
    if score >= watchlist_threshold:
        return "watchlist"
    return "reject"
