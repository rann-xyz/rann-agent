"""
Agent Exceptions

Hierarchical exception system for precise error handling.
"""

from typing import Any


class RannAgentError(Exception):
    """Base exception for all RANN Agent errors"""

    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


class ConfigurationError(RannAgentError):
    """Configuration validation or loading error"""


class LLMError(RannAgentError):
    """Base LLM provider error"""


class LLMTimeoutError(LLMError):
    """LLM request timed out"""


class LLMRateLimitError(LLMError):
    """Rate limit exceeded"""


class LLMAuthError(LLMError):
    """Authentication failed"""


class LLMContextOverflowError(LLMError):
    """Context window exceeded"""


class ModelRoutingError(RannAgentError):
    """Model routing decision failed"""


class ToolError(RannAgentError):
    """Base tool execution error"""


class ToolNotFoundError(ToolError):
    """Tool does not exist in registry"""


class ToolNotEnabledError(ToolError):
    """Tool exists but is disabled"""


class ToolExecutionError(ToolError):
    """Tool execution failed"""


class ToolTimeoutError(ToolError):
    """Tool execution timed out"""


class ToolPolicyDeniedError(ToolError):
    """Tool execution denied by policy"""

    def __init__(self, message: str, tool: str, policy: str, **kwargs):
        self.tool = tool
        self.policy = policy
        super().__init__(message, {"tool": tool, "policy": policy, **kwargs})


class ToolValidationError(ToolError):
    """Tool parameter validation failed"""


class SecurityError(RannAgentError):
    """Security policy violation"""


class CommandInjectionError(SecurityError):
    """Command injection detected"""


class PathTraversalError(SecurityError):
    """Path traversal attempt detected"""


class SecretLeakError(SecurityError):
    """Secret or credential exposure detected"""


class BudgetExceededError(RannAgentError):
    """Budget limit exceeded"""


class TokenBudgetExceededError(BudgetExceededError):
    """Token budget exceeded"""


class TimeBudgetExceededError(BudgetExceededError):
    """Time budget exceeded"""


class ToolBudgetExceededError(BudgetExceededError):
    """Tool call budget exceeded"""


class CostBudgetExceededError(BudgetExceededError):
    """Financial budget exceeded"""


class StateMachineError(RannAgentError):
    """State machine violation"""


class VerificationError(RannAgentError):
    """Task verification failed"""


class RollbackError(RannAgentError):
    """Rollback operation failed"""


class MemoryError(RannAgentError):
    """Memory operation error"""


class OrchestrationError(RannAgentError):
    """Multi-agent orchestration error"""


class TaskGraphError(RannAgentError):
    """Task graph error"""


class PlanningError(RannAgentError):
    """Planning/strategy error"""


class StrategySelectionError(PlanningError):
    """Strategy selection failed"""


class RecoveryError(RannAgentError):
    """Recovery operation failed"""


class CheckpointError(RannAgentError):
    """Checkpoint operation failed"""


class SessionError(RannAgentError):
    """Session management error"""


class SkillError(RannAgentError):
    """Skill system error"""


class PluginError(RannAgentError):
    """Plugin system error"""
