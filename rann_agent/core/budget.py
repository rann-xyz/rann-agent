"""
Budget Engine

Tracks and enforces token, time, tool, model-call, and financial budgets.
As required by MASTER PROMPT Section 14.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import structlog

logger = structlog.get_logger()


@dataclass
class Budget:
    """Budget limits for a run"""
    max_tokens: int = 100000
    max_time_seconds: float = 3600  # 1 hour
    max_tool_calls: int = 100
    max_model_calls: int = 50
    max_cost_usd: float = 10.0
    max_turns: int = 50
    
    # Warning thresholds (percentage)
    warning_threshold: float = 0.8  # Warn at 80%


@dataclass 
class BudgetTracker:
    """Tracks budget consumption"""
    budget: Budget
    start_time: datetime = field(default_factory=datetime.now)
    
    # Current consumption
    tokens_used: int = 0
    model_calls: int = 0
    tool_calls: int = 0
    cost_usd: float = 0.0
    turns: int = 0
    
    # Token breakdown
    input_tokens: int = 0
    output_tokens: int = 0
    
    def get_elapsed_seconds(self) -> float:
        return (datetime.now() - self.start_time).total_seconds()
    
    def tokens_remaining(self) -> int:
        return max(0, self.budget.max_tokens - self.tokens_used)
    
    def time_remaining_seconds(self) -> float:
        return max(0, self.budget.max_time_seconds - self.get_elapsed_seconds())
    
    def tool_calls_remaining(self) -> int:
        return max(0, self.budget.max_tool_calls - self.tool_calls)
    
    def model_calls_remaining(self) -> int:
        return max(0, self.budget.max_model_calls - self.model_calls)
    
    def cost_remaining_usd(self) -> float:
        return max(0, self.budget.max_cost_usd - self.cost_usd)
    
    def turns_remaining(self) -> int:
        return max(0, self.budget.max_turns - self.turns)
    
    def is_exhausted(self) -> bool:
        """Check if ANY budget is exhausted"""
        return (
            self.tokens_remaining() <= 0 or
            self.time_remaining_seconds() <= 0 or
            self.tool_calls_remaining() <= 0 or
            self.model_calls_remaining() <= 0 or
            self.cost_remaining_usd() <= 0 or
            self.turns_remaining() <= 0
        )
    
    def get_limit_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all limits"""
        return {
            "tokens": {
                "used": self.tokens_used,
                "limit": self.budget.max_tokens,
                "remaining": self.tokens_remaining(),
                "pct": self.tokens_used / max(1, self.budget.max_tokens)
            },
            "time": {
                "used_seconds": self.get_elapsed_seconds(),
                "limit_seconds": self.budget.max_time_seconds,
                "remaining_seconds": self.time_remaining_seconds(),
                "pct": self.get_elapsed_seconds() / max(1, self.budget.max_time_seconds)
            },
            "tool_calls": {
                "used": self.tool_calls,
                "limit": self.budget.max_tool_calls,
                "remaining": self.tool_calls_remaining(),
                "pct": self.tool_calls / max(1, self.budget.max_tool_calls)
            },
            "model_calls": {
                "used": self.model_calls,
                "limit": self.budget.max_model_calls,
                "remaining": self.model_calls_remaining(),
                "pct": self.model_calls / max(1, self.budget.max_model_calls)
            },
            "cost": {
                "used_usd": self.cost_usd,
                "limit_usd": self.budget.max_cost_usd,
                "remaining_usd": self.cost_remaining_usd(),
                "pct": self.cost_usd / max(1, self.budget.max_cost_usd)
            },
            "turns": {
                "used": self.turns,
                "limit": self.budget.max_turns,
                "remaining": self.turns_remaining(),
                "pct": self.turns / max(1, self.budget.max_turns)
            }
        }
    
    def check_warnings(self) -> list[str]:
        """Check for budget warnings"""
        warnings = []
        status = self.get_limit_status()
        
        for key, data in status.items():
            if data["pct"] >= self.budget.warning_threshold:
                used_val = data.get("used", data.get("used_seconds", data.get("used_usd", data["used"])))
                limit_val = data.get("limit", data.get("limit_seconds", data.get("limit_usd", data["limit"])))
                warnings.append(f"{key}: {data['pct']:.0%} used ({used_val} of {limit_val})")
        
        return warnings


class BudgetEngine:
    """
    Manages budgets for agent runs.
    
    Tracks consumption, enforces limits, and provides warnings.
    """
    
    def __init__(self, budget: Optional[Budget] = None):
        self.budget = budget or Budget()
        self._tracker: Optional[BudgetTracker] = None
        
        logger.info("budget_engine_init", budget=self.budget)
    
    def start_run(self) -> BudgetTracker:
        """Start tracking a new run"""
        self._tracker = BudgetTracker(budget=self.budget)
        logger.info("budget_run_started", budget=self.budget)
        return self._tracker
    
    @property
    def tracker(self) -> BudgetTracker:
        """Get current tracker"""
        if self._tracker is None:
            raise RuntimeError("Budget engine not started - call start_run()")
        return self._tracker
    
    def can_make_model_call(self, estimated_tokens: int = 0, estimated_cost: float = 0) -> tuple[bool, str]:
        """
        Check if a model call is allowed within budget.
        
        Returns:
            (allowed, reason)
        """
        if self.tracker.tokens_remaining() < estimated_tokens:
            return False, f"Token budget: {self.tracker.tokens_remaining()} remaining"
        
        if self.tracker.model_calls_remaining() <= 0:
            return False, f"Model call budget: {self.tracker.model_calls_remaining()} remaining"
        
        if self.tracker.cost_remaining_usd() < estimated_cost:
            return False, f"Cost budget: ${self.tracker.cost_remaining_usd():.4f} remaining"
        
        if self.tracker.time_remaining_seconds() <= 0:
            return False, f"Time budget: {self.tracker.time_remaining_seconds():.1f}s remaining"
        
        return True, "OK"
    
    def can_make_tool_call(self) -> tuple[bool, str]:
        """Check if a tool call is allowed"""
        if self.tracker.tool_calls_remaining() <= 0:
            return False, f"Tool call budget: {self.tracker.tool_calls_remaining()} remaining"
        
        if self.tracker.time_remaining_seconds() <= 0:
            return False, f"Time budget: {self.tracker.time_remaining_seconds():.1f}s remaining"
        
        return True, "OK"
    
    def record_model_call(self, input_tokens: int, output_tokens: int, cost_usd: float = 0) -> None:
        """Record a model call"""
        self.tracker.model_calls += 1
        self.tracker.input_tokens += input_tokens
        self.tracker.output_tokens += output_tokens
        self.tracker.tokens_used += input_tokens + output_tokens
        self.tracker.cost_usd += cost_usd
        
        logger.debug(
            "budget_model_call",
            model_calls=self.tracker.model_calls,
            tokens_total=self.tracker.tokens_used,
            cost_usd=self.tracker.cost_usd
        )
    
    def record_tool_call(self) -> None:
        """Record a tool call"""
        self.tracker.tool_calls += 1
        
        logger.debug(
            "budget_tool_call",
            tool_calls=self.tracker.tool_calls
        )
    
    def record_turn(self) -> None:
        """Record a turn"""
        self.tracker.turns += 1
        
        logger.debug(
            "budget_turn",
            turns=self.tracker.turns
        )
    
    def get_status(self) -> Dict[str, Any]:
        """Get current budget status"""
        if self._tracker is None:
            return {"status": "not_started"}
        
        return {
            "budget": {
                "max_tokens": self.budget.max_tokens,
                "max_time_seconds": self.budget.max_time_seconds,
                "max_tool_calls": self.budget.max_tool_calls,
                "max_model_calls": self.budget.max_model_calls,
                "max_cost_usd": self.budget.max_cost_usd,
            },
            "tracker": self.tracker.get_limit_status(),
            "warnings": self.tracker.check_warnings(),
            "is_exhausted": self.tracker.is_exhausted()
        }