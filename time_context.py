"""Offline local-clock facts, independent of all model providers.

Sessions mean the first valid input in this process for each conversation.
Historical interaction timestamps remain in the existing SQLite messages table.
"""
from dataclasses import dataclass
from datetime import datetime
from threading import RLock


def local_now():
    return datetime.now().astimezone()


def parse_timestamp(value):
    try:
        result = value if isinstance(value, datetime) else datetime.fromisoformat(value)
        return result.astimezone()  # Legacy naive timestamps use OS local timezone.
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def get_time_period(hour):
    for low, high, name in ((5, 9, '清晨'), (9, 12, '上午'), (12, 14, '中午'),
                            (14, 18, '下午'), (18, 23, '晚上')):
        if low <= hour < high:
            return name
    return '深夜'


def elapsed(now, previous):
    previous = parse_timestamp(previous)
    return None if previous is None else max(0, int(now.timestamp() - previous.timestamp()))


def describe_duration(seconds):
    if seconds is None:
        return '未知（无历史或时间戳不可用）'
    if seconds < 60:
        return '不足1分钟'
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    return '约' + (f'{days}天' if days else '') + (f'{hours}小时' if hours else '') + (f'{minutes}分钟' if minutes else '')


@dataclass(frozen=True)
class TemporalContext:
    current_datetime: datetime
    last_interaction: datetime | None
    idle_duration: int | None
    last_message_duration: int | None
    session_started_at: datetime
    session_duration: int

    @property
    def current_period(self):
        return get_time_period(self.current_datetime.hour)

    @property
    def date(self):
        return self.current_datetime.strftime('%Y-%m-%d')

    @property
    def time(self):
        return self.current_datetime.strftime('%H:%M:%S')

    @property
    def weekday(self):
        return self.current_datetime.weekday()

    @property
    def hour(self):
        return self.current_datetime.hour

    def to_prompt(self):
        return (f'当前本机日期：{self.date}\n当前时间：{self.time}\n'
                f'星期：星期{"一二三四五六日"[self.weekday]}\n小时：{self.hour}\n'
                f'当前时段：{self.current_period}\n'
                f'距当前消息之前的上一次有效用户互动：{describe_duration(self.idle_duration)}\n'
                f'距本会话上一条用户消息：{describe_duration(self.last_message_duration)}\n'
                f'本次会话开始：{self.session_started_at.isoformat(timespec="seconds")}\n'
                f'本次会话持续：{describe_duration(self.session_duration)}\n'
                '时间来自操作系统本地时钟，间隔已由 Python 计算。时间是环境事实；'
                '仅在问候、作息、久别或当前话题相关时自然使用，不要每条回复机械报时，'
                '不要自行做日期算术或把未知间隔说成久别。系统时间倒退时差归零。')


class TimeContextService:
    def __init__(self, clock=None):
        self.clock = clock or local_now
        self._sessions = {}
        self._lock = RLock()

    def capture(self, conversation_id):
        """Call BEFORE saving the current input; snapshot survives provider switches."""
        from memory import load_temporal_history
        now = parse_timestamp(self.clock()) or local_now()
        with self._lock:
            started = self._sessions.setdefault(conversation_id, now)
        try:
            last_global, last_local = load_temporal_history(conversation_id)
        except Exception:
            # Optional environmental context must not break an otherwise valid chat.
            last_global = last_local = None
        return TemporalContext(now, parse_timestamp(last_global), elapsed(now, last_global),
                               elapsed(now, last_local), started, elapsed(now, started) or 0)


default_time_service = TimeContextService()
