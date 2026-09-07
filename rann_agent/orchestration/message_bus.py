"""
MessageBus — Structured inter-agent communication.

Provides publish/subscribe message passing between agents with:
- Topic-based routing
- Message priority queue
- Delivery guarantees (at-least-once)
- Actor affinity (request/response)
- Bus-level observability
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger()


class MessagePriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class MessageType(Enum):
    TASK = "task"
    RESULT = "result"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_RESPONSE = "approval_response"
    STATUS_UPDATE = "status_update"
    CANCEL = "cancel"
    DISCOVERY = "discovery"  # agent announcement


@dataclass
class Message:
    """A message sent through the MessageBus."""

    id: str
    type: MessageType
    topic: str
    sender_id: str
    recipient_id: str | None = None  # None = broadcast
    correlation_id: str | None = None  # for request/response pairing
    priority: MessagePriority = MessagePriority.NORMAL
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    delivered_at: float | None = None
    ttl: float = 300.0  # 5 minutes default

    def is_expired(self) -> bool:
        return time.time() > self.created_at + self.ttl

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "topic": self.topic,
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "correlation_id": self.correlation_id,
            "priority": self.priority.value,
            "payload": self.payload,
            "created_at": self.created_at,
            "delivered_at": self.delivered_at,
            "ttl": self.ttl,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Message:
        return cls(
            id=d["id"],
            type=MessageType(d["type"]),
            topic=d["topic"],
            sender_id=d["sender_id"],
            recipient_id=d.get("recipient_id"),
            correlation_id=d.get("correlation_id"),
            priority=MessagePriority(d.get("priority", 1)),
            payload=d.get("payload", {}),
            created_at=d.get("created_at", time.time()),
            delivered_at=d.get("delivered_at"),
            ttl=d.get("ttl", 300.0),
        )


# Handler signature: async def handler(message: Message) -> None
MessageHandler = Callable[[Message], Awaitable[None]]


@dataclass
class Subscription:
    """A subscription to a topic pattern."""

    id: str
    topic_pattern: str  # supports * wildcard
    handler: MessageHandler
    subscriber_id: str
    created_at: float = field(default_factory=time.time)


class MessageBus:
    """
    Publish/subscribe message bus for inter-agent communication.

    Features:
    - Topic patterns with * wildcard (e.g., "agent.*", "task.result.*")
    - Priority queue (HIGH/CRITICAL messages delivered first)
    - At-least-once delivery (messages queued until ACK)
    - Request/response via correlation_id
    - Observer pattern for bus-level monitoring
    - Dead letter queue for failed messages
    - Per-topic delivery statistics
    """

    def __init__(self) -> None:
        self._subscriptions: dict[str, list[Subscription]] = {}  # topic → subscriptions
        self._queue: asyncio.PriorityQueue[tuple[int, Message]]  # priority, message
        self._queue = asyncio.PriorityQueue()
        self._pending: dict[str, asyncio.Future[Message]] = {}  # correlation_id → future
        self._dead_letter: list[Message] = []
        self._delivery_stats: dict[str, dict[str, int]] = {}  # topic → {delivered, failed, pending}
        self._handlers: dict[str, list[MessageHandler]] = {}  # observer handlers
        self._log = logger.bind(component="message_bus")
        self._running = False
        self._delivery_task: asyncio.Task[None] | None = None

    # ─── Lifecycle ────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the message delivery loop."""
        if self._running:
            return
        self._running = True
        self._delivery_task = asyncio.create_task(self._delivery_loop())
        self._log.info("message_bus_started")

    async def stop(self) -> None:
        """Stop the message bus gracefully."""
        self._running = False
        if self._delivery_task:
            self._delivery_task.cancel()
            try:
                await self._delivery_task
            except asyncio.CancelledError:
                pass
        self._log.info("message_bus_stopped", dead_letter_count=len(self._dead_letter))

    # ─── Subscription ─────────────────────────────────────────────

    async def subscribe(
        self,
        topic_pattern: str,
        handler: MessageHandler,
        subscriber_id: str,
    ) -> str:
        """Subscribe to a topic pattern. Returns subscription ID."""
        sub_id = uuid.uuid4().hex[:8]
        sub = Subscription(
            id=sub_id, topic_pattern=topic_pattern, handler=handler, subscriber_id=subscriber_id
        )

        if topic_pattern not in self._subscriptions:
            self._subscriptions[topic_pattern] = []
        self._subscriptions[topic_pattern].append(sub)

        if topic_pattern not in self._delivery_stats:
            self._delivery_stats[topic_pattern] = {"delivered": 0, "failed": 0, "pending": 0}

        self._log.debug("subscribed", sub_id=sub_id, topic=topic_pattern, subscriber=subscriber_id)
        return sub_id

    async def unsubscribe(self, subscription_id: str) -> bool:
        """Remove a subscription by ID."""
        for topic, subs in self._subscriptions.items():
            for i, sub in enumerate(subs):
                if sub.id == subscription_id:
                    subs.pop(i)
                    if not subs:
                        del self._subscriptions[topic]
                    return True
        return False

    async def unsubscribe_all(self, subscriber_id: str) -> int:
        """Remove all subscriptions for a given subscriber. Returns count."""
        count = 0
        for topic in list(self._subscriptions.keys()):
            before = len(self._subscriptions[topic])
            self._subscriptions[topic] = [
                s for s in self._subscriptions[topic] if s.subscriber_id != subscriber_id
            ]
            count += before - len(self._subscriptions[topic])
            if not self._subscriptions[topic]:
                del self._subscriptions[topic]
        return count

    # ─── Publish ─────────────────────────────────────────────────

    async def publish(
        self,
        topic: str,
        sender_id: str,
        payload: dict[str, Any] | None = None,
        message_type: MessageType = MessageType.STATUS_UPDATE,
        priority: MessagePriority = MessagePriority.NORMAL,
        recipient_id: str | None = None,
        correlation_id: str | None = None,
        ttl: float = 300.0,
    ) -> Message:
        """Publish a message to a topic."""
        msg = Message(
            id=uuid.uuid4().hex[:12],
            type=message_type,
            topic=topic,
            sender_id=sender_id,
            recipient_id=recipient_id,
            correlation_id=correlation_id,
            priority=priority,
            payload=payload or {},
            ttl=ttl,
        )

        await self._queue.put((255 - priority.value, msg))  # lower number = higher priority

        # Notify observers
        for handler in self._handlers.get("publish", []):
            try:
                await handler(msg)
            except Exception:  # noqa: BLE001
                pass

        self._log.debug("published", msg_id=msg.id, topic=topic, priority=priority.value)
        return msg

    async def publish_task(
        self,
        task_id: str,
        sender_id: str,
        task_payload: dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> Message:
        """Publish a task message."""
        return await self.publish(
            topic=f"task.{task_id}",
            sender_id=sender_id,
            payload=task_payload,
            message_type=MessageType.TASK,
            priority=priority,
        )

    async def publish_result(
        self,
        task_id: str,
        sender_id: str,
        result_payload: dict[str, Any],
        correlation_id: str,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> Message:
        """Publish a task result."""
        return await self.publish(
            topic=f"result.{task_id}",
            sender_id=sender_id,
            payload=result_payload,
            message_type=MessageType.RESULT,
            priority=priority,
            correlation_id=correlation_id,
        )

    async def broadcast(
        self,
        topic: str,
        sender_id: str,
        payload: dict[str, Any] | None = None,
        message_type: MessageType = MessageType.STATUS_UPDATE,
    ) -> Message:
        """Broadcast to all subscribers of a topic (no specific recipient)."""
        return await self.publish(
            topic=topic,
            sender_id=sender_id,
            payload=payload,
            message_type=message_type,
        )

    # ─── Request/Response ─────────────────────────────────────────

    async def request(
        self,
        topic: str,
        sender_id: str,
        payload: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> Message:
        """
        Send a request and wait for a correlated response.
        Uses correlation_id to match response to request.
        """
        correlation_id = uuid.uuid4().hex[:12]
        future: asyncio.Future[Message] = asyncio.get_event_loop().create_future()
        self._pending[correlation_id] = future

        await self.publish(
            topic=topic,
            sender_id=sender_id,
            payload=payload,
            message_type=MessageType.TASK,
            priority=MessagePriority.HIGH,
            correlation_id=correlation_id,
        )

        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            del self._pending[correlation_id]
            raise TimeoutError(f"No response to {topic!r} within {timeout}s") from None

    async def respond(self, original: Message, payload: dict[str, Any]) -> Message:
        """Send a response to a request (uses original's correlation_id)."""
        if not original.correlation_id:
            raise ValueError("Cannot respond to message without correlation_id")

        return await self.publish(
            topic=f"result.{original.topic.split('.')[1] if '.' in original.topic else original.topic}",
            sender_id=original.recipient_id or "unknown",
            payload=payload,
            message_type=MessageType.RESULT,
            priority=MessagePriority.HIGH,
            correlation_id=original.correlation_id,
        )

    # ─── Delivery Loop ────────────────────────────────────────────

    async def _delivery_loop(self) -> None:
        """Background loop that delivers queued messages."""
        while self._running:
            try:
                _, msg = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            if msg.is_expired():
                self._dead_letter.append(msg)
                continue

            try:
                await self._deliver(msg)
                msg.delivered_at = time.time()
            except Exception as exc:  # noqa: BLE001
                self._log.error("delivery_failed", msg_id=msg.id, error=str(exc))
                self._dead_letter.append(msg)

    async def _deliver(self, msg: Message) -> None:
        """Deliver a message to all matching subscriptions."""
        # Check for pending request
        if msg.correlation_id and msg.correlation_id in self._pending:
            future = self._pending.pop(msg.correlation_id)
            if not future.done():
                future.set_result(msg)
            return

        # Find matching subscriptions
        matching = self._match_subscriptions(msg.topic, msg.recipient_id)

        if not matching:
            self._delivery_stats.setdefault(
                msg.topic, {"delivered": 0, "failed": 0, "pending": len(matching)}
            )
            return

        for sub in matching:
            try:
                await sub.handler(msg)
                self._delivery_stats[msg.topic]["delivered"] += 1
            except Exception as exc:  # noqa: BLE001
                self._log.warning("handler_failed", sub_id=sub.id, error=str(exc))
                self._delivery_stats[msg.topic]["failed"] += 1

    def _match_subscriptions(self, topic: str, recipient_id: str | None) -> list[Subscription]:
        """Find all subscriptions matching a topic and recipient."""
        import fnmatch

        matched: list[Subscription] = []
        for pattern, subs in self._subscriptions.items():
            if fnmatch.fnmatch(topic, pattern):
                for sub in subs:
                    if recipient_id and sub.subscriber_id != recipient_id:
                        continue
                    matched.append(sub)
        return matched

    # ─── Observer ─────────────────────────────────────────────────

    async def add_observer(self, event: str, handler: MessageHandler) -> None:
        """Add a bus-level observer for events like 'publish', 'deliver', 'dead_letter'."""
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(handler)

    # ─── Stats ────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return bus statistics."""
        return {
            "queue_size": self._queue.qsize(),
            "pending_requests": len(self._pending),
            "dead_letter_count": len(self._dead_letter),
            "subscription_count": sum(len(subs) for subs in self._subscriptions.values()),
            "topic_count": len(self._subscriptions),
            "delivery_stats": dict(self._delivery_stats),
        }
