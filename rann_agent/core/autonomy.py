"""
Autonomy levels for RANN Agent.
As required by MASTER PROMPT Section 51.
"""

from enum import IntEnum
from typing import Dict, Callable, Optional
import structlog

logger = structlog.get_logger()


class AutonomyLevel(IntEnum):
    """Autonomy levels for agent execution."""
    LEVEL_0_OBSERVE = 0  # Observe only
    LEVEL_1_READ = 1     # Read/search only
    LEVEL_2_MODIFY_TEST = 2  # Modify + test with checkpoints (DEFAULT)
    LEVEL_3_CODING = 3   # Autonomous coding inside approved workspace
    LEVEL_4_LOW_RISK_COMMIT = 4  # Low-risk commits after verification
    LEVEL_5_HIGH_AUTONOMY = 5  # High autonomy under strict governance

    @property
    def description(self) -> str:
        descriptions = {
            0: "Observe only",
            1: "Read/search only",
            2: "Modify + test with checkpoints (DEFAULT)",
            3: "Autonomous coding inside approved workspace",
            4: "Low-risk commits after verification",
            5: "High autonomy under strict governance",
        }
        return descriptions.get(self, "Unknown")


# Default level
DEFAULT_AUTONOMY = AutonomyLevel.LEVEL_2_MODIFY_TEST

# Action -> minimum required level
ACTION_REQUIREMENTS: Dict[str, AutonomyLevel] = {
    # Read actions - Level 0
    "observe": AutonomyLevel.LEVEL_0_OBSERVE,
    # Read/search - Level 1
    "read": AutonomyLevel.LEVEL_1_READ,
    "search": AutonomyLevel.LEVEL_1_READ,
    "grep": AutonomyLevel.LEVEL_1_READ,
    "list": AutonomyLevel.LEVEL_1_READ,
    # Modify with checkpoints - Level 2
    "edit": AutonomyLevel.LEVEL_2_MODIFY_TEST,
    "write": AutonomyLevel.LEVEL_2_MODIFY_TEST,
    "patch": AutonomyLevel.LEVEL_2_MODIFY_TEST,
    "test": AutonomyLevel.LEVEL_2_MODIFY_TEST,
    "run": AutonomyLevel.LEVEL_2_MODIFY_TEST,
    # Autonomous coding - Level 3
    "implement": AutonomyLevel.LEVEL_3_CODING,
    "refactor": AutonomyLevel.LEVEL_3_CODING,
    "debug": AutonomyLevel.LEVEL_3_CODING,
    # Low-risk commits - Level 4
    "commit": AutonomyLevel.LEVEL_4_LOW_RISK_COMMIT,
    "branch": AutonomyLevel.LEVEL_4_LOW_RISK_COMMIT,
    # High autonomy - Level 5
    "merge": AutonomyLevel.LEVEL_5_HIGH_AUTONOMY,
    "deploy": AutonomyLevel.LEVEL_5_HIGH_AUTONOMY,
    "delete_branch": AutonomyLevel.LEVEL_5_HIGH_AUTONOMY,
}


class AutonomyGuard:
    """Guards execution based on autonomy levels."""

    def __init__(self, current_level: AutonomyLevel = DEFAULT_AUTONOMY) -> None:
        self.current_level = current_level

    def set_level(self, level: AutonomyLevel) -> None:
        self.current_level = level
        logger.info("autonomy_level_set", level=level.name, value=int(level))

    def can_execute(self, action: str, required_level: Optional[AutonomyLevel] = None) -> bool:
        """Check if current autonomy level allows the action."""
        if required_level is None:
            required_level = ACTION_REQUIREMENTS.get(action, AutonomyLevel.LEVEL_2_MODIFY_TEST)

        allowed = int(self.current_level) >= int(required_level)
        if not allowed:
            logger.warning(
                "autonomy_blocked",
                action=action,
                current_level=int(self.current_level),
                required_level=int(required_level),
            )
        return allowed

    def require_level(self, action: str) -> None:
        """Raise if action not allowed at current level."""
        if not self.can_execute(action):
            level = ACTION_REQUIREMENTS.get(action, AutonomyLevel.LEVEL_2_MODIFY_TEST)
            raise PermissionError(
                f"Action '{action}' requires autonomy level {level.name} "
                f"(current: {self.current_level.name})"
            )

    def escalate(self, action: str, reason: str) -> bool:
        """Request escalation for a higher-privilege action."""
        logger.info("autonomy_escalation_requested", action=action, reason=reason)
        # In a full implementation, this would request human approval
        return False