"""
Unit tests for context_trim module.
"""

from rann_agent.memory import context_trim
from rann_agent.memory.context_trim import (
    disable_test_mode,
    enable_test_mode,
    estimate_tokens,
    trim_context,
)

# Use a small-context model for realistic trimming tests
SMALL_MODEL = "minimax/minimax-m2.7-highspeed:free"  # 16k window


def make_msg(role: str, content: str) -> dict:
    """Helper to create a message dict."""
    return {"role": role, "content": content}


def make_messages(n: int, content_len: int = 100) -> list:
    """Create n messages with filler content."""
    messages = [make_msg("system", "You are a helpful assistant." * 10)]
    for i in range(n):
        messages.append(make_msg("user", f"Message {i}: " + "x" * content_len))
    return messages


class TestSystemPromptAlwaysPreserved:
    """test_system_prompt_always_preserved"""

    def test_trim_removes_middle_but_keeps_system(self):
        # Use small max_tokens to force trimming
        messages = [
            make_msg("system", "SYSTEM_PROMPT"),
        ] + [make_msg("user", f"msg{i}") for i in range(50)]
        result = trim_context(messages, SMALL_MODEL, max_tokens=5000)
        assert result[0]["role"] == "system"
        assert result[0]["content"] == "SYSTEM_PROMPT"

    def test_no_system_message(self):
        """When there's no system message, trimming still works."""
        messages = [make_msg("user", f"msg{i}") for i in range(50)]
        result = trim_context(messages, SMALL_MODEL)
        # Should still return something valid
        assert len(result) > 0

    def test_system_is_first_even_after_trim(self):
        """System prompt is always index 0 in result."""
        messages = (
            [make_msg("system", "Important system prompt.")]
            + [make_msg("assistant", "Old reply.")]
            + [make_msg("user", f"User message {i}.") for i in range(100)]
        )
        result = trim_context(messages, SMALL_MODEL, max_tokens=5000)
        assert result[0]["role"] == "system"


class TestRecentMessagesAlwaysKept:
    """test_recent_messages_always_kept"""

    def test_last_10_messages_preserved(self):
        """The last 10 messages are never removed."""
        # Create 50 messages, last 10 have unique markers
        unique_tail = [f"TAIL_MARKER_{i}" for i in range(10)]
        messages = [make_msg("system", "System")]
        for i in range(40):
            messages.append(make_msg("user", f"middle_{i}"))
        for marker in unique_tail:
            messages.append(make_msg("user", marker))

        result = trim_context(messages, SMALL_MODEL, max_tokens=5000)

        # All tail markers must be present
        result_contents = [m["content"] for m in result]
        for marker in unique_tail:
            assert marker in result_contents

    def test_trim_within_tail_count(self):
        """If total messages <= tail_count + system, nothing is trimmed."""
        messages = [make_msg("system", "System")] + [make_msg("user", f"msg{i}") for i in range(9)]
        result = trim_context(messages, SMALL_MODEL)
        assert len(result) == len(messages)


class TestTrimReducesTokenCount:
    """test_trim_reduces_token_count"""

    def test_trim_reduces_token_count(self):
        """Verify that trimming actually reduces token estimate."""
        # Use test mode for deterministic counting with a small max_tokens to force trim
        enable_test_mode()
        try:
            messages = make_messages(200, content_len=300)
            before = estimate_tokens(messages)
            # Use a small max_tokens to force trimming
            result = trim_context(messages, SMALL_MODEL, max_tokens=8000)
            after = estimate_tokens(result)
            assert after < before
        finally:
            disable_test_mode()

    def test_trim_result_fits_in_context(self):
        """Result of trim_context should fit in context window."""
        enable_test_mode()
        try:
            messages = make_messages(200, content_len=300)
            result = trim_context(messages, SMALL_MODEL, max_tokens=16000)
            result_tokens = estimate_tokens(result)
            # In test mode, 201 messages * 50 tokens = 10050
            # Available = 16000 - 2000 = 14000
            assert result_tokens <= 14000
        finally:
            disable_test_mode()

    def test_explicit_max_tokens_respected(self):
        """Setting max_tokens lower forces more aggressive trimming."""
        enable_test_mode()
        try:
            messages = make_messages(50, content_len=200)
            result_default = trim_context(messages, SMALL_MODEL)
            result_low = trim_context(messages, SMALL_MODEL, max_tokens=4000)
            # In test mode: 51 msgs * 50 = 2550 (no trim needed)
            # With max_tokens=4000: available=2000, still 2550 > 2000 → trims
            assert len(result_low) < len(result_default)
        finally:
            disable_test_mode()


class TestFallbackWhenNoTiktoken:
    """test_fallback_when_no_tiktoken"""

    def test_fallback_when_no_tiktoken(self):
        """When tiktoken is unavailable, char/4 estimate is used."""
        original_has_tiktoken = context_trim._HAS_TIKTOKEN

        try:
            # Simulate tiktoken not available
            context_trim._HAS_TIKTOKEN = False

            messages = [make_msg("user", "Hello world! " * 50)]
            tokens = estimate_tokens(messages)
            # char/4 estimate: len("Hello world! " * 50) / 4 ≈ 525 / 4 ≈ 131
            assert tokens > 0
            assert tokens < len("Hello world! " * 50)  # definitely less than char count
        finally:
            context_trim._HAS_TIKTOKEN = original_has_tiktoken


class TestWith100Messages:
    """test_with_100_messages"""

    def test_with_100_messages(self):
        """Stress test with 100 messages using small context model."""
        enable_test_mode()
        try:
            # In test mode: 101 msgs * 50 = 5050 tokens
            # Available on minimax (16k-2k=14k) → doesn't trim
            # Use gpt-3.5-turbo (16385) → available ~14385 → no trim
            # Use a very small max_tokens to force trim
            messages = make_messages(100, content_len=200)
            result = trim_context(messages, SMALL_MODEL, max_tokens=8000)
            # With max_tokens=8000, available = 6000
            # In test mode: 101 * 50 = 5050 < 6000 → still doesn't trim
            # Need a different approach: use the SMALL_MODEL default but
            # since test mode gives 50/method, 5050 < 14000 → no trim
            # The test needs to verify trimming happened by checking len
            # We need to force a scenario where it definitely trims
            # Use max_tokens that forces trimming
            result = trim_context(messages, SMALL_MODEL, max_tokens=3000)
            # available = 1000, 101*50=5050 > 1000 → trims to ~20 msgs
            assert len(result) < 100
            assert result[0]["role"] == "system"
        finally:
            disable_test_mode()

    def test_with_100_messages_under_small_limit(self):
        """100 messages with a very small context limit."""
        enable_test_mode()
        try:
            messages = make_messages(100, content_len=200)
            result = trim_context(messages, SMALL_MODEL, max_tokens=4000)
            assert len(result) > 0
            assert result[0]["role"] == "system"
            # Should have trimmed significantly
            assert len(result) < 50
        finally:
            disable_test_mode()


class TestWith1000Messages:
    """test_with_1000_messages"""

    def test_with_1000_messages(self):
        """Stress test with 1000 messages using small context model."""
        enable_test_mode()
        try:
            messages = make_messages(1000, content_len=100)
            result = trim_context(messages, SMALL_MODEL, max_tokens=8000)
            # 1001 msgs * 50 = 50050 tokens
            # available = 6000 → must trim heavily
            assert len(result) < 200
            assert result[0]["role"] == "system"
            assert estimate_tokens(result) < estimate_tokens(messages)
        finally:
            disable_test_mode()

    def test_with_1000_messages_gpt4(self):
        """1000 messages with GPT-4o context window - also needs trimming."""
        enable_test_mode()
        try:
            messages = make_messages(1000, content_len=200)
            result = trim_context(messages, "gpt-4o", max_tokens=20000)
            # 1001 * 50 = 50050 > 18000 → must trim
            assert len(result) < 500
            assert result[0]["role"] == "system"
        finally:
            disable_test_mode()


class TestEstimateTokens:
    """Tests for estimate_tokens helper."""

    def test_empty_messages(self):
        assert estimate_tokens([]) == 0

    def test_single_message(self):
        msg = make_msg("user", "Hello")
        assert estimate_tokens([msg]) > 0

    def test_test_mode(self):
        """Test mode gives deterministic fixed estimate."""
        enable_test_mode()
        try:
            msgs = [make_msg("user", f"msg{i}") for i in range(5)]
            # 5 messages * 50 tokens = 250
            assert estimate_tokens(msgs) == 250
        finally:
            disable_test_mode()

    def test_code_content_estimate(self):
        """Code-heavy content should use higher token estimate."""
        code_msg = make_msg("system", "```python\ndef foo():\n    pass\n```")
        plain_msg = make_msg("system", "hello world")
        code_tokens = estimate_tokens([code_msg])
        plain_tokens = estimate_tokens([plain_msg])
        # Code message is longer in tokens relative to chars than plain text
        assert code_tokens > plain_tokens
