"""
Web scraping and search tools
"""

from typing import Dict, Any, List
import structlog

from rann_agent.tools.registry import Tool, ToolResult

logger = structlog.get_logger()


class WebSearchTool(Tool):
    """Web search"""
    
    name = "web_search"
    description = "Search the web for information"
    parameters = {
        "query": {"type": "string", "required": True},
        "limit": {"type": "integer", "default": 5},
    }
    
    def __init__(self, config):
        self.config = config
    
    async def execute(self, query: str, limit: int = 5, **kwargs) -> Dict[str, Any]:
        """Search web"""
        try:
            import aiohttp
            
            # Use DuckDuckGo HTML API (no key needed)
            url = "https://html.duckduckgo.com/html/"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    data={"q": query},
                    headers={"User-Agent": "Rann-Agent/1.0"}
                ) as resp:
                    html = await resp.text()
            
            # Parse results (simplified)
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            
            results = []
            for result in soup.select('.result')[:limit]:
                title_elem = result.select_one('.result__title')
                snippet_elem = result.select_one('.result__snippet')
                
                if title_elem:
                    results.append({
                        "title": title_elem.get_text(strip=True),
                        "url": title_elem.get('href', ''),
                        "snippet": snippet_elem.get_text(strip=True) if snippet_elem else '',
                    })
            
            output = "\n\n".join(
                f"**{r['title']}**\n{r['url']}\n{r['snippet']}"
                for r in results
            )
            
            return ToolResult(
                tool=self.name,
                success=True,
                output=output,
                metadata={"count": len(results), "query": query}
            ).to_dict()
            
        except Exception as e:
            logger.error("web_search_error", error=str(e))
            return ToolResult(
                tool=self.name,
                success=False,
                error=str(e)
            ).to_dict()


class WebExtractTool(Tool):
    """Extract content from URLs"""
    
    name = "web_extract"
    description = "Extract text content from web pages"
    parameters = {
        "urls": {"type": "array", "required": True},
        "char_limit": {"type": "integer", "default": 15000},
    }
    
    def __init__(self, config):
        self.config = config
        self.timeout = config.tools.web.get("timeout", 30)
    
    async def execute(self, urls: List[str], char_limit: int = 15000, **kwargs) -> Dict[str, Any]:
        """Extract web content"""
        try:
            import aiohttp
            from bs4 import BeautifulSoup
            from markdownify import markdownify as md
            
            results = []
            
            async with aiohttp.ClientSession() as session:
                for url in urls[:5]:  # Max 5 URLs
                    try:
                        async with session.get(
                            url,
                            timeout=aiohttp.ClientTimeout(total=self.timeout),
                            headers={"User-Agent": "Rann-Agent/1.0"}
                        ) as resp:
                            html = await resp.text()
                        
                        # Parse and convert to markdown
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Remove script and style elements
                        for script in soup(["script", "style"]):
                            script.decompose()
                        
                        # Get text
                        text = md(str(soup))
                        
                        # Truncate if needed
                        if len(text) > char_limit:
                            text = text[:char_limit] + "\n\n[Content truncated...]"
                        
                        results.append({
                            "url": url,
                            "title": soup.title.string if soup.title else url,
                            "content": text,
                            "success": True,
                        })
                    
                    except Exception as e:
                        results.append({
                            "url": url,
                            "error": str(e),
                            "success": False,
                        })
            
            # Format output
            output = "\n\n---\n\n".join(
                f"# {r['title']}\nURL: {r['url']}\n\n{r.get('content', r.get('error'))}"
                for r in results
            )
            
            return ToolResult(
                tool=self.name,
                success=True,
                output=output,
                metadata={"count": len(results)}
            ).to_dict()
            
        except Exception as e:
            logger.error("web_extract_error", error=str(e))
            return ToolResult(
                tool=self.name,
                success=False,
                error=str(e)
            ).to_dict()
