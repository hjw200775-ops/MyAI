"""时间事实。只描述现在和上次互动，不生成要发送的话。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from time_context import describe_duration, elapsed, get_time_period, local_now, parse_timestamp

LONG_ABSENCE_SECONDS = 12 * 3600
OVERNIGHT_LIMIT_SECONDS = 36 * 3600


@dataclass(frozen=True)
class TimeAwareness:
    now: datetime
    last_seen: datetime | None
    elapsed_seconds: int | None
    current_period: str
    gap_kind: str
    fact: str

    @property
    def time(self) -> str:
        return self.now.strftime("%H:%M")

    @property
    def date(self) -> str:
        return self.now.strftime("%Y-%m-%d")


def last_interaction(conversation_id: int) -> datetime | None:
    """读现有消息时间。不调用 TimeContextService.capture，因此不会把会话开始提前到启动时刻。"""
    from memory import load_temporal_history
    latest, _local = load_temporal_history(conversation_id)
    return parse_timestamp(latest)


def observe(conversation_id: int | None = None, *, now: datetime | None = None,
            last_seen: datetime | None = None, clock=None) -> TimeAwareness:
    moment = parse_timestamp(now if now is not None else (clock or local_now)())
    if moment is None:
        raise ValueError("invalid clock")
    if last_seen is None and conversation_id is not None:
        seen = last_interaction(conversation_id)
    else:
        seen = parse_timestamp(last_seen) if last_seen is not None else None
    seconds = elapsed(moment, seen)
    kind = _gap_kind(seen, moment, seconds)
    return TimeAwareness(moment, seen, seconds, get_time_period(moment.hour), kind,
                         _fact(seen, moment, seconds, kind))


def _gap_kind(last: datetime | None, now: datetime, seconds: int | None) -> str:
    if last is None or seconds is None:
        return "unknown"
    if (now.date() - last.date()).days == 1 and seconds < OVERNIGHT_LIMIT_SECONDS:
        return "overnight"
    if seconds >= LONG_ABSENCE_SECONDS:
        return "long"
    if seconds < 5 * 60:
        return "recent"
    return "same_stretch"


def _day_label(moment: datetime, today) -> str:
    if moment.date() == today:
        return "今天"
    if moment.date() == today - timedelta(days=1):
        return "昨天"
    return moment.strftime("%Y-%m-%d")


def _fact(last: datetime | None, now: datetime, seconds: int | None, kind: str) -> str:
    current = f"现在：{_day_label(now, now.date())} {now.strftime('%H:%M')}"
    if last is None:
        return current + "；还没有互动记录"
    previous = f"上次互动：{_day_label(last, now.date())} {last.strftime('%H:%M')}"
    if kind == "overnight":
        gap = "隔了一夜"
    else:
        gap = describe_duration(seconds)
    return f"{previous}；{current}；间隔：{gap}"


__all__ = ["TimeAwareness", "observe", "last_interaction", "LONG_ABSENCE_SECONDS"]
