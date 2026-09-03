"""
Command risk classification for RANN Agent.
As required by MASTER PROMPT Section 7.
"""

import re
from enum import Enum
from typing import Tuple, List, Optional, Dict, Any
import structlog

logger = structlog.get_logger()


class CommandRiskLevel(Enum):
    READ_ONLY = "read_only"
    LOW_RISK = "low_risk"
    MODIFYING = "modifying"
    DESTRUCTIVE = "destructive"
    PRIVILEGED = "privileged"
    NETWORK = "network"
    PRODUCTION = "production"


# Patterns for dangerous commands
DESTRUCTIVE_PATTERNS = [
    (r"rm\s+-rf\s+/", "Root recursion delete"),
    (r"rm\s+-rf\s+\*", "Bulk file delete"),
    (r"chmod\s+-R\s+000", "Remove all permissions"),
    (r"chmod\s+-R\s+777", "World-writable permissions"),
    (r"dd\s+if=", "Direct disk write"),
    (r">\s*/dev/sd", "Write to block device"),
    (r"mkfs\s+", "Format filesystem"),
    (r"fork\s+bomb", "Fork bomb"),
]

PRIVILEGED_PATTERNS = [
    (r"\bsudo\s+", "Superuser execution"),
    (r"\bsu\s+", "Switch user"),
    (r"systemctl\s+(stop|disable|kill)", "Systemd control"),
    (r"service\s+(stop|restart)", "Service management"),
    (r"init\s+0", "System halt"),
    (r"reboot", "System reboot"),
    (r"shutdown", "System shutdown"),
]

PRODUCTION_PATTERNS = [
    (r"kubectl\s+(apply|delete)\s+-f", "Kubernetes deployment"),
    (r"kubectl\s+delete\s+", "Kubernetes resource deletion"),
    (r"docker\s+push", "Docker image push"),
    (r"docker\s+rmi\s+-f", "Docker image deletion"),
    (r"aws\s+ec2\s+terminate-instance", "AWS instance termination"),
    (r"terraform\s+destroy", "Terraform destruction"),
    (r"gcloud\s+compute\s+instances\s+delete", "GCP instance deletion"),
    (r"az\s+vm\s+delete", "Azure VM deletion"),
]

NETWORK_PATTERNS = [
    (r"curl\s+.*--data", "HTTP POST with curl"),
    (r"wget\s+.*-O\s+", "Download to arbitrary path"),
    (r"nc\s+-[elLp]", "Netcat listener/shell"),
    (r"ssh\s+.*-o\s+StrictHostKeyChecking=no", "SSH bypass host check"),
    (r"telnet\s+", "Telnet connection"),
    (r"ftp\s+", "FTP connection"),
]

MODIFYING_PATTERNS = [
    (r"(echo|printf)\s+.*>\s*", "File write with redirect"),
    (r"(echo|printf)\s+.*>>\s*", "File append with redirect"),
    (r"tee\s+", "Tee to file"),
    (r"sed\s+-i", "Sed in-place edit"),
    (r"patch\s+", "Apply patch"),
]


class CommandPolicy:
    """Classifies and enforces command risk policies."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}

    def classify(self, command: str) -> Tuple[CommandRiskLevel, str]:
        """Classify a command's risk level and return reason."""
        cmd_lower = command.lower()

        # Check destructive patterns first (highest risk)
        for pattern, reason in DESTRUCTIVE_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return CommandRiskLevel.DESTRUCTIVE, reason

        # Check privileged patterns
        for pattern, reason in PRIVILEGED_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return CommandRiskLevel.PRIVILEGED, reason

        # Check production patterns
        for pattern, reason in PRODUCTION_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return CommandRiskLevel.PRODUCTION, reason

        # Check network patterns
        for pattern, reason in NETWORK_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return CommandRiskLevel.NETWORK, reason

        # Check modifying patterns
        for pattern, reason in MODIFYING_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return CommandRiskLevel.MODIFYING, reason

        # Read-only commands
        read_only_commands = {"ls", "cat", "head", "tail", "grep", "find", "stat", "pwd", "whoami", "id", "date"}
        first_word = command.strip().split()[0] if command.strip() else ""
        if first_word in read_only_commands:
            return CommandRiskLevel.READ_ONLY, "Read-only command"

        return CommandRiskLevel.LOW_RISK, "Standard command"

    def check(
        self, command: str, max_risk: CommandRiskLevel = CommandRiskLevel.MODIFYING
    ) -> Tuple[bool, str]:
        """
        Check if a command is allowed at the given risk threshold.

        Returns (allowed, reason).
        """
        risk_level, reason = self.classify(command)

        risk_order = {
            CommandRiskLevel.READ_ONLY: 0,
            CommandRiskLevel.LOW_RISK: 1,
            CommandRiskLevel.MODIFYING: 2,
            CommandRiskLevel.NETWORK: 3,
            CommandRiskLevel.PRIVILEGED: 4,
            CommandRiskLevel.DESTRUCTIVE: 5,
            CommandRiskLevel.PRODUCTION: 6,
        }

        allowed = risk_order[risk_level] <= risk_order[max_risk]

        if not allowed:
            logger.warning(
                "command_blocked",
                command=command[:100],
                risk=risk_level.value,
                reason=reason,
                max_risk=max_risk.value,
            )
            return False, f"Command blocked: {reason} (risk: {risk_level.value})"

        return True, reason

    def requires_approval(self, command: str) -> bool:
        """Check if a command requires approval before execution."""
        risk, _ = self.classify(command)
        return risk in {
            CommandRiskLevel.DESTRUCTIVE,
            CommandRiskLevel.PRIVILEGED,
            CommandRiskLevel.PRODUCTION,
        }