"""主动开口的决策。只返回建议，不发送、不启动计时器、不改时间线状态。

已有的 ProactiveTimelineService 继续负责待办的延期和取消。
这里即使看到到期事项，也不会把它当成可以发送的许可。
"""
from __future__ import annotations

from dataclasses import dataclass

from .companion_state import CompanionState
from .time_awareness import LONG_ABSENCE_SECONDS, TimeAwareness

RECENT_SECONDS = 5 * 60


@dataclass(frozen=True)
class ProactiveDecision:
    should_reply: bool
    reason: str


class ProactiveManager:
    def __init__(self, *, recent_seconds: int = RECENT_SECONDS,
                 long_absence_seconds: int = LONG_ABSENCE_SECONDS):
        self.recent_seconds = recent_seconds
        self.long_absence_seconds = long_absence_seconds

    def decide(self, state: CompanionState, awareness: TimeAwareness, *,
               scheduled_due: int = 0) -> ProactiveDecision:
        if not state.proactive_enabled:
            return ProactiveDecision(False, "主动陪伴已关闭")
        if state.current_activity == "chatting":
            return ProactiveDecision(False, "用户正在对话")
        elapsed = awareness.elapsed_seconds
        if elapsed is None:
            return ProactiveDecision(False, "还没有互动记录")
        if elapsed < self.recent_seconds:
            return ProactiveDecision(False, "用户刚刚离开不到5分钟")
        if elapsed >= self.long_absence_seconds:
            # scheduled_due 只说明时间线上有候选，不能单独把 should_reply 设为真。
            return ProactiveDecision(True, "用户12小时未互动")
        if scheduled_due:
            return ProactiveDecision(False, "时间线上有待复核事项，但间隔还不够长")
        return ProactiveDecision(False, "间隔还不够长，先不主动开口")


__all__ = ["ProactiveDecision", "ProactiveManager", "RECENT_SECONDS"]
