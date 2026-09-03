"""
RANN Agent Core Module

Phase 1: Explicit state machine, events, budget, verification, runtime.
"""

from rann_agent.core.config import Config
from rann_agent.core.context import Context, Message
from rann_agent.core.llm_provider import LLMProvider, BaseLLMProvider

# Phase 1: Core Runtime
from rann_agent.core.state import AgentState, AgentStateMachine, InvalidStateTransitionError
from rann_agent.core.events import (
    Event, EventType, EventStatus, EventEmitter,
    emit_run_created, emit_run_started, emit_model_requested,
    emit_tool_started, emit_tool_completed, emit_verification_passed,
    emit_run_completed, emit_error
)
from rann_agent.core.budget import Budget, BudgetTracker, BudgetEngine
from rann_agent.core.exceptions import (
    RannAgentError,
    ConfigurationError,
    LLMError, LLMTimeoutError, LLMRateLimitError, LLMAuthError, LLMContextOverflowError,
    ModelRoutingError,
    ToolError, ToolNotFoundError, ToolNotEnabledError, ToolExecutionError,
    ToolTimeoutError, ToolPolicyDeniedError, ToolValidationError,
    SecurityError, CommandInjectionError, PathTraversalError, SecretLeakError,
    BudgetExceededError, TokenBudgetExceededError, TimeBudgetExceededError,
    ToolBudgetExceededError, CostBudgetExceededError,
    StateMachineError,
    VerificationError, RollbackError,
    MemoryError, OrchestrationError, TaskGraphError,
    PlanningError, StrategySelectionError, RecoveryError,
    CheckpointError, SessionError, SkillError, PluginError
)
from rann_agent.core.lifecycle import AgentLifecycle
from rann_agent.core.verification import (
    VerificationEngine, VerificationLevel, VerificationResult,
    VerificationStatus, VerificationCheck, VerificationChecks
)
from rann_agent.core.runtime import RuntimeAgent

__all__ = [
    # Config & Context
    "Config", "Context", "Message", "LLMProvider", "BaseLLMProvider",
    # Phase 1: State & Events
    "AgentState", "AgentStateMachine", "InvalidStateTransitionError",
    "Event", "EventType", "EventStatus", "EventEmitter",
    "emit_run_created", "emit_run_started", "emit_model_requested",
    "emit_tool_started", "emit_tool_completed", "emit_verification_passed",
    "emit_run_completed", "emit_error",
    # Phase 1: Budget
    "Budget", "BudgetTracker", "BudgetEngine",
    # Phase 1: Exceptions
    "RannAgentError", "ConfigurationError",
    "LLMError", "LLMTimeoutError", "LLMRateLimitError", "LLMAuthError", "LLMContextOverflowError",
    "ModelRoutingError",
    "ToolError", "ToolNotFoundError", "ToolNotEnabledError", "ToolExecutionError",
    "ToolTimeoutError", "ToolPolicyDeniedError", "ToolValidationError",
    "SecurityError", "CommandInjectionError", "PathTraversalError", "SecretLeakError",
    "BudgetExceededError", "TokenBudgetExceededError", "TimeBudgetExceededError",
    "ToolBudgetExceededError", "CostBudgetExceededError",
    "StateMachineError",
    "VerificationError",
    "MemoryError", "OrchestrationError", "TaskGraphError",
    "PlanningError", "StrategySelectionError", "RecoveryError",
    "CheckpointError", "SessionError", "SkillError", "PluginError",
    # Phase 1: Lifecycle & Verification
    "AgentLifecycle", "VerificationEngine", "VerificationLevel",
    "VerificationResult", "VerificationStatus", "VerificationCheck", "VerificationChecks",
    # Phase 1: Runtime
    "RuntimeAgent",
]