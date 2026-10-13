"""小悠当前状态的只读快照。

情绪和关系仍由 emotion.py / relationship.py 持有。
这里只封装读取结果，并记住陪伴层自己的少量字段。
不新建数据表。
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Callable, Mapping

from emotion import get_emotion
from relationship import get_relationship
from time_context import parse_timestamp

ACTIVITIES = ("idle", "chatting", "thinking")
PRESENCE = ("unknown", "present", "away")


def _copy_map(values: Mapping) -> dict:
    return {str(key): values[key] for key in values}


@dataclass(frozen=True)
class CompanionState:
    mood: dict
    relationship: dict
    last_interaction_time: datetime | None = None
    current_activity: str = "idle"
    user_presence: str = "unknown"
    proactive_enabled: bool = True

    def __post_init__(self) -> None:
        if self.current_activity not in ACTIVITIES:
            raise ValueError(f"unknown activity: {self.current_activity}")
        if self.user_presence not in PRESENCE:
            raise ValueError(f"unknown presence: {self.user_presence}")
        object.__setattr__(self, "mood", _copy_map(self.mood))
        object.__setattr__(self, "relationship", _copy_map(self.relationship))

    @classmethod
    def capture(cls, *, conversation_id: int | None = None,
                emotion: Callable[[], Mapping] = get_emotion,
                relationship: Callable[[], Mapping] = get_relationship,
                last_interaction_time: datetime | None = None) -> "CompanionState":
        """从现有模块读情绪和关系。传入 conversation_id 时只查询上次互动，不开启会话计时。"""
        if last_interaction_time is None and conversation_id is not None:
            from .time_awareness import last_interaction
            last_interaction_time = last_interaction(conversation_id)
        return cls(
            mood=dict(emotion()),
            relationship=dict(relationship()),
            last_interaction_time=last_interaction_time,
        )

    def update(self, **changes) -> "CompanionState":
        """更新陪伴层字段。情绪和关系要改仍走原来的 change_* 函数，再用 refresh 读回。"""
        allowed = {"last_interaction_time", "current_activity", "user_presence", "proactive_enabled"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"cannot overwrite source fields: {sorted(unknown)}")
        if "last_interaction_time" in changes and changes["last_interaction_time"] is not None:
            parsed = parse_timestamp(changes["last_interaction_time"])
            if parsed is None:
                raise ValueError("invalid last_interaction_time")
            changes["last_interaction_time"] = parsed
        return replace(self, **changes)

    def refresh(self, *, emotion: Callable[[], Mapping] = get_emotion,
                relationship: Callable[[], Mapping] = get_relationship) -> "CompanionState":
        return replace(self, mood=_copy_map(emotion()), relationship=_copy_map(relationship()))

    def save(self) -> dict:
        """可序列化快照。mood / relationship 只是当时的读数，不是另一套存储。"""
        when = self.last_interaction_time
        return {
            "mood": dict(self.mood),
            "relationship": dict(self.relationship),
            "last_interaction_time": None if when is None else when.isoformat(timespec="seconds"),
            "current_activity": self.current_activity,
            "user_presence": self.user_presence,
            "proactive_enabled": self.proactive_enabled,
        }

    @classmethod
    def load(cls, data: Mapping, *, emotion: Callable[[], Mapping] = get_emotion,
             relationship: Callable[[], Mapping] = get_relationship) -> "CompanionState":
        """恢复陪伴层字段，并重新读取情绪和关系，避免快照盖过原模块。"""
        when = data.get("last_interaction_time")
        return cls(
            mood=dict(emotion()),
            relationship=dict(relationship()),
            last_interaction_time=None if not when else parse_timestamp(when),
            current_activity=str(data.get("current_activity") or "idle"),
            user_presence=str(data.get("user_presence") or "unknown"),
            proactive_enabled=bool(data.get("proactive_enabled", True)),
        )


__all__ = ["CompanionState", "ACTIVITIES", "PRESENCE"]
