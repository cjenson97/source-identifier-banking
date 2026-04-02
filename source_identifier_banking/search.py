import os
import time
from abc import ABC, abstractmethod
import requests
import structlog

logger = structlog.get_logger()


class SearchProvider(ABC):
    """Abstract base class for search providers."""

    @abstractmethod
    def search(self, query: str) -> list[dict]:
        """
        Execute a search query and return results.

        Each result is a dict with keys: title, url, description.
        """


class DuckDuckGoProvider(SearchProvider):
    """Search provider using the DuckDuckGo search library."""

    def __init__(self, max_results: int = 10, delay: float = 2.0) -> None:
        """Initialise with result limit and rate-limit delay."""
        self.max_results = max_results
        self.delay = delay

    def search(self, query: str) -> list[dict]:
        """Search DuckDuckGo and return results as list of dicts."""
        try:
            from duckduckgo_search import DDGS
            time.sleep(self.delay)
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=self.max_results):
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "description": r.get("body", ""),
                    })
            return results
        except Exception as exc:
            logger.warning("ddg_search_failed", query=query, error=str(exc))
            return []


class SerperProvider(SearchProvider):
    """Search provider using the Serper API."""

    SERPER_URL = "https://google.serper.dev/search"

    def __init__(self, api_key: str | None = None, max_results: int = 10, timeout: int = 15) -> None:
        """Initialise with optional API key, result limit, and timeout."""
        self.api_key = api_key or os.environ.get("SERPER_API_KEY", "")
        self.max_results = max_results
        self.timeout = timeout

    def search(self, query: str) -> list[dict]:
        """Search via Serper API and return results as list of dicts."""
        if not self.api_key:
            logger.warning("serper_no_api_key")
            return []
        try:
            response = requests.post(
                self.SERPER_URL,
                json={"q": query, "num": self.max_results},
                headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            results = []
            for item in data.get("organic", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "description": item.get("snippet", ""),
                })
            return results
        except Exception as exc:
            logger.warning("serper_search_failed", query=query, error=str(exc))
            return []


class MockSearchProvider(SearchProvider):
    """Mock search provider for testing."""

    def __init__(self, results: list[dict]) -> None:
        """Initialise with a pre-configured list of results."""
        self._results = results

    def search(self, query: str) -> list[dict]:
        """Return the pre-configured mock results."""
        return self._results


def get_provider(config: dict) -> SearchProvider:
    """
    Factory function to create a SearchProvider from a config dict.

    Config should have a 'provider' key of 'duckduckgo' or 'serper'.
    """
    provider_name = config.get("provider", "duckduckgo")
    max_results = config.get("max_results_per_query", 10)
    delay = config.get("rate_limit_delay_seconds", 2.0)
    timeout = config.get("request_timeout_seconds", 15)

    if provider_name == "serper":
        api_key = os.environ.get(config.get("api_key_env", "SERPER_API_KEY"), "")
        return SerperProvider(api_key=api_key, max_results=max_results, timeout=timeout)
    return DuckDuckGoProvider(max_results=max_results, delay=delay)
