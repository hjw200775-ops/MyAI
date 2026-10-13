"""记忆 / 视觉 / 设置页。

记忆和设置走 ChatController，不直接访问数据库。主题只通过回调写入 ui_prefs。
旧弹窗仍留在 ui.dialogs，主界面不再打开它们。
"""
from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from . import theme
from .controller import PROVIDER_LABELS, ChatController
from .models import MEMORY_CATEGORY_LABELS, MemoryItem
from .theme import FONT, RADIUS, SIZE, SPACING, ctk_color
from .widgets import Card, PageHeader

_APPEARANCE_LABELS = {"dark": "Dark", "light": "Light", "system": "System"}
_APPEARANCE_KEYS = {label: key for key, label in _APPEARANCE_LABELS.items()}
_EMOTION_ROWS = (("开心", "happiness"), ("难过", "sadness"), ("生气", "anger"))
_RELATION_ROWS = (("信任", "trust"), ("熟悉", "familiarity"), ("亲近", "closeness"))


def filter_memories(items: list[MemoryItem], query: str) -> list[MemoryItem]:
    """按内容和分类做本地过滤，不调用模型。"""
    text = query.strip().lower()
    if not text:
        return list(items)
    return [
        item for item in items
        if text in item.content.lower()
        or text in item.category_label.lower()
        or text in item.category.lower()
    ]


class _BoundedScroll(ctk.CTkScrollableFrame):
    """内容列最宽 content_max，超宽窗口里居中，避免卡片被拉满。"""

    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        kwargs.setdefault("scrollbar_button_color", ctk_color("scrollbar"))
        kwargs.setdefault("scrollbar_button_hover_color", ctk_color("scrollbar_hover"))
        super().__init__(master, **kwargs)
        self.column = ctk.CTkFrame(self, fg_color="transparent")
        self.column.pack(anchor="n", fill="x", expand=True)
        self._parent_canvas.bind("<Configure>", self._fit_width, add="+")

    def _fit_width(self, event) -> None:
        if event.widget is not self._parent_canvas:
            return
        side = max(0, (int(event.width) - SIZE.content_max) // 2)
        self.column.pack_configure(padx=side)


def _section_label(master, text: str) -> ctk.CTkLabel:
    label = ctk.CTkLabel(master, text=text, anchor="w", font=theme.font(FONT.md, "bold"),
                         text_color=ctk_color("text_primary"))
    label.pack(fill="x", padx=SPACING.lg, pady=(SPACING.lg, SPACING.xs))
    return label


def _body_label(master, text: str) -> ctk.CTkLabel:
    label = ctk.CTkLabel(master, text=text, anchor="w", justify="left", wraplength=SIZE.content_max - 64,
                         font=theme.font(FONT.sm), text_color=ctk_color("text_secondary"))
    label.pack(fill="x", padx=SPACING.lg, pady=(0, SPACING.sm))
    return label


def _quiet_button(master, text: str, command, *, width: int = 64) -> ctk.CTkButton:
    return ctk.CTkButton(
        master, text=text, width=width, height=28, command=command,
        corner_radius=RADIUS.sm, fg_color="transparent",
        hover_color=ctk_color("surface_hover"),
        text_color=ctk_color("text_secondary"), font=theme.font(FONT.sm))


def _soft_button(master, text: str, command) -> ctk.CTkButton:
    return ctk.CTkButton(
        master, text=text, height=32, command=command,
        corner_radius=RADIUS.sm, fg_color=ctk_color("primary_soft"),
        hover_color=ctk_color("surface_hover"),
        text_color=ctk_color("text_on_soft"), font=theme.font(FONT.sm))


class MemoryPage(ctk.CTkFrame):
    def __init__(self, master, controller: ChatController, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self.controller = controller
        self._query = ""
        self._editing_id: int | None = None
        self._editor_open = False

        scroll = _BoundedScroll(self)
        scroll.pack(fill="both", expand=True)
        self.scroll = scroll
        column = scroll.column
        PageHeader(column, "记忆", "小悠记得的关于你和你们之间的事情").pack(
            fill="x", padx=SPACING.sm, pady=(SPACING.xs, SPACING.md))

        toolbar = ctk.CTkFrame(column, fg_color="transparent")
        toolbar.pack(fill="x", padx=SPACING.sm, pady=(0, SPACING.md))
        self.search_entry = ctk.CTkEntry(
            toolbar, placeholder_text="搜索记忆……", height=36,
            corner_radius=RADIUS.sm, border_width=0,
            fg_color=ctk_color("surface_alt"), text_color=ctk_color("text_primary"),
            placeholder_text_color=ctk_color("text_muted"), font=theme.font(FONT.sm))
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, SPACING.sm))
        self.search_entry.bind("<KeyRelease>", lambda _event: self._on_search())
        self.add_button = _soft_button(toolbar, "+ 添加记忆", self._start_add)
        self.add_button.pack(side="right")

        self._editor = Card(column)
        self._editor_box = ctk.CTkTextbox(
            self._editor, height=72, wrap="word", corner_radius=RADIUS.sm,
            border_width=0, fg_color=ctk_color("surface_alt"),
            text_color=ctk_color("text_primary"), font=theme.font(FONT.sm),
            scrollbar_button_color=ctk_color("scrollbar"),
            scrollbar_button_hover_color=ctk_color("scrollbar_hover"))
        self._editor_box.pack(fill="x", padx=SPACING.lg, pady=(SPACING.lg, SPACING.sm))
        editor_row = ctk.CTkFrame(self._editor, fg_color="transparent")
        editor_row.pack(fill="x", padx=SPACING.lg, pady=(0, SPACING.lg))
        labels = list(MEMORY_CATEGORY_LABELS.values())
        self._category = ctk.CTkOptionMenu(
            editor_row, values=labels, width=120, height=32,
            fg_color=ctk_color("surface_alt"), button_color=ctk_color("surface_hover"),
            button_hover_color=ctk_color("surface_active"),
            text_color=ctk_color("text_primary"), font=theme.font(FONT.sm),
            dropdown_fg_color=ctk_color("surface"),
            dropdown_hover_color=ctk_color("surface_hover"),
            dropdown_text_color=ctk_color("text_primary"))
        self._category.pack(side="left")
        self._category.set(MEMORY_CATEGORY_LABELS["other"])
        _soft_button(editor_row, "保存", self._commit_editor).pack(side="right")
        _quiet_button(editor_row, "取消", self._close_editor).pack(side="right", padx=(0, SPACING.sm))
        self._editor_status = ctk.CTkLabel(
            self._editor, text="", anchor="w", font=theme.font(FONT.xs),
            text_color=ctk_color("text_muted"))
        self._editor_status.pack(fill="x", padx=SPACING.lg, pady=(0, SPACING.sm))

        self._list = ctk.CTkFrame(column, fg_color="transparent")
        self._list.pack(fill="x", padx=SPACING.sm)
        self._empty = ctk.CTkLabel(
            column, text="", justify="left", anchor="w", font=theme.font(FONT.sm),
            text_color=ctk_color("text_secondary"))
        self.refresh()

    def on_show(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        items = filter_memories(self.controller.memories(), self._query)
        for child in self._list.winfo_children():
            child.destroy()
        self._empty.pack_forget()
        if not items:
            all_items = self.controller.memories()
            if self._query.strip() and all_items:
                text = "没有找到相关记忆。"
            elif not all_items:
                text = "小悠还没有记住什么。\n添加一条，她之后聊天时会用到。"
            else:
                text = "没有找到相关记忆。"
            self._empty.configure(text=text)
            self._empty.pack(fill="x", padx=SPACING.lg, pady=SPACING.lg)
            return
        for item in items:
            self._build_card(item)

    def _build_card(self, item: MemoryItem) -> None:
        card = Card(self._list)
        card.pack(fill="x", pady=(0, SPACING.md))
        chip = ctk.CTkLabel(
            card, text=item.category_label, font=theme.font(FONT.xs),
            text_color=ctk_color("text_on_soft"), fg_color=ctk_color("primary_soft"),
            corner_radius=RADIUS.xs)
        chip.pack(anchor="w", padx=SPACING.lg, pady=(SPACING.lg, SPACING.xs))
        content = ctk.CTkLabel(
            card, text=item.content, anchor="w", justify="left",
            wraplength=SIZE.content_max - 4 * SPACING.lg,
            font=theme.font(FONT.md), text_color=ctk_color("text_primary"))
        content.pack(fill="x", padx=SPACING.lg)
        card.bind("<Configure>", lambda event, label=content: label.configure(
            wraplength=max(160, event.width - 2 * SPACING.lg)), add="+")
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(anchor="e", padx=SPACING.sm, pady=(SPACING.xs, SPACING.sm))
        _quiet_button(actions, "编辑", lambda mid=item.id: self._start_edit(mid)).pack(side="left")
        _quiet_button(actions, "删除", lambda mid=item.id: self._delete(mid)).pack(side="left")

    def _on_search(self) -> None:
        self._query = self.search_entry.get()
        self.refresh()

    def _start_add(self) -> None:
        self._open_editor(None, "", MEMORY_CATEGORY_LABELS["other"])

    def _start_edit(self, memory_id: int) -> None:
        item = next((row for row in self.controller.memories() if row.id == memory_id), None)
        if item is None:
            self.refresh()
            return
        self._open_editor(item.id, item.content, item.category_label)

    def _open_editor(self, memory_id: int | None, content: str, category_label: str) -> None:
        self._editing_id = memory_id
        self._editor_open = True
        self._editor_box.delete("1.0", "end")
        self._editor_box.insert("1.0", content)
        self._category.set(category_label if category_label in MEMORY_CATEGORY_LABELS.values()
                           else MEMORY_CATEGORY_LABELS["other"])
        self._editor_status.configure(text="")
        self._editor.pack(fill="x", padx=SPACING.sm, pady=(0, SPACING.md), before=self._list)
        self._editor_box.focus()

    def _close_editor(self) -> None:
        self._editor_open = False
        self._editing_id = None
        self._editor.pack_forget()

    def _category_key(self) -> str:
        label = self._category.get()
        for key, value in MEMORY_CATEGORY_LABELS.items():
            if value == label:
                return key
        return "other"

    def _commit_editor(self) -> None:
        content = self._editor_box.get("1.0", "end-1c")
        category = self._category_key()
        if self._editing_id is None:
            saved = self.controller.add_memory(content, category)
        else:
            saved = self.controller.update_memory(self._editing_id, content, category)
        if not saved:
            self._editor_status.configure(text="没有记下这条。内容可能是空的，或已经有一条相同的记忆。")
            return
        self._close_editor()
        self.refresh()

    def _delete(self, memory_id: int) -> None:
        if not messagebox.askyesno("删除记忆", "确定删除这条记忆吗？", parent=self.winfo_toplevel()):
            return
        self.controller.delete_memory(memory_id)
        if self._editing_id == memory_id:
            self._close_editor()
        self.refresh()


class VisionPage(ctk.CTkFrame):
    def __init__(self, master, controller: ChatController, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self.controller = controller
        scroll = _BoundedScroll(self)
        scroll.pack(fill="both", expand=True)
        self.scroll = scroll
        column = scroll.column
        PageHeader(column, "视觉", "小悠目前可以在聊天中理解你发送的图片。").pack(
            fill="x", padx=SPACING.sm, pady=(SPACING.xs, SPACING.md))
        card = Card(column)
        card.pack(fill="x", padx=SPACING.sm, pady=(0, SPACING.md))
        _section_label(card, "当前图片能力")
        _body_label(card, "直接在聊天输入框点击 + 上传图片即可。")
        _body_label(card, "小悠会在这条对话里理解你发送的图片。这里没有单独的视觉开关。")

    def on_show(self) -> None:
        return None


class SettingsPage(ctk.CTkFrame):
    def __init__(self, master, controller: ChatController, *, add_listener, remove_listener,
                 on_provider_saved, appearance: str, on_appearance, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self.controller = controller
        self._remove_listener = remove_listener
        self._on_provider_saved = on_provider_saved
        self._on_appearance = on_appearance
        self._appearance = appearance if appearance in _APPEARANCE_LABELS else "dark"
        self._loading = False

        scroll = _BoundedScroll(self)
        scroll.pack(fill="both", expand=True)
        self.scroll = scroll
        column = scroll.column
        PageHeader(column, "设置", "外观、模型和角色状态。").pack(
            fill="x", padx=SPACING.sm, pady=(SPACING.xs, SPACING.md))

        appearance_card = Card(column)
        appearance_card.pack(fill="x", padx=SPACING.sm, pady=(0, SPACING.md))
        _section_label(appearance_card, "外观")
        _body_label(appearance_card, "主题")
        self._appearance_picker = ctk.CTkSegmentedButton(
            appearance_card, values=list(_APPEARANCE_LABELS.values()), height=32,
            font=theme.font(FONT.sm), command=self._change_appearance,
            fg_color=ctk_color("surface_alt"),
            selected_color=ctk_color("primary"),
            selected_hover_color=ctk_color("primary_hover"),
            unselected_color=ctk_color("surface_alt"),
            unselected_hover_color=ctk_color("surface_hover"),
            text_color=ctk_color("text_primary"))
        self._appearance_picker.pack(anchor="w", padx=SPACING.lg, pady=(0, SPACING.lg))
        self._loading = True
        self._appearance_picker.set(_APPEARANCE_LABELS[self._appearance])
        self._loading = False

        model_card = Card(column)
        model_card.pack(fill="x", padx=SPACING.sm, pady=(0, SPACING.md))
        _section_label(model_card, "AI 模型")
        _body_label(model_card, "当前 Provider。完整配置在这里，聊天页只做快速切换。")
        self._provider_picker = ctk.CTkSegmentedButton(
            model_card, values=list(PROVIDER_LABELS.values()), height=32,
            font=theme.font(FONT.sm), command=self._change_provider_form,
            fg_color=ctk_color("surface_alt"),
            selected_color=ctk_color("primary"),
            selected_hover_color=ctk_color("primary_hover"),
            unselected_color=ctk_color("surface_alt"),
            unselected_hover_color=ctk_color("surface_hover"),
            text_color=ctk_color("text_primary"))
        self._provider_picker.pack(anchor="w", padx=SPACING.lg, pady=(0, SPACING.md))

        self._ollama_box = ctk.CTkFrame(model_card, fg_color="transparent")
        ctk.CTkLabel(self._ollama_box, text="模型名称", anchor="w", font=theme.font(FONT.sm),
                     text_color=ctk_color("text_secondary")).pack(fill="x", pady=(0, SPACING.xs))
        self._model_entry = ctk.CTkEntry(
            self._ollama_box, height=36, corner_radius=RADIUS.sm, border_width=0,
            fg_color=ctk_color("surface_alt"), text_color=ctk_color("text_primary"),
            font=theme.font(FONT.sm))
        self._model_entry.pack(fill="x", pady=(0, SPACING.sm))
        ctk.CTkLabel(self._ollama_box, text="Base URL", anchor="w", font=theme.font(FONT.sm),
                     text_color=ctk_color("text_secondary")).pack(fill="x", pady=(0, SPACING.xs))
        self._url_entry = ctk.CTkEntry(
            self._ollama_box, height=36, corner_radius=RADIUS.sm, border_width=0,
            fg_color=ctk_color("surface_alt"), text_color=ctk_color("text_primary"),
            font=theme.font(FONT.sm))
        self._url_entry.pack(fill="x", pady=(0, SPACING.sm))
        self._check_button = _quiet_button(self._ollama_box, "检查连接", self._check_connection, width=96)
        self._check_button.pack(anchor="w", pady=(0, SPACING.sm))

        actions = ctk.CTkFrame(model_card, fg_color="transparent")
        actions.pack(fill="x", padx=SPACING.lg, pady=(0, SPACING.xs))
        self._save_button = _soft_button(actions, "保存", self._save_provider)
        self._save_button.pack(side="right")
        self._status = ctk.CTkLabel(
            model_card, text="", anchor="w", justify="left", wraplength=SIZE.content_max - 64,
            font=theme.font(FONT.sm), text_color=ctk_color("text_secondary"))
        self._status.pack(fill="x", padx=SPACING.lg, pady=(0, SPACING.lg))
        self._load_provider_form()

        self._character = Card(column)
        self._character.pack(fill="x", padx=SPACING.sm, pady=(0, SPACING.md))
        _section_label(self._character, "角色")
        ctk.CTkLabel(self._character, text="角色状态 · 调试", anchor="w",
                     font=theme.font(FONT.sm, "bold"),
                     text_color=ctk_color("text_secondary")).pack(
            fill="x", padx=SPACING.lg, pady=(0, SPACING.xs))
        _body_label(self._character, "这些数值只供观察，不能在这里修改，也不会写进聊天记录。")
        self._meters = ctk.CTkFrame(self._character, fg_color="transparent")
        self._meters.pack(fill="x", padx=SPACING.sm, pady=(0, SPACING.lg))

        about = Card(column)
        about.pack(fill="x", padx=SPACING.sm, pady=(0, SPACING.xl))
        _section_label(about, "关于")
        ctk.CTkLabel(about, text=theme.CHARACTER_NAME, anchor="w",
                     font=theme.font(FONT.lg, "bold"),
                     text_color=ctk_color("text_primary")).pack(fill="x", padx=SPACING.lg)
        _body_label(about, theme.APP_VERSION_LABEL)
        _body_label(about, "一个正在成长的桌面 AI 伙伴。")

        add_listener(self._on_connection)
        self.bind("<Destroy>", self._unregister, add="+")
        self._refresh_character()

    def on_show(self) -> None:
        self._load_provider_form()
        self._refresh_character()

    def _unregister(self, event) -> None:
        if event.widget is self:
            self._remove_listener(self._on_connection)

    def _change_appearance(self, label: str) -> None:
        if self._loading:
            return
        mode = _APPEARANCE_KEYS.get(label)
        if mode is None or mode == self._appearance:
            return
        self._appearance = mode
        self._on_appearance(mode)

    def _draft(self):
        return self.controller.draft_settings(
            self._provider_picker.get(), self._model_entry.get(), self._url_entry.get())

    def _is_ollama(self) -> bool:
        return self._draft().text_provider == "ollama"

    def _load_provider_form(self) -> None:
        settings = self.controller.user_settings
        self._loading = True
        self._provider_picker.set(PROVIDER_LABELS.get(settings.text_provider, PROVIDER_LABELS["deepseek"]))
        self._loading = False
        self._set_entry(self._model_entry, settings.ollama_model)
        self._set_entry(self._url_entry, settings.ollama_base_url)
        self._sync_ollama_fields()

    @staticmethod
    def _set_entry(entry, value: str) -> None:
        entry.configure(state="normal")
        entry.delete(0, "end")
        entry.insert(0, value)

    def _change_provider_form(self, _label: str) -> None:
        if self._loading:
            return
        self._sync_ollama_fields()

    def _sync_ollama_fields(self) -> None:
        if self._is_ollama():
            self._ollama_box.pack(fill="x", padx=SPACING.lg, pady=(0, SPACING.sm), before=self._save_button.master)
            self._check_button.configure(state="normal")
            self._status.configure(text="可检查 Ollama 服务与模型是否可用。")
        else:
            self._ollama_box.pack_forget()
            self._check_button.configure(state="disabled")
            self._status.configure(text="当前文字 Provider：DeepSeek 云端。图片理解不随这里切换。")

    def _check_connection(self) -> None:
        if not self._is_ollama():
            return
        self._check_button.configure(state="disabled", text="检查中...")
        self._status.configure(text="正在检查 Ollama...")
        self.controller.check_connection(self._draft())

    def _on_connection(self, event) -> None:
        if not self.winfo_exists():
            return
        self._check_button.configure(text="检查连接")
        self._sync_ollama_fields()
        if self._draft() == event.draft:
            self._status.configure(text=event.message)

    def _save_provider(self) -> None:
        try:
            self.controller.save_settings(self._draft())
        except (OSError, ValueError):
            messagebox.showerror("无法保存设置", "设置保存失败，请检查配置内容及目录写入权限。",
                                 parent=self.winfo_toplevel())
            return
        self._on_provider_saved()
        self._status.configure(text="已保存。下一条消息会使用这个 Provider。")

    def _refresh_character(self) -> None:
        for child in self._meters.winfo_children():
            child.destroy()
        emotion = self.controller.emotion_state()
        relation = self.controller.relationship_state()
        ctk.CTkLabel(self._meters, text="情绪", anchor="w", font=theme.font(FONT.sm),
                     text_color=ctk_color("text_primary")).pack(fill="x", padx=SPACING.sm, pady=(SPACING.sm, 0))
        for label, key in _EMOTION_ROWS:
            self._meter(label, emotion.get(key, 0))
        stage = relation.get("stage_label") or relation.get("stage") or ""
        ctk.CTkLabel(self._meters, text=f"关系    阶段：{stage}", anchor="w",
                     font=theme.font(FONT.sm), text_color=ctk_color("text_primary")).pack(
            fill="x", padx=SPACING.sm, pady=(SPACING.md, 0))
        for label, key in _RELATION_ROWS:
            self._meter(label, relation.get(key, 0))

    def _meter(self, label: str, value) -> None:
        try:
            number = max(0.0, min(100.0, float(value)))
        except (TypeError, ValueError):
            number = 0.0
        row = ctk.CTkFrame(self._meters, fg_color="transparent")
        row.pack(fill="x", padx=SPACING.sm, pady=SPACING.xs)
        ctk.CTkLabel(row, text=label, width=48, anchor="w", font=theme.font(FONT.sm),
                     text_color=ctk_color("text_secondary")).pack(side="left")
        bar = ctk.CTkProgressBar(
            row, height=8, progress_color=ctk_color("primary"), fg_color=ctk_color("surface_hover"))
        bar.pack(side="left", fill="x", expand=True, padx=SPACING.sm)
        bar.set(number / 100)
        ctk.CTkLabel(row, text=f"{number:.0f}", width=36, anchor="e", font=theme.font(FONT.xs),
                     text_color=ctk_color("text_muted")).pack(side="right")


__all__ = ["MemoryPage", "VisionPage", "SettingsPage", "filter_memories"]
