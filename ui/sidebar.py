"""左侧 72px 图标导航栏 + 底部小悠状态。"""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from . import theme
from .assets import avatar_ctk_image
from .theme import FONT, SIZE, SPACING, ctk_color
from .widgets import NavButton, StatusIndicator

# (key, 显示文字, 图标名)。未来预留：("voice", "语音", ...), ("character", "角色", ...), ("plugins", "插件", ...)
NAV_ITEMS: tuple[tuple[str, str, str], ...] = (
    ("chat", "对话", "chat"),
    ("memory", "记忆", "memory"),
    ("vision", "视觉", "vision"),
    ("settings", "设置", "settings"),
)


class Sidebar(ctk.CTkFrame):
    def __init__(self, master, on_select: Callable[[str], None], **kwargs):
        kwargs.setdefault("fg_color", ctk_color("surface_alt"))
        kwargs.setdefault("corner_radius", 0)
        kwargs.setdefault("width", SIZE.sidebar_width)
        super().__init__(master, **kwargs)
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)  # 中间弹性空间
        self._on_select = on_select
        self._buttons: dict[str, NavButton] = {}

        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.grid(row=0, column=0, pady=(SPACING.md, 0))
        for key, label, icon in NAV_ITEMS:
            button = NavButton(nav, key, label, icon, command=lambda k=key: self._on_select(k))
            button.pack(pady=(0, SPACING.xs))
            self._buttons[key] = button

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, pady=(0, SPACING.md))
        self._avatar = avatar_ctk_image(SIZE.avatar_md)
        ctk.CTkLabel(footer, text="", image=self._avatar, width=SIZE.avatar_md).pack()
        ctk.CTkLabel(footer, text=theme.CHARACTER_NAME, font=theme.font(FONT.xs, "bold"),
                     text_color=ctk_color("text_primary")).pack(pady=(SPACING.xs, 0))
        self.status = StatusIndicator(footer, text="在线")
        self.status.pack(pady=(2, 0))

    def set_active(self, key: str) -> None:
        for name, button in self._buttons.items():
            button.set_active(name == key)

    def set_status(self, text: str, dot_color=None) -> None:
        self.status.set_status(text, dot_color)


__all__ = ["Sidebar", "NAV_ITEMS"]
