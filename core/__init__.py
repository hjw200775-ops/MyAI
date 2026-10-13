"""Companion core。UI 只通过 Controller 使用这里，不直接碰数据库或模型。"""

from .companion_state import CompanionState
from .events import CompanionEvent, CompanionEventKind, EventLog
from .proactive import ProactiveDecision, ProactiveManager
from .time_awareness import TimeAwareness, observe

__all__ = [
    "CompanionState",
    "CompanionEvent",
    "CompanionEventKind",
    "EventLog",
    "ProactiveDecision",
    "ProactiveManager",
    "TimeAwareness",
    "observe",
]
