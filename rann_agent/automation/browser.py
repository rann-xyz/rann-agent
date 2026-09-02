"""
Browser automation using Playwright.
"""

from typing import Dict, Any, Optional, List
import asyncio


class BrowserAutomation:
    """
    Automate web browsers for scraping and interaction.
    """
    
    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
    
    async def initialize(self, headless: bool = True):
        """Initialize browser."""
        try:
            from playwright.async_api import async_playwright
            
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=headless)
            self.context = await self.browser.new_context()
            self.page = await self.context.new_page()
            
            return True
        except ImportError:
            print("Playwright not installed: pip install playwright")
            return False
        except Exception as e:
            print(f"Failed to initialize browser: {e}")
            return False
    
    async def navigate(self, url: str) -> Dict:
        """Navigate to URL."""
        if not self.page:
            await self.initialize()
        
        try:
            await self.page.goto(url, wait_until="networkidle")
            return {
                'success': True,
                'url': self.page.url,
                'title': await self.page.title()
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def screenshot(self, path: str = "screenshot.png") -> str:
        """Take screenshot."""
        if not self.page:
            return ""
        
        await self.page.screenshot(path=path, full_page=True)
        return path
    
    async def extract_text(self, selector: str = "body") -> str:
        """Extract text from page."""
        if not self.page:
            return ""
        
        try:
            element = await self.page.query_selector(selector)
            if element:
                return await element.inner_text()
            return ""
        except Exception:
            return ""
    
    async def click(self, selector: str) -> bool:
        """Click element."""
        if not self.page:
            return False
        
        try:
            await self.page.click(selector)
            return True
        except Exception:
            return False
    
    async def fill(self, selector: str, text: str) -> bool:
        """Fill input field."""
        if not self.page:
            return False
        
        try:
            await self.page.fill(selector, text)
            return True
        except Exception:
            return False
    
    async def close(self):
        """Close browser."""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
