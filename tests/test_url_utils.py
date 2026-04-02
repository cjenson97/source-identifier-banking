import pytest
from source_identifier_banking.url_utils import (
    canonicalize_url,
    extract_domain,
    is_same_domain,
    normalize_domain,
)


def test_canonicalize_http_to_https():
    assert canonicalize_url("http://example.com").startswith("https://")


def test_canonicalize_strips_www():
    result = canonicalize_url("https://www.example.com")
    assert "www." not in result


def test_canonicalize_trailing_slash():
    result = canonicalize_url("https://example.com/path/")
    assert not result.endswith("/")


def test_extract_domain():
    assert extract_domain("https://www.example.com/path") == "example.com"


def test_normalize_domain():
    assert normalize_domain("WWW.Example.COM") == "example.com"


def test_is_same_domain_true():
    assert is_same_domain("https://www.example.com/a", "https://example.com/b") is True


def test_is_same_domain_false():
    assert is_same_domain("https://example.com", "https://other.com") is False
