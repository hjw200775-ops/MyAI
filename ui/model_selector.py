"""聊天页右上角的模型快捷切换。

只切换已经保存过的文字 Provider。模型名、Base URL 和连接检查在设置页。
切换调用现有 save_settings / apply_text_settings。已经发出的请求仍使用发送时
固定下来的 Provider，这里不会改那一轮。
"""
from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from . import theme
from .controller import PROVIDER_LABELS, ChatController
from .theme import FONT, RADIUS, SPACING, ctk_color

_BUTTON_LIMIT = 22


def shorten_model_name(name: str, limit: int = _BUTTON_LIMIT) -> str:
    text = str(name or "").strip() or "模型"
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


class ModelSelector(ctk.CTkFrame):
    """低权重按钮。点开后只列出 DeepSeek / Ollama 两个已有 Provider。"""

    def __init__(self, master, controller: ChatController, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self.controller = controller
        self._open = False

        self.button = ctk.CTkButton(
            self, text=self._label(), height=28, width=10,
            corner_radius=RADIUS.sm, fg_color="transparent",
            hover_color=ctk_color("surface_hover"),
            text_color=ctk_color("text_secondary"), font=theme.font(FONT.sm),
            command=self._toggle)
        self.button.pack(anchor="e")

        self._menu = ctk.CTkFrame(self, fg_color=ctk_color("surface_alt"), corner_radius=RADIUS.sm)
        self._choices: dict[str, ctk.CTkButton] = {}
        for key, label in PROVIDER_LABELS.items():
            button = ctk.CTkButton(
                self._menu, text=label, anchor="w", height=32,
                corner_radius=RADIUS.sm, fg_color="transparent",
                hover_color=ctk_color("surface_hover"),
                text_color=ctk_color("text_primary"), font=theme.font(FONT.sm),
                command=lambda provider=key: self.choose(provider))
            button.pack(fill="x", padx=SPACING.xs, pady=SPACING.xs)
            self._choices[key] = button
        self.refresh()

    def _label(self) -> str:
        return shorten_model_name(self.controller.model_display_name) + " ▾"

    def refresh(self) -> None:
        current = self.controller.user_settings.text_provider
        self.button.configure(text=self._label())
        for key, button in self._choices.items():
            selected = key == current
            button.configure(text_color=ctk_color("primary" if selected else "text_primary"))

    def choose(self, provider_key: str) -> None:
        self._hide()
        current = self.controller.user_settings
        if provider_key == current.text_provider:
            return
        draft = self.controller.draft_settings(
            provider_key, current.ollama_model, current.ollama_base_url)
        try:
            self.controller.save_settings(draft)
        except (OSError, ValueError):
            messagebox.showerror("无法切换模型", "设置没有保存，当前模型保持不变。",
                                 parent=self.winfo_toplevel())
            return
        self.refresh()

    def _toggle(self) -> None:
        if self._open:
            self._hide()
        else:
            self._menu.pack(anchor="e", pady=(SPACING.xs, 0))
            self._open = True
            self.refresh()

    def _hide(self) -> None:
        self._menu.pack_forget()
        self._open = False


__all__ = ["ModelSelector", "shorten_model_name"]
