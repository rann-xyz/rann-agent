"""
Tool Registry with full CRUD for RANN Agent.
Complete tool registration, discovery, enable/disable, metadata management.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import structlog

logger = structlog.get_logger()


class ToolStatus(Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    BETA = "beta"
    DEPRECATED = "deprecated"


@dataclass
class ToolMetadata:
    name: str
    description: str
    category: str
    version: str = "1.0.0"
    author: str = ""
    tags: List[str] = field(default_factory=list)
    status: ToolStatus = ToolStatus.ENABLED
    capabilities: List[str] = field(default_factory=list)
    input_schema: Optional[Dict] = None
    output_schema: Optional[Dict] = None
    risk_level: str = "low"  # low, medium, high, critical
    requires_approval: bool = False
    rate_limit: Optional[int] = None  # calls per minute
    timeout_seconds: int = 60
    created_at: str = ""
    updated_at: str = ""
    call_count: int = 0
    failure_count: int = 0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: Dict) -> "ToolMetadata":
        data = dict(data)
        if "status" in data and isinstance(data["status"], str):
            data["status"] = ToolStatus(data["status"])
        return cls(**data)


@dataclass
class ToolRegistration:
    metadata: ToolMetadata
    handler: Callable
    schema_version: str = "1.0"


class ToolRegistry:
    """Central tool registry with CRUD operations, persistence, and discovery."""

    def __init__(self, registry_path: Optional[Path] = None):
        if registry_path is None:
            registry_path = Path.home() / ".rann-agent" / "tool_registry.json"
        self.registry_path = Path(registry_path)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self._tools: Dict[str, ToolRegistration] = {}
        self._load()

    def _load(self) -> None:
        """Load registry from disk."""
        if not self.registry_path.exists():
            return
        try:
            with open(self.registry_path) as f:
                data = json.load(f)
            for name, reg_data in data.items():
                if "handler" in reg_data:
                    del reg_data["handler"]  # Can't serialize functions
                self._tools[name] = ToolRegistration(
                    metadata=ToolMetadata.from_dict(reg_data.get("metadata", {})),
                    handler=None,  # Handler must be re-registered
                    schema_version=reg_data.get("schema_version", "1.0")
                )
            logger.info("tool_registry_loaded", count=len(self._tools))
        except Exception as e:
            logger.warning("tool_registry_load_failed", error=str(e))

    def _save(self) -> None:
        """Persist registry to disk."""
        data = {}
        for name, reg in self._tools.items():
            d = reg.metadata.to_dict()
            d["schema_version"] = reg.schema_version
            data[name] = d
        with open(self.registry_path, "w") as f:
            json.dump(data, f, indent=2)

    # === CRUD Operations ===

    def register(
        self,
        name: str,
        handler: Callable,
        description: str,
        category: str = "general",
        **kwargs
    ) -> ToolMetadata:
        """Register a new tool."""
        if name in self._tools:
            raise ValueError(f"Tool already registered: {name}")

        metadata = ToolMetadata(name=name, description=description, category=category, **kwargs)
        self._tools[name] = ToolRegistration(metadata=metadata, handler=handler)
        self._save()
        logger.info("tool_registered", name=name, category=category)
        return metadata

    def unregister(self, name: str) -> bool:
        """Remove a tool from the registry."""
        if name not in self._tools:
            return False
        del self._tools[name]
        self._save()
        logger.info("tool_unregistered", name=name)
        return True

    def get(self, name: str) -> Optional[ToolMetadata]:
        """Get tool metadata."""
        reg = self._tools.get(name)
        return reg.metadata if reg else None

    def get_handler(self, name: str) -> Optional[Callable]:
        """Get tool handler."""
        reg = self._tools.get(name)
        return reg.handler if reg else None

    def update(self, name: str, **updates) -> Optional[ToolMetadata]:
        """Update tool metadata."""
        reg = self._tools.get(name)
        if not reg:
            return None
        for key, value in updates.items():
            if hasattr(reg.metadata, key):
                setattr(reg.metadata, key, value)
        reg.metadata.updated_at = datetime.utcnow().isoformat()
        self._save()
        logger.info("tool_updated", name=name, updates=list(updates.keys()))
        return reg.metadata

    def list_all(self) -> List[ToolMetadata]:
        """List all registered tools."""
        return [r.metadata for r in self._tools.values()]

    def list_enabled(self) -> List[ToolMetadata]:
        """List enabled tools."""
        return [r.metadata for r in self._tools.values() if r.metadata.status == ToolStatus.ENABLED]

    def list_disabled(self) -> List[ToolMetadata]:
        """List disabled tools."""
        return [r.metadata for r in self._tools.values() if r.metadata.status == ToolStatus.DISABLED]

    def list_by_category(self, category: str) -> List[ToolMetadata]:
        """List tools by category."""
        return [r.metadata for r in self._tools.values() if r.metadata.category == category]

    def list_beta(self) -> List[ToolMetadata]:
        """List beta tools."""
        return [r.metadata for r in self._tools.values() if r.metadata.status == ToolStatus.BETA]

    # === Status Management ===

    def enable(self, name: str) -> bool:
        """Enable a tool."""
        return self.update(name, status=ToolStatus.ENABLED) is not None

    def disable(self, name: str) -> bool:
        """Disable a tool."""
        return self.update(name, status=ToolStatus.DISABLED) is not None

    def deprecate(self, name: str, replacement: Optional[str] = None) -> bool:
        """Mark a tool as deprecated."""
        meta = self.get(name)
        if not meta:
            return False
        self.update(name, status=ToolStatus.DEPRECATED)
        logger.warning("tool_deprecated", name=name, replacement=replacement)
        return True

    def mark_beta(self, name: str) -> bool:
        """Mark a tool as beta."""
        return self.update(name, status=ToolStatus.BETA) is not None

    # === Discovery ===

    def search(self, query: str) -> List[ToolMetadata]:
        """Search tools by name, description, or tags."""
        q = query.lower()
        results = []
        for reg in self._tools.values():
            m = reg.metadata
            if (q in m.name.lower() or q in m.description.lower() or
                q in m.category.lower() or any(q in t.lower() for t in m.tags)):
                results.append(m)
        return results

    def has(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    def is_enabled(self, name: str) -> bool:
        """Check if a tool is enabled."""
        meta = self.get(name)
        return meta is not None and meta.status == ToolStatus.ENABLED

    # === Usage Tracking ===

    def record_call(self, name: str, success: bool) -> None:
        """Record a tool call."""
        reg = self._tools.get(name)
        if not reg:
            return
        reg.metadata.call_count += 1
        if not success:
            reg.metadata.failure_count += 1
        reg.metadata.updated_at = datetime.utcnow().isoformat()
        self._save()

    def get_stats(self, name: str) -> Optional[Dict[str, Any]]:
        """Get usage statistics for a tool."""
        meta = self.get(name)
        if not meta:
            return None
        failure_rate = meta.failure_count / meta.call_count if meta.call_count > 0 else 0.0
        return {
            "name": meta.name,
            "call_count": meta.call_count,
            "failure_count": meta.failure_count,
            "failure_rate": round(failure_rate, 3),
            "last_updated": meta.updated_at,
            "status": meta.status.value
        }

    def top_by_usage(self, limit: int = 10) -> List[ToolMetadata]:
        """Get most-used tools."""
        return sorted(
            [r.metadata for r in self._tools.values() if r.metadata.call_count > 0],
            key=lambda m: m.call_count,
            reverse=True
        )[:limit]

    def recently_added(self, limit: int = 10) -> List[ToolMetadata]:
        """Get recently added tools."""
        return sorted(
            [r.metadata for r in self._tools.values()],
            key=lambda m: m.created_at,
            reverse=True
        )[:limit]

    # === Bulk Operations ===

    def bulk_register(self, tools: List[Dict[str, Any]]) -> List[str]:
        """Bulk register tools. Returns list of registered names."""
        registered = []
        for tool_spec in tools:
            name = tool_spec.get("name")
            handler = tool_spec.get("handler")
            if not name or not handler:
                continue
            try:
                self.register(name, handler, **tool_spec)
                registered.append(name)
            except ValueError:
                pass  # Already registered
        return registered

    def clear(self) -> int:
        """Clear all tools. Returns count removed."""
        count = len(self._tools)
        self._tools.clear()
        self._save()
        return count

    def export_schema(self) -> Dict[str, Any]:
        """Export tool schemas for LLM consumption."""
        return {
            "tools": [
                {
                    "name": m.name,
                    "description": m.description,
                    "category": m.category,
                    "input_schema": m.input_schema,
                    "output_schema": m.output_schema,
                    "risk_level": m.risk_level,
                    "requires_approval": m.requires_approval,
                }
                for m in self.list_enabled()
            ]
        }