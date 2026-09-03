"""
Model Router

Routes tasks to optimal models based on complexity, cost, and capabilities.
As required by MASTER PROMPT Section 15.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import structlog

logger = structlog.get_logger()


class TaskComplexity(Enum):
    TRIVIAL = "trivial"      # Simple factual queries
    LOW = "low"              # Basic reasoning
    MEDIUM = "medium"        # Multi-step reasoning
    HIGH = "high"            # Complex planning/coding
    EXTREME = "extreme"      # Research-level tasks


@dataclass
class ModelCapability:
    name: str
    provider: str
    context_window: int
    cost_per_1k_input: float
    cost_per_1k_output: float
    supports_functions: bool = True
    supports_vision: bool = False
    supports_streaming: bool = True
    max_output_tokens: int = 4096


@dataclass
class RoutingDecision:
    model: str
    provider: str
    complexity: TaskComplexity
    reasoning: str
    estimated_cost: float
    estimated_latency_ms: float


class ModelRouter:
    """
    Routes tasks to optimal models.
    """
    
    # Registry of available models
    MODELS: Dict[str, ModelCapability] = {
        "claude-fable-5-1": ModelCapability(
            name="claude-fable-5-1",
            provider="custom",
            context_window=200000,
            cost_per_1k_input=0.003,
            cost_per_1k_output=0.015,
            supports_functions=True,
            supports_vision=True
        ),
        "claude-sonnet-4-20250514": ModelCapability(
            name="claude-sonnet-4-20250514",
            provider="anthropic",
            context_window=200000,
            cost_per_1k_input=0.003,
            cost_per_1k_output=0.015,
            supports_functions=True,
            supports_vision=True
        ),
        "gpt-4o": ModelCapability(
            name="gpt-4o",
            provider="openai",
            context_window=128000,
            cost_per_1k_input=0.005,
            cost_per_1k_output=0.015,
            supports_functions=True,
            supports_vision=True
        ),
        "gpt-4o-mini": ModelCapability(
            name="gpt-4o-mini",
            provider="openai",
            context_window=128000,
            cost_per_1k_input=0.00015,
            cost_per_1k_output=0.0006,
            supports_functions=True,
            supports_vision=True
        ),
        "o3-mini": ModelCapability(
            name="o3-mini",
            provider="openai",
            context_window=65536,
            cost_per_1k_input=0.00055,
            cost_per_1k_output=0.0022,
            supports_functions=True,
            supports_vision=False
        ),
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._user_preferences: Dict[str, str] = {}
        self._log = structlog.get_logger().bind(component="model_router")
        
        self.default_model = self._config.get("default_model", "claude-fable-5-1")
        self.default_provider = self._config.get("default_provider", "custom")
    
    def route(
        self,
        task: str,
        context_length: int = 0,
        requires_vision: bool = False,
        requires_functions: bool = True,
        user: Optional[str] = None,
        budget: Optional[float] = None
    ) -> RoutingDecision:
        """
        Route a task to the optimal model.
        """
        complexity = self._estimate_complexity(task)
        
        # Check user preference
        if user and user in self._user_preferences:
            preferred = self._user_preferences[user]
            if preferred in self.MODELS:
                model = self.MODELS[preferred]
                if self._model_satisfies(model, requires_vision, requires_functions, context_length):
                    return RoutingDecision(
                        model=preferred,
                        provider=model.provider,
                        complexity=complexity,
                        reasoning=f"User preference: {preferred}",
                        estimated_cost=self._estimate_cost(model, task),
                        estimated_latency_ms=100
                    )
        
        # Budget filtering
        candidates = {
            name: cap for name, cap in self.MODELS.items()
            if self._model_satisfies(cap, requires_vision, requires_functions, context_length)
        }
        
        if budget:
            candidates = {
                name: cap for name, cap in candidates.items()
                if self._estimate_cost(cap, task) <= budget
            }
        
        if not candidates:
            # Fallback to default
            model = self.MODELS[self.default_model]
            return RoutingDecision(
                model=self.default_model,
                provider=self.default_provider,
                complexity=complexity,
                reasoning="Fallback to default (no candidates after filtering)",
                estimated_cost=self._estimate_cost(model, task),
                estimated_latency_ms=200
            )
        
        # Select based on complexity
        if complexity == TaskComplexity.TRIVIAL:
            selected = min(candidates.items(), key=lambda x: x[1].cost_per_1k_input)
        elif complexity == TaskComplexity.LOW:
            selected = min(candidates.items(), key=lambda x: x[1].cost_per_1k_input + x[1].cost_per_1k_output)
        elif complexity in {TaskComplexity.MEDIUM, TaskComplexity.HIGH}:
            selected = min(candidates.items(), key=lambda x: x[1].cost_per_1k_output)
        else:  # EXTREME
            selected = max(candidates.items(), key=lambda x: x[1].context_window)
        
        model_name, model_cap = selected
        return RoutingDecision(
            model=model_name,
            provider=model_cap.provider,
            complexity=complexity,
            reasoning=f"Selected for {complexity.value} complexity",
            estimated_cost=self._estimate_cost(model_cap, task),
            estimated_latency_ms=100
        )
    
    def _estimate_complexity(self, task: str) -> TaskComplexity:
        """Estimate task complexity from description"""
        task_lower = task.lower()
        
        # Trivial indicators
        trivial_keywords = ["what is", "who is", "when did", "define", "lookup"]
        if any(k in task_lower for k in trivial_keywords):
            return TaskComplexity.TRIVIAL
        
        # Low complexity
        low_keywords = ["explain", "summarize", "convert", "translate", "format"]
        if any(k in task_lower for k in low_keywords):
            return TaskComplexity.LOW
        
        # Medium complexity
        medium_keywords = ["compare", "analyze", "find bugs", "review", "plan"]
        if any(k in task_lower for k in medium_keywords):
            return TaskComplexity.MEDIUM
        
        # High complexity
        high_keywords = ["implement", "build", "design", "architect", "create from scratch", "refactor"]
        if any(k in task_lower for k in high_keywords):
            return TaskComplexity.HIGH
        
        # Extreme
        extreme_keywords = ["research", "benchmark", "write paper", "novel algorithm", "develop new"]
        if any(k in task_lower for k in extreme_keywords):
            return TaskComplexity.EXTREME
        
        return TaskComplexity.MEDIUM
    
    def _model_satisfies(
        self,
        model: ModelCapability,
        requires_vision: bool,
        requires_functions: bool,
        context_length: int
    ) -> bool:
        if requires_vision and not model.supports_vision:
            return False
        if requires_functions and not model.supports_functions:
            return False
        if context_length > model.context_window:
            return False
        return True
    
    def _estimate_cost(self, model: ModelCapability, task: str) -> float:
        input_tokens = len(task) // 4
        estimated_output = len(task) // 2
        return (input_tokens / 1000) * model.cost_per_1k_input + (estimated_output / 1000) * model.cost_per_1k_output
    
    def set_user_preference(self, user: str, model: str) -> None:
        self._user_preferences[user] = model
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": m.name,
                "provider": m.provider,
                "context_window": m.context_window,
                "cost_input": m.cost_per_1k_input,
                "cost_output": m.cost_per_1k_output,
                "supports_vision": m.supports_vision,
                "supports_functions": m.supports_functions
            }
            for m in self.MODELS.values()
        ]