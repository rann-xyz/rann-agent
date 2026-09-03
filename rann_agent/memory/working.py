"""
Working Memory

Short-term conversational memory for current session.
As required by MASTER PROMPT Section 25.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
import structlog

logger = structlog.get_logger()


@dataclass
class WorkingMemoryItem:
    """A single item in working memory"""
    key: str
    value: Any
    created_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorkingMemory:
    """
    Short-term memory for current conversation/session.
    - Key-value store with TTL
    - LRU eviction when capacity reached
    - Access tracking for relevance
    """
    
    def __init__(self, max_items: int = 1000, default_ttl_seconds: int = 3600):
        self._items: Dict[str, WorkingMemoryItem] = {}
        self._max_items = max_items
        self._default_ttl = default_ttl_seconds
        self._log = structlog.get_logger().bind(component="working_memory")
    
    def store(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Store a value in working memory"""
        if len(self._items) >= self._max_items and key not in self._items:
            self._evict_lru()
        
        self._items[key] = WorkingMemoryItem(
            key=key,
            value=value,
            metadata={"ttl": ttl_seconds or self._default_ttl}
        )
        self._log.debug("working_memory_store", key=key)
    
    def recall(self, key: str) -> Optional[Any]:
        """Recall a value from working memory"""
        item = self._items.get(key)
        if not item:
            return None
        
        item.access_count += 1
        item.last_accessed = datetime.now()
        return item.value
    
    def forget(self, key: str) -> bool:
        """Remove a value from working memory"""
        if key in self._items:
            del self._items[key]
            return True
        return False
    
    def update(self, key: str, value: Any) -> bool:
        """Update existing value"""
        if key in self._items:
            self._items[key].value = value
            self._items[key].last_accessed = datetime.now()
            return True
        return False
    
    def clear(self) -> None:
        """Clear all working memory"""
        self._items.clear()
        self._log.info("working_memory_cleared")
    
    def keys(self) -> List[str]:
        return list(self._items.keys())
    
    def items(self) -> List[tuple]:
        return [(k, v.value) for k, v in self._items.items()]
    
    def _evict_lru(self) -> None:
        """Evict least recently accessed item"""
        if not self._items:
            return
        
        lru_key = min(
            self._items.keys(),
            key=lambda k: self._items[k].last_accessed
        )
        del self._items[lru_key]
        self._log.debug("working_memory_evicted", key=lru_key)
    
    def get_recent(self, n: int = 10) -> List[Any]:
        """Get n most recently accessed items"""
        sorted_items = sorted(
            self._items.values(),
            key=lambda x: x.last_accessed,
            reverse=True
        )
        return [item.value for item in sorted_items[:n]]
    
    def search(self, query: str) -> List[Any]:
        """Search for items containing query in key or value"""
        results = []
        query_lower = query.lower()
        for item in self._items.values():
            if query_lower in item.key.lower():
                results.append(item.value)
            elif isinstance(item.value, str) and query_lower in item.value.lower():
                results.append(item.value)
        return results
    
    def stats(self) -> Dict[str, Any]:
        return {
            "total_items": len(self._items),
            "max_items": self._max_items,
            "total_accesses": sum(i.access_count for i in self._items.values()),
            "oldest_item": min((i.created_at for i in self._items.values()), default=None),
            "most_accessed": max(
                [(k, v.access_count) for k, v in self._items.items()],
                default=(None, 0),
                key=lambda x: x[1]
            )[0]
        }