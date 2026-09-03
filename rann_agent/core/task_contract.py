"""
Task Contract

Defines the binding contract between user and agent for a task execution.
Implements V3 Section 4 specification.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
import uuid
import structlog

logger = structlog.get_logger()


class TaskCategory(Enum):
    """Task category classification"""
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    REFACTORING = "refactoring"
    TESTING = "testing"
    DEBUGGING = "debugging"
    DEPLOYMENT = "deployment"
    RESEARCH = "research"
    DOCUMENTATION = "documentation"
    DATA_ANALYSIS = "data_analysis"
    INFRASTRUCTURE = "infrastructure"
    SECURITY_AUDIT = "security_audit"
    GENERAL = "general"


class RiskLevel(Enum):
    """Risk level for task execution"""
    LOW = "low"           # Read operations, non-destructive
    MEDIUM = "medium"     # Local modifications, builds
    HIGH = "high"         # Network operations, deployments
    CRITICAL = "critical"  # Destructive operations, system changes


class AutonomyLevel(Enum):
    """Agent autonomy level for task execution"""
    LEVEL_0 = 0  # Full human control - every action approved
    LEVEL_1 = 1  # Human approves planning phase
    LEVEL_2 = 2  # Human approves before high-risk actions
    LEVEL_3 = 3  # Agent plans and executes, human reviews result
    LEVEL_4 = 4  # Agent fully autonomous within constraints


@dataclass
class TaskContract:
    """
    Immutable task contract defining the scope, constraints, and acceptance
    criteria for a task execution.

    Attributes:
        task_id: Unique identifier for this task
        user_request: Raw user request text
        objective: Interpreted high-level objective
        task_category: Classification of task type
        workspace: Working directory for task execution
        constraints: List of constraints to respect
        acceptance_criteria: List of criteria for task completion
        prohibited_actions: Actions the agent must not take
        required_tools: Tools the agent must use
        verification_strategy: Strategy for verifying completion
        risk_level: Assessed risk level
        autonomy_level: Agent autonomy level
        max_iterations: Maximum planning/execution iterations
        max_tool_calls: Maximum tool calls allowed
        timeout_seconds: Maximum execution time
        budget_tokens: Maximum token budget
    """
    task_id: str
    user_request: str
    objective: str
    task_category: TaskCategory
    workspace: str
    constraints: List[str] = field(default_factory=list)
    acceptance_criteria: List[str] = field(default_factory=list)
    prohibited_actions: List[str] = field(default_factory=list)
    required_tools: List[str] = field(default_factory=list)
    verification_strategy: str = "default"
    risk_level: RiskLevel = RiskLevel.LOW
    autonomy_level: AutonomyLevel = AutonomyLevel.LEVEL_2
    max_iterations: int = 50
    max_tool_calls: int = 200
    timeout_seconds: int = 3600
    budget_tokens: int = 50000

    def __post_init__(self):
        """Validate the contract after initialization"""
        if not self.task_id:
            self.task_id = str(uuid.uuid4())
        
        if self.max_iterations <= 0:
            raise ValueError("max_iterations must be positive")
        if self.max_tool_calls <= 0:
            raise ValueError("max_tool_calls must be positive")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.budget_tokens <= 0:
            raise ValueError("budget_tokens must be positive")

    def is_action_prohibited(self, action: str) -> bool:
        """Check if an action is prohibited"""
        action_lower = action.lower()
        return any(
            prohibited.lower() in action_lower
            for prohibited in self.prohibited_actions
        )

    def get_risk_description(self) -> str:
        """Get human-readable risk description"""
        descriptions = {
            RiskLevel.LOW: "Read-only operations with no system modifications",
            RiskLevel.MEDIUM: "Local modifications and builds",
            RiskLevel.HIGH: "Network operations and deployments",
            RiskLevel.CRITICAL: "Destructive operations and system changes",
        }
        return descriptions.get(self.risk_level, "Unknown risk level")

    def get_autonomy_description(self) -> str:
        """Get human-readable autonomy description"""
        descriptions = {
            AutonomyLevel.LEVEL_0: "Full human control - every action requires approval",
            AutonomyLevel.LEVEL_1: "Human approves planning phase",
            AutonomyLevel.LEVEL_2: "Human approves before high-risk actions",
            AutonomyLevel.LEVEL_3: "Agent plans and executes, human reviews result",
            AutonomyLevel.LEVEL_4: "Fully autonomous within constraints",
        }
        return descriptions.get(self.autonomy_level, "Unknown autonomy level")

    def to_summary(self) -> Dict[str, Any]:
        """Get a summary dict for logging/debugging"""
        return {
            "task_id": self.task_id,
            "objective": self.objective,
            "category": self.task_category.value,
            "risk_level": self.risk_level.value,
            "autonomy_level": self.autonomy_level.name,
            "workspace": self.workspace,
            "max_iterations": self.max_iterations,
            "max_tool_calls": self.max_tool_calls,
            "timeout_seconds": self.timeout_seconds,
            "budget_tokens": self.budget_tokens,
            "num_constraints": len(self.constraints),
            "num_acceptance_criteria": len(self.acceptance_criteria),
            "num_prohibited_actions": len(self.prohibited_actions),
            "num_required_tools": len(self.required_tools),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "task_id": self.task_id,
            "user_request": self.user_request,
            "objective": self.objective,
            "task_category": self.task_category.value,
            "workspace": self.workspace,
            "constraints": self.constraints,
            "acceptance_criteria": self.acceptance_criteria,
            "prohibited_actions": self.prohibited_actions,
            "required_tools": self.required_tools,
            "verification_strategy": self.verification_strategy,
            "risk_level": self.risk_level.value,
            "autonomy_level": self.autonomy_level.value,
            "max_iterations": self.max_iterations,
            "max_tool_calls": self.max_tool_calls,
            "timeout_seconds": self.timeout_seconds,
            "budget_tokens": self.budget_tokens,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskContract":
        """Deserialize from dictionary"""
        return cls(
            task_id=data["task_id"],
            user_request=data["user_request"],
            objective=data["objective"],
            task_category=TaskCategory(data["task_category"]),
            workspace=data["workspace"],
            constraints=data.get("constraints", []),
            acceptance_criteria=data.get("acceptance_criteria", []),
            prohibited_actions=data.get("prohibited_actions", []),
            required_tools=data.get("required_tools", []),
            verification_strategy=data.get("verification_strategy", "default"),
            risk_level=RiskLevel(data.get("risk_level", "low")),
            autonomy_level=AutonomyLevel(data.get("autonomy_level", 2)),
            max_iterations=data.get("max_iterations", 50),
            max_tool_calls=data.get("max_tool_calls", 200),
            timeout_seconds=data.get("timeout_seconds", 3600),
            budget_tokens=data.get("budget_tokens", 50000),
        )


def create_task_contract(
    user_request: str,
    objective: str,
    task_category: TaskCategory,
    workspace: str,
    constraints: Optional[List[str]] = None,
    acceptance_criteria: Optional[List[str]] = None,
    prohibited_actions: Optional[List[str]] = None,
    required_tools: Optional[List[str]] = None,
    verification_strategy: str = "default",
    risk_level: RiskLevel = RiskLevel.LOW,
    autonomy_level: AutonomyLevel = AutonomyLevel.LEVEL_2,
    max_iterations: int = 50,
    max_tool_calls: int = 200,
    timeout_seconds: int = 3600,
    budget_tokens: int = 50000,
) -> TaskContract:
    """
    Factory function to create a TaskContract with validation logging.
    """
    contract = TaskContract(
        task_id=str(uuid.uuid4()),
        user_request=user_request,
        objective=objective,
        task_category=task_category,
        workspace=workspace,
        constraints=constraints or [],
        acceptance_criteria=acceptance_criteria or [],
        prohibited_actions=prohibited_actions or [],
        required_tools=required_tools or [],
        verification_strategy=verification_strategy,
        risk_level=risk_level,
        autonomy_level=autonomy_level,
        max_iterations=max_iterations,
        max_tool_calls=max_tool_calls,
        timeout_seconds=timeout_seconds,
        budget_tokens=budget_tokens,
    )

    logger.info(
        "task_contract_created",
        **contract.to_summary()
    )

    return contract