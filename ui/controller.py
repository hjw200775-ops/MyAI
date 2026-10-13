"""ChatController：从 gui.py 迁出的全部非 UI 逻辑。

职责：
- 持有会话 / 请求 / 已选图片 / 用户设置等运行时状态（原模块级 global）；
- 以与原 gui.py 完全相同的线程模型执行请求：
    worker 线程 → queue.Queue → 主线程定时 poll()；
- 封装会话、记忆、情绪、关系、设置的读写，视图只调用本类，不直接 import 业务模块。

约束：
- 本模块不 import tkinter / customtkinter，可在离线测试中直接驱动；
- 不改变 ai / memory / llm / settings 的任何行为，只是搬运调用方式。

原 gui.py 中必须保留的隐藏行为（已逐条对应）：
1. 发送时固定本轮文字 Provider，worker 与后台分析都在 text_provider_scope 内执行；
2. 只有回复真正作为 assistant 消息写入数据库（且有用户文字）时才启动后台分析；
3. 错误文案 / 「已记住」提示不入库，仅通过事件交给视图临时展示；
4. 手动增删改记忆后调用 refresh_system_prompt()；
5. 后台分析任何异常都吞掉，不得杀死 worker；
6. 设置保存后 apply_text_settings 热切换，Vision 不受影响；
7. 连接检查结果带着 draft 回到主线程，由视图判断是否过期。
"""
from __future__ import annotations

import queue
import threading
from pathlib import Path
from typing import Callable

from ai import chat, process_post_reply_tasks, refresh_system_prompt, text_provider_scope
from emotion import get_emotion
from llm import apply_text_settings, create_provider, get_default_provider
from llm.config import LLMConfig
from llm.ollama import OllamaProvider
from media import SUPPORTED_IMAGE_EXTENSIONS, validate_image
from memory import (create_conversation, delete_conversation, delete_memory,
                    get_or_create_current_conversation, list_conversations,
                    load_memories, load_message_records, load_messages,
                    rename_conversation, save_memory, update_memory)
from relationship import get_relationship
from settings import UserSettings, get_settings_service
from core.companion_state import CompanionState
from core.events import CompanionEvent, CompanionEventKind, EventLog
from core.proactive import ProactiveManager
from core.time_awareness import observe
from time_context import local_now

from .models import (MEMORY_CATEGORY_LABELS, BackgroundEvent, ConnectionCheckEvent,
                     ConversationItem, MemoryItem, MessageItem, PollResult, ReplyEvent)

PROVIDER_LABELS: dict[str, str] = {"deepseek": "DeepSeek 云端", "ollama": "Ollama 本地"}
PROVIDER_BY_LABEL: dict[str, str] = {v: k for k, v in PROVIDER_LABELS.items()}
MODEL_DISPLAY_NAMES: dict[str, str] = {"deepseek": "DeepSeek Flash", "ollama": "Ollama"}
RELATIONSHIP_STAGE_LABELS: dict[str, str] = {"new": "刚认识", "familiar": "熟悉", "close": "亲近"}
GREETING_TEXT = "你好呀。"
MEMORY_SAVED_TEMPLATE = "[已记住或更新：{}]"
REQUEST_FAILED_PREFIX = "处理消息失败："
POLL_INTERVAL_MS = 50


def provider_label(settings: UserSettings) -> str:
    return PROVIDER_LABELS.get(settings.text_provider, PROVIDER_LABELS["deepseek"])


class ChatController:
    """聊天 / 会话 / 记忆 / 设置的非 UI 控制器。所有公开方法只能在主线程调用。"""

    def __init__(self, *, thread_factory: Callable[..., threading.Thread] | None = None):
        self._thread_factory = thread_factory or (
            lambda **kw: threading.Thread(daemon=True, **kw))
        self._result_queue: "queue.Queue[ReplyEvent]" = queue.Queue()
        self._background_queue: "queue.Queue[BackgroundEvent]" = queue.Queue()
        self._connection_queue: "queue.Queue[ConnectionCheckEvent]" = queue.Queue()

        self.conversation_id: int = get_or_create_current_conversation()
        self.request_in_progress: bool = False
        self.selected_image_path: str | None = None

        self.settings_service = get_settings_service()
        self.user_settings: UserSettings = self.settings_service.load()
        apply_text_settings(self.user_settings)
        self.events = EventLog()
        self.companion = CompanionState.capture(conversation_id=self.conversation_id)
        self.events.publish(CompanionEvent.create(CompanionEventKind.APP_START))

    # ------------------------------------------------------------------ #
    # Provider / 设置
    # ------------------------------------------------------------------ #
    @property
    def provider_label(self) -> str:
        return provider_label(self.user_settings)

    @property
    def model_display_name(self) -> str:
        """给低权重模型选择器用的短名称。"""
        if self.user_settings.text_provider == "ollama":
            return self.user_settings.ollama_model or MODEL_DISPLAY_NAMES["ollama"]
        return MODEL_DISPLAY_NAMES["deepseek"]

    @staticmethod
    def draft_settings(provider_key_or_label: str, ollama_model: str,
                       ollama_base_url: str) -> UserSettings:
        provider = PROVIDER_BY_LABEL.get(provider_key_or_label, provider_key_or_label)
        return UserSettings(
            text_provider=provider,
            ollama_model=ollama_model.strip(),
            ollama_base_url=ollama_base_url.strip(),
        )

    def save_settings(self, draft: UserSettings) -> UserSettings:
        """持久化并热切换文字 Provider；OSError / ValueError 原样抛给视图提示。"""
        saved = self.settings_service.save(draft)
        apply_text_settings(saved)
        self.user_settings = saved
        return saved

    def check_connection(self, draft: UserSettings) -> None:
        """异步检查 Ollama；结果经 poll() 以 ConnectionCheckEvent 返回。"""
        def worker():
            try:
                provider = create_provider(LLMConfig.from_settings(draft))
                if not isinstance(provider, OllamaProvider):
                    raise ValueError("请先选择 Ollama 本地。")
                text = provider.check_status().message
            except Exception:
                text = "检查失败：请确认模型名和 Base URL。"
            self._connection_queue.put(ConnectionCheckEvent(draft, text))

        self._thread_factory(target=worker).start()

    # ------------------------------------------------------------------ #
    # 会话
    # ------------------------------------------------------------------ #
    def conversations(self) -> list[ConversationItem]:
        return [
            ConversationItem(cid, title, created, updated, cid == self.conversation_id)
            for cid, title, created, updated in list_conversations()
        ]

    def switch_conversation(self, conversation_id: int) -> None:
        self.conversation_id = int(conversation_id)
        self.clear_image()

    def new_conversation(self, title: str = "新对话") -> int:
        self.switch_conversation(create_conversation(title))
        return self.conversation_id

    def rename_conversation(self, conversation_id: int, title: str) -> bool:
        return rename_conversation(conversation_id, title)

    def delete_conversation(self, conversation_id: int) -> bool:
        """删除会话；若删的是当前会话，则切到最新的或新建一个。返回当前会话是否变化。"""
        was_current = int(conversation_id) == self.conversation_id
        if delete_conversation(conversation_id) and was_current:
            remaining = list_conversations()
            self.conversation_id = remaining[0][0] if remaining else create_conversation()
            return True
        return False

    # ------------------------------------------------------------------ #
    # 消息
    # ------------------------------------------------------------------ #
    def history(self, conversation_id: int | None = None,
                limit: int | None = None) -> list[MessageItem]:
        cid = self.conversation_id if conversation_id is None else conversation_id
        return [MessageItem.from_record(row) for row in load_message_records(cid, limit=limit)]

    @staticmethod
    def greeting() -> MessageItem:
        return MessageItem.transient_assistant(GREETING_TEXT)

    def last_message_is_assistant(self, conversation_id: int | None = None) -> bool:
        cid = self.conversation_id if conversation_id is None else conversation_id
        rows = load_messages(cid)
        return bool(rows) and rows[-1][2] == "assistant"

    # ------------------------------------------------------------------ #
    # 图片
    # ------------------------------------------------------------------ #
    @staticmethod
    def image_file_patterns() -> str:
        return " ".join(f"*{ext}" for ext in sorted(SUPPORTED_IMAGE_EXTENSIONS))

    @staticmethod
    def validate_image_path(path_value: str | Path) -> Path:
        """只校验不记住；失败抛 ValueError / OSError（与原逻辑一致）。"""
        return validate_image(path_value)

    def set_image(self, path: str | Path) -> None:
        """视图完成预览生成后再调用，保证失败时不会残留半选中状态。"""
        self.selected_image_path = str(path)

    def select_image(self, path_value: str | Path) -> Path:
        """校验并记住待发送图片。"""
        path = self.validate_image_path(path_value)
        self.set_image(path)
        return path

    def clear_image(self) -> None:
        self.selected_image_path = None

    # ------------------------------------------------------------------ #
    # 发送 / 轮询
    # ------------------------------------------------------------------ #
    def can_send(self, user_text: str) -> bool:
        return bool(user_text.strip() or self.selected_image_path) and not self.request_in_progress

    def send(self, user_text: str) -> bool:
        """提交一条消息。返回 False 表示被忽略（空内容或请求进行中）。"""
        user_text = user_text.strip()
        if not self.can_send(user_text):
            return False
        image_path = self.selected_image_path
        conversation_id = self.conversation_id
        self.request_in_progress = True
        self.clear_image()
        self._note_user_message()
        provider = get_default_provider()          # 固定本轮 Provider
        self._thread_factory(
            target=self._ask_ai, args=(user_text, image_path, conversation_id, provider)
        ).start()
        return True

    def _ask_ai(self, user_text, image_path, conversation_id, provider):
        try:
            with text_provider_scope(provider):
                ai_reply, saved_memory = chat(user_text, conversation_id, image_path=image_path)
            latest = load_message_records(conversation_id, limit=1)
            persisted = bool(latest and latest[-1]["role"] == "assistant"
                             and latest[-1]["content"] == ai_reply)
            self._result_queue.put(ReplyEvent(conversation_id, ai_reply, saved_memory, persisted))
            if user_text and persisted:
                self._thread_factory(
                    target=self._run_background_tasks,
                    args=(user_text, ai_reply, conversation_id, provider),
                ).start()
        except Exception as exc:
            from llm.diagnostics import report_error
            self._result_queue.put(
                ReplyEvent(conversation_id, REQUEST_FAILED_PREFIX + report_error(exc), None, False))

    def _run_background_tasks(self, user_text, ai_reply, conversation_id, provider):
        try:
            with text_provider_scope(provider):
                saved_memory, title = process_post_reply_tasks(user_text, ai_reply, conversation_id)
        except Exception:
            # 标题 / 记忆 / 状态分析是可选的，绝不能让 worker 崩溃。
            saved_memory, title = None, None
        self._background_queue.put(BackgroundEvent(conversation_id, saved_memory, title))

    def poll(self) -> PollResult:
        """主线程定时调用；取出全部事件并更新 request_in_progress。"""
        result = PollResult()
        for source, bucket in ((self._result_queue, result.replies),
                               (self._background_queue, result.background),
                               (self._connection_queue, result.connection_checks)):
            try:
                while True:
                    bucket.append(source.get_nowait())
            except queue.Empty:
                pass
        if result.replies:
            self.request_in_progress = False
            if self.companion.current_activity == "chatting":
                self.companion = self.companion.update(current_activity="idle")
        return result

    # ------------------------------------------------------------------ #
    # 记忆
    # ------------------------------------------------------------------ #
    def memories(self) -> list[MemoryItem]:
        return [
            MemoryItem(mid, content, category,
                       MEMORY_CATEGORY_LABELS.get(category, "其他"), created, updated)
            for mid, content, category, created, updated in load_memories()
        ]

    def add_memory(self, content: str, category: str = "other") -> bool:
        if save_memory(content, category):
            refresh_system_prompt()
            self._note_memory("add")
            return True
        return False

    def update_memory(self, memory_id: int, content: str, category: str = "other") -> bool:
        if update_memory(memory_id, content, category):
            refresh_system_prompt()
            self._note_memory("update")
            return True
        return False

    def delete_memory(self, memory_id: int) -> bool:
        if delete_memory(memory_id):
            refresh_system_prompt()
            self._note_memory("delete")
            return True
        return False

    # ------------------------------------------------------------------ #
    # 角色状态（调试）
    # ------------------------------------------------------------------ #
    @staticmethod
    def emotion_state() -> dict:
        return get_emotion()

    @staticmethod
    def relationship_state() -> dict:
        state = dict(get_relationship())
        state["stage_label"] = RELATIONSHIP_STAGE_LABELS.get(state.get("stage"), state.get("stage"))
        return state

    def companion_snapshot(self) -> dict:
        """给侧栏或以后的陪伴状态读。不改界面布局。"""
        return self.companion.save()

    def proactive_decision(self):
        """只返回要不要开口的建议，不发送。"""
        return ProactiveManager().decide(self.companion, observe(self.conversation_id))

    def _note_user_message(self) -> None:
        now = local_now()
        self.companion = self.companion.update(
            last_interaction_time=now, current_activity="chatting", user_presence="present")
        self.events.publish(CompanionEvent.create(
            CompanionEventKind.USER_MESSAGE,
            {"conversation_id": self.conversation_id}, created_at=now))

    def _note_memory(self, action: str) -> None:
        self.events.publish(CompanionEvent.create(
            CompanionEventKind.MEMORY_UPDATED, {"action": action}))


__all__ = [
    "ChatController", "provider_label", "PROVIDER_LABELS", "PROVIDER_BY_LABEL",
    "RELATIONSHIP_STAGE_LABELS", "GREETING_TEXT", "MEMORY_SAVED_TEMPLATE",
    "REQUEST_FAILED_PREFIX", "POLL_INTERVAL_MS",
]
