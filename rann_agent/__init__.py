"""
RANN Agent - Next-generation autonomous AI engineering platform.

THE MODEL GENERATES DECISIONS. RANN CONTROLS EXECUTION.
"""

__version__ = "1.0.0"
__author__ = "RANN Team"
__license__ = "MIT"

# Core
# Cognition
from rann_agent.cognition.evaluator import EvaluationResult, Evaluator
from rann_agent.cognition.strategy import StrategySelector, StrategyType
from rann_agent.core.agent import Agent
from rann_agent.core.approval import ApprovalRequest, ApprovalSystem, ApprovalType
from rann_agent.core.autonomy import AutonomyGuard
from rann_agent.core.budget import Budget, BudgetEngine
from rann_agent.core.config import Config
from rann_agent.core.event_bus import Event, EventBus, EventType
from rann_agent.core.events import EventEmitter, EventStatus, EventType
from rann_agent.core.evidence import Evidence, EvidenceLedger, EvidenceType
from rann_agent.core.exceptions import RannAgentError as RANNError
from rann_agent.core.idempotency import IdempotencyLevel, OperationTracker
from rann_agent.core.runtime import RuntimeAgent
from rann_agent.core.schemas import (
    FailureSchema,
    FinalStatusSchema,
    LessonSchema,
    PlanSchema,
    TaskStatusSchema,
    VerificationResultSchema,
)
from rann_agent.core.state import AgentState, AgentStateMachine
from rann_agent.core.task_contract import (
    AutonomyLevel,
    RiskLevel,
    TaskCategory,
    TaskContract,
)
from rann_agent.core.tool_result import ToolResult

# Learning
from rann_agent.learning.engine import LearningEngine, LearningEpisode, Lesson
from rann_agent.memory.conflict import ConflictResolver, ConflictType, MemoryConflict
from rann_agent.memory.episodic_store import EpisodicEpisode, EpisodicMemoryStore
from rann_agent.memory.procedural import ProceduralMemory
from rann_agent.memory.project_store import ProjectContext, ProjectMemoryStore
from rann_agent.memory.semantic_store import SemanticFact, SemanticMemoryStore

# Memory
from rann_agent.memory.working import WorkingMemory
from rann_agent.orchestration.command_policy import CommandPolicy, CommandRiskLevel
from rann_agent.orchestration.model_router import ModelRouter

# Orchestration
from rann_agent.orchestration.task_graph import TaskGraph, TaskStatus
from rann_agent.orchestration.tool_policy import RiskLevel as ToolRiskLevel
from rann_agent.orchestration.tool_policy import ToolPolicyEngine

# Planning
from rann_agent.planning.planner import Plan, PlanAction, Planner, PlanQualityGate
from rann_agent.planning.progress import Iteration, ProgressEngine, StallReport
from rann_agent.planning.recovery import (
    FailureAnalysis,
    FailureType,
    RecoveryEngine,
    RecoveryResult,
)
from rann_agent.planning.semantic_diff import (
    ImpactAnalyzer,
    ImpactReport,
    SemanticDiff,
    SemanticDiffResult,
)

# Security
from rann_agent.security.sandbox import SandboxConfig, SandboxExecutor, SandboxType
from rann_agent.security.secrets import SecretDetector, SecretScrubber
from rann_agent.security.validation import (
    CommandValidator,
    InputValidator,
    PathValidator,
)
from rann_agent.skills.evaluator import SkillEvaluator, TestCase
from rann_agent.skills.loader import SkillLoader

# Skills
from rann_agent.skills.registry import SkillMetadata, SkillRegistry

# Storage
from rann_agent.storage.database import Database
from rann_agent.storage.locks import FileLock, LockManager, LockType, WorkspaceLock
from rann_agent.storage.queue import DurableQueue, Job, JobStatus
from rann_agent.storage.recovery import (
    CrashRecovery,
    IncompleteRun,
    ReconciliationResult,
)
from rann_agent.tools.discovery import ToolDiscovery

# Tools
from rann_agent.tools.executor import ToolExecutor
from rann_agent.tools.filesystem import FilesystemEngine
from rann_agent.tools.real_terminal import RealTerminalExecutor
from rann_agent.tools.tool_registry import ToolMetadata, ToolRegistry, ToolStatus

__all__ = [
    "Agent",
    "AgentState",
    "AgentStateMachine",
    "ApprovalRequest",
    "ApprovalSystem",
    "ApprovalType",
    "AutonomyGuard",
    "AutonomyLevel",
    "Budget",
    "BudgetEngine",
    "CommandPolicy",
    "CommandRiskLevel",
    "CommandValidator",
    "Config",
    "ConflictResolver",
    "ConflictType",
    "CrashRecovery",
    # Storage
    "Database",
    "DurableQueue",
    "EpisodicEpisode",
    "EpisodicMemoryStore",
    "EvaluationResult",
    # Cognition
    "Evaluator",
    "Event",
    "EventBus",
    "EventEmitter",
    "EventStatus",
    "EventType",
    "Evidence",
    "EvidenceLedger",
    "EvidenceType",
    "FailureAnalysis",
    "FailureSchema",
    "FailureType",
    "FileLock",
    "FilesystemEngine",
    "FinalStatusSchema",
    "IdempotencyLevel",
    "ImpactAnalyzer",
    "ImpactReport",
    "IncompleteRun",
    "InputValidator",
    "Iteration",
    "Job",
    "JobStatus",
    # Learning
    "LearningEngine",
    "LearningEpisode",
    "Lesson",
    "LessonSchema",
    "LockManager",
    "LockType",
    "MemoryConflict",
    "ModelRouter",
    "OperationTracker",
    "PathValidator",
    "Plan",
    "PlanAction",
    "PlanQualityGate",
    "PlanSchema",
    # Planning
    "Planner",
    "ProceduralMemory",
    "ProgressEngine",
    "ProjectContext",
    "ProjectMemoryStore",
    "RANNError",
    "RealTerminalExecutor",
    "ReconciliationResult",
    "RecoveryEngine",
    "RecoveryResult",
    "RiskLevel",
    # Core
    "RuntimeAgent",
    "SandboxConfig",
    # Security
    "SandboxExecutor",
    "SandboxType",
    "SecretDetector",
    "SecretScrubber",
    "SemanticDiff",
    "SemanticDiffResult",
    "SemanticFact",
    "SemanticMemoryStore",
    "SkillEvaluator",
    "SkillLoader",
    "SkillMetadata",
    # Skills
    "SkillRegistry",
    "StallReport",
    "StrategySelector",
    "StrategyType",
    "TaskCategory",
    "TaskContract",
    # Orchestration
    "TaskGraph",
    "TaskStatus",
    "TaskStatusSchema",
    "TestCase",
    "ToolDiscovery",
    # Tools
    "ToolExecutor",
    "ToolMetadata",
    "ToolPolicyEngine",
    "ToolRegistry",
    "ToolResult",
    "ToolRiskLevel",
    "ToolStatus",
    "VerificationResultSchema",
    # Memory
    "WorkingMemory",
    "WorkspaceLock",
    # Version
    "__version__",
]
