"""
Planner module for RANN Agent.
As required by MASTER PROMPT Section 15.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import structlog

logger = structlog.get_logger()


@dataclass
class PlanAction:
    action_id: str
    tool: str
    args: Dict[str, Any]
    expected: str
    rollback: str


@dataclass
class Plan:
    objective: str
    assumptions: List[str] = field(default_factory=list)
    files_to_inspect: List[str] = field(default_factory=list)
    files_to_change: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    actions: List[PlanAction] = field(default_factory=list)
    expected_results: List[str] = field(default_factory=list)
    verification: str = "default"
    rollback_plan: str = ""
    risk: str = "medium"  # low, medium, high
    created_at: str = ""


class PlanQualityGate:
    """Validates a plan meets minimum quality standards."""

    def check(self, plan: Plan) -> Tuple[bool, List[str]]:
        issues = []

        if not plan.objective:
            issues.append("Objective is empty")

        if not plan.files_to_inspect and plan.files_to_change:
            issues.append("Plan modifies files without inspecting them first")

        if not plan.actions:
            issues.append("Plan has no actions")

        if plan.rollback_plan == "" and plan.risk == "high":
            issues.append("High-risk plan has no rollback plan")

        if not plan.verification:
            issues.append("No verification strategy defined")

        # Check acceptance criteria coverage
        if not plan.expected_results:
            issues.append("No expected results defined")

        passed = len(issues) == 0
        if not passed:
            logger.warning("plan_quality_gate_failed", issues=issues)
        return passed, issues


class Planner:
    """Generates structured execution plans from task contracts."""

    def plan(self, contract: "TaskContract", context: Dict[str, Any]) -> Plan:
        """
        Generate a plan from a task contract.
        
        In a full implementation, this would use an LLM to analyze
        the task and generate appropriate actions.
        """
        plan = Plan(
            objective=contract.objective,
            files_to_inspect=[],
            files_to_change=[],
            verification=f"Verify: {contract.verification_strategy}",
            risk=contract.risk_level.name.lower() if hasattr(contract, 'risk_level') else "medium",
            rollback_plan="Restore from checkpoint on failure",
        )
        logger.info("plan_generated", objective=plan.objective, risk=plan.risk)
        return plan

    def validate(self, plan: Plan) -> Tuple[bool, List[str]]:
        gate = PlanQualityGate()
        return gate.check(plan)