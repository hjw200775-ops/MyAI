"""窗口内部的视觉标题区（方案 A）。

系统标题栏仍由 Windows 绘制并承载 ─ □ ×；这里只是窗口顶部 44px 的品牌区：
小悠头像 + 名称 + 很小的版本号。右侧预留插槽（Phase 6 放模型选择器）。
"""
from __future__ import annotations

import customtkinter as ctk

from . import theme
from .assets import avatar_ctk_image
from .theme import FONT, SIZE, SPACING, ctk_color


class TitleBar(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", ctk_color("titlebar"))
        kwargs.setdefault("corner_radius", 0)
        kwargs.setdefault("height", SIZE.titlebar_height)
        super().__init__(master, **kwargs)
        self.grid_propagate(False)
        self.grid_columnconfigure(1, weight=1)

        self._avatar = avatar_ctk_image(SIZE.avatar_sm)
        ctk.CTkLabel(self, text="", image=self._avatar, width=SIZE.avatar_sm).grid(
            row=0, column=0, padx=(SPACING.lg, SPACING.sm), pady=SPACING.sm, sticky="w")

        brand = ctk.CTkFrame(self, fg_color="transparent")
        brand.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(brand, text=theme.CHARACTER_NAME, font=theme.font(FONT.lg, "bold"),
                     text_color=ctk_color("titlebar_text")).pack(side="left")
        ctk.CTkLabel(brand, text=theme.APP_VERSION_LABEL, font=theme.font(FONT.xs),
                     text_color=ctk_color("text_muted")).pack(side="left", padx=(SPACING.sm, 0),
                                                             pady=(3, 0))

        # 右侧插槽：后续放模型选择器等低权重控件
        self.right_slot = ctk.CTkFrame(self, fg_color="transparent", width=SPACING.sm,
                                       height=SIZE.titlebar_height - 2 * SPACING.sm)
        self.right_slot.grid(row=0, column=2, padx=(0, SPACING.lg), sticky="e")


__all__ = ["TitleBar"]
