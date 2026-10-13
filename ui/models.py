"""UI 层消息模型。

数据库 messages.role 仍只允许 'user' / 'assistant'（memory.py 的 CHECK 约束不变）。
PROACTIVE / SYSTEM 只是展示层分类：
- PROACTIVE 预留给 V1.7 主动对话，本版不会产生；
- SYSTEM 用于不入库的临时提示（错误、「已记住」、问候占位）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class MessageKind(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    PROACTIVE = "proactive"
    SYSTEM = "system"

    @classmethod
    def from_role(cls, role: object) -> "MessageKind":
        return cls.USER if str(role or "").lower() == "user" else cls.ASSISTANT


@dataclass(frozen=True)
class MessageItem:
    """视图渲染用的一条消息；由数据库记录或临时提示构造。"""

    kind: MessageKind
    content: str = ""
    image_name: str | None = None     # 托管图片文件名（与 messages.image_path 一致）
    created_at: str | None = None
    message_id: int | None = None     # 临时消息为 None
    persisted: bool = True            # False 表示未写入数据库的临时提示

    @classmethod
    def from_record(cls, row: Mapping[str, Any]) -> "MessageItem":
        return cls(
            kind=MessageKind.from_role(row.get("role")),
            content=str(row.get("content") or ""),
            image_name=row.get("image_path") or None,
            created_at=row.get("created_at"),
            message_id=row.get("id"),
            persisted=True,
        )

    @classmethod
    def system(cls, content: str) -> "MessageItem":
        return cls(kind=MessageKind.SYSTEM, content=content, persisted=False)

    @classmethod
    def transient_assistant(cls, content: str) -> "MessageItem":
        """API 失败时的提示文案：原逻辑以「小悠：」前缀展示但不入库。"""
        return cls(kind=MessageKind.ASSISTANT, content=content, persisted=False)


@dataclass(frozen=True)
class ReplyEvent:
    """一次前台请求的结果（对应原 result_queue 四元组）。"""

    conversation_id: int
    reply: str
    saved_memory: str | None = None
    persisted: bool = False           # 回复是否已作为 assistant 消息写入数据库


@dataclass(frozen=True)
class BackgroundEvent:
    """后台标题 / 记忆分析结果（对应原 background_result_queue 三元组）。"""

    conversation_id: int
    saved_memory: str | None = None
    generated_title: str | None = None


@dataclass(frozen=True)
class ConnectionCheckEvent:
    """Ollama 连接检查结果；draft 用于让 UI 忽略已过期的检查。"""

    draft: Any
    message: str


@dataclass(frozen=True)
class ConversationItem:
    id: int
    title: str
    created_at: str
    updated_at: str
    selected: bool = False


@dataclass(frozen=True)
class MemoryItem:
    id: int
    content: str
    category: str
    category_label: str
    created_at: str | None = None
    updated_at: str | None = None


MEMORY_CATEGORY_LABELS: dict[str, str] = {
    "identity": "身份", "interest": "兴趣", "study": "学习", "work": "工作",
    "goal": "目标", "preference": "偏好", "relationship": "关系", "other": "其他",
}


@dataclass
class PollResult:
    """一次轮询取出的全部事件；视图按需处理。"""

    replies: list[ReplyEvent] = field(default_factory=list)
    background: list[BackgroundEvent] = field(default_factory=list)
    connection_checks: list[ConnectionCheckEvent] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.replies or self.background or self.connection_checks)


__all__ = [
    "MessageKind", "MessageItem", "ReplyEvent", "BackgroundEvent",
    "ConnectionCheckEvent", "ConversationItem", "MemoryItem",
    "MEMORY_CATEGORY_LABELS", "PollResult",
]
