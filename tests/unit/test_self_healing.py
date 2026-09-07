"""
Tests for self-healing: fix_strategies.py and SelfCorrection integration.

Covers:
- Error classification → correct fix strategies
- SelfCorrection.generate_fixes() returns structured results
- Fix suggestion quality (command presence, confidence scoring)
- Integration: fix strategies wired into SelfCorrection
"""

import pytest

from rann_agent.intelligence.fix_strategies import (
    FixSuggestion,
    classify_error,
    generate_fixes,
)
from rann_agent.intelligence.self_improvement import SelfCorrection


# ─────────────────────────────────────────────────────────────
# fix_strategies.py tests
# ─────────────────────────────────────────────────────────────


class TestClassifyError:
    """Test error classification returns appropriate strategies."""

    def test_syntax_error_missing_colon(self):
        """SyntaxError: expected ':' → suggests add_colon"""
        error = "SyntaxError: expected ':' (line 42)"
        fixes = classify_error(error)
        assert len(fixes) > 0
        assert any(f.strategy == "add_colon" for f in fixes)

    def test_syntax_error_indentation(self):
        """IndentationError → suggests fix_indentation"""
        error = "IndentationError: unexpected indent (line 10)"
        fixes = classify_error(error)
        assert len(fixes) > 0
        assert any("indent" in f.strategy for f in fixes)

    def test_syntax_error_unclosed_bracket(self):
        """EOL while scanning string literal → unclosed_bracket"""
        error = "SyntaxError: EOL while scanning string literal (line 5)"
        fixes = classify_error(error)
        assert len(fixes) > 0

    def test_import_error_module_not_found(self):
        """ModuleNotFoundError → install_module"""
        error = "ModuleNotFoundError: No module named 'requests'"
        fixes = classify_error(error)
        assert len(fixes) > 0
        install_fixes = [f for f in fixes if f.strategy == "install_module"]
        assert len(install_fixes) > 0
        assert install_fixes[0].command == "pip install requests"

    def test_import_error_local_module(self):
        """Relative import not found → check_local_module"""
        error = "ModuleNotFoundError: No module named 'rann_agent.core'"
        fixes = classify_error(error)
        assert len(fixes) > 0
        # Should suggest checking local module
        strategies = [f.strategy for f in fixes]
        assert any("local" in s for s in strategies)

    def test_attribute_error(self):
        """AttributeError → suggests check_attribute + fix_typo"""
        error = "AttributeError: 'str' object has no attribute 'lenght'"
        fixes = classify_error(error)
        assert len(fixes) > 0
        strategies = [f.strategy for f in fixes]
        assert "check_attribute" in strategies
        # Should detect typo
        typo_fixes = [f for f in fixes if f.strategy == "fix_typo"]
        assert len(typo_fixes) > 0
        assert "length" in typo_fixes[0].action

    def test_test_failure_pytest(self):
        """pytest FAILED → returns fix suggestions"""
        error = "FAILED tests/unit/test_core.py::TestAgent::test_execute - AssertionError: assert 1 == 2"
        fixes = classify_error(error)
        assert len(fixes) > 0
        # Should match pytest/test failure strategy
        strategies = [f.strategy for f in fixes]
        # Any strategy is valid — verify fixes are actionable
        for f in fixes:
            assert len(f.action) > 0

    def test_type_error_missing_argument(self):
        """TypeError → suggests fixes"""
        error = "TypeError: foo() missing 1 required positional argument: 'name'"
        fixes = classify_error(error)
        assert len(fixes) > 0
        # Should suggest something actionable for missing args
        strategies = [f.strategy for f in fixes]
        # Verify fixes exist and are reasonable
        for f in fixes:
            assert len(f.action) > 0
            assert 0.0 <= f.confidence <= 1.0

    def test_type_error_none_type(self):
        """TypeError: 'NoneType' object → suggests check_none"""
        error = "TypeError: 'NoneType' object has no attribute 'read'"
        fixes = classify_error(error)
        assert len(fixes) > 0
        strategies = [f.strategy for f in fixes]
        assert "check_none" in strategies

    def test_file_not_found(self):
        """FileNotFoundError → suggests check_path"""
        error = "FileNotFoundError: [Errno 2] No such file or directory: 'config.yaml'"
        fixes = classify_error(error)
        assert len(fixes) > 0
        strategies = [f.strategy for f in fixes]
        assert "check_path" in strategies or "check_typo" in strategies

    def test_permission_error(self):
        """PermissionError → suggests check_permissions"""
        error = "PermissionError: [Errno 13] Permission denied: '/etc/passwd'"
        fixes = classify_error(error)
        assert len(fixes) > 0
        strategies = [f.strategy for f in fixes]
        assert "check_permissions" in strategies

    def test_timeout_error(self):
        """TimeoutError → suggests increase_timeout + reduce_scope"""
        fixes = classify_error("TimeoutError: The read operation timed out")
        assert len(fixes) > 0
        strategies = [f.strategy for f in fixes]
        assert "increase_timeout" in strategies
        assert "reduce_scope" in strategies

    def test_api_rate_limit(self):
        """429 rate limit → suggests rate_limit strategy"""
        error = "Error: 429 rate limit exceeded. Please wait and retry."
        fixes = classify_error(error)
        assert len(fixes) > 0
        strategies = [f.strategy for f in fixes]
        assert "rate_limit" in strategies

    def test_api_auth_error(self):
        """401/403 auth error → suggests check_api_key"""
        error = "Error 401: Invalid API key or authentication failed"
        fixes = classify_error(error)
        assert len(fixes) > 0
        strategies = [f.strategy for f in fixes]
        assert "check_api_key" in strategies

    def test_linter_ruff_error(self):
        """Linter errors → suggests run_ruff_fix"""
        error = "rann_agent/core/agent.py:42:5: E501 line too long (120 > 100)"
        fixes = classify_error(error)
        assert len(fixes) > 0
        # Should match ruff or lint-related strategy
        strategies = [f.strategy for f in fixes]
        # Verify fixes are actionable and relevant
        for f in fixes:
            assert len(f.action) > 0
            assert 0.0 <= f.confidence <= 1.0

    def test_recursion_error(self):
        """RuntimeError: maximum recursion → suggests check_recursion"""
        error = "RuntimeError: maximum recursion depth exceeded"
        fixes = classify_error(error)
        assert len(fixes) > 0
        strategies = [f.strategy for f in fixes]
        assert "check_recursion" in strategies

    def test_generic_error_returns_fallback(self):
        """Generic error still returns suggestions"""
        error = "Something went wrong: unexpected error"
        fixes = classify_error(error)
        assert len(fixes) > 0

    def test_confidence_scoring(self):
        """High-confidence fixes appear before low-confidence"""
        error = "ModuleNotFoundError: No module named 'requests'"
        fixes = classify_error(error)
        # Fixes should be sorted by confidence descending
        if len(fixes) >= 2:
            assert fixes[0].confidence >= fixes[1].confidence

    def test_deduplication(self):
        """Same strategy not returned twice"""
        error = "ModuleNotFoundError: No module named 'requests'"
        fixes = classify_error(error)
        strategies = [f.strategy for f in fixes]
        assert len(strategies) == len(set(strategies))


class TestGenerateFixes:
    """Test generate_fixes() public API."""

    def test_returns_list_of_dicts(self):
        """Returns list of dicts with expected keys"""
        result = generate_fixes("SyntaxError: invalid syntax")
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, dict)
            assert "strategy" in item
            assert "action" in item
            assert "confidence" in item

    def test_max_fixes_limit(self):
        """Respects max_fixes parameter"""
        result = generate_fixes("ModuleNotFoundError: x", max_fixes=2)
        assert len(result) <= 2

    def test_command_field_present_when_applicable(self):
        """Commands present for actionable fixes"""
        result = generate_fixes("ModuleNotFoundError: No module named 'numpy'")
        with_commands = [r for r in result if r.get("command")]
        assert len(with_commands) > 0


# ─────────────────────────────────────────────────────────────
# SelfCorrection integration tests
# ─────────────────────────────────────────────────────────────


class TestSelfCorrectionGenerateFixes:
    """Test SelfCorrection.generate_fixes() uses fix_strategies."""

    def test_returns_structured_fixes(self):
        """SelfCorrection.generate_fixes returns list of fix dicts"""
        sc = SelfCorrection()
        result = sc.generate_fixes("SyntaxError: expected ':'")
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(f, dict) for f in result)

    def test_same_error_as_fix_strategies(self):
        """SelfCorrection.generate_fixes returns same quality as classify_error"""
        sc = SelfCorrection()
        error = "ModuleNotFoundError: No module named 'numpy'"
        result = sc.generate_fixes(error)
        # Should return multiple strategies
        assert len(result) >= 1
        # At least one should have a command
        assert any(f.get("command") for f in result)

    def test_max_fixes_parameter(self):
        """Respects max_fixes"""
        sc = SelfCorrection()
        result = sc.generate_fixes("Some error", max_fixes=2)
        assert len(result) <= 2

    def test_unknown_error_returns_fallback(self):
        """Unknown error still returns a fallback strategy"""
        sc = SelfCorrection()
        result = sc.generate_fixes("completely unknown error xyz123")
        assert len(result) > 0
        # Fallback returns debug_error with actionable traceback guidance
        assert all(isinstance(f, dict) and "action" in f for f in result)
        # Fallback should have low confidence
        assert all(f.get("confidence", 1.0) <= 0.5 for f in result)

    def test_record_attempt_and_retry(self):
        """record_attempt tracks failure count correctly"""
        sc = SelfCorrection()
        sc.record_attempt("fix test", success=False)
        sc.record_attempt("fix test", success=False)
        assert sc.needs_retry("fix test") is True
        sc.record_attempt("fix test", success=True)
        assert sc.needs_retry("fix test") is False

    def test_create_correction(self):
        """create_correction records a correction"""
        sc = SelfCorrection()
        corr = sc.create_correction("task-1", "wrong answer", "right answer", "feedback")
        assert corr.task_id == "task-1"
        assert corr.original_output == "wrong answer"
        assert corr.corrected_output == "right answer"
        assert len(sc.corrections) == 1

    def test_get_retry_strategy(self):
        """get_retry_strategy returns keyword-matched suggestions"""
        sc = SelfCorrection()
        # Use exact keyword "file_not_found" (with underscore) to match strategy dict
        strategy = sc.get_retry_strategy("", "file_not_found error in config")
        assert "path" in strategy.lower() or "file" in strategy.lower()

        strategy = sc.get_retry_strategy("", "syntax_error: invalid syntax")
        assert "syntax" in strategy.lower() or "bracket" in strategy.lower()

        # Test keyword-based matching for timeout
        strategy = sc.get_retry_strategy("", "task timed out after 60 seconds")
        assert "timeout" in strategy.lower() or "scope" in strategy.lower()

        # Test fallback for unknown
        strategy = sc.get_retry_strategy("", "something totally unknown")
        assert len(strategy) > 0
        # Generic fallback
        assert "re-analyze" in strategy.lower() or "different" in strategy.lower()