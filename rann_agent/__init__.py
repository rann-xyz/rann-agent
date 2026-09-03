"""
RANN Agent - Next-generation autonomous AI engineering platform.

THE MODEL GENERATES DECISIONS. RANN CONTROLS EXECUTION.
"""

__version__ = "1.0.0"
__author__ = "RANN Team"
__license__ = "MIT"

# Core
from rann_agent.core.runtime import RuntimeAgent
from rann_agent.core.agent import Agent
from rann_agent.core.config import Config
from rann_agent.core.budget import Budget, BudgetEngine
from rann_agent.core.state import AgentStateMachine, AgentState
from rann_agent.core.events import EventEmitter, EventType, EventStatus
from rann_agent.core.exceptions import RannAgentError as RANNError
from rann_agent.core.task_contract import TaskContract, TaskCategory, RiskLevel, AutonomyLevel
from rann_agent.core.tool_result import ToolResult
from rann_agent.core.evidence import EvidenceLedger, Evidence, EvidenceType
from rann_agent.core.event_bus import EventBus, Event, EventType
from rann_agent.core.autonomy import AutonomyGuard
from rann_agent.core.approval import ApprovalSystem, ApprovalType, ApprovalRequest
from rann_agent.core.idempotency import OperationTracker, IdempotencyLevel
from rann_agent.core.schemas import (
    TaskStatusSchema, PlanSchema, VerificationResultSchema, FailureSchema,
    LessonSchema, FinalStatusSchema
)

# Orchestration
from rann_agent.orchestration.task_graph import TaskGraph, TaskStatus
from rann_agent.orchestration.tool_policy import ToolPolicyEngine, RiskLevel as ToolRiskLevel
from rann_agent.orchestration.model_router import ModelRouter
from rann_agent.orchestration.command_policy import CommandPolicy, CommandRiskLevel

# Planning
from rann_agent.planning.planner import Planner, Plan, PlanAction, PlanQualityGate
from rann_agent.planning.progress import ProgressEngine, Iteration, StallReport
from rann_agent.planning.recovery import RecoveryEngine, FailureAnalysis, FailureType, RecoveryResult
from rann_agent.planning.semantic_diff import SemanticDiff, SemanticDiffResult, ImpactAnalyzer, ImpactReport

# Memory
from rann_agent.memory.working import WorkingMemory
from rann_agent.memory.procedural import ProceduralMemory
from rann_agent.memory.conflict import ConflictResolver, MemoryConflict, ConflictType
from rann_agent.memory.project_store import ProjectMemoryStore, ProjectContext
from rann_agent.memory.episodic_store import EpisodicMemoryStore, EpisodicEpisode
from rann_agent.memory.semantic_store import SemanticMemoryStore, SemanticFact

# Learning
from rann_agent.learning.engine import LearningEngine, LearningEpisode, Lesson

# Skills
from rann_agent.skills.registry import SkillRegistry, SkillMetadata
from rann_agent.skills.loader import SkillLoader
from rann_agent.skills.evaluator import SkillEvaluator, TestCase

# Tools
from rann_agent.tools.executor import ToolExecutor
from rann_agent.tools.discovery import ToolDiscovery
from rann_agent.tools.real_terminal import RealTerminalExecutor
from rann_agent.tools.filesystem import FilesystemEngine
from rann_agent.tools.tool_registry import ToolRegistry, ToolMetadata, ToolStatus

# Storage
from rann_agent.storage.database import Database
from rann_agent.storage.recovery import CrashRecovery, IncompleteRun, ReconciliationResult
from rann_agent.storage.queue import DurableQueue, Job, JobStatus
from rann_agent.storage.locks import LockManager, FileLock, WorkspaceLock, LockType

# Cognition
from rann_agent.cognition.evaluator import Evaluator, EvaluationResult
from rann_agent.cognition.strategy import StrategySelector, StrategyType

# Security
from rann_agent.security.sandbox import SandboxExecutor, SandboxType, SandboxConfig
from rann_agent.security.secrets import SecretScrubber, SecretDetector
from rann_agent.security.validation import PathValidator, CommandValidator, InputValidator

__all__ = [
    # Version
    "__version__",
    # Core
    "RuntimeAgent", "Agent", "Config", "Budget", "BudgetEngine",
    "AgentStateMachine", "AgentState", "EventEmitter", "EventType", "EventStatus", "RANNError",
    "TaskContract", "TaskCategory", "RiskLevel", "AutonomyLevel", "ToolResult",
    "EvidenceLedger", "Evidence", "EvidenceType",
    "EventBus", "Event",
    "AutonomyGuard",
    "ApprovalSystem", "ApprovalType", "ApprovalRequest",
    "OperationTracker", "IdempotencyLevel",
    "TaskStatusSchema", "PlanSchema", "VerificationResultSchema", "FailureSchema",
    "LessonSchema", "FinalStatusSchema",
    # Orchestration
    "TaskGraph", "TaskStatus", "ToolPolicyEngine", "ToolRiskLevel", "ModelRouter",
    "CommandPolicy", "CommandRiskLevel",
    # Planning
    "Planner", "Plan", "PlanAction", "PlanQualityGate",
    "ProgressEngine", "Iteration", "StallReport",
    "RecoveryEngine", "FailureAnalysis", "FailureType", "RecoveryResult",
    "SemanticDiff", "SemanticDiffResult", "ImpactAnalyzer", "ImpactReport",
    # Memory
    "WorkingMemory", "ProceduralMemory",
    "ConflictResolver", "MemoryConflict", "ConflictType",
    "ProjectMemoryStore", "ProjectContext",
    "EpisodicMemoryStore", "EpisodicEpisode",
    "SemanticMemoryStore", "SemanticFact",
    # Learning
    "LearningEngine", "LearningEpisode", "Lesson",
    # Skills
    "SkillRegistry", "SkillMetadata", "SkillLoader", "SkillEvaluator", "TestCase",
    # Tools
    "ToolExecutor", "ToolDiscovery", "RealTerminalExecutor", "FilesystemEngine",
    "ToolRegistry", "ToolMetadata", "ToolStatus",
    # Storage
    "Database", "CrashRecovery", "IncompleteRun", "ReconciliationResult",
    "DurableQueue", "Job", "JobStatus",
    "LockManager", "FileLock", "WorkspaceLock", "LockType",
    # Cognition
    "Evaluator", "EvaluationResult", "StrategySelector", "StrategyType",
    # Security
    "SandboxExecutor", "SandboxType", "SandboxConfig",
    "SecretScrubber", "SecretDetector",
    "PathValidator", "CommandValidator", "InputValidator",
]