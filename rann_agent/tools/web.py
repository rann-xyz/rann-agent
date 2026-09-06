"""
Web scraping and search tools with pluggable providers.
"""

import os
from abc import ABC, abstractmethod
from typing import Any

import structlog

from rann_agent.tools.registry import Tool, ToolResult

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Search Providers
# ---------------------------------------------------------------------------


class SearchProvider(ABC):
    """Abstract base for web search providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier."""
        ...

    @abstractmethod
    async def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """
        Perform a web search.

        Returns:
            List of dicts with keys: title, url, snippet
        """
        ...


class DuckDuckGoProvider(SearchProvider):
    """DuckDuckGo HTML API (no key required)."""

    name = "duckduckgo"

    async def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        import aiohttp
        from bs4 import BeautifulSoup

        url = "https://html.duckduckgo.com/html/"
        async with aiohttp.ClientSession() as session, session.post(
            url,
            data={"q": query},
            headers={"User-Agent": "Rann-Agent/1.0"},
        ) as resp:
            html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")
        results = []
        for result in soup.select(".result")[:limit]:
            title_elem = result.select_one(".result__title")
            snippet_elem = result.select_one(".result__snippet")
            if title_elem:
                results.append(
                    {
                        "title": title_elem.get_text(strip=True),
                        "url": title_elem.get("href", ""),
                        "snippet": (
                            snippet_elem.get_text(strip=True) if snippet_elem else ""
                        ),
                    }
                )
        return results


class BraveProvider(SearchProvider):
    """Brave Search API (requires BRAVE_API_KEY)."""

    name = "brave"

    async def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        import aiohttp

        api_key = os.environ.get("BRAVE_API_KEY")
        if not api_key:
            raise ValueError("BRAVE_API_KEY environment variable not set")

        url = "https://api.search.brave.com/res/v1/web/search"
        params = {"q": query, "count": min(limit, 20)}
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": api_key,
            "User-Agent": "Rann-Agent/1.0",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers) as resp:
                resp.raise_for_status()
                data = await resp.json()

        results = []
        web_results = data.get("web", {}).get("results", [])
        for item in web_results[:limit]:
            results.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("description", ""),
                }
            )
        return results


class SearXNGProvider(SearchProvider):
    """Self-hosted SearXNG instance (requires SEARXNG_URL)."""

    name = "searxng"

    async def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        import aiohttp

        base_url = os.environ.get("SEARXNG_URL", "").rstrip("/")
        if not base_url:
            raise ValueError("SEARXNG_URL environment variable not set")

        url = f"{base_url}/search"
        params = {"q": query, "format": "json", "engines": "general"}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                resp.raise_for_status()
                data = await resp.json()

        results = []
        for item in data.get("results", [])[:limit]:
            results.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", ""),
                }
            )
        return results


class TavilyProvider(SearchProvider):
    """Tavily AI search (requires TAVILY_API_KEY)."""

    name = "tavily"

    async def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        import aiohttp

        api_key = os.environ.get("TAVILY_API_KEY")
        if not api_key:
            raise ValueError("TAVILY_API_KEY environment variable not set")

        url = "https://api.tavily.com/search"
        payload = {"api_key": api_key, "query": query, "max_results": limit}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                resp.raise_for_status()
                data = await resp.json()

        results = []
        for item in data.get("results", [])[:limit]:
            results.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", ""),
                }
            )
        return results


class GoogleCSEProvider(SearchProvider):
    """Google Custom Search Engine (requires GOOGLE_CSE_API_KEY and GOOGLE_CSE_SEARCHENGINE_ID)."""

    name = "google_cse"

    async def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        import aiohttp

        api_key = os.environ.get("GOOGLE_CSE_API_KEY")
        search_engine_id = os.environ.get("GOOGLE_CSE_SEARCHENGINE_ID")
        if not api_key or not search_engine_id:
            raise ValueError(
                "GOOGLE_CSE_API_KEY and GOOGLE_CSE_SEARCHENGINE_ID environment variables must be set"
            )

        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": api_key,
            "cx": search_engine_id,
            "q": query,
            "num": min(limit, 10),
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                resp.raise_for_status()
                data = await resp.json()

        results = []
        for item in data.get("items", [])[:limit]:
            results.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                }
            )
        return results


_SEARCH_PROVIDERS: dict[str, type[SearchProvider]] = {
    "duckduckgo": DuckDuckGoProvider,
    "brave": BraveProvider,
    "searxng": SearXNGProvider,
    "tavily": TavilyProvider,
    "google_cse": GoogleCSEProvider,
}


def get_search_provider(name: str) -> SearchProvider:
    """Factory: return a search provider instance by name."""
    cls = _SEARCH_PROVIDERS.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown search provider '{name}'. Available: {list(_SEARCH_PROVIDERS.keys())}"
        )
    return cls()


# ---------------------------------------------------------------------------
# Extract Providers
# ---------------------------------------------------------------------------


class ExtractProvider(ABC):
    """Abstract base for web content extraction providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier."""
        ...

    @abstractmethod
    async def extract(
        self, urls: list[str], char_limit: int = 15000
    ) -> list[dict[str, Any]]:
        """
        Extract content from URLs.

        Returns:
            List of dicts with keys: url, title, content, success
            (or url, error, success on failure).
        """
        ...


class AioHTTPProvider(ExtractProvider):
    """BeautifulSoup + markdownify (default, no extra dependencies)."""

    name = "aiohttp"

    async def extract(
        self, urls: list[str], char_limit: int = 15000
    ) -> list[dict[str, Any]]:
        import aiohttp
        from bs4 import BeautifulSoup
        from markdownify import markdownify as md

        results = []
        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession() as session:
            for url in urls[:5]:
                try:
                    async with session.get(
                        url,
                        timeout=timeout,
                        headers={"User-Agent": "Rann-Agent/1.0"},
                    ) as resp:
                        html = await resp.text()

                    soup = BeautifulSoup(html, "html.parser")
                    for elem in soup(["script", "style"]):
                        elem.decompose()

                    text = md(str(soup))
                    if len(text) > char_limit:
                        text = text[:char_limit] + "\n\n[Content truncated...]"

                    results.append(
                        {
                            "url": url,
                            "title": soup.title.string if soup.title else url,
                            "content": text,
                            "success": True,
                        }
                    )
                except Exception as e:
                    results.append(
                        {
                            "url": url,
                            "error": str(e),
                            "success": False,
                        }
                    )
        return results


class TrafilaturaProvider(ExtractProvider):
    """Trafilatura-based extraction (better article extraction, falls back to aiohttp)."""

    name = "trafilatura"

    def __init__(self):
        self._aiohttp = AioHTTPProvider()

    async def extract(
        self, urls: list[str], char_limit: int = 15000
    ) -> list[dict[str, Any]]:
        try:
            import trafilatura
        except ImportError:
            logger.warning("trafilatura not installed, falling back to aiohttp")
            return await self._aiohttp.extract(urls, char_limit)

        results = []
        for url in urls[:5]:
            try:
                downloaded = trafilatura.fetch_url(url)
                if downloaded is None:
                    raise ValueError("Failed to download page")

                text = trafilatura.extract(downloaded, output_format="markdown")
                if text is None:
                    raise ValueError("Failed to extract content")

                if len(text) > char_limit:
                    text = text[:char_limit] + "\n\n[Content truncated...]"

                # Trafilatura doesn't easily expose title; use the url as fallback
                results.append(
                    {
                        "url": url,
                        "title": url,
                        "content": text,
                        "success": True,
                    }
                )
            except Exception as e:
                logger.warning("trafilatura_extract_error", url=url, error=str(e))
                # Fall back to aiohttp for this URL
                fallback = await self._aiohttp.extract([url], char_limit)
                results.append(fallback[0])
        return results


class PlaywrightProvider(ExtractProvider):
    """Playwright + Chromium for JS-rendered pages (falls back to aiohttp)."""

    name = "playwright"

    def __init__(self):
        self._aiohttp = AioHTTPProvider()

    async def extract(
        self, urls: list[str], char_limit: int = 15000
    ) -> list[dict[str, Any]]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("playwright not installed, falling back to aiohttp")
            return await self._aiohttp.extract(urls, char_limit)

        results = []
        for url in urls[:5]:
            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    page = await browser.new_page()
                    await page.goto(url, wait_until="networkidle", timeout=30000)
                    content = await page.content()
                    title = await page.title()
                    await browser.close()

                from bs4 import BeautifulSoup
                from markdownify import markdownify as md

                soup = BeautifulSoup(content, "html.parser")
                for elem in soup(["script", "style"]):
                    elem.decompose()

                text = md(str(soup))
                if len(text) > char_limit:
                    text = text[:char_limit] + "\n\n[Content truncated...]"

                results.append(
                    {
                        "url": url,
                        "title": title or url,
                        "content": text,
                        "success": True,
                    }
                )
            except Exception as e:
                logger.warning("playwright_extract_error", url=url, error=str(e))
                fallback = await self._aiohttp.extract([url], char_limit)
                results.append(fallback[0])
        return results


_EXTRACT_PROVIDERS: dict[str, type[ExtractProvider]] = {
    "aiohttp": AioHTTPProvider,
    "trafilatura": TrafilaturaProvider,
    "playwright": PlaywrightProvider,
}


def get_extract_provider(name: str) -> ExtractProvider:
    """Factory: return an extract provider instance by name."""
    cls = _EXTRACT_PROVIDERS.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown extract provider '{name}'. Available: {list(_EXTRACT_PROVIDERS.keys())}"
        )
    return cls()


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


class WebSearchTool(Tool):
    """Web search tool with pluggable provider support."""

    name = "web_search"
    description = "Search the web for information"
    parameters = {
        "query": {"type": "string", "required": True},
        "limit": {"type": "integer", "default": 5},
        "provider": {"type": "string", "default": "duckduckgo"},
    }

    def __init__(self, config):
        self.config = config
        default_provider = (
            config.tools.web_search.get("default_provider", "duckduckgo")
            if hasattr(config, "tools") and hasattr(config.tools, "web_search")
            else "duckduckgo"
        )
        self._default_provider = default_provider

    async def execute(
        self, query: str, limit: int = 5, provider: str | None = None, **kwargs
    ) -> dict[str, Any]:
        """Execute web search, delegating to the selected provider."""
        provider_name = provider or self._default_provider
        try:
            searcher = get_search_provider(provider_name)
            results = await searcher.search(query, limit)

            output = "\n\n".join(
                f"**{r['title']}**\n{r['url']}\n{r['snippet']}" for r in results
            )
            return ToolResult(
                tool=self.name,
                success=True,
                output=output,
                metadata={
                    "count": len(results),
                    "query": query,
                    "provider": provider_name,
                },
            ).to_dict()

        except Exception as e:
            logger.error("web_search_error", provider=provider_name, error=str(e))
            return ToolResult(
                tool=self.name,
                success=False,
                error=str(e),
            ).to_dict()


class WebExtractTool(Tool):
    """Web content extraction tool with pluggable provider support."""

    name = "web_extract"
    description = "Extract text content from web pages"
    parameters = {
        "urls": {"type": "array", "required": True},
        "char_limit": {"type": "integer", "default": 15000},
        "provider": {"type": "string", "default": "aiohttp"},
    }

    def __init__(self, config):
        self.config = config
        default_provider = (
            config.tools.web_extract.get("default_provider", "aiohttp")
            if hasattr(config, "tools") and hasattr(config.tools, "web_extract")
            else "aiohttp"
        )
        self._default_provider = default_provider

    async def execute(
        self,
        urls: list[str],
        char_limit: int = 15000,
        provider: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Execute content extraction, delegating to the selected provider."""
        provider_name = provider or self._default_provider
        try:
            extractor = get_extract_provider(provider_name)
            results = await extractor.extract(urls, char_limit)

            output = "\n\n---\n\n".join(
                f"# {r.get('title', r['url'])}\nURL: {r['url']}\n\n{r.get('content', r.get('error', ''))}"
                for r in results
            )
            return ToolResult(
                tool=self.name,
                success=True,
                output=output,
                metadata={"count": len(results), "provider": provider_name},
            ).to_dict()

        except Exception as e:
            logger.error("web_extract_error", provider=provider_name, error=str(e))
            return ToolResult(
                tool=self.name,
                success=False,
                error=str(e),
            ).to_dict()
