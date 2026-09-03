"""
Agent Exceptions

Hierarchical exception system for precise error handling.
"""

from typing import Optional, Any, Dict


class RannAgentError(Exception):
    """Base exception for all RANN Agent errors"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        return {"error": self.__class__.__name__, "message": self.message, "details": self.details}


class ConfigurationError(RannAgentError):
    """Configuration validation or loading error"""
    pass


class LLMError(RannAgentError):
    """Base LLM provider error"""
    pass


class LLMTimeoutError(LLMError):
    """LLM request timed out"""
    pass


class LLMRateLimitError(LLMError):
    """Rate limit exceeded"""
    pass


class LLMAuthError(LLMError):
    """Authentication failed"""
    pass


class LLMContextOverflowError(LLMError):
    """Context window exceeded"""
    pass


class ModelRoutingError(RannAgentError):
    """Model routing decision failed"""
    pass


class ToolError(RannAgentError):
    """Base tool execution error"""
    pass


class ToolNotFoundError(ToolError):
    """Tool does not exist in registry"""
    pass


class ToolNotEnabledError(ToolError):
    """Tool exists but is disabled"""
    pass


class ToolExecutionError(ToolError):
    """Tool execution failed"""
    pass


class ToolTimeoutError(ToolError):
    """Tool execution timed out"""
    pass


class ToolPolicyDeniedError(ToolError):
    """Tool execution denied by policy"""
    def __init__(self, message: str, tool: str, policy: str, **kwargs):
        self.tool = tool
        self.policy = policy
        super().__init__(message, {"tool": tool, "policy": policy, **kwargs})


class ToolValidationError(ToolError):
    """Tool parameter validation failed"""
    pass


class SecurityError(RannAgentError):
    """Security policy violation"""
    pass


class CommandInjectionError(SecurityError):
    """Command injection detected"""
    pass


class PathTraversalError(SecurityError):
    """Path traversal attempt detected"""
    pass


class SecretLeakError(SecurityError):
    """Secret or credential exposure detected"""
    pass


class BudgetExceededError(RannAgentError):
    """Budget limit exceeded"""
    pass


class TokenBudgetExceededError(BudgetExceededError):
    """Token budget exceeded"""
    pass


class TimeBudgetExceededError(BudgetExceededError):
    """Time budget exceeded"""
    pass


class ToolBudgetExceededError(BudgetExceededError):
    """Tool call budget exceeded"""
    pass


class CostBudgetExceededError(BudgetExceededError):
    """Financial budget exceeded"""
    pass


class StateMachineError(RannAgentError):
    """State machine violation"""
    pass


class VerificationError(RannAgentError):
    """Task verification failed"""
    pass


class RollbackError(RannAgentError):
    """Rollback operation failed"""
    pass


class MemoryError(RannAgentError):
    """Memory operation error"""
    pass


class OrchestrationError(RannAgentError):
    """Multi-agent orchestration error"""
    pass


class TaskGraphError(RannAgentError):
    """Task graph error"""
    pass


class PlanningError(RannAgentError):
    """Planning/strategy error"""
    pass


class StrategySelectionError(PlanningError):
    """Strategy selection failed"""
    pass


class RecoveryError(RannAgentError):
    """Recovery operation failed"""
    pass


class CheckpointError(RannAgentError):
    """Checkpoint operation failed"""
    pass


class SessionError(RannAgentError):
    """Session management error"""
    pass


class SkillError(RannAgentError):
    """Skill system error"""
    pass


class PluginError(RannAgentError):
    """Plugin system error"""
    pass