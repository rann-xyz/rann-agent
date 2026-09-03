"""
LLM Provider abstraction layer
"""

from typing import List, Dict, Any, Optional, AsyncIterator
import asyncio
import json
from abc import ABC, abstractmethod
import structlog

logger = structlog.get_logger()


class BaseLLMProvider(ABC):
    """Base class for LLM providers"""
    
    @abstractmethod
    async def complete(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Generate completion"""
        pass
    
    @abstractmethod
    async def stream(self, messages: List[Dict[str, str]]) -> AsyncIterator[str]:
        """Stream completion tokens"""
        pass


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude provider"""
    
    def __init__(self, api_key: str, model: str, **kwargs):
        from anthropic import AsyncAnthropic
        
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model
        self.temperature = kwargs.get("temperature", 0.7)
        self.max_tokens = kwargs.get("max_tokens", 8192)
    
    async def complete(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Generate completion with Claude"""
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=messages,
            )
            
            return {
                "content": response.content[0].text,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
                "model": response.model,
            }
        except Exception as e:
            logger.error("anthropic_error", error=str(e))
            raise
    
    async def stream(self, messages: List[Dict[str, str]]) -> AsyncIterator[str]:
        """Stream tokens from Claude"""
        async with self.client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text


class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT provider"""
    
    def __init__(self, api_key: str, model: str, **kwargs):
        from openai import AsyncOpenAI
        
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.temperature = kwargs.get("temperature", 0.7)
        self.max_tokens = kwargs.get("max_tokens", 8192)
    
    async def complete(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Generate completion with GPT"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            
            return {
                "content": response.choices[0].message.content,
                "usage": {
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                },
                "model": response.model,
            }
        except Exception as e:
            logger.error("openai_error", error=str(e))
            raise
    
    async def stream(self, messages: List[Dict[str, str]]) -> AsyncIterator[str]:
        """Stream tokens from GPT"""
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True,
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class CustomProvider(BaseLLMProvider):
    """Custom API-compatible provider (e.g., seekai.cc)"""

    def __init__(self, api_key: str, model: str, base_url: str = "http://localhost:8000", **kwargs):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.temperature = kwargs.get("temperature", 0.7)
        self.max_tokens = kwargs.get("max_tokens", 4096)

    async def complete(self, messages: List[Dict[str, str]], tools: List[Dict] = None) -> Dict[str, Any]:
        """Generate completion with custom API (OpenAI-compatible)"""
        import aiohttp

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            payload["tools"] = tools
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Custom API error {resp.status}: {text}")
                result = await resp.json()
                
                message = result["choices"][0]["message"]
                response = {
                    "content": message.get("content", ""),
                    "usage": result.get("usage", {}),
                    "model": result.get("model", self.model),
                }
                
                # Parse tool calls if present (function calling format)
                if "tool_calls" in message and message["tool_calls"]:
                    response["tool_calls"] = [
                        {
                            "name": tc.get("function", {}).get("name") or tc.get("name"),
                            "parameters": json.loads(tc.get("function", {}).get("arguments", "{}"))
                                if isinstance(tc.get("function", {}).get("arguments"), str)
                                else tc.get("function", {}).get("arguments", {}),
                        }
                        for tc in message["tool_calls"]
                    ]
                elif "tool_call" in message:
                    # Some APIs use singular
                    tc = message["tool_call"]
                    response["tool_calls"] = [{
                        "name": tc.get("function", {}).get("name") or tc.get("name"),
                        "parameters": json.loads(tc.get("function", {}).get("arguments", "{}"))
                            if isinstance(tc.get("function", {}).get("arguments"), str)
                            else tc.get("function", {}).get("arguments", {}),
                    }]
                
                return response

    async def stream(self, messages: List[Dict[str, str]], tools: List[Dict] = None) -> AsyncIterator[str]:
        """Stream tokens from custom API (OpenAI-compatible)"""
        import aiohttp

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            payload["tools"] = tools
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload
            ) as resp:
                async for line in resp.content:
                    if line:
                        import json
                        try:
                            data = json.loads(line)
                            if "choices" in data and data["choices"]:
                                content = data["choices"][0]["delta"].get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue


class OllamaProvider(BaseLLMProvider):
    """Ollama local models provider"""
    
    def __init__(self, model: str, host: str = "http://localhost:11434", **kwargs):
        self.model = model
        self.host = host
        self.temperature = kwargs.get("temperature", 0.7)
    
    async def complete(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Generate completion with Ollama"""
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.host}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": self.temperature},
                }
            ) as resp:
                result = await resp.json()
                return {
                    "content": result["message"]["content"],
                    "usage": {},
                    "model": self.model,
                }
    
    async def stream(self, messages: List[Dict[str, str]]) -> AsyncIterator[str]:
        """Stream tokens from Ollama"""
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.host}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                }
            ) as resp:
                async for line in resp.content:
                    import json
                    data = json.loads(line)
                    if "message" in data:
                        yield data["message"].get("content", "")


class LLMProvider:
    """
    Main LLM provider with fallback support and retry logic
    """
    
    def __init__(self, config):
        self.config = config
        self.provider = config.agent.llm.provider
        self.model = config.agent.llm.model
        
        # Initialize primary provider
        self.primary = self._create_provider(
            self.provider,
            self.model,
            config.get_api_key(self.provider)
        )
        
        # Initialize fallback providers
        self.fallbacks = []
        for fb in config.agent.llm.fallback_providers:
            provider = self._create_provider(
                fb["provider"],
                fb["model"],
                config.get_api_key(fb["provider"])
            )
            self.fallbacks.append(provider)
        
        logger.info(
            "llm_provider_init",
            primary=self.provider,
            model=self.model,
            fallbacks=len(self.fallbacks)
        )
    
    def _create_provider(self, provider: str, model: str, api_key: Optional[str]) -> BaseLLMProvider:
        """Create provider instance"""
        kwargs = {
            "temperature": self.config.agent.llm.temperature,
            "max_tokens": self.config.agent.llm.max_tokens,
        }
        
        if provider == "anthropic":
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not set")
            return AnthropicProvider(api_key, model, **kwargs)
        
        elif provider == "openai":
            if not api_key:
                raise ValueError("OPENAI_API_KEY not set")
            return OpenAIProvider(api_key, model, **kwargs)
        
        elif provider == "ollama":
            host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
            return OllamaProvider(model, host, **kwargs)

        elif provider == "xkiro":
            base_url = "https://api.xkiro.com"
            return CustomProvider(api_key or os.getenv("HERMES_CUSTOM_API_XKIRO_COM_API_KEY", ""), model, base_url, **kwargs)

        elif provider == "custom":
            base_url = os.getenv("CUSTOM_API_BASE", "https://seekai.cc")
            return CustomProvider(api_key or "none", model, base_url, **kwargs)

        else:
            raise ValueError(f"Unknown provider: {provider}")
    
    async def complete(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Complete with primary provider (no retry)"""
        return await self.primary.complete(messages)
    
    async def complete_with_retry(self, messages: List[Dict[str, str]], tools: List[Dict] = None) -> Dict[str, Any]:
        """
        Complete with retry and fallback logic
        """
        max_attempts = self.config.agent.llm.retry["max_attempts"]
        backoff = self.config.agent.llm.retry["backoff_multiplier"]
        
        # Try primary provider with retries
        for attempt in range(max_attempts):
            try:
                return await self.primary.complete(messages, tools=tools)
            except Exception as e:
                logger.warning(
                    "llm_primary_failed",
                    attempt=attempt + 1,
                    error=str(e)
                )
                if attempt < max_attempts - 1:
                    await asyncio.sleep(backoff ** attempt)
                else:
                    logger.error("llm_primary_exhausted")
        
        # Try fallback providers
        for i, fallback in enumerate(self.fallbacks):
            try:
                logger.info("trying_fallback", fallback_index=i)
                return await fallback.complete(messages, tools=tools)
            except Exception as e:
                logger.warning("fallback_failed", fallback_index=i, error=str(e))
        
        raise Exception("All LLM providers failed")
    
    async def stream(self, messages: List[Dict[str, str]]) -> AsyncIterator[str]:
        """Stream from primary provider"""
        async for token in self.primary.stream(messages):
            yield token


import os
