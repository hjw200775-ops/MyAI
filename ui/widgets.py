"""基础 UI 组件：全部颜色 / 圆角 / 间距取自 ui.theme。"""
from __future__ import annotations

import customtkinter as ctk

from . import theme
from .icons import ctk_icon
from .theme import FONT, RADIUS, SIZE, SPACING, ctk_color


class Card(ctk.CTkFrame):
    """卡片容器：surface 底色、md 圆角、无描边。"""

    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", ctk_color("surface"))
        kwargs.setdefault("corner_radius", RADIUS.md)
        super().__init__(master, **kwargs)


class PageHeader(ctk.CTkFrame):
    """页面标题区：大标题 + 可选副标题。"""

    def __init__(self, master, title: str, subtitle: str | None = None, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self.title_label = ctk.CTkLabel(self, text=title, anchor="w",
                                        font=theme.font(FONT.xl, "bold"),
                                        text_color=ctk_color("text_primary"))
        self.title_label.pack(side="top", anchor="w")
        self.subtitle_label = None
        if subtitle:
            self.subtitle_label = ctk.CTkLabel(self, text=subtitle, anchor="w", justify="left",
                                               font=theme.font(FONT.sm),
                                               text_color=ctk_color("text_secondary"))
            self.subtitle_label.pack(side="top", anchor="w", pady=(SPACING.xs, 0))


class IconButton(ctk.CTkButton):
    """无边框图标按钮：默认透明，hover 浅底。"""

    def __init__(self, master, icon: str, *, size: int = SIZE.nav_button,
                 icon_size: int = SIZE.icon, text: str = "",
                 colors: tuple[str, str] | None = None, **kwargs):
        colors = colors or ctk_color("text_secondary")
        kwargs.setdefault("width", size)
        kwargs.setdefault("height", size)
        kwargs.setdefault("corner_radius", RADIUS.sm)
        kwargs.setdefault("fg_color", "transparent")
        kwargs.setdefault("hover_color", ctk_color("surface_hover"))
        kwargs.setdefault("text_color", colors)
        kwargs.setdefault("border_width", 0)
        super().__init__(master, text=text, image=ctk_icon(icon, icon_size, colors), **kwargs)


class NavButton(ctk.CTkButton):
    """侧栏导航按钮：图标在上、短文字在下；active 时换成强调色。"""

    def __init__(self, master, key: str, label: str, icon: str, command, **kwargs):
        self.key = key
        self._normal_icon = ctk_icon(icon, SIZE.icon, ctk_color("text_secondary"))
        self._active_icon = ctk_icon(icon, SIZE.icon, ctk_color("primary"))
        kwargs.setdefault("width", SIZE.nav_button + 12)
        kwargs.setdefault("height", SIZE.nav_button + 12)
        kwargs.setdefault("corner_radius", RADIUS.sm)
        kwargs.setdefault("border_width", 0)
        kwargs.setdefault("fg_color", "transparent")
        kwargs.setdefault("hover_color", ctk_color("surface_hover"))
        kwargs.setdefault("text_color", ctk_color("text_secondary"))
        kwargs.setdefault("font", theme.font(FONT.xs))
        super().__init__(master, text=label, image=self._normal_icon, compound="top",
                         command=command, **kwargs)
        self._active = False

    def set_active(self, active: bool) -> None:
        if active == self._active:
            return
        self._active = active
        if active:
            self.configure(fg_color=ctk_color("primary_soft"), hover_color=ctk_color("primary_soft"),
                           text_color=ctk_color("primary"), image=self._active_icon)
        else:
            self.configure(fg_color="transparent", hover_color=ctk_color("surface_hover"),
                           text_color=ctk_color("text_secondary"), image=self._normal_icon)


class StatusIndicator(ctk.CTkFrame):
    """角色状态：彩色圆点 + 文案（例如 ● 在线）。"""

    def __init__(self, master, text: str = "在线", dot_color=None, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self.dot = ctk.CTkLabel(self, text="●", width=12, font=theme.font(FONT.xs),
                                text_color=dot_color or ctk_color("success"))
        self.dot.pack(side="left")
        self.label = ctk.CTkLabel(self, text=text, font=theme.font(FONT.xs),
                                  text_color=ctk_color("text_secondary"))
        self.label.pack(side="left", padx=(SPACING.xs, 0))

    def set_status(self, text: str, dot_color=None) -> None:
        self.label.configure(text=text)
        if dot_color is not None:
            self.dot.configure(text_color=dot_color)


__all__ = ["Card", "PageHeader", "IconButton", "NavButton", "StatusIndicator"]
