"""对话页。

结构：
    ConversationPanel（可折叠第二列） | 工具行 + 消息列表（MessageBubble） + InputPanel

消息列表：
- 首次 / 切换会话只渲染最近 PAGE_SIZE 条，顶部提供「加载更早的消息」；
- 回复到达后增量追加（fetch_new），不再全量重渲染；
- SYSTEM 提示（错误 / 记忆更新）与问候语只存在于本次会话的内存中，不进入数据库。
"""
from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable

import customtkinter as ctk

from . import theme
from .assets import make_thumbnail
from .chat_history import MessageWindow
from .controller import ChatController
from .input_panel import InputPanel
from .message_bubble import MessageBubble, ThinkingBubble
from .model_selector import ModelSelector
from .models import BackgroundEvent, MessageItem, MessageKind, ReplyEvent
from .theme import FONT, RADIUS, SIZE, SPACING, ctk_color
from .widgets import IconButton

RESIZE_DEBOUNCE_MS = 80


class ConversationPanel(ctk.CTkFrame):
    """会话列表列：新建 / 切换 / 重命名 / 删除。"""

    def __init__(self, master, controller: ChatController, *, on_switch, on_new, on_collapse,
                 on_current_deleted, **kwargs):
        kwargs.setdefault("fg_color", ctk_color("surface_alt"))
        kwargs.setdefault("corner_radius", RADIUS.md)
        kwargs.setdefault("width", SIZE.conversation_panel_width)
        super().__init__(master, **kwargs)
        self.pack_propagate(False)
        self.controller = controller
        self._on_switch = on_switch
        self._on_current_deleted = on_current_deleted

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=SPACING.sm, pady=(SPACING.md, SPACING.sm))
        ctk.CTkLabel(header, text="会话", font=theme.font(FONT.lg, "bold"),
                     text_color=ctk_color("text_primary")).pack(side="left", padx=(SPACING.sm, 0))
        IconButton(header, "panel", size=28, icon_size=16, command=on_collapse).pack(side="right")

        self.new_button = ctk.CTkButton(self, text="＋ 新建对话", command=on_new,
                                        corner_radius=RADIUS.sm,
                                        fg_color=ctk_color("primary"),
                                        hover_color=ctk_color("primary_hover"),
                                        text_color=ctk_color("on_primary"))
        self.new_button.pack(fill="x", padx=SPACING.md, pady=(0, SPACING.sm))
        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list_frame.pack(fill="both", expand=True, padx=SPACING.xs, pady=(0, SPACING.sm))

    def refresh(self) -> None:
        for widget in self.list_frame.winfo_children():
            widget.destroy()
        for item in self.controller.conversations():
            row = ctk.CTkFrame(self.list_frame, corner_radius=RADIUS.sm,
                               fg_color=ctk_color("surface_active") if item.selected else "transparent")
            row.pack(fill="x", pady=3)
            ctk.CTkButton(row, text=item.title, anchor="w", fg_color="transparent", width=60,
                          text_color=ctk_color("text_primary"),
                          hover_color=ctk_color("surface_hover"),
                          command=lambda cid=item.id: self._on_switch(cid)).pack(
                              side="left", fill="x", expand=True, padx=(2, 0), pady=2)
            ctk.CTkButton(row, text="✎", width=30, fg_color="transparent",
                          text_color=ctk_color("text_secondary"),
                          hover_color=ctk_color("surface_hover"),
                          command=lambda cid=item.id: self._rename(cid)).pack(side="left", padx=1)
            ctk.CTkButton(row, text="×", width=30, fg_color="transparent",
                          text_color=ctk_color("text_secondary"),
                          hover_color=ctk_color("error"),
                          command=lambda cid=item.id, value=item.title:
                          self._remove(cid, value)).pack(side="right", padx=(0, 2))

    def _rename(self, conversation_id):
        title = ctk.CTkInputDialog(text="请输入新的会话标题：", title="重命名会话").get_input()
        if title is not None and self.controller.rename_conversation(conversation_id, title):
            self.refresh()
            self._on_switch(self.controller.conversation_id, refresh_only=True)

    def _remove(self, conversation_id, title):
        parent = self.winfo_toplevel()
        if not messagebox.askyesno("删除会话", f"确定删除“{title}”吗？\n聊天记录将一起删除。", parent=parent):
            return
        if self.controller.delete_conversation(conversation_id):
            self._on_current_deleted()
        self.refresh()


class ChatPage(ctk.CTkFrame):
    def __init__(self, master, controller: ChatController, *,
                 add_listener, remove_listener,
                 panel_collapsed: bool = False,
                 on_panel_toggle: Callable[[bool], None] | None = None,
                 on_status: Callable[[str], None] | None = None, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self.controller = controller
        self._add_listener = add_listener
        self._remove_listener = remove_listener
        self._on_panel_toggle = on_panel_toggle
        self._on_status = on_status or (lambda key: None)
        self._panel_collapsed = panel_collapsed

        # 渲染状态
        self.window: MessageWindow | None = None
        self.bubbles: list[MessageBubble] = []
        self._transients: dict[int, list[MessageItem]] = {}   # 会话 → 本次运行内的临时提示
        self._pending_bubble: MessageBubble | None = None
        self._thinking: ThinkingBubble | None = None
        self._older_button: ctk.CTkButton | None = None
        self._greeting_bubble: MessageBubble | None = None
        self._max_width = 420
        self._resize_job: str | None = None

        # ---- 第二列：会话列表 --------------------------------------------------
        self.panel = ConversationPanel(
            self, controller, on_switch=self.switch_conversation,
            on_new=self.new_conversation, on_collapse=lambda: self.set_panel_collapsed(True),
            on_current_deleted=self.render_current_conversation)

        # ---- 主区 ------------------------------------------------------------
        self.main_frame = ctk.CTkFrame(self, fg_color=ctk_color("surface"), corner_radius=RADIUS.md)

        toolbar = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        toolbar.pack(fill="x", padx=SPACING.sm, pady=(SPACING.sm, 0))
        self.expand_button = IconButton(toolbar, "panel", size=28, icon_size=16,
                                        command=lambda: self.set_panel_collapsed(False))
        self.title_label = ctk.CTkLabel(toolbar, text="", anchor="w", font=theme.font(FONT.sm),
                                        text_color=ctk_color("text_secondary"))
        self.title_label.pack(side="left", padx=(SPACING.sm, 0))
        self.model_selector = ModelSelector(toolbar, controller)
        self.model_selector.pack(side="right", padx=(SPACING.sm, SPACING.sm))

        self.message_list = ctk.CTkScrollableFrame(self.main_frame, fg_color="transparent")
        self.message_list.pack(fill="both", expand=True, padx=SPACING.sm, pady=(SPACING.xs, SPACING.sm))
        # 监听画布而不是内层 frame：滚到底时内层 frame 在窗口缩放后可能不发 Configure。
        self.message_list._parent_canvas.bind("<Configure>", self._on_canvas_resize, add="+")

        self.input_panel = InputPanel(self.main_frame, on_send=self.send_message,
                                      on_pick_image=self.select_image)
        self.input_panel.set_remove_handler(self.clear_selected_image)
        self.input_panel.pack(fill="x", padx=SPACING.lg, pady=(0, SPACING.lg))

        self._layout_columns()
        self.panel.refresh()
        self.render_current_conversation()

    # ------------------------------------------------------------------ #
    # 布局：第二列折叠
    # ------------------------------------------------------------------ #
    def _layout_columns(self) -> None:
        self.panel.pack_forget()
        self.main_frame.pack_forget()
        self.expand_button.pack_forget()
        if not self._panel_collapsed:
            self.panel.pack(side="left", fill="y", padx=(0, SPACING.md))
        else:
            self.expand_button.pack(side="left", before=self.title_label)
        self.main_frame.pack(side="left", fill="both", expand=True)

    def set_panel_collapsed(self, collapsed: bool) -> None:
        if collapsed == self._panel_collapsed:
            return
        self._panel_collapsed = collapsed
        self._layout_columns()
        if self._on_panel_toggle is not None:
            self._on_panel_toggle(collapsed)

    @property
    def panel_collapsed(self) -> bool:
        return self._panel_collapsed

    def refresh_provider_label(self) -> None:
        self.model_selector.refresh()

    # ------------------------------------------------------------------ #
    # 图片
    # ------------------------------------------------------------------ #
    def clear_selected_image(self):
        self.controller.clear_image()
        self.input_panel.clear_preview()

    def select_image(self):
        value = filedialog.askopenfilename(
            title="选择图片",
            filetypes=[("图片文件", self.controller.image_file_patterns()), ("所有文件", "*.*")],
            parent=self.winfo_toplevel(),
        )
        if not value:
            return
        try:
            path = self.controller.validate_image_path(value)
            image = make_thumbnail(path, SIZE.input_preview)
        except (OSError, ValueError) as exc:
            messagebox.showerror("无法选择图片", str(exc), parent=self.winfo_toplevel())
            return
        self.controller.set_image(path)
        self.input_panel.show_preview(image, path.name)

    # ------------------------------------------------------------------ #
    # 消息列表渲染
    # ------------------------------------------------------------------ #
    def _on_canvas_resize(self, event) -> None:
        if event.widget is not self.message_list._parent_canvas:
            return
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        width = event.width
        self._resize_job = self.after(RESIZE_DEBOUNCE_MS, lambda w=width: self._apply_max_width(w))

    def _apply_max_width(self, list_width: int) -> None:
        self._resize_job = None
        canvas = self.message_list._parent_canvas
        list_width = canvas.winfo_width() or list_width
        width = max(160, int(list_width * SIZE.bubble_max_ratio))
        if width == self._max_width:
            return
        self._max_width = width
        for bubble in self.bubbles:
            bubble.set_max_width(width)

    def _clear_list(self) -> None:
        for widget in self.message_list.winfo_children():
            widget.destroy()
        self.bubbles = []
        self._pending_bubble = None
        self._thinking = None
        self._older_button = None
        self._greeting_bubble = None

    def _remove_greeting(self) -> None:
        if self._greeting_bubble is not None:
            if self._greeting_bubble in self.bubbles:
                self.bubbles.remove(self._greeting_bubble)
            self._greeting_bubble.destroy()
            self._greeting_bubble = None

    def _scroll_to_end(self) -> None:
        def _go():
            try:
                canvas = self.message_list._parent_canvas
                canvas.update_idletasks()
                bbox = canvas.bbox("all")
                if bbox:
                    canvas.configure(scrollregion=bbox)
                canvas.yview_moveto(1.0)
            except Exception:
                pass
        self.after_idle(_go)
        self.after(80, _go)

    def _make_bubble(self, item: MessageItem, *, local_image_path=None, before=None) -> MessageBubble:
        bubble = MessageBubble(self.message_list, item, local_image_path=local_image_path,
                               max_width=self._max_width)
        if before is not None:
            bubble.pack(fill="x", before=before)
        else:
            bubble.pack(fill="x")
        return bubble

    def _append(self, item: MessageItem, *, local_image_path=None) -> MessageBubble:
        bubble = self._make_bubble(item, local_image_path=local_image_path)
        self.bubbles.append(bubble)
        return bubble

    def _append_transient(self, item: MessageItem) -> MessageBubble:
        """临时提示：进入本会话的内存列表，不进入数据库。"""
        self._transients.setdefault(self.controller.conversation_id, []).append(item)
        return self._append(item)

    def _ensure_older_button(self) -> None:
        if self._older_button is not None:
            self._older_button.destroy()
            self._older_button = None
        if self.window is not None and self.window.has_more:
            self._older_button = ctk.CTkButton(
                self.message_list, text=theme.LOAD_OLDER_TEXT, height=28, width=160,
                corner_radius=RADIUS.sm, fg_color="transparent",
                hover_color=ctk_color("surface_hover"), text_color=ctk_color("text_secondary"),
                font=theme.font(FONT.sm), command=self.load_older)
            self._older_button.pack(pady=(SPACING.xs, SPACING.sm))
            # 放到列表最顶部（按 pack 顺序而非创建顺序）
            slaves = [w for w in self.message_list.pack_slaves() if w is not self._older_button]
            if slaves:
                self._older_button.pack_configure(before=slaves[0])

    def render_current_conversation(self) -> None:
        cid = self.controller.conversation_id
        self._clear_list()
        self.window = MessageWindow(self.controller, cid)
        items = self.window.load_latest()
        self._ensure_older_button()
        self._greeting_bubble = self._append(self.controller.greeting()) if not items else None
        for item in items:
            self._append(item)
        for item in self._transients.get(cid, []):
            self._append(item)
        self._refresh_title()
        self._scroll_to_end()

    def load_older(self) -> None:
        if self.window is None:
            return
        older = self.window.load_older()
        if not older:
            self._ensure_older_button()
            return
        anchor = self.bubbles[0] if self.bubbles else None
        inserted = []
        for item in older:
            inserted.append(self._make_bubble(item, before=anchor))
        self.bubbles = inserted + self.bubbles
        self._ensure_older_button()

    def _refresh_title(self) -> None:
        current = next((c for c in self.controller.conversations() if c.selected), None)
        self.title_label.configure(text=current.title if current else "")

    # ------------------------------------------------------------------ #
    # 会话操作
    # ------------------------------------------------------------------ #
    def switch_conversation(self, conversation_id, refresh_only: bool = False) -> None:
        if refresh_only:
            self._refresh_title()
            return
        self.controller.switch_conversation(conversation_id)
        self.clear_selected_image()
        self.render_current_conversation()
        self.panel.refresh()

    def new_conversation(self) -> None:
        self.controller.new_conversation("新对话")
        self.clear_selected_image()
        self.render_current_conversation()
        self.panel.refresh()
        self.input_panel.focus_input()

    @property
    def input_box(self):
        """兼容 MainWindow 启动时的 focus 调用。"""
        return self.input_panel.textbox

    def set_input_enabled(self, enabled: bool) -> None:
        self.input_panel.set_enabled(enabled)

    # ------------------------------------------------------------------ #
    # 事件（由 MainWindow 轮询后分发）
    # ------------------------------------------------------------------ #
    def _remove_thinking(self) -> None:
        if self._thinking is not None:
            self._thinking.destroy()
            self._thinking = None

    def on_reply(self, event: ReplyEvent) -> None:
        if event.conversation_id == self.controller.conversation_id and self.window is not None:
            self._remove_thinking()
            new_items = self.window.fetch_new()
            if self._pending_bubble is not None and any(
                    m.kind is MessageKind.USER for m in new_items):
                # 用户消息已入库：用持久化版本替换发送时的临时气泡
                self._pending_bubble.destroy()
                if self._pending_bubble in self.bubbles:
                    self.bubbles.remove(self._pending_bubble)
            self._pending_bubble = None
            if new_items:
                self._remove_greeting()
            for item in new_items:
                self._append(item)
            if not event.persisted:
                self._append_transient(MessageItem.system(event.reply))
            if event.saved_memory:
                self._append_transient(MessageItem.system(theme.MEMORY_SAVED_TEXT.format(event.saved_memory)))
            self._scroll_to_end()
        self.panel.refresh()
        self._refresh_title()
        self.set_input_enabled(True)
        self._on_status("online")

    def on_background(self, event: BackgroundEvent) -> None:
        if event.saved_memory and event.conversation_id == self.controller.conversation_id:
            self._append_transient(MessageItem.system(theme.MEMORY_SAVED_TEXT.format(event.saved_memory)))
            self._scroll_to_end()
        if event.generated_title:
            self.panel.refresh()
            self._refresh_title()

    def send_message(self) -> None:
        user_text = self.input_panel.get_text().strip()
        image_path = self.controller.selected_image_path
        if not self.controller.can_send(user_text):
            return
        if not self.controller.send(user_text):
            return
        self._remove_greeting()
        pending = MessageItem(kind=MessageKind.USER, content=user_text,
                              image_name=Path(image_path).name if image_path else None, persisted=False)
        self._pending_bubble = self._append(pending, local_image_path=image_path)
        self._thinking = ThinkingBubble(
            self.message_list,
            text=theme.THINKING_TEXT["vision" if image_path else "default"])
        self._thinking.pack(fill="x")
        self._scroll_to_end()
        self.input_panel.clear_text()
        self.clear_selected_image()
        self.set_input_enabled(False)
        self._on_status("thinking")


__all__ = ["ChatPage", "ConversationPanel"]
