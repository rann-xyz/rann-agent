"""
Secret detection and scrubbing for RANN Agent.

Detects and redacts API keys, passwords, tokens, and certificates
from text output to prevent accidental secret exposure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Pattern, Tuple

import structlog

from rann_agent.core.exceptions import SecretLeakError

logger = structlog.get_logger()


class SecretType(str, Enum):
    """Types of secrets that can be detected."""

    API_KEY = "api_key"
    PASSWORD = "password"
    TOKEN = "token"
    CERTIFICATE = "certificate"
    PRIVATE_KEY = "private_key"
    GENERIC_SECRET = "generic_secret"


@dataclass
class SecretMatch:
    """A detected secret in text."""

    secret_type: SecretType
    value: str  # The actual secret value (for logging/debugging only)
    start: int  # Start index in original text
    end: int  # End index in original text
    pattern_name: str  # Which pattern matched


class SecretDetector:
    """
    Detect secrets in text using regex patterns.

    Supports detection of:
    - API keys (AWS, GitHub, OpenAI, Anthropic, etc.)
    - Passwords in URLs or config files
    - Authentication tokens (Bearer, JWT, etc.)
    - Certificates (PEM format)
    - Private keys (RSA, EC, etc.)

    Example:
        detector = SecretDetector()
        matches = detector.detect("My API key is sk-abc123xyz")
        # Returns [SecretMatch(secret_type=SecretType.API_KEY, ...)]
    """

    # Compiled regex patterns for secret detection
    PATTERNS: List[Tuple[str, SecretType, Pattern]] = [
        # AWS Access Key ID
        (
            "aws_access_key",
            SecretType.API_KEY,
            re.compile(r"\b(AKIA[0-9A-Z]{16})\b"),
        ),
        # AWS Secret Access Key
        (
            "aws_secret_key",
            SecretType.API_KEY,
            re.compile(r"\b[A-Za-z0-9/+=]{40}\b(?=\s*$|\s*[^\x00-\x7F])"),
        ),
        # GitHub Token
        (
            "github_token",
            SecretType.TOKEN,
            re.compile(r"\b(gho_[0-9a-zA-Z]{36}|github_pat_[0-9a-zA-Z_]{22,255})\b"),
        ),
        # GitHub OAuth
        (
            "github_oauth",
            SecretType.TOKEN,
            re.compile(r"\b(gil_[0-9a-f]{40}|gla_[0-9a-f]{64})\b"),
        ),
        # OpenAI API Key
        (
            "openai_key",
            SecretType.API_KEY,
            re.compile(r"\b(sk-[0-9a-zA-Z]{48})\b"),
        ),
        # Anthropic API Key
        (
            "anthropic_key",
            SecretType.API_KEY,
            re.compile(r"\b(sk-ant-[0-9a-zA-Z-]{48,})\b"),
        ),
        # Google API Key
        (
            "google_api_key",
            SecretType.API_KEY,
            re.compile(r"\b(AIza[0-9a-zA-Z_-]{35})\b"),
        ),
        # Stripe API Key
        (
            "stripe_key",
            SecretType.API_KEY,
            re.compile(r"\b(sk_live_[0-9a-zA-Z]{24,}|rk_live_[0-9a-zA-Z]{24,})\b"),
        ),
        # Slack Token
        (
            "slack_token",
            SecretType.TOKEN,
            re.compile(r"\b(xox[baprs]-[0-9a-zA-Z-]{10,})\b"),
        ),
        # Generic Bearer Token
        (
            "bearer_token",
            SecretType.TOKEN,
            re.compile(r"\bBearer\s+[0-9a-zA-Z_-]{20,}\b"),
        ),
        # JWT Token
        (
            "jwt_token",
            SecretType.TOKEN,
            re.compile(r"\b(eyJ[0-9a-zA-Z_-]+\.eyJ[0-9a-zA-Z_-]+\.[0-9a-zA-Z_-]+)\b"),
        ),
        # Password in URL
        (
            "url_password",
            SecretType.PASSWORD,
            re.compile(r"://[^:]+:([^@]+)@"),
        ),
        # Generic password pattern (less aggressive)
        (
            "generic_password",
            SecretType.PASSWORD,
            re.compile(r'(?:password|pwd|passwd|secret)\s*[=:]\s*["\']?([^"\'\s]{8,})["\']?', re.IGNORECASE),
        ),
        # Generic API key pattern (very generic - last resort)
        (
            "generic_api_key",
            SecretType.API_KEY,
            re.compile(r"\b[a-zA-Z0-9_-]{32,64}\b"),
        ),
        # PEM Certificate
        (
            "pem_certificate",
            SecretType.CERTIFICATE,
            re.compile(
                r"-----BEGIN\s+CERTIFICATE-----\s*[0-9a-zA-Z+/=\s]+-----END\s+CERTIFICATE-----",
                re.MULTILINE,
            ),
        ),
        # PEM Private Key
        (
            "pem_private_key",
            SecretType.PRIVATE_KEY,
            re.compile(
                r"-----BEGIN\s+(?:RSA\s+|EC\s+|DSA\s+|OPENSSH\s+)?PRIVATE\s+KEY-----\s*[0-9a-zA-Z+/=\s]+-----END\s+(?:RSA\s+|EC\s+|DSA\s+|OPENSSH\s+)?PRIVATE\s+KEY-----",
                re.MULTILINE,
            ),
        ),
        # AWS MWS Key
        (
            "aws_mws_key",
            SecretType.API_KEY,
            re.compile(r"\b(amzn\.mws\.[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b"),
        ),
        # Twilio API Key
        (
            "twilio_key",
            SecretType.API_KEY,
            re.compile(r"\b(SK[0-9a-f]{32})\b"),
        ),
        # Mailgun API Key
        (
            "mailgun_key",
            SecretType.API_KEY,
            re.compile(r"\b(key-[0-9a-f]{32})\b"),
        ),
        # SendGrid API Key
        (
            "sendgrid_key",
            SecretType.API_KEY,
            re.compile(r"\b(SG\.[0-9a-zA-Z_-]{22}\.[0-9a-zA-Z_-]{43})\b"),
        ),
    ]

    def __init__(self, strict: bool = False):
        """
        Initialize the secret detector.

        Args:
            strict: If True, use higher-confidence patterns only.
                    If False, include more patterns with potential false positives.
        """
        self.strict = strict
        if strict:
            # In strict mode, skip the generic patterns
            self._patterns = [p for p in self.PATTERNS if "generic" not in p[0]]
        else:
            self._patterns = self.PATTERNS

    def detect(self, text: str) -> List[SecretMatch]:
        """
        Detect all secrets in the given text.

        Args:
            text: Text to scan for secrets

        Returns:
            List of SecretMatch objects describing found secrets
        """
        if not text:
            return []

        matches: List[SecretMatch] = []
        seen_positions: set = set()  # Avoid duplicate matches at same position

        for pattern_name, secret_type, pattern in self._patterns:
            for match in pattern.finditer(text):
                # Skip if we've already matched at this position
                if match.start() in seen_positions:
                    continue

                secret_value = match.group(0)
                if secret_type == SecretType.PASSWORD and pattern_name == "url_password":
                    # For URL passwords, group 1 is the actual password
                    secret_value = match.group(1)

                matches.append(
                    SecretMatch(
                        secret_type=secret_type,
                        value=secret_value,
                        start=match.start(),
                        end=match.end(),
                        pattern_name=pattern_name,
                    )
                )
                seen_positions.add(match.start())

        # Sort by position
        matches.sort(key=lambda m: m.start)

        if matches:
            logger.debug(
                "secrets_detected",
                count=len(matches),
                types=[m.secret_type.value for m in matches],
            )

        return matches

    def contains_secrets(self, text: str) -> bool:
        """Check if text contains any secrets (faster than detect for boolean check)."""
        return bool(self.detect(text))

    def get_secret_types(self, text: str) -> List[SecretType]:
        """Get list of secret types found in text."""
        matches = self.detect(text)
        return list({m.secret_type for m in matches})


class SecretScrubber:
    """
    Scrub secrets from text by replacing them with redaction markers.

    Example:
        scrubber = SecretScrubber()
        clean = scrubber.scrub("API key is sk-abc123xyz")
        # Returns "API key is [REDACTED: api_key: sk-***]"
    """

    REDACTED_PREFIX = "[REDACTED"
    REDACTED_SUFFIX = "]"

    def __init__(
        self,
        detector: Optional[SecretDetector] = None,
        include_type: bool = True,
        show_prefix: bool = False,
    ):
        """
        Initialize the scrubber.

        Args:
            detector: SecretDetector instance (creates default if None)
            include_type: Include secret type in the redaction marker
            show_prefix: Show first few characters of the secret (e.g., "sk-***")
        """
        self.detector = detector or SecretDetector()
        self.include_type = include_type
        self.show_prefix = show_prefix

    def scrub(self, text: str) -> str:
        """
        Replace all detected secrets in text with redaction markers.

        Args:
            text: Text containing secrets

        Returns:
            Text with secrets replaced by [REDACTED] markers
        """
        if not text:
            return text

        matches = self.detector.detect(text)
        if not matches:
            return text

        # Process matches in reverse order to preserve positions
        result = text
        for match in reversed(matches):
            redaction = self._format_redaction(match)
            result = result[: match.start] + redaction + result[match.end:]

        logger.debug(
            "secrets_scrubbed",
            count=len(matches),
            original_length=len(text),
            scrubbed_length=len(result),
        )

        return result

    def _format_redaction(self, match: SecretMatch) -> str:
        """Format the redaction marker for a secret match."""
        if self.show_prefix and match.value:
            # Show first 4 chars for context
            prefix_len = min(4, len(match.value))
            prefix = match.value[:prefix_len]
            prefix_display = f": {prefix}***"
        else:
            prefix_display = ""

        if self.include_type:
            return f"{self.REDACTED_PREFIX}: {match.secret_type.value}{prefix_display}{self.REDACTED_SUFFIX}"
        else:
            return f"{self.REDACTED_PREFIX}{prefix_display}{self.REDACTED_SUFFIX}"

    def check_and_raise(self, text: str, context: str = "") -> None:
        """
        Check text for secrets and raise SecretLeakError if any are found.

        Args:
            text: Text to check
            context: Additional context for the error message

        Raises:
            SecretLeakError: If any secrets are detected
        """
        matches = self.detector.detect(text)
        if matches:
            secret_types = list({m.secret_type for m in matches})
            raise SecretLeakError(
                f"Secret detected in {context}" if context else "Secret detected in output",
                details={
                    "secret_types": [t.value for t in secret_types],
                    "count": len(matches),
                },
            )