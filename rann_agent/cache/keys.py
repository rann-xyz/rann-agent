"""
Cache key generation utilities.

Provides stable, collision-resistant hash keys for cache entries.
Used by CacheManager to generate keys for LLM responses, tool calls, and embeddings.
"""

import hashlib
import json
from typing import Any


def hash_data(data: Any) -> str:
    """
    Create a stable SHA-256 hash of arbitrary serializable data.

    Uses JSON with sorted keys for stable serialization across runs.
    Truncates to 16 hex chars (64 bits) — sufficient for cache key collision
    resistance in single-agent workloads.

    Args:
        data: Any JSON-serializable Python object

    Returns:
        16-character hex string
    """
    try:
        serialized = json.dumps(data, sort_keys=True, ensure_ascii=True)
    except (TypeError, ValueError):
        # Fallback for non-JSON-serializable objects
        serialized = repr(data)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


def cache_key(
    prefix: str,
    *,
    messages: list | None = None,
    prompt: str | None = None,
    params: dict | None = None,
    tool_name: str | None = None,
    args: dict | None = None,
    model: str | None = None,
    embedding_text: str | None = None,
) -> str:
    """
    Generate a stable cache key for LLM responses, tool calls, or embeddings.

    Args:
        prefix: Namespace prefix (e.g. "llm", "tool", "embedding")
        messages: Chat messages list (for LLM cache)
        prompt: Single prompt string (alternative to messages)
        params: LLM parameters (model, temperature, max_tokens, etc.)
        tool_name: Name of the tool (for tool cache)
        args: Tool arguments (for tool cache)
        model: Model name (included in key for model-specific caching)
        embedding_text: Text to embed (for embedding cache)

    Returns:
        Cache key string: "{prefix}:{hash}"

    Example:
        >>> key = cache_key("llm", messages=[{"role":"user","content":"hi"}], model="claude-sonnet-4")
        >>> print(key)
        llm:a3f5c2d1e8b90742
    """
    # Build a canonical dict for hashing
    canonical = {}

    if messages is not None:
        canonical["messages"] = messages
    if prompt is not None:
        canonical["prompt"] = prompt
    if params is not None:
        # Sort params keys for stability
        canonical["params"] = dict(sorted(params.items()))
    if tool_name is not None:
        canonical["tool"] = tool_name
    if args is not None:
        canonical["args"] = dict(sorted(args.items()))
    if model is not None:
        canonical["model"] = model
    if embedding_text is not None:
        canonical["text"] = embedding_text

    hash_val = hash_data(canonical)
    return f"{prefix}:{hash_val}"


def llm_cache_key(messages: list, model: str, **params) -> str:
    """
    Convenience wrapper for LLM response cache keys.

    Includes model and all params in the key so different models/params
    get different cache entries.
    """
    return cache_key(
        "llm",
        messages=messages,
        model=model,
        params=params if params else None,
    )


def tool_cache_key(tool_name: str, args: dict) -> str:
    """
    Convenience wrapper for idempotent tool call cache keys.

    Only includes tool_name and args — not model since tools don't use models.
    """
    return cache_key("tool", tool_name=tool_name, args=args)


def embedding_cache_key(text: str, model: str) -> str:
    """
    Convenience wrapper for embedding vector cache keys.

    Includes the embedding model so different models get different vectors.
    """
    return cache_key("embedding", embedding_text=text, model=model)
