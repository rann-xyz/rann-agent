"""
Input validation for RANN Agent security.

Provides validators for paths, commands, and general input to prevent
injection attacks and path traversal vulnerabilities.
"""

from __future__ import annotations

import os
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import structlog

from rann_agent.core.exceptions import (
    CommandInjectionError,
    PathTraversalError,
    SecurityError,
    ToolValidationError,
)

logger = structlog.get_logger()


class PathValidator:
    """
    Validate file paths to prevent path traversal attacks.

    Ensures that resolved paths remain within an allowed base directory.

    Example:
        validator = PathValidator()
        if validator.validate_path(user_path, base_dir="/safe/dir"):
            # Safe to access
        else:
            # Reject - would escape base_dir
    """

    # Patterns that indicate path traversal attempts
    TRAVERSAL_PATTERNS = [
        re.compile(r"\.\./"),  # ../
        re.compile(r"\.\.$"),  # .. at end
        re.compile(r"^/etc/passwd"),  # Absolute path to sensitive file
        re.compile(r"^/etc/shadow"),
        re.compile(r"\.\./", re.IGNORECASE),  # Case-insensitive ../
    ]

    # Sensitive system paths that should never be accessible
    PROTECTED_PATHS = {
        "/",
        "/etc",
        "/root",
        "/home",
        "/var",
        "/usr",
        "/bin",
        "/sbin",
        "/lib",
        "/sys",
        "/proc",
        "/dev",
        "/boot",
        "/opt",
        "/srv",
        "/mnt",
        "/media",
        "/snap",
        "~",
    }

    def __init__(self, allow_absolute: bool = False):
        """
        Initialize the path validator.

        Args:
            allow_absolute: If True, allow absolute paths that point within base_dir.
                           If False, reject all absolute paths.
        """
        self.allow_absolute = allow_absolute

    def validate_path(
        self,
        path: str,
        base_dir: Optional[str] = None,
        follow_symlinks: bool = False,
    ) -> bool:
        """
        Validate that a path is safe to access.

        Args:
            path: The path to validate (can be relative or absolute)
            base_dir: The base directory to restrict access to.
                     If None, no base directory restriction is applied.
            follow_symlinks: If True, resolve and validate symlinks.
                            If False, only check the literal path.

        Returns:
            True if the path is safe to access

        Raises:
            PathTraversalError: If the path would escape the base directory
            SecurityError: If the path is to a protected system path
        """
        if not path:
            logger.warning("empty_path_rejected")
            return False

        # Normalize the path
        original_path = path
        path = path.strip()

        # Check for traversal patterns
        for pattern in self.TRAVERSAL_PATTERNS:
            if pattern.search(path):
                logger.warning(
                    "path_traversal_pattern_detected",
                    path=original_path,
                    pattern=pattern.pattern,
                )
                raise PathTraversalError(
                    f"Path traversal pattern detected: {original_path}",
                    details={"path": original_path, "pattern": pattern.pattern},
                )

        # Check if path is a protected system path
        normalized_for_check = os.path.normpath(os.path.abspath(path)) if os.path.isabs(path) else path
        for protected in self.PROTECTED_PATHS:
            if normalized_for_check == protected or normalized_for_check.startswith(protected + os.sep):
                logger.warning("protected_path_access_attempt", path=original_path, protected=protected)
                raise SecurityError(
                    f"Access to protected path not allowed: {original_path}",
                    details={"path": original_path, "protected": protected},
                )

        # If base_dir is specified, enforce it
        if base_dir:
            base_dir = os.path.abspath(os.path.expanduser(base_dir))

            try:
                if follow_symlinks:
                    # Resolve the full path, following symlinks
                    resolved_path = os.path.abspath(os.path.normpath(path))
                    if not os.path.isabs(resolved_path):
                        resolved_path = os.path.abspath(os.path.join(base_dir, resolved_path))
                else:
                    # Just join and normalize without following symlinks
                    if os.path.isabs(path):
                        resolved_path = os.path.abspath(path)
                    else:
                        resolved_path = os.path.abspath(os.path.join(base_dir, path))
            except (ValueError, OSError) as e:
                logger.error("path_resolution_failed", path=original_path, error=str(e))
                return False

            # Check that resolved path is within base_dir
            if not resolved_path.startswith(base_dir + os.sep) and resolved_path != base_dir:
                logger.warning(
                    "path_escapes_base_directory",
                    path=original_path,
                    resolved=resolved_path,
                    base_dir=base_dir,
                )
                raise PathTraversalError(
                    f"Path escapes base directory: {original_path}",
                    details={
                        "path": original_path,
                        "resolved": resolved_path,
                        "base_dir": base_dir,
                    },
                )

            return True

        # No base_dir restriction - just check patterns
        return True

    def validate_paths(
        self,
        paths: List[str],
        base_dir: Optional[str] = None,
    ) -> Tuple[List[str], List[str]]:
        """
        Validate multiple paths, returning valid and invalid separately.

        Args:
            paths: List of paths to validate
            base_dir: Base directory to restrict access to

        Returns:
            Tuple of (valid_paths, invalid_paths)
        """
        valid = []
        invalid = []

        for path in paths:
            try:
                if self.validate_path(path, base_dir):
                    valid.append(path)
                else:
                    invalid.append(path)
            except (PathTraversalError, SecurityError):
                invalid.append(path)

        return valid, invalid


class CommandValidator:
    """
    Validate shell commands to prevent command injection attacks.

    Blocks dangerous shell patterns including:
    - Command separators: ; | & $() `` <>
    - Environment variable expansion: $VAR ${VAR}
    - Globs and wildcards: * ? [ ]
    - Path redirects: > < >> <<
    - Background execution: &
    """

    # Regex for dangerous shell metacharacters
    DANGEROUS_CHARS = re.compile(
        r"[;"
        r"|"  # Pipe
        r"&"  # Background/AND
        r"\$[\(\{]"  # Command substitution
        r"`"  # Backtick substitution
        r"<"  # Input redirect
        r">>"  # Output append redirect
        r">"  # Output redirect
        r"<<"  # Here-doc
        r"\*"  # Glob
        r"\?"  # Glob
        r"\["  # Glob
        r"\]"  # Glob
        r"!"  # History expansion
        r"%"  # Job control
        r"\\"  # Escape
        r"\n"  # Newline in command
        r"]"
    )

    # Whitelist of allowed characters for simple alphanumeric commands
    SAFE_PATTERN = re.compile(r"^[a-zA-Z0-9_\-./]+$")

    # Known dangerous commands
    DANGEROUS_COMMANDS = {
        "rm -rf",
        "rm -rf /",
        "mkfs",
        "dd",
        ":(){:|:&};:",  # Fork bomb
        "chmod -R 777",
        "chown -R",
        "wget",
        "curl",
        "nc",
        "netcat",
        "ncat",
        "bash -i",
        "python -c",
        "perl -e",
        "ruby -e",
        "php -r",
        "exec",
        "eval",
    }

    def __init__(self, allow_shell: bool = False):
        """
        Initialize the command validator.

        Args:
            allow_shell: If True, allow shell features (dangerous!).
                        If False (default), reject any shell metacharacters.
        """
        self.allow_shell = allow_shell

    def validate_command(self, cmd: str) -> Tuple[bool, str]:
        """
        Validate a shell command for safety.

        Args:
            cmd: The command string to validate

        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """
        if not cmd:
            return False, "Empty command"

        cmd = cmd.strip()

        if not cmd:
            return False, "Empty command after whitespace strip"

        # Check length
        if len(cmd) > 10000:
            return False, f"Command too long ({len(cmd)} chars, max 10000)"

        # Check for obviously dangerous commands
        cmd_lower = cmd.lower()
        for dangerous in self.DANGEROUS_COMMANDS:
            if cmd_lower.startswith(dangerous) or cmd_lower == dangerous:
                return False, f"Dangerous command blocked: {dangerous}"

        # If shell is allowed, do less restrictive validation
        if self.allow_shell:
            return self._validate_command_shell_allowed(cmd)

        # Strict validation - no shell metacharacters
        return self._validate_command_strict(cmd)

    def _validate_command_strict(self, cmd: str) -> Tuple[bool, str]:
        """Strict validation - reject any shell special characters."""
        if not self.SAFE_PATTERN.match(cmd):
            # Find which dangerous characters are present
            dangerous_found = set()
            for char in cmd:
                if not char.isalnum() and char not in "_-./":
                    dangerous_found.add(char)

            if dangerous_found:
                return False, f"Command contains unsafe characters: {''.join(sorted(dangerous_found))}"

        return True, ""

    def _validate_command_shell_allowed(self, cmd: str) -> Tuple[bool, str]:
        """Validation when shell features are permitted (less strict)."""
        # Check for dangerous patterns even with shell allowed
        if self.DANGEROUS_CHARS.search(cmd):
            return False, "Command contains potentially dangerous shell metacharacters"

        return True, ""

    def validate_args(self, args: List[str]) -> Tuple[bool, str]:
        """
        Validate a list of command arguments.

        Each argument is checked individually for safety.

        Args:
            args: List of command arguments

        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """
        if not args:
            return False, "No arguments provided"

        for i, arg in enumerate(args):
            # Arguments should generally be safe filenames/values
            # Allow more than SAFE_PATTERN since args can contain many chars
            if len(arg) > 10000:
                return False, f"Argument {i} too long ({len(arg)} chars)"

            # Check for newlines (command injection via argument)
            if "\n" in arg or "\r" in arg:
                return False, f"Argument {i} contains newline character"

        return True, ""

    def quote_argument(self, arg: str) -> str:
        """
        Safely quote an argument for shell execution.

        Uses shlex.quote for proper shell escaping.

        Args:
            arg: The argument to quote

        Returns:
            Safely quoted argument string
        """
        return shlex.quote(arg)


class InputValidator:
    """
    General-purpose input validation for agent parameters.

    Validates strings, numbers, lists, and dictionaries against
    configurable rules.
    """

    # Maximum lengths for various input types
    MAX_STRING_LENGTH = 100000  # 100KB
    MAX_LIST_LENGTH = 1000
    MAX_DICT_KEYS = 100
    MAX_DEPTH = 10  # Max nesting depth

    # Patterns for potentially dangerous content
    DANGEROUS_PATTERNS = [
        (re.compile(r"<script[^>]*>", re.IGNORECASE), "script_tag"),
        (re.compile(r"javascript:", re.IGNORECASE), "javascript_protocol"),
        (re.compile(r"on\w+\s*=", re.IGNORECASE), "html_event_handler"),
        (re.compile(r"data:text/html", re.IGNORECASE), "data_url_html"),
    ]

    def __init__(
        self,
        max_string_length: Optional[int] = None,
        max_list_length: Optional[int] = None,
        max_depth: Optional[int] = None,
    ):
        """
        Initialize the input validator.

        Args:
            max_string_length: Maximum allowed string length
            max_list_length: Maximum allowed list length
            max_depth: Maximum nesting depth
        """
        self.max_string_length = max_string_length or self.MAX_STRING_LENGTH
        self.max_list_length = max_list_length or self.MAX_LIST_LENGTH
        self.max_depth = max_depth or self.MAX_DEPTH

    def validate_string(
        self,
        value: str,
        allow_empty: bool = False,
        pattern: Optional[re.Pattern] = None,
    ) -> Tuple[bool, str]:
        """
        Validate a string input.

        Args:
            value: String to validate
            allow_empty: If True, allow empty strings
            pattern: Optional regex pattern to match against

        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """
        if not isinstance(value, str):
            return False, f"Expected string, got {type(value).__name__}"

        if not value:
            if allow_empty:
                return True, ""
            return False, "Empty string not allowed"

        if len(value) > self.max_string_length:
            return False, f"String too long ({len(value)} > {self.max_string_length})"

        if pattern and not pattern.match(value):
            return False, f"String does not match required pattern"

        # Check for dangerous HTML/JS patterns
        for dangerous_re, pattern_name in self.DANGEROUS_PATTERNS:
            if dangerous_re.search(value):
                return False, f"Potentially dangerous content detected: {pattern_name}"

        return True, ""

    def validate_number(
        self,
        value,
        min_val: Optional[float] = None,
        max_val: Optional[float] = None,
    ) -> Tuple[bool, str]:
        """
        Validate a numeric input.

        Args:
            value: Number to validate
            min_val: Minimum allowed value
            max_val: Maximum allowed value

        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """
        if not isinstance(value, (int, float)):
            return False, f"Expected number, got {type(value).__name__}"

        if min_val is not None and value < min_val:
            return False, f"Value {value} below minimum {min_val}"

        if max_val is not None and value > max_val:
            return False, f"Value {value} above maximum {max_val}"

        return True, ""

    def validate_list(
        self,
        value: list,
        max_length: Optional[int] = None,
        element_validator: Optional[callable] = None,
    ) -> Tuple[bool, str]:
        """
        Validate a list input.

        Args:
            value: List to validate
            max_length: Maximum allowed length (defaults to self.max_list_length)
            element_validator: Optional function(value) -> (is_valid, reason) for each element

        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """
        if not isinstance(value, list):
            return False, f"Expected list, got {type(value).__name__}"

        max_len = max_length or self.max_list_length
        if len(value) > max_len:
            return False, f"List too long ({len(value)} > {max_len})"

        if element_validator:
            for i, elem in enumerate(value):
                valid, reason = element_validator(elem)
                if not valid:
                    return False, f"Element {i} invalid: {reason}"

        return True, ""

    def validate_dict(
        self,
        value: dict,
        max_keys: Optional[int] = None,
        key_validator: Optional[callable] = None,
        value_validator: Optional[callable] = None,
        depth: int = 0,
    ) -> Tuple[bool, str]:
        """
        Validate a dictionary input recursively.

        Args:
            value: Dictionary to validate
            max_keys: Maximum number of keys
            key_validator: Optional function(key) -> (is_valid, reason)
            value_validator: Optional function(value) -> (is_valid, reason)
            depth: Current nesting depth (used internally)

        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """
        if not isinstance(value, dict):
            return False, f"Expected dict, got {type(value).__name__}"

        if depth > self.max_depth:
            return False, f"Maximum nesting depth exceeded ({self.max_depth})"

        max_k = max_keys or self.MAX_DICT_KEYS
        if len(value) > max_k:
            return False, f"Dictionary has too many keys ({len(value)} > {max_k})"

        for k, v in value.items():
            if key_validator:
                valid, reason = key_validator(k)
                if not valid:
                    return False, f"Key '{k}' invalid: {reason}"

            if value_validator:
                valid, reason = value_validator(v)
                if not valid:
                    return False, f"Value for key '{k}' invalid: {reason}"

            # Recursively validate nested dicts/lists
            if isinstance(v, dict):
                valid, reason = self.validate_dict(v, depth=depth + 1)
                if not valid:
                    return False, f"Nested dict for key '{k}': {reason}"
            elif isinstance(v, list):
                valid, reason = self.validate_list(v)
                if not valid:
                    return False, f"Nested list for key '{k}': {reason}"

        return True, ""

    def validate(self, value, expected_type: type) -> Tuple[bool, str]:
        """
        Validate a value against an expected type.

        Args:
            value: Value to validate
            expected_type: The expected Python type

        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """
        if expected_type == str:
            return self.validate_string(value)
        elif expected_type in (int, float):
            return self.validate_number(value)
        elif expected_type == list:
            return self.validate_list(value)
        elif expected_type == dict:
            return self.validate_dict(value)
        else:
            if not isinstance(value, expected_type):
                return False, f"Expected {expected_type.__name__}, got {type(value).__name__}"
            return True, ""