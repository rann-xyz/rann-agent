"""
Context trimming for RANN Agent.

Provides trimming strategies to keep conversation history within model context limits.
Strategy: keep system prompt (index 0), keep recent messages (tail_count=10),
drop oldest from middle.
"""

from typing import Any

try:
    import tiktoken

    _HAS_TIKTOKEN = True
except ImportError:
    tiktoken = None
    _HAS_TIKTOKEN = False

from rann_agent.utils.context_window import (
    CONTEXT_WINDOWS,
    DEFAULT_WINDOW,
    RESERVED_TOKENS,
)

# Test mode for deterministic behavior
_TEST_MODE = False
_TEST_TOKEN_ESTIMATE = 50  # fixed estimate per message in test mode


def enable_test_mode():
    """Enable test mode for deterministic token counting."""
    global _TEST_MODE
    _TEST_MODE = True


def disable_test_mode():
    """Disable test mode."""
    global _TEST_MODE
    _TEST_MODE = False


def _get_tiktoken_encoder():
    """Get tiktoken encoder if available."""
    if not _HAS_TIKTOKEN:
        return None
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None


def estimate_tokens(messages: list[dict[str, Any]]) -> int:
    """
    Estimate token count for a list of messages.

    Uses tiktoken if available (accurate), otherwise falls back to char/4 estimate.
    In test mode, returns a fixed estimate per message for deterministic results.
    """
    if _TEST_MODE:
        return len(messages) * _TEST_TOKEN_ESTIMATE

    if not messages:
        return 0

    # Try tiktoken first
    encoder = _get_tiktoken_encoder()
    if encoder is not None:
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            # role names add overhead
            total += len(encoder.encode(str(content)))
        return total

    # Fallback: char/4 estimate
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        # Check for code markers
        if any(ck in content for ck in ["```", "def ", "class ", "import ", "//", "#"]):
            total += len(content) // 3
        else:
            total += len(content) // 4
    return total


def trim_context(
    messages: list[dict[str, Any]],
    model: str,
    max_tokens: int | None = None,
) -> list[dict[str, Any]]:
    """
    Trim messages to fit within model context window.

    Strategy:
    - Always keep system prompt (index 0) if present
    - Always keep the most recent `tail_count` messages (default 10)
    - If still over budget, drop oldest non-system messages from the middle

    Args:
        messages: List of message dicts with 'role' and 'content' keys
        model: Model name to determine context window size
        max_tokens: Optional override for max tokens (default: use model default)

    Returns:
        Trimmed message list (always includes system prompt if it was present)
    """
    if not messages:
        return messages

    tail_count = 10
    max_context = max_tokens or CONTEXT_WINDOWS.get(model, DEFAULT_WINDOW)
    available = max_context - RESERVED_TOKENS

    # Check if trimming is needed
    current_tokens = estimate_tokens(messages)
    if current_tokens <= available:
        return messages

    # Identify system prompt (usually index 0 with role='system')
    system_msg = None
    system_idx = -1
    for i, msg in enumerate(messages):
        role = msg.get("role", "").lower()
        if role == "system":
            system_msg = msg
            system_idx = i
            break

    # Build initial result: system (if any) + recent tail messages
    if system_msg is not None:
        result = [system_msg]
    else:
        result = []

    result.extend(messages[-tail_count:])

    # Check if we fit now
    if estimate_tokens(result) <= available:
        # We fit with just system + tail, but need to add some middle messages
        pass
    else:
        # Even system + tail doesn't fit — fall back to strict tail-only
        return result

    # Middle section: messages between system and tail
    if system_idx == 0:
        middle_start = 1
    else:
        middle_start = 0

    middle = list(messages[middle_start : len(messages) - tail_count])
    tail = list(messages[-tail_count:])

    # Binary search: find max number of middle messages (from newest to oldest) that fit
    # middle is ordered oldest→newest; we want to take newest first
    middle_reversed = list(reversed(middle))  # newest first

    # Build result by progressively adding newest middle messages
    # result = [system?] + selected_middle + tail
    # We want the max subset of middle_reversed (prefix) that fits

    # Start with just system + tail, try adding middle messages newest-first
    result = [system_msg] if system_msg else []
    result.extend(tail)

    # Greedy: add as many as possible from middle_reversed (newest first)
    for msg in middle_reversed:
        # Insert just before the tail
        result.insert(len(result) - tail_count, msg)
        if estimate_tokens(result) > available:
            result.pop(len(result) - tail_count - 1)
            break

    return result


def get_context_limit(model: str, max_tokens: int | None = None) -> int:
    """Get the effective context limit for a model."""
    return max_tokens or CONTEXT_WINDOWS.get(model, DEFAULT_WINDOW)


def get_available_tokens(model: str, max_tokens: int | None = None) -> int:
    """Get available tokens after reserving space for system/response overhead."""
    return get_context_limit(model, max_tokens) - RESERVED_TOKENS
