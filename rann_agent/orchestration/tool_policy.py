"""
Tool Policy Engine

Permission classification and enforcement for tool execution.
As required by MASTER PROMPT Section 18.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any, Callable
from enum import Enum
import structlog

logger = structlog.get_logger()


class RiskLevel(Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PolicyAction(Enum):
    ALLOW = "allow"
    DENY = "deny"
    APPROVE = "approve"
    SANDBOX = "sandbox"
    RATE_LIMIT = "rate_limit"


@dataclass
class ToolPolicy:
    tool_name: str
    risk_level: RiskLevel
    default_action: PolicyAction
    requires_approval: bool = False
    allowed_roles: Set[str] = field(default_factory=set)
    max_calls_per_run: int = 0
    max_concurrent: int = 1
    sandbox_required: bool = False
    sandbox_type: str = "none"
    cost_per_call: float = 0.0
    audit_all_calls: bool = False
    log_parameters: bool = False
    blocked_users: Set[str] = field(default_factory=set)
    blocked_contexts: Set[str] = field(default_factory=set)


@dataclass
class PolicyDecision:
    action: PolicyAction
    allowed: bool
    reason: str
    risk_level: Optional[RiskLevel] = None
    conditions: Dict[str, Any] = field(default_factory=dict)


class ToolPolicyEngine:
    """
    Enforces tool execution policies.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._policies: Dict[str, ToolPolicy] = {}
        self._role_permissions: Dict[str, Set[str]] = {}
        self._call_counts: Dict[str, int] = {}
        self._log = structlog.get_logger().bind(component="tool_policy")
        self._load_default_policies()
    
    def _load_default_policies(self) -> None:
        defaults = {
            "file_read": ToolPolicy("file_read", RiskLevel.SAFE, PolicyAction.ALLOW, log_parameters=True),
            "file_search": ToolPolicy("file_search", RiskLevel.SAFE, PolicyAction.ALLOW),
            "web_search": ToolPolicy("web_search", RiskLevel.SAFE, PolicyAction.ALLOW),
            "web_extract": ToolPolicy("web_extract", RiskLevel.SAFE, PolicyAction.ALLOW),
            "memory_search": ToolPolicy("memory_search", RiskLevel.SAFE, PolicyAction.ALLOW),
            "file_write": ToolPolicy("file_write", RiskLevel.LOW, PolicyAction.ALLOW, audit_all_calls=True, log_parameters=True),
            "git": ToolPolicy("git", RiskLevel.LOW, PolicyAction.ALLOW, audit_all_calls=True),
            "terminal": ToolPolicy("terminal", RiskLevel.MEDIUM, PolicyAction.APPROVE, audit_all_calls=True, log_parameters=True),
            "code_execution": ToolPolicy("code_execution", RiskLevel.HIGH, PolicyAction.APPROVE, sandbox_required=True, audit_all_calls=True),
            "docker": ToolPolicy("docker", RiskLevel.CRITICAL, PolicyAction.DENY, requires_approval=True),
            "kubernetes": ToolPolicy("kubernetes", RiskLevel.CRITICAL, PolicyAction.DENY, requires_approval=True),
            "database": ToolPolicy("database", RiskLevel.HIGH, PolicyAction.DENY, requires_approval=True),
        }
        self._policies.update(defaults)
    
    def get_policy(self, tool_name: str) -> Optional[ToolPolicy]:
        return self._policies.get(tool_name)
    
    def check(
        self,
        tool_name: str,
        user: Optional[str] = None,
        context: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None
    ) -> PolicyDecision:
        policy = self._policies.get(tool_name)
        
        if not policy:
            return PolicyDecision(
                action=PolicyAction.DENY,
                allowed=False,
                reason=f"No policy defined for tool: {tool_name}",
                risk_level=RiskLevel.CRITICAL
            )
        
        # Check blocked users
        if user and user in policy.blocked_users:
            return PolicyDecision(
                action=PolicyAction.DENY,
                allowed=False,
                reason=f"User {user} is blocked from using {tool_name}",
                risk_level=policy.risk_level
            )
        
        # Check blocked contexts
        if context and context in policy.blocked_contexts:
            return PolicyDecision(
                action=PolicyAction.DENY,
                allowed=False,
                reason=f"Context {context} is blocked for {tool_name}",
                risk_level=policy.risk_level
            )
        
        # Check role permissions
        if policy.allowed_roles and user:
            role = self._get_user_role(user)
            if role not in policy.allowed_roles:
                return PolicyDecision(
                    action=PolicyAction.DENY,
                    allowed=False,
                    reason=f"User role {role} not allowed for {tool_name}",
                    risk_level=policy.risk_level
                )
        
        # Check rate limits
        if policy.max_calls_per_run > 0:
            current = self._call_counts.get(tool_name, 0)
            if current >= policy.max_calls_per_run:
                return PolicyDecision(
                    action=PolicyAction.RATE_LIMIT,
                    allowed=False,
                    reason=f"Rate limit reached for {tool_name}: {current}/{policy.max_calls_per_run}",
                    risk_level=policy.risk_level
                )
        
        # Build conditions
        conditions = {}
        if policy.sandbox_required:
            conditions["sandbox_type"] = policy.sandbox_type
        
        return PolicyDecision(
            action=policy.default_action,
            allowed=policy.default_action in {PolicyAction.ALLOW, PolicyAction.SANDBOX},
            reason=f"Allowed: {tool_name} (risk: {policy.risk_level.value})",
            risk_level=policy.risk_level,
            conditions=conditions
        )
    
    def record_call(self, tool_name: str) -> None:
        self._call_counts[tool_name] = self._call_counts.get(tool_name, 0) + 1
    
    def reset_counts(self) -> None:
        self._call_counts.clear()
    
    def set_policy(self, policy: ToolPolicy) -> None:
        self._policies[policy.tool_name] = policy
    
    def _get_user_role(self, user: str) -> str:
        return "default"
    
    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_policies": len(self._policies),
            "policies_by_risk": {
                r.value: len([p for p in self._policies.values() if p.risk_level == r])
                for r in RiskLevel
            },
            "call_counts": self._call_counts.copy()
        }