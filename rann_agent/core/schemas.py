"""
Structured output schemas for RANN Agent.
As required by MASTER PROMPT Section 44.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskStatusSchema(Enum):
    QUEUED = "queued"
    ANALYZING = "analyzing"
    CONTEXT_READY = "context_ready"
    PLANNING = "planning"
    WAITING_POLICY = "waiting_policy"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    RECOVERING = "recovering"
    ACCEPTANCE_CHECK = "acceptance_check"
    LEARNING = "learning"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    BLOCKED = "blocked"
    ROLLED_BACK = "rolled_back"


class VerificationLevel(Enum):
    NONE = 0
    STATIC = 1
    FOCUSED_TEST = 2
    RELEVANT_SUITE = 3
    INTEGRATION = 4
    E2E = 5


@dataclass
class TaskStatusSchema:
    task_id: str
    status: TaskStatusSchema
    progress: float  # 0.0 to 1.0
    current_step: int
    total_steps: int
    budget_used: dict[str, Any]
    last_activity: str
    error: str | None = None


@dataclass
class PlanSchema:
    objective: str
    files_to_inspect: list[str]
    files_to_change: list[str]
    actions: list[dict[str, Any]]
    expected_results: list[str]
    verification: str
    risk: str
    rollback_plan: str
    quality_passed: bool
    quality_issues: list[str] = field(default_factory=list)


@dataclass
class VerificationResultSchema:
    verification_id: str
    criterion: str
    method: str
    expected: str
    actual: str
    success: bool
    evidence: dict[str, Any]
    timestamp: str


@dataclass
class FailureSchema:
    failure_type: str
    root_cause: str
    contributing_factors: list[str]
    evidence: list[str]
    recovery_plan: str
    recovery_attempted: bool
    recovery_succeeded: bool


@dataclass
class LessonSchema:
    lesson_id: str
    category: str
    content: str
    evidence: list[str]
    confidence: float
    validated: bool
    sample_size: int


@dataclass
class FinalStatusSchema:
    status: str  # PASS, PARTIAL, FAIL, BLOCKED
    task_id: str
    output: str
    verification_results: list[VerificationResultSchema]
    evidence_ids: list[str]
    failures: list[FailureSchema]
    lessons_learned: list[str]
    total_iterations: int
    total_tool_calls: int
    total_cost: float
    total_latency_ms: float
    rollback_performed: bool
    blocked_reason: str | None = None
