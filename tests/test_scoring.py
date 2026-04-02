import pytest
from source_identifier_banking.scoring import (
    score_candidate,
    apply_policy_filters,
    recommend_action,
)

DEFAULT_CONFIG = {
    "scoring_weights": {
        "authority": 0.30,
        "relevance": 0.30,
        "frequency": 0.15,
        "usability": 0.15,
        "uniqueness": 0.10,
    },
    "recommend_add_threshold": 0.65,
    "recommend_watchlist_threshold": 0.35,
    "policy_filters": {
        "exclude_domain_patterns": ["insurance", "pension", "wikipedia", "linkedin", "twitter"],
        "us_legislation_trackers": ["congress.gov", "govtrack.us"],
    },
}


def _make_candidate(url: str, name: str = "Test", desc: str = "") -> dict:
    return {
        "homepage_url": url,
        "source_name": name,
        "description": desc,
        "evidence_samples": [{"url": url, "title": name}],
        "feed_url": None,
        "fs_coverage_tags": [],
    }


def test_score_gov_domain_higher():
    gov = _make_candidate("https://regulator.gov", "Financial Regulator", "banking regulation")
    com = _make_candidate("https://somesite.com", "Some Site", "general content")
    gov_score = score_candidate(gov, set(), DEFAULT_CONFIG)
    com_score = score_candidate(com, set(), DEFAULT_CONFIG)
    assert gov_score > com_score


def test_score_existing_domain_returns_zero():
    candidate = _make_candidate("https://fca.org.uk", "FCA")
    score = score_candidate(candidate, {"fca.org.uk"}, DEFAULT_CONFIG)
    assert score == 0.0


def test_policy_filter_excludes_insurance():
    candidate = _make_candidate("https://insurance-regulator.com")
    keep, reason = apply_policy_filters(candidate, DEFAULT_CONFIG)
    assert keep is False
    assert "insurance" in reason.lower()


def test_policy_filter_allows_valid_domain():
    candidate = _make_candidate("https://fca.org.uk")
    keep, reason = apply_policy_filters(candidate, DEFAULT_CONFIG)
    assert keep is True
    assert reason == ""


def test_recommend_action_add():
    assert recommend_action(0.8, DEFAULT_CONFIG) == "add"


def test_recommend_action_watchlist():
    assert recommend_action(0.5, DEFAULT_CONFIG) == "watchlist"


def test_recommend_action_reject():
    assert recommend_action(0.2, DEFAULT_CONFIG) == "reject"
