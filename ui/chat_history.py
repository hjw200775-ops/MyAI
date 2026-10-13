"""消息窗口：决定「渲染哪些消息」的纯 Python 逻辑，不依赖 tkinter。

只使用 ChatController.history(conversation_id, limit) 这一已有接口（返回最近 N 条、按时间正序），
不触碰数据库或 Controller 实现。

- load_latest()：首次 / 切换会话时取最近 PAGE_SIZE 条，并判断是否还有更早消息；
- load_older()：向前再取一页，返回需要插到顶部的消息；
- fetch_new()：回复到达后只取「比当前最后一条更新」的消息，用于增量追加。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .models import MessageItem

PAGE_SIZE = 40
NEW_MESSAGE_PROBE = 6  # 一次发送最多新增 user + assistant 两条；取 6 条留余量


class HistorySource(Protocol):
    def history(self, conversation_id: int | None = None,
                limit: int | None = None) -> list[MessageItem]: ...


@dataclass
class MessageWindow:
    source: HistorySource
    conversation_id: int
    page_size: int = PAGE_SIZE
    items: list[MessageItem] = field(default_factory=list)
    has_more: bool = False

    # ------------------------------------------------------------------ #
    @property
    def first_id(self) -> int | None:
        return self.items[0].message_id if self.items else None

    @property
    def last_id(self) -> int | None:
        return self.items[-1].message_id if self.items else None

    # ------------------------------------------------------------------ #
    def load_latest(self) -> list[MessageItem]:
        fetched = self.source.history(self.conversation_id, limit=self.page_size + 1)
        self.has_more = len(fetched) > self.page_size
        self.items = fetched[-self.page_size:] if fetched else []
        return list(self.items)

    def load_older(self) -> list[MessageItem]:
        """返回应插入到当前列表顶部的更早消息（按时间正序）。"""
        if not self.has_more or self.first_id is None:
            return []
        want = len(self.items) + self.page_size
        fetched = self.source.history(self.conversation_id, limit=want + 1)
        older = [m for m in fetched if m.message_id is not None and m.message_id < self.first_id]
        self.has_more = len(older) > self.page_size
        older = older[-self.page_size:] if older else []
        self.items = older + self.items
        return older

    def fetch_new(self) -> list[MessageItem]:
        """回复到达后调用：只返回尚未渲染的持久化消息，并并入窗口。"""
        fetched = self.source.history(self.conversation_id, limit=NEW_MESSAGE_PROBE)
        last = self.last_id
        new = [m for m in fetched
               if m.message_id is not None and (last is None or m.message_id > last)]
        if last is None and not self.items and fetched:
            # 空会话第一次拿到消息：NEW_MESSAGE_PROBE 条就是全部
            new = fetched
        self.items.extend(new)
        return new


__all__ = ["MessageWindow", "PAGE_SIZE", "NEW_MESSAGE_PROBE", "HistorySource"]
