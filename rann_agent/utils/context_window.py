"""
Context Window Manager for RANN Agent.

Manages conversation history to stay within LLM context limits.
Strategies: truncate, summarize, or drop old messages.
"""

from typing import Any, Literal

import structlog

logger = structlog.get_logger()

# Model context windows (tokens)
CONTEXT_WINDOWS = {
    "claude-fable-5": 200000,
    "claude-sonnet-4-20250514": 200000,
    "claude-opus-4-20250514": 200000,
    "claude-3-5-sonnet-20241022": 200000,
    "claude-3-5-haiku-20241022": 200000,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4-turbo": 128000,
    "gpt-3.5-turbo": 16385,
    "deepseek-chat": 64000,
    "llama-3.1-70b-versatile": 128000,
    "minimax/minimax-m2.7-highspeed:free": 16000,
    "gemini-1.5-flash": 1000000,
    "gemini-1.5-pro": 1000000,
}

# Reserved space for system prompt and response (estimate)
RESERVED_TOKENS = 2000
DEFAULT_WINDOW = 16000


class ContextWindowManager:
    """
    Manage conversation history to fit within model context limits.

    Strategies:
    - `truncate`: Remove oldest messages from the middle
    - `summarize`: (placeholder) Replace old messages with summary
    - `drop_oldest`: Simply drop oldest messages
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        strategy: Literal["truncate", "drop_oldest"] = "truncate",
        max_tokens: int | None = None,
    ):
        self.model = model
        self.max_context = max_tokens or CONTEXT_WINDOWS.get(model, DEFAULT_WINDOW)
        self.strategy = strategy
        # Leave head (system) and tail (recent) intact, trim middle
        self.head_count = 1  # system prompt
        self.tail_count = 10  # recent messages
        self.target_tokens = self.max_context - RESERVED_TOKENS

    def estimate_tokens(self, messages: list[dict[str, Any]]) -> int:
        """
        Rough token estimate: ~4 chars per token for English/Indonesian mix.
        More accurate for code-heavy content.
        """
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            # Rough: 4 chars/token, but code is ~3 chars/token
            if any(
                ck in content for ck in ["```", "def ", "class ", "import ", "//", "#"]
            ):
                total += len(content) // 3
            else:
                total += len(content) // 4
        return total

    def fit(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Trim messages to fit within context window.
        Returns the trimmed message list (always includes system prompt).
        """
        target = (max_tokens or self.target_tokens) - RESERVED_TOKENS
        current_tokens = self.estimate_tokens(messages)

        if current_tokens <= target:
            return messages

        logger.info(
            "context_trimming",
            strategy=self.strategy,
            model=self.model,
            current_tokens=current_tokens,
            target_tokens=target,
        )

        if self.strategy == "truncate":
            return self._truncate(messages, target)
        else:
            return self._drop_oldest(messages, target)

    def _truncate(
        self, messages: list[dict[str, Any]], target: int
    ) -> list[dict[str, Any]]:
        """
        Remove middle messages, keeping head (system) and tail (recent).
        Binary search to find optimal split point.
        """
        if len(messages) <= self.head_count + self.tail_count:
            return messages[-self.tail_count :] if messages else messages

        result = list(messages[: self.head_count])  # keep system
        result.extend(messages[-self.tail_count :])  # keep recent

        # Check if it fits
        if self.estimate_tokens(result) <= target:
            return result

        # Fallback: simple drop
        return self._drop_oldest(messages, target)

    def _drop_oldest(
        self, messages: list[dict[str, Any]], target: int
    ) -> list[dict[str, Any]]:
        """
        Drop oldest messages until it fits.
        Always keeps the system prompt.
        """
        if not messages:
            return messages

        result = list(messages)
        while self.estimate_tokens(result) > target and len(result) > self.head_count:
            result.pop(self.head_count)  # remove after system prompt

        return result


def trim_context(
    messages: list[dict[str, Any]],
    model: str,
    strategy: str = "truncate",
) -> list[dict[str, Any]]:
    """Convenience function."""
    manager = ContextWindowManager(model=model, strategy=strategy)
    return manager.fit(messages)
