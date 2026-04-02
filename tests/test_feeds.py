import responses as resp_lib
import requests
from source_identifier_banking.feeds import detect_feeds, COMMON_FEED_PATHS

HOMEPAGE = "https://example.com"


@resp_lib.activate(assert_all_requests_are_fired=False)
def test_detect_feeds_from_html_link_tags():
    html = """<html><head>
    <link rel="alternate" type="application/rss+xml" href="/feed.xml" title="RSS">
    </head><body></body></html>"""
    resp_lib.add(resp_lib.GET, HOMEPAGE, body=html, status=200, content_type="text/html")
    resp_lib.add(resp_lib.GET, HOMEPAGE + "/sitemap.xml", status=404)
    session = requests.Session()
    feeds = detect_feeds(HOMEPAGE, session)
    assert any("feed.xml" in f for f in feeds)


@resp_lib.activate(assert_all_requests_are_fired=False)
def test_detect_feeds_from_atom_link_tags():
    html = """<html><head>
    <link rel="alternate" type="application/atom+xml" href="/atom.xml" title="Atom">
    </head><body></body></html>"""
    resp_lib.add(resp_lib.GET, HOMEPAGE, body=html, status=200, content_type="text/html")
    resp_lib.add(resp_lib.GET, HOMEPAGE + "/sitemap.xml", status=404)
    session = requests.Session()
    feeds = detect_feeds(HOMEPAGE, session)
    assert any("atom.xml" in f for f in feeds)


@resp_lib.activate(assert_all_requests_are_fired=False)
def test_detect_feeds_common_paths():
    resp_lib.add(resp_lib.GET, HOMEPAGE, body="<html></html>", status=200)
    resp_lib.add(resp_lib.HEAD, HOMEPAGE + "/feed.xml", status=200)
    resp_lib.add(resp_lib.GET, HOMEPAGE + "/sitemap.xml", status=404)
    # All other HEAD requests will raise ConnectionError which feeds.py catches gracefully
    session = requests.Session()
    feeds = detect_feeds(HOMEPAGE, session)
    assert any("feed.xml" in f for f in feeds)


@resp_lib.activate(assert_all_requests_are_fired=False)
def test_detect_feeds_no_feeds_found():
    resp_lib.add(resp_lib.GET, HOMEPAGE, body="<html><body>nothing</body></html>", status=200)
    resp_lib.add(resp_lib.GET, HOMEPAGE + "/sitemap.xml", status=404)
    # All HEAD requests for common paths will raise ConnectionError - caught gracefully
    session = requests.Session()
    feeds = detect_feeds(HOMEPAGE, session)
    assert feeds == []
