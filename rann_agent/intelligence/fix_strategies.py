"""
Fix Strategy Registry

Maps error types → targeted fix functions.
Each strategy returns actionable fix suggestions with commands.

Used by SelfCorrection to generate real fixes, not stubs.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

# ─────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────


@dataclass
class FixSuggestion:
    """A single fix suggestion with metadata."""

    strategy: str
    action: str
    command: str | None = None
    file_to_edit: str | None = None
    confidence: float = 0.8  # 0.0–1.0
    reason: str = ""


# ─────────────────────────────────────────────────────────────
# Strategy functions
# Each takes (error_msg, context) → list[FixSuggestion]
# ─────────────────────────────────────────────────────────────


def _syntax_error_strategy(error_msg: str, context: dict) -> list[FixSuggestion]:
    """Handle Python SyntaxError, IndentationError, TabError."""
    suggestions = []

    # Missing colon after def/class/if/for/while/with
    if re.search(r"expected '['\"':']", error_msg):
        suggestions.append(
            FixSuggestion(
                strategy="add_colon",
                action="Add missing colon at end of function/class/if/for statement",
                confidence=0.9,
                reason="Error message explicitly mentions expected ':'",
            )
        )

    # Unclosed bracket/parenthesis
    if "EOL" in error_msg or "EOF" in error_msg or "unterminated" in error_msg.lower():
        suggestions.append(
            FixSuggestion(
                strategy="unclosed_bracket",
                action="Find the unclosed bracket/parenthesis/string — check end of file",
                confidence=0.8,
                reason="Error suggests unclosed construct",
            )
        )

    # Indentation error
    if "indent" in error_msg.lower():
        suggestions.append(
            FixSuggestion(
                strategy="fix_indentation",
                action="Use consistent indentation (4 spaces). Check for mixed tabs/spaces.",
                confidence=0.9,
                reason="Indentation error detected",
            )
        )

    # Try to extract the problematic line from error
    line_match = re.search(r"line (\d+)", error_msg)
    if line_match:
        line_num = int(line_match.group(1))
        suggestions.append(
            FixSuggestion(
                strategy="inspect_line",
                action=f"Inspect line {line_num} and surrounding context for syntax issues",
                confidence=0.7,
                reason=f"Error located at line {line_num}",
            )
        )

    # Default fallback
    if not suggestions:
        suggestions.append(
            FixSuggestion(
                strategy="parse_file",
                action="Run: python3 -m py_compile <file> to get exact error location",
                confidence=0.5,
            )
        )

    return suggestions


def _import_error_strategy(error_msg: str, context: dict) -> list[FixSuggestion]:
    """Handle ImportError, ModuleNotFoundError."""
    suggestions = []

    # Extract module name
    module_match = re.search(r"No module named ['\"]([^'\"]+)['\"]", error_msg)
    module_name = module_match.group(1) if module_match else None

    if module_name:
        suggestions.append(
            FixSuggestion(
                strategy="install_module",
                action=f"Install missing module: pip install {module_name}",
                command=f"pip install {module_name}",
                file_to_edit="requirements.txt",
                confidence=0.9,
                reason=f"Module '{module_name}' not found",
            )
        )

        # Check if it's a local/relative import
        if "." in module_name:
            parent = module_name.split(".")[0]
            suggestions.append(
                FixSuggestion(
                    strategy="check_local_module",
                    action=f"Check if '{parent}' directory exists and has __init__.py",
                    confidence=0.7,
                    reason="Relative import not found",
                )
            )
        else:
            suggestions.append(
                FixSuggestion(
                    strategy="check_local_path",
                    action=f"Ensure '{module_name}' is in PYTHONPATH or project root",
                    confidence=0.6,
                )
            )

        # Try alternative package names for common packages
        alt_names = {
            "PIL": "pillow",
            "cv2": "opencv-python",
            "sklearn": "scikit-learn",
            "yaml": "pyyaml",
            "dotenv": "python-dotenv",
            "nose": "pytest",
            "futures": "concurrent.futures",
        }
        if module_name in alt_names:
            alt = alt_names[module_name]
            suggestions.append(
                FixSuggestion(
                    strategy="install_alt_package",
                    action=f"Try installing '{alt}' instead of '{module_name}'",
                    command=f"pip install {alt}",
                    confidence=0.8,
                    reason=f"'{module_name}' is often installed as '{alt}'",
                )
            )

    # If extraction failed, give a generic debug command
    if not suggestions:
        suggestions.append(
            FixSuggestion(
                strategy="debug_import",
                action="Run: python3 -c 'import <module_name>' to isolate the import chain",
                confidence=0.5,
            )
        )

    return suggestions


def _attribute_error_strategy(error_msg: str, context: dict) -> list[FixSuggestion]:
    """Handle AttributeError — missing attribute/method."""
    suggestions = []

    # Extract object and attribute
    match = re.search(r"'([^']+)' object has no attribute '([^']+)'", error_msg)
    if match:
        obj_type = match.group(1)
        attr = match.group(2)
        suggestions.append(
            FixSuggestion(
                strategy="check_attribute",
                action=f"'{obj_type}' has no attribute '{attr}'. Check for typos or import issues.",
                confidence=0.9,
                reason=f"Attribute '{attr}' not found on '{obj_type}'",
            )
        )

        # Common typos
        common_misspellings = {
            "lenght": "length",
            "lenght": "length",
            "widht": "width",
            "heigth": "height",
            "attribte": "attribute",
            "functon": "function",
            "methos": "method",
            "parm": "param",
            "paramater": "parameter",
            "definaton": "definition",
        }
        if attr in common_misspellings:
            correct = common_misspellings[attr]
            suggestions.append(
                FixSuggestion(
                    strategy="fix_typo",
                    action=f"Did you mean '{correct}' instead of '{attr}'?",
                    confidence=0.95,
                    reason="Common misspelling detected",
                )
            )

        # Check for version mismatch
        suggestions.append(
            FixSuggestion(
                strategy="check_version",
                action=f"Check if '{obj_type}' API changed in a newer version",
                confidence=0.6,
                reason="Attribute may have been renamed or removed",
            )
        )
    else:
        suggestions.append(
            FixSuggestion(
                strategy="debug_attribute",
                action="Check the object's type and available attributes with dir()",
                confidence=0.6,
            )
        )

    return suggestions


def _test_failure_strategy(error_msg: str, context: dict) -> list[FixSuggestion]:
    """Handle pytest/test failures."""
    suggestions = []

    # Extract test name
    test_match = re.search(r"FAILED ([\w\.]+)", error_msg)
    test_name = test_match.group(1) if test_match else None

    # Extract assertion error
    if "AssertionError" in error_msg or "assert" in error_msg.lower():
        assertions = re.findall(r"assert [^,\n]+", error_msg)
        if assertions:
            suggestions.append(
                FixSuggestion(
                    strategy="inspect_assertion",
                    action=f"Check assertion: {assertions[0]}",
                    confidence=0.9,
                    reason="Assertion failed",
                )
            )

    if test_name:
        suggestions.append(
            FixSuggestion(
                strategy="run_single_test",
                action=f"Run only '{test_name}' to isolate: pytest {test_name} -v",
                command=f"pytest {test_name} -v --tb=short",
                confidence=0.8,
                reason=f"Failed test: {test_name}",
            )
        )

        suggestions.append(
            FixSuggestion(
                strategy="run_with_traceback",
                action=f"Run with full traceback: pytest {test_name} -v --tb=long",
                command=f"pytest {test_name} -v --tb=long",
                confidence=0.7,
                reason="Get detailed failure context",
            )
        )

    # Check for missing test setup
    if "fixture" in error_msg.lower() or "setup" in error_msg.lower():
        suggestions.append(
            FixSuggestion(
                strategy="check_fixture",
                action="Ensure required pytest fixtures are defined and imported",
                confidence=0.8,
                reason="Fixture-related failure",
            )
        )

    return suggestions


def _type_error_strategy(error_msg: str, context: dict) -> list[FixSuggestion]:
    """Handle TypeError — wrong argument types."""
    import re
    suggestions = []

    # Extract expected vs actual
    match = re.search(r"(\w+)\.(\w+)\(\) expected (\w+) but got (\w+)", error_msg)
    if match:
        method = f"{match.group(1)}.{match.group(2)}"
        expected = match.group(3)
        actual = match.group(4)
        suggestions.append(
            FixSuggestion(
                strategy="fix_argument_type",
                action=f"'{method}' expects {expected}, got {actual}. Check argument types.",
                confidence=0.9,
                reason=f"Type mismatch: expected {expected}, got {actual}",
            )
        )

    # NoneType error
    if "Nonetype" in error_msg or "NoneType" in error_msg or "'None'" in error_msg:
        suggestions.append(
            FixSuggestion(
                strategy="check_none",
                action="Object is None. Add null check or ensure it's initialized before use.",
                confidence=0.9,
                reason="NoneType error — object not initialized",
            )
        )

    # Missing argument — match "missing N required argument" without complex quotes
    if "missing" in error_msg.lower() and "required" in error_msg.lower() and "argument" in error_msg.lower():
        suggestions.append(
            FixSuggestion(
                strategy="add_argument",
                action="Function call is missing a required argument. Check the function signature.",
                confidence=0.9,
                reason="Required argument missing",
            )
        )

    # Wrong argument type (e.g., "got str, expected int", "can only concatenate str (not 'int')")
    type_mismatch = re.search(
        r"can only concatenate (\w+).*not '(\w+)'|expected (.+?) but got (.+)",
        error_msg,
        re.IGNORECASE,
    )
    if type_mismatch:
        groups = type_mismatch.groups()
        if groups[0]:  # "can only concatenate X (not 'Y')"
            actual, expected = groups[0], groups[1]
        else:  # "expected X but got Y"
            expected, actual = groups[2].strip(), groups[3].strip()
        suggestions.append(
            FixSuggestion(
                strategy="fix_type_mismatch",
                action=f"Type mismatch: expected {expected}, got {actual}. Convert the argument.",
                confidence=0.85,
                reason=f"Type mismatch: {expected} vs {actual}",
            )
        )

    # Unhashable type (e.g., dict as set key)
    if "unhashable" in error_msg.lower():
        suggestions.append(
            FixSuggestion(
                strategy="check_hashable",
                action="Object is unhashable. Use a hashable type (str, int, tuple) as dict key or set element.",
                confidence=0.9,
                reason="Unhashable type used in hash context",
            )
        )

    return suggestions


def _file_not_found_strategy(error_msg: str, context: dict) -> list[FixSuggestion]:
    """Handle FileNotFoundError, IsADirectoryError."""
    suggestions = []

    path_match = re.search(r"[/\w\-\_. ]+", error_msg)
    suggestions.append(
        FixSuggestion(
            strategy="check_path",
            action="Verify file path exists. Use absolute paths for reliability.",
            confidence=0.8,
        )
    )

    suggestions.append(
        FixSuggestion(
            strategy="list_directory",
            action="List directory contents to find the correct filename",
            command="ls -la",
            confidence=0.7,
        )
    )

    # Check for typo in filename
    if path_match:
        path = path_match.group(0)
        suggestions.append(
            FixSuggestion(
                strategy="check_typo",
                action=f"Check for typo in path: '{path}'",
                confidence=0.6,
            )
        )

    return suggestions


def _permission_error_strategy(error_msg: str, context: dict) -> list[FixSuggestion]:
    """Handle PermissionError, AccessDenied."""
    suggestions = []

    suggestions.append(
        FixSuggestion(
            strategy="check_permissions",
            action="Check file/directory permissions. Use 'ls -la' to inspect.",
            command="ls -la",
            confidence=0.9,
            reason="Permission denied",
        )
    )

    suggestions.append(
        FixSuggestion(
            strategy="fix_permissions",
            action="Fix permissions: chmod +r/w for files, chmod +rwx for directories",
            confidence=0.7,
        )
    )

    return suggestions


def _timeout_error_strategy(error_msg: str, context: dict) -> list[FixSuggestion]:
    """Handle timeout errors."""
    suggestions = []

    suggestions.append(
        FixSuggestion(
            strategy="increase_timeout",
            action="Increase timeout value for the operation",
            confidence=0.8,
            reason="Operation timed out",
        )
    )

    suggestions.append(
        FixSuggestion(
            strategy="reduce_scope",
            action="Break task into smaller steps to avoid timeout",
            confidence=0.7,
            reason="Large operations may timeout",
        )
    )

    return suggestions


def _api_error_strategy(error_msg: str, context: dict) -> list[FixSuggestion]:
    """Handle LLM/API provider errors (rate limit, auth, etc.)."""
    import re
    suggestions = []
    error_lower = error_msg.lower()

    # HTTP status codes
    if re.search(r"\b401\b", error_msg):
        suggestions.append(
            FixSuggestion(
                strategy="check_api_key",
                action="HTTP 401 — authentication failed. Verify API key is correct and not expired.",
                confidence=0.95,
                reason="401 Unauthorized",
            )
        )
    if re.search(r"\b403\b", error_msg):
        suggestions.append(
            FixSuggestion(
                strategy="check_permissions",
                action="HTTP 403 — access forbidden. Check API key permissions/scopes.",
                confidence=0.9,
                reason="403 Forbidden",
            )
        )
    if re.search(r"\b429\b", error_msg):
        suggestions.append(
            FixSuggestion(
                strategy="rate_limit",
                action="HTTP 429 — rate limit exceeded. Wait and retry with exponential backoff.",
                confidence=0.95,
                reason="429 Too Many Requests",
            )
        )

    # Keyword-based detection (supplements codes)
    if "rate" in error_lower or "limit" in error_lower:
        suggestions.append(
            FixSuggestion(
                strategy="rate_limit",
                action="Rate limit hit. Wait and retry with exponential backoff.",
                confidence=0.9,
                reason="Rate limit keyword detected",
            )
        )

    if "authentication" in error_lower or "auth" in error_lower or "unauthorized" in error_lower:
        if not any(s.strategy == "check_api_key" for s in suggestions):
            suggestions.append(
                FixSuggestion(
                    strategy="check_api_key",
                    action="Authentication error. Verify API key is correct and has not expired.",
                    confidence=0.9,
                    reason="Authentication keyword detected",
                )
            )

    if "forbidden" in error_lower:
        suggestions.append(
            FixSuggestion(
                strategy="check_permissions",
                action="Access forbidden. Check API key permissions/scopes.",
                confidence=0.8,
                reason="Forbidden keyword",
            )
        )

    if "api.key" in error_lower or "apikey" in error_lower or "credential" in error_lower:
        suggestions.append(
            FixSuggestion(
                strategy="check_api_key",
                action="API key/credential issue. Verify key is correct.",
                confidence=0.9,
                reason="API key credential detected",
            )
        )

    if "quota" in error_lower or "budget exceeded" in error_lower:
        suggestions.append(
            FixSuggestion(
                strategy="check_quota",
                action="API quota/budget exceeded. Check provider dashboard.",
                confidence=0.9,
                reason="Quota exceeded",
            )
        )

    if "connection" in error_lower or "timeout" in error_lower or "network" in error_lower:
        suggestions.append(
            FixSuggestion(
                strategy="retry_connection",
                action="Network issue. Retry with longer timeout.",
                confidence=0.7,
                reason="Connection error",
            )
        )

    return suggestions


def _runtime_error_strategy(error_msg: str, context: dict) -> list[FixSuggestion]:
    """Handle generic RuntimeError, generic Exception."""
    suggestions = []

    # Recursion depth
    if "recursion" in error_msg.lower() or "maximum recursion" in error_msg.lower():
        suggestions.append(
            FixSuggestion(
                strategy="check_recursion",
                action="Recursion limit reached. Use iteration or increase sys.setrecursionlimit().",
                confidence=0.95,
                reason="Recursion depth exceeded",
            )
        )

    # Out of memory
    if "memory" in error_msg.lower() or "oom" in error_msg.lower():
        suggestions.append(
            FixSuggestion(
                strategy="reduce_memory",
                action="Memory exhausted. Process large data in chunks.",
                confidence=0.9,
                reason="Out of memory",
            )
        )

    # Generic — try to extract useful info
    suggestions.append(
        FixSuggestion(
            strategy="debug_error",
            action="Run with full traceback to identify exact failure point: python3 -v <script>",
            confidence=0.5,
        )
    )

    return suggestions


def _linter_error_strategy(error_msg: str, context: dict) -> list[FixSuggestion]:
    """Handle ruff/black/mypy lint errors."""
    suggestions = []

    error_lower = error_msg.lower()

    if "ruff" in error_lower or any(
        code in error_msg for code in ["E", "F", "W", "I", "S", "B", "UP", "ASYNC"]
    ):
        suggestions.append(
            FixSuggestion(
                strategy="run_ruff_fix",
                action="Run ruff with --fix to auto-correct: ruff check . --fix",
                command="ruff check . --fix",
                confidence=0.9,
                reason="Ruff lint error detected",
            )
        )

    if "black" in error_lower:
        suggestions.append(
            FixSuggestion(
                strategy="run_black",
                action="Run black to format: black .",
                command="black .",
                confidence=0.9,
                reason="Black formatting issue",
            )
        )

    if "mypy" in error_lower:
        suggestions.append(
            FixSuggestion(
                strategy="run_mypy",
                action="Run mypy to check types: mypy rann_agent --ignore-missing-imports",
                command="mypy rann_agent --ignore-missing-imports",
                confidence=0.8,
                reason="Type checking error",
            )
        )

    # Extract error code
    code_match = re.search(r"([A-Z]\d{3,4})", error_msg)
    if code_match:
        code = code_match.group(1)
        suggestions.append(
            FixSuggestion(
                strategy="lookup_error",
                action=f"Look up ruff error code {code}: ruff rule {code}",
                confidence=0.7,
                reason=f"Error code: {code}",
            )
        )

    return suggestions


# ─────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────

# Error type → list of strategy functions (checked in order, first match wins)
# IMPORTANT: More specific patterns MUST come before generic ones.
# All patterns compiled as re.Pattern for correct word-boundary matching.
ERROR_TYPE_STRATEGIES: list[tuple[re.Pattern, list]] = [
    # Python syntax/parse errors — specific class names
    (re.compile(r"\bsyntaxerror\b", re.IGNORECASE), [_syntax_error_strategy]),
    (re.compile(r"\bindentationerror\b", re.IGNORECASE), [_syntax_error_strategy]),
    (re.compile(r"\btaberror\b", re.IGNORECASE), [_syntax_error_strategy]),
    # Import/module errors — specific class names
    (re.compile(r"\bimporterror\b", re.IGNORECASE), [_import_error_strategy]),
    (re.compile(r"\bmodulenotfounderror\b", re.IGNORECASE), [_import_error_strategy]),
    # Attribute/method errors
    (re.compile(r"\battributeerror\b", re.IGNORECASE), [_attribute_error_strategy]),
    # Test failures — match FAILED/pytest/assertionerror in context
    (re.compile(r"\bfailed\b.*\bpytest\b|\bpytest\b.*\bfailed\b", re.IGNORECASE), [_test_failure_strategy]),
    (re.compile(r"\bassertionerror\b", re.IGNORECASE), [_test_failure_strategy]),
    (re.compile(r"\bpytest\b", re.IGNORECASE), [_test_failure_strategy]),
    # Type errors — specific class name
    (re.compile(r"\btypeerror\b", re.IGNORECASE), [_type_error_strategy]),
    # File errors — specific class names
    (re.compile(r"\bfilenotfounderror\b", re.IGNORECASE), [_file_not_found_strategy]),
    (re.compile(r"\bpermissionerror\b", re.IGNORECASE), [_permission_error_strategy]),
    (re.compile(r"\bisadirectoryerror\b", re.IGNORECASE), [_permission_error_strategy]),
    # Timeout — specific class name
    (re.compile(r"\btimeouterror\b", re.IGNORECASE), [_timeout_error_strategy]),
    # API/provider errors — HTTP status codes as words (429, 401, 403)
    (re.compile(r"\b429\b|\b401\b|\b403\b"), [_api_error_strategy]),
    # API errors — keyword phrases
    (re.compile(r"\brate.limit\b|\brate limit\b", re.IGNORECASE), [_api_error_strategy]),
    (re.compile(r"\bauthentication\b|\bapi.key\b|\bapikey\b|\bcredential\b|\bunauthorized\b|\bforbidden\b", re.IGNORECASE), [_api_error_strategy]),
    # Linter errors
    (re.compile(r"\bruff\b|\bblack\b|\bmypy\b|\bpylint\b|\bflake8\b", re.IGNORECASE), [_linter_error_strategy]),
    # Generic runtime — LAST RESORT only
    (re.compile(r"\bruntimeerror\b", re.IGNORECASE), [_runtime_error_strategy]),
    (re.compile(r"\bexception\b", re.IGNORECASE), [_runtime_error_strategy]),
]

# Fallback when no match
DEFAULT_STRATEGY = _runtime_error_strategy


def classify_error(error_msg: str) -> list[FixSuggestion]:
    """
    Classify an error message and return targeted fix suggestions.

    Args:
        error_msg: The full error message (e.g. from traceback)

    Returns:
        List of FixSuggestion objects, best first
    """
    error_lower = error_msg.lower()

    for pattern, strategies in ERROR_TYPE_STRATEGIES:
        if isinstance(pattern, re.Pattern) and pattern.search(error_lower):
            results = []
            for strat_fn in strategies:
                results.extend(strat_fn(error_msg, {}))
            if results:
                return _deduplicate_and_rank(results)

    # Fallback — no strategy matched or all returned empty
    return _deduplicate_and_rank(DEFAULT_STRATEGY(error_msg, {}))


def _deduplicate_and_rank(suggestions: list[FixSuggestion]) -> list[FixSuggestion]:
    """Remove duplicate strategies and sort by confidence descending."""
    if not suggestions:
        # Return a default fallback suggestion
        return [
            FixSuggestion(
                strategy="debug_error",
                action="Run with full traceback to identify exact failure point: python3 -v <script>",
                confidence=0.3,
                reason="No specific fix strategy found for this error type",
            )
        ]
    seen: set[str] = set()
    unique: list[FixSuggestion] = []
    for s in suggestions:
        if s.strategy not in seen:
            seen.add(s.strategy)
            unique.append(s)
    unique.sort(key=lambda x: x.confidence, reverse=True)
    return unique


def generate_fixes(error_msg: str, max_fixes: int = 5) -> list[dict]:
    """
    Main entry point: classify error and return structured fixes.

    Returns list of dicts suitable for SelfCorrection consumption.
    """
    suggestions = classify_error(error_msg)[:max_fixes]
    return [
        {
            "strategy": s.strategy,
            "action": s.action,
            "command": s.command,
            "file_to_edit": s.file_to_edit,
            "confidence": s.confidence,
            "reason": s.reason,
        }
        for s in suggestions
    ]