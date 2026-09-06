"""
RANN Agent Core Module

Phase 1: Explicit state machine, events, budget, verification, runtime.
"""

from rann_agent.core.budget import Budget, BudgetEngine, BudgetTracker
from rann_agent.core.config import Config
from rann_agent.core.context import Context, Message
from rann_agent.core.events import (
    Event,
    EventEmitter,
    EventStatus,
    EventType,
    emit_error,
    emit_model_requested,
    emit_run_completed,
    emit_run_created,
    emit_run_started,
    emit_tool_completed,
    emit_tool_started,
    emit_verification_passed,
)
from rann_agent.core.exceptions import (
    BudgetExceededError,
    CheckpointError,
    CommandInjectionError,
    ConfigurationError,
    CostBudgetExceededError,
    LLMAuthError,
    LLMContextOverflowError,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
    MemoryError,
    ModelRoutingError,
    OrchestrationError,
    PathTraversalError,
    PlanningError,
    PluginError,
    RannAgentError,
    RecoveryError,
    RollbackError,
    SecretLeakError,
    SecurityError,
    SessionError,
    SkillError,
    StateMachineError,
    StrategySelectionError,
    TaskGraphError,
    TimeBudgetExceededError,
    TokenBudgetExceededError,
    ToolBudgetExceededError,
    ToolError,
    ToolExecutionError,
    ToolNotEnabledError,
    ToolNotFoundError,
    ToolPolicyDeniedError,
    ToolTimeoutError,
    ToolValidationError,
    VerificationError,
)
from rann_agent.core.lifecycle import AgentLifecycle
from rann_agent.core.llm_provider import BaseLLMProvider, LLMProvider
from rann_agent.core.runtime import RuntimeAgent

# Phase 1: Core Runtime
from rann_agent.core.state import (
    AgentState,
    AgentStateMachine,
    InvalidStateTransitionError,
)
from rann_agent.core.verification import (
    VerificationCheck,
    VerificationChecks,
    VerificationEngine,
    VerificationLevel,
    VerificationResult,
    VerificationStatus,
)

__all__ = [
    # Phase 1: Lifecycle & Verification
    "AgentLifecycle",
    # Phase 1: State & Events
    "AgentState",
    "AgentStateMachine",
    "BaseLLMProvider",
    # Phase 1: Budget
    "Budget",
    "BudgetEngine",
    "BudgetExceededError",
    "BudgetTracker",
    "CheckpointError",
    "CommandInjectionError",
    # Config & Context
    "Config",
    "ConfigurationError",
    "Context",
    "CostBudgetExceededError",
    "Event",
    "EventEmitter",
    "EventStatus",
    "EventType",
    "InvalidStateTransitionError",
    "LLMAuthError",
    "LLMContextOverflowError",
    "LLMError",
    "LLMProvider",
    "LLMRateLimitError",
    "LLMTimeoutError",
    "MemoryError",
    "Message",
    "ModelRoutingError",
    "OrchestrationError",
    "PathTraversalError",
    "PlanningError",
    "PluginError",
    # Phase 1: Exceptions
    "RannAgentError",
    "RecoveryError",
    # Phase 1: Runtime
    "RuntimeAgent",
    "SecretLeakError",
    "SecurityError",
    "SessionError",
    "SkillError",
    "StateMachineError",
    "StrategySelectionError",
    "TaskGraphError",
    "TimeBudgetExceededError",
    "TokenBudgetExceededError",
    "ToolBudgetExceededError",
    "ToolError",
    "ToolExecutionError",
    "ToolNotEnabledError",
    "ToolNotFoundError",
    "ToolPolicyDeniedError",
    "ToolTimeoutError",
    "ToolValidationError",
    "VerificationCheck",
    "VerificationChecks",
    "VerificationEngine",
    "VerificationError",
    "VerificationLevel",
    "VerificationResult",
    "VerificationStatus",
    "emit_error",
    "emit_model_requested",
    "emit_run_completed",
    "emit_run_created",
    "emit_run_started",
    "emit_tool_completed",
    "emit_tool_started",
    "emit_verification_passed",
]
