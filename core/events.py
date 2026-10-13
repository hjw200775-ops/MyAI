"""Companion 事件。只记录事实，不改 UI，也不调用模型。"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import Lock
from typing import Any

from time_context import local_now


class CompanionEventKind(str, Enum):
    USER_MESSAGE = "user_message"
    APP_START = "app_start"
    TIME_CHANGED = "time_changed"
    LONG_ABSENCE = "long_absence"
    MEMORY_UPDATED = "memory_updated"


@dataclass(frozen=True)
class CompanionEvent:
    kind: CompanionEventKind
    created_at: datetime
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, kind: CompanionEventKind | str, payload: dict | None = None,
               created_at: datetime | None = None) -> "CompanionEvent":
        return cls(CompanionEventKind(kind), created_at or local_now(), dict(payload or {}))


class EventLog:
    """进程内队列。publish 可来自控制层；consume 只在主线程取走。"""

    def __init__(self) -> None:
        self._items: deque[CompanionEvent] = deque()
        self._lock = Lock()

    def publish(self, event: CompanionEvent) -> CompanionEvent:
        if not isinstance(event, CompanionEvent):
            raise TypeError("expected CompanionEvent")
        with self._lock:
            self._items.append(event)
        return event

    def consume(self) -> CompanionEvent | None:
        with self._lock:
            if not self._items:
                return None
            return self._items.popleft()

    def pending(self) -> int:
        with self._lock:
            return len(self._items)


__all__ = ["CompanionEvent", "CompanionEventKind", "EventLog"]
