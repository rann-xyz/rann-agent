"""
Tool Permission Layer

Enforces tool execution policies based on TaskContract constraints.
Validates tool calls against allowed/prohibited tools before execution.
Provides audit logging for all tool invocations.

Features:
- Allowlist/denylist per task category
- Risk-based tool gating (HIGH/CRITICAL tools require approval)
- Execution audit trail
- Policy override with audit logging
- Integration with TaskContract prohibited_actions
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger()


class ToolCategory(Enum):
    """Categories of tools by risk/complexity"""

    # Read operations
    READ = "read"  # File reading, search, git log, etc.
    ANALYSIS = "analysis"  # Linting, type checking, tests
    # Write operations
    WRITE = "write"  # File creation, editing
    REFACTOR = "refactor"  # Code transformations
    # Execution
    BUILD = "build"  # Compilation, builds, packaging
    TEST = "test"  # Running tests
    DEPLOY = "deploy"  # Deployments, releases
    # System
    SYSTEM = "system"  # Shell commands, env changes
    NETWORK = "network"  # HTTP requests, API calls
    DESTRUCTIVE = "destructive"  # rm, git reset --hard, etc.


@dataclass
class ToolDefinition:
    """Definition of a tool"""

    name: str
    category: ToolCategory
    risk_level: str = "low"  # low, medium, high, critical
    description: str = ""
    required_permissions: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)  # Regex patterns for matching

    def matches(self, tool_name: str) -> bool:
        """Check if this definition matches a tool name"""
        name_lower = tool_name.lower()
        if self.name.lower() == name_lower:
            return True
        return any(re.search(pattern, name_lower, re.IGNORECASE) for pattern in self.patterns)


# Built-in tool registry
BUILTIN_TOOLS: list[ToolDefinition] = [
    # READ tools
    ToolDefinition(
        name="read_file",
        category=ToolCategory.READ,
        risk_level="low",
        description="Read file contents",
        patterns=[r"read.*file", r"cat", r"view.*file"],
    ),
    ToolDefinition(
        name="search_files",
        category=ToolCategory.READ,
        risk_level="low",
        description="Search file contents",
        patterns=[r"grep", r"search.*file", r"rg", r"find.*string"],
    ),
    ToolDefinition(
        name="browser_exec",
        category=ToolCategory.READ,
        risk_level="low",
        description="Read web pages via browser",
        patterns=[r"browse", r"fetch.*url", r"scrape"],
    ),
    # WRITE tools
    ToolDefinition(
        name="write_file",
        category=ToolCategory.WRITE,
        risk_level="medium",
        description="Write/create files",
        patterns=[r"write.*file", r"create.*file", r"edit.*file"],
    ),
    ToolDefinition(
        name="patch",
        category=ToolCategory.WRITE,
        risk_level="medium",
        description="Modify existing files",
        patterns=[r"patch", r"modify.*file", r"replace.*string"],
    ),
    # REFACTOR tools
    ToolDefinition(
        name="terminal",
        category=ToolCategory.SYSTEM,
        risk_level="high",
        description="Execute shell commands",
        patterns=[r"shell", r"bash", r"exec", r"run.*command", r"subprocess"],
    ),
    # BUILD tools
    ToolDefinition(
        name="execute_code",
        category=ToolCategory.BUILD,
        risk_level="medium",
        description="Execute Python code",
        patterns=[r"python.*exec", r"run.*code", r"execute.*code"],
    ),
    # TEST tools
    ToolDefinition(
        name="execute_code",  # Also used for tests
        category=ToolCategory.TEST,
        risk_level="medium",
        description="Run tests",
        patterns=[r"pytest", r"test", r"unittest"],
    ),
    # DEPLOY tools
    ToolDefinition(
        name="delegate_task",
        category=ToolCategory.DEPLOY,
        risk_level="high",
        description="Deploy to cloud platforms",
        patterns=[r"deploy", r"vercel", r"heroku", r"render"],
    ),
    # DESTRUCTIVE tools
    ToolDefinition(
        name="terminal",
        category=ToolCategory.DESTRUCTIVE,
        risk_level="critical",
        description="Delete files or directories",
        patterns=[r"rm\s+-rf", r"rmdir", r"delete.*file", r"unlink"],
    ),
    ToolDefinition(
        name="terminal",
        category=ToolCategory.DESTRUCTIVE,
        risk_level="critical",
        description="Git reset or force push",
        patterns=[r"git.*reset.*hard", r"git.*force.*push", r"git.*clean.*-fd"],
    ),
]


@dataclass
class ToolCall:
    """Record of a tool call attempt"""

    call_id: str
    tool_name: str
    arguments: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: str = "pending"  # pending, allowed, denied, error
    denial_reason: str | None = None
    policy_override: bool = False
    override_reason: str | None = None
    execution_time_ms: float | None = None


class PermissionDecision(Enum):
    """Decision from permission check"""

    ALLOWED = "allowed"
    DENIED = "denied"
    APPROVAL_REQUIRED = "approval_required"
    BLOCKED = "blocked"


@dataclass
class PolicyCheckResult:
    """Result of a policy check"""

    decision: PermissionDecision
    tool_name: str
    reason: str
    requires_approval: bool = False
    approval_level: int | None = None
    policy_matched: str | None = None


class ToolPermissionLayer:
    """
    Enforces tool execution policies.

    Usage:
        layer = ToolPermissionLayer()

        # Check if a tool call is allowed
        result = layer.check_permission("terminal", {"command": "rm -rf /tmp/foo"})
        if result.decision == PermissionDecision.DENIED:
            print(f"Blocked: {result.reason}")

        # Record approval
        layer.record_approval(call_id, approved_by="user@example.com")

        # Execute with permission check
        result = await layer.execute_with_permission("terminal", {"command": "ls"}, callback)
    """

    def __init__(
        self,
        allowlist: list[str] | None = None,
        denylist: list[str] | None = None,
        require_approval_above: str = "high",
    ):
        self.allowlist: set[str] = set(allowlist or [])
        self.denylist: set[str] = set(denylist or [])
        self.require_approval_above = require_approval_above  # risk level
        self._tool_registry: dict[str, ToolDefinition] = {t.name: t for t in BUILTIN_TOOLS}
        self._audit_log: list[ToolCall] = []
        self._pending_approvals: dict[str, ToolCall] = {}

        logger.info(
            "tool_permission_layer_init",
            allowlist_count=len(self.allowlist),
            denylist_count=len(self.denylist),
            require_approval_above=require_approval_above,
        )

    def register_tool(self, tool: ToolDefinition) -> None:
        """Register a custom tool definition"""
        self._tool_registry[tool.name] = tool

    def get_tool_definition(self, tool_name: str) -> ToolDefinition | None:
        """Get tool definition by name"""
        return self._tool_registry.get(tool_name)

    def check_permission(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        task_category: str | None = None,
        risk_level: str | None = None,
        prohibited_actions: list[str] | None = None,
    ) -> PolicyCheckResult:
        """
        Check if a tool call is permitted.

        Args:
            tool_name: Name of the tool
            arguments: Tool arguments
            task_category: Task category for category-based rules
            risk_level: Override risk level
            prohibited_actions: List of prohibited action patterns from TaskContract

        Returns:
            PolicyCheckResult with decision and reason
        """
        import uuid

        call_id = str(uuid.uuid4())[:8]
        args = arguments or {}
        args_str = str(args)

        # Check denylist first (highest priority)
        if tool_name in self.denylist:
            reason = f"Tool '{tool_name}' is on the denylist"
            self._log_call(call_id, tool_name, args, "denied", denial_reason=reason)
            return PolicyCheckResult(
                decision=PermissionDecision.DENIED,
                tool_name=tool_name,
                reason=reason,
            )

        # Check allowlist (if specified)
        if self.allowlist and tool_name not in self.allowlist:
            reason = f"Tool '{tool_name}' is not on the allowlist"
            self._log_call(call_id, tool_name, args, "denied", denial_reason=reason)
            return PolicyCheckResult(
                decision=PermissionDecision.DENIED,
                tool_name=tool_name,
                reason=reason,
            )

        # Check prohibited_actions from TaskContract
        if prohibited_actions:
            for prohibited in prohibited_actions:
                prohibited_lower = prohibited.lower()
                if prohibited_lower in tool_name.lower() or prohibited_lower in args_str.lower():
                    reason = f"Action matches prohibited pattern: '{prohibited}'"
                    self._log_call(call_id, tool_name, args, "denied", denial_reason=reason)
                    return PolicyCheckResult(
                        decision=PermissionDecision.DENIED,
                        tool_name=tool_name,
                        reason=reason,
                        policy_matched="prohibited_actions",
                    )

        # Get tool definition for risk assessment
        tool_def = self.get_tool_definition(tool_name)
        effective_risk = risk_level or (tool_def.risk_level if tool_def else "low")

        # Check if approval is required based on risk
        risk_order = ["low", "medium", "high", "critical"]
        if risk_order.index(effective_risk) >= risk_order.index(self.require_approval_above):
            reason = f"Tool '{tool_name}' requires approval (risk: {effective_risk})"
            call = self._log_call(call_id, tool_name, args, "pending")
            self._pending_approvals[call_id] = call
            return PolicyCheckResult(
                decision=PermissionDecision.APPROVAL_REQUIRED,
                tool_name=tool_name,
                reason=reason,
                requires_approval=True,
                approval_level=risk_order.index(effective_risk),
                policy_matched="risk_based",
            )

        # Get category-specific reason
        category = tool_def.category.value if tool_def else "unknown"
        reason = f"Tool '{tool_name}' allowed (category: {category}, risk: {effective_risk})"
        self._log_call(call_id, tool_name, args, "allowed")
        return PolicyCheckResult(
            decision=PermissionDecision.ALLOWED,
            tool_name=tool_name,
            reason=reason,
        )

    def record_approval(
        self, call_id: str, approved_by: str | None = None, notes: str | None = None
    ) -> bool:
        """
        Record approval for a pending tool call.

        Returns True if approval was recorded.
        """
        if call_id not in self._pending_approvals:
            logger.warning("approval_call_id_not_found", call_id=call_id)
            return False

        call = self._pending_approvals[call_id]
        call.status = "allowed"
        call.policy_override = True
        call.override_reason = notes or f"Approved by {approved_by or 'unknown'}"

        logger.info(
            "tool_call_approved",
            call_id=call_id,
            tool_name=call.tool_name,
            approved_by=approved_by,
        )

        # Update audit log
        for logged_call in self._audit_log:
            if logged_call.call_id == call_id:
                logged_call.status = "allowed"
                logged_call.policy_override = True
                logged_call.override_reason = call.override_reason
                break

        return True

    def record_denial(
        self, call_id: str, denied_by: str | None = None, reason: str | None = None
    ) -> bool:
        """Record denial of a pending tool call"""
        if call_id not in self._pending_approvals:
            return False

        call = self._pending_approvals[call_id]
        call.status = "denied"
        call.denial_reason = reason or f"Denied by {denied_by or 'unknown'}"

        for logged_call in self._audit_log:
            if logged_call.call_id == call_id:
                logged_call.status = "denied"
                logged_call.denial_reason = call.denial_reason
                break

        return True

    def is_approved(self, call_id: str) -> bool:
        """Check if a call has been approved"""
        call = self._pending_approvals.get(call_id)
        return call is not None and call.status == "allowed"

    def get_pending_approvals(self) -> list[ToolCall]:
        """Get all pending approvals"""
        return [c for c in self._pending_approvals.values() if c.status == "pending"]

    def get_audit_log(
        self,
        tool_name: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[ToolCall]:
        """Get audit log with optional filters"""
        results = self._audit_log[-limit:]
        if tool_name:
            results = [c for c in results if c.tool_name == tool_name]
        if status:
            results = [c for c in results if c.status == status]
        return results

    def _log_call(
        self,
        call_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        status: str,
        denial_reason: str | None = None,
        policy_override: bool = False,
        override_reason: str | None = None,
    ) -> ToolCall:
        """Log a tool call"""
        call = ToolCall(
            call_id=call_id,
            tool_name=tool_name,
            arguments=arguments,
            status=status,
            denial_reason=denial_reason,
            policy_override=policy_override,
            override_reason=override_reason,
        )
        self._audit_log.append(call)
        return call

    async def execute_with_permission(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        executor: callable,
        task_category: str | None = None,
        risk_level: str | None = None,
        prohibited_actions: list[str] | None = None,
    ) -> tuple[PolicyCheckResult, Any]:
        """
        Check permission then execute if allowed.

        Returns (check_result, execution_result).
        If denied, returns (denial_result, None).
        """
        check_result = self.check_permission(
            tool_name=tool_name,
            arguments=arguments,
            task_category=task_category,
            risk_level=risk_level,
            prohibited_actions=prohibited_actions,
        )

        if check_result.decision == PermissionDecision.DENIED:
            return check_result, None

        if check_result.decision == PermissionDecision.APPROVAL_REQUIRED:
            # Check if already approved
            matching_calls = [
                c for c in self._audit_log if c.tool_name == tool_name and c.status == "pending"
            ]
            if matching_calls:
                call = matching_calls[-1]
                if not self.is_approved(call.call_id):
                    return check_result, None

        # Execute
        try:
            import asyncio

            if asyncio.iscoroutinefunction(executor):
                result = await executor(arguments)
            else:
                result = executor(arguments)
            return check_result, result
        except Exception:
            # Log execution error
            matching = [
                c for c in self._audit_log if c.tool_name == tool_name and c.status == "allowed"
            ]
            if matching:
                matching[-1].status = "error"
            raise

    def get_policy_summary(self) -> dict[str, Any]:
        """Get summary of current policy configuration"""
        return {
            "allowlist": list(self.allowlist),
            "denylist": list(self.denylist),
            "require_approval_above": self.require_approval_above,
            "registered_tools": len(self._tool_registry),
            "audit_log_size": len(self._audit_log),
            "pending_approvals": len(self.get_pending_approvals()),
            "total_calls": len(self._audit_log),
            "allowed_calls": len([c for c in self._audit_log if c.status == "allowed"]),
            "denied_calls": len([c for c in self._audit_log if c.status == "denied"]),
        }
