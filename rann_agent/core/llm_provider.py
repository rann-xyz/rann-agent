"""
LLM Provider abstraction layer - Clean Provider Architecture
"""
import asyncio
import json
import os
import threading
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

import structlog

logger = structlog.get_logger()

# Module-level LLM client cache
_LLM_CLIENT_CACHE: dict[tuple, object] = {}
_LLM_CLIENT_CACHE_LOCK = threading.Lock()


def clear_client_cache() -> None:
    with _LLM_CLIENT_CACHE_LOCK:
        _LLM_CLIENT_CACHE.clear()


class BaseLLMProvider(ABC):
    @abstractmethod
    async def complete(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        pass

    @abstractmethod
    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        pass


class AnthropicProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str, **kwargs):
        cache_key = ("anthropic", api_key, model)
        with _LLM_CLIENT_CACHE_LOCK:
            if cache_key in _LLM_CLIENT_CACHE:
                self.client = _LLM_CLIENT_CACHE[cache_key]
            else:
                from anthropic import AsyncAnthropic
                self.client = AsyncAnthropic(api_key=api_key)
                _LLM_CLIENT_CACHE[cache_key] = self.client
        self.model = model
        self.temperature = kwargs.get("temperature", 0.7)
        self.max_tokens = kwargs.get("max_tokens", 8192)

    async def complete(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            messages=messages,
        )
        return {
            "content": response.content[0].text,
            "usage": {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens},
            "model": response.model,
        }

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        async with self.client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str, **kwargs):
        cache_key = ("openai", api_key, model)
        with _LLM_CLIENT_CACHE_LOCK:
            if cache_key in _LLM_CLIENT_CACHE:
                self.client = _LLM_CLIENT_CACHE[cache_key]
            else:
                from openai import AsyncOpenAI
                self.client = AsyncOpenAI(api_key=api_key)
                _LLM_CLIENT_CACHE[cache_key] = self.client
        self.model = model
        self.temperature = kwargs.get("temperature", 0.7)
        self.max_tokens = kwargs.get("max_tokens", 8192)

    async def complete(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return {
            "content": response.choices[0].message.content,
            "usage": {"prompt_tokens": response.usage.prompt_tokens, "completion_tokens": response.usage.completion_tokens},
            "model": response.model,
        }

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
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


class OllamaProvider(BaseLLMProvider):
    def __init__(self, model: str, host: str = "http://localhost:11434", **kwargs):
        self.model = model
        self.host = host
        self.temperature = kwargs.get("temperature", 0.7)

    async def complete(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.host}/api/chat",
                json={"model": self.model, "messages": messages, "stream": False, "options": {"temperature": self.temperature}},
            ) as resp:
                result = await resp.json()
                return {"content": result["message"]["content"], "usage": {}, "model": self.model}

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.host}/api/chat",
                json={"model": self.model, "messages": messages, "stream": True},
            ) as resp:
                async for line in resp.content:
                    if line:
                        import json
                        try:
                            data = json.loads(line)
                            if "message" in data:
                                yield data["message"].get("content", "")
                        except json.JSONDecodeError:
                            continue


class CustomProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str, base_url: str, **kwargs):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.temperature = kwargs.get("temperature", 0.7)
        self.max_tokens = kwargs.get("max_tokens", 4096)

    async def _create_url(self) -> str:
        """Create proper chat completions URL, handling /v1 prefix in base_url."""
        base = self.base_url
        # If base_url already ends with /v1, don't add another
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"

    async def complete(self, messages: list[dict[str, str]], tools: list[dict] | None = None) -> dict[str, Any]:
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

        chat_url = await self._create_url()
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                chat_url,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"API error {resp.status}: {text}")
                result = await resp.json()
                message = result["choices"][0]["message"]
                response = {"content": message.get("content", ""), "usage": result.get("usage", {}), "model": result.get("model", self.model)}
                
                if message.get("tool_calls"):
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
                    tc = message["tool_call"]
                    response["tool_calls"] = [
                        {
                            "name": tc.get("function", {}).get("name") or tc.get("name"),
                            "parameters": json.loads(tc.get("function", {}).get("arguments", "{}"))
                            if isinstance(tc.get("function", {}).get("arguments"), str)
                            else tc.get("function", {}).get("arguments", {}),
                        }
                    ]
                return response

    async def stream(self, messages: list[dict[str, str]], tools: list[dict] | None = None) -> AsyncIterator[str]:
        import aiohttp
        payload = {"model": self.model, "messages": messages, "stream": True, "temperature": self.temperature, "max_tokens": self.max_tokens}
        if tools:
            payload["tools"] = tools
        
        chat_url = await self._create_url()
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                chat_url,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
            ) as resp:
                async for line in resp.content:
                    if line:
                        import json
                        try:
                            data = json.loads(line)
                            if data.get("choices"):
                                content = data["choices"][0]["delta"].get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue


class LLMProvider:
    VALID_PROVIDERS = ["anthropic", "openai", "ollama", "custom"]

    def __init__(self, config):
        self.config = config
        self.provider = config.agent.llm.provider.lower()
        self.model = config.agent.llm.model

        if self.provider not in self.VALID_PROVIDERS:
            raise ValueError(f"Invalid provider: {self.provider}. Must be one of: {self.VALID_PROVIDERS}")

        self.primary = self._create_provider(self.provider, self.model, config.get_api_key(self.provider))
        self.fallbacks = []
        for fb in config.agent.llm.fallback_providers:
            provider = fb["provider"].lower()
            if provider not in self.VALID_PROVIDERS:
                logger.warning("invalid_fallback_provider", provider=provider)
                continue
            provider_instance = self._create_provider(provider, fb["model"], config.get_api_key(provider))
            self.fallbacks.append(provider_instance)

        logger.info("llm_provider_init", primary=self.provider, model=self.model, fallbacks=len(self.fallbacks))

    def _create_provider(self, provider: str, model: str, api_key: str | None) -> BaseLLMProvider:
        kwargs = {"temperature": self.config.agent.llm.temperature, "max_tokens": self.config.agent.llm.max_tokens}

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

        elif provider == "custom":
            base_url = os.getenv("LLM_API_BASE", "")
            return CustomProvider(api_key or "", model, base_url, **kwargs)

        else:
            raise ValueError(f"Unknown provider: {provider}")

    async def complete(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        return await self.primary.complete(messages)

    async def complete_with_retry(self, messages: list[dict[str, str]], tools: list[dict] | None = None) -> dict[str, Any]:
        max_attempts = self.config.agent.llm.retry["max_attempts"]
        backoff = self.config.agent.llm.retry["backoff_multiplier"]

        for attempt in range(max_attempts):
            try:
                result = await self.primary.complete(messages, tools=tools)
                if tools and "tool_calls" in result:
                    return result
                return result
            except Exception as e:
                logger.warning("llm_primary_failed", attempt=attempt + 1, error=str(e))
                if attempt < max_attempts - 1:
                    await asyncio.sleep(backoff**attempt)
                else:
                    logger.error("llm_primary_exhausted")

        for i, fallback in enumerate(self.fallbacks):
            try:
                logger.info("trying_fallback", fallback_index=i)
                return await fallback.complete(messages, tools=tools)
            except Exception as e:
                logger.warning("fallback_failed", fallback_index=i, error=str(e))

        raise Exception("All LLM providers failed")

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        async for token in self.primary.stream(messages):
            yield token