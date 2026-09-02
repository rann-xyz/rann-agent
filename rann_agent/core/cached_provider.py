"""
Integration with LLM provider to use cache
"""

from rann_agent.core.llm_provider import LLMProvider
from rann_agent.utils.cache import CacheManager


class CachedLLMProvider(LLMProvider):
    """LLM Provider with caching support"""
    
    def __init__(self, config):
        super().__init__(config)
        self.cache = CacheManager(config)
    
    async def complete_with_retry(self, messages):
        """Complete with cache check first"""
        # Try cache first
        cached = await self.cache.get_llm_response(messages)
        if cached:
            return cached
        
        # Cache miss - call actual LLM
        result = await super().complete_with_retry(messages)
        
        # Cache the result
        await self.cache.set_llm_response(messages, result)
        
        return result
