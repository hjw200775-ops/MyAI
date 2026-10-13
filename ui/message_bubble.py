"""角色化消息气泡。

四种 MessageKind：
    USER       右对齐，primary_soft 底色
    ASSISTANT  左对齐：28px 圆形头像 + 「小悠」+ 气泡；时间通过 set_time() 预留
    PROACTIVE  同 ASSISTANT，但名称为「小悠 · 刚刚想起你」且用强调色——不出现工程化描述
    SYSTEM     居中小字，用于错误 / 记忆提示 / 状态提示，不入库

气泡最大宽度由 ChatPage 根据聊天区宽度调用 set_max_width() 统一控制。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import customtkinter as ctk

from . import theme
from .assets import avatar_ctk_image, hosted_image_thumbnail, make_thumbnail
from .models import MessageItem, MessageKind
from .theme import FONT, RADIUS, SIZE, SPACING, ctk_color

SHOW_MESSAGE_TIME = False      # 时间显示开关；接口已预留（set_time）
BUBBLE_PAD_X = SPACING.md
BUBBLE_PAD_Y = SPACING.sm
DEFAULT_MAX_WIDTH = 420
IMAGE_BOX = (280, 200)

_avatar_cache: dict[int, ctk.CTkImage] = {}


def _avatar(size: int) -> ctk.CTkImage:
    if size not in _avatar_cache:
        _avatar_cache[size] = avatar_ctk_image(size)
    return _avatar_cache[size]


def format_time(created_at: str | None) -> str:
    """ISO 时间戳 → 'HH:MM'；损坏或缺失返回空串。"""
    if not created_at:
        return ""
    try:
        return datetime.fromisoformat(created_at).strftime("%H:%M")
    except ValueError:
        return ""


class MessageBubble(ctk.CTkFrame):
    """一条消息（整行）。"""

    def __init__(self, master, item: MessageItem, *, local_image_path: str | Path | None = None,
                 max_width: int = DEFAULT_MAX_WIDTH, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self.item = item
        self.kind = item.kind
        self._max_width = max_width
        self._text_label: ctk.CTkLabel | None = None
        self._time_label: ctk.CTkLabel | None = None
        self._image: ctk.CTkImage | None = None
        self._image_label: ctk.CTkLabel | None = None

        if self.kind is MessageKind.SYSTEM:
            self._build_system()
        elif self.kind is MessageKind.USER:
            self._build_user(local_image_path)
        else:
            self._build_assistant(proactive=self.kind is MessageKind.PROACTIVE,
                                  local_image_path=local_image_path)

    # ------------------------------------------------------------------ #
    # 构建
    # ------------------------------------------------------------------ #
    def _bubble(self, master, fill: str, radius: int = RADIUS.lg) -> ctk.CTkFrame:
        return ctk.CTkFrame(master, fg_color=ctk_color(fill), corner_radius=radius)

    def _fill_bubble(self, bubble: ctk.CTkFrame, text_color: str,
                     local_image_path: str | Path | None) -> None:
        """在气泡里依次放入图片（如有）和文字（如有）。"""
        image = None
        if local_image_path is not None:
            try:
                image = make_thumbnail(local_image_path, IMAGE_BOX)
            except (OSError, ValueError):
                image = None
        elif self.item.image_name:
            image = hosted_image_thumbnail(self.item.image_name, IMAGE_BOX)

        has_text = bool(self.item.content)
        if image is not None:
            self._image = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
            self._image_label = ctk.CTkLabel(bubble, text="", image=self._image)
            self._image_label.pack(anchor="w", padx=BUBBLE_PAD_X,
                                   pady=(BUBBLE_PAD_Y, BUBBLE_PAD_Y if has_text else BUBBLE_PAD_Y))
        elif self.item.image_name:
            # 托管图片已不存在：降级为文件名占位，与旧版行为一致
            ctk.CTkLabel(bubble, text=f"[图片：{self.item.image_name}]", anchor="w",
                         font=theme.font(FONT.sm), text_color=ctk_color("text_muted")).pack(
                anchor="w", padx=BUBBLE_PAD_X, pady=(BUBBLE_PAD_Y, 0 if has_text else BUBBLE_PAD_Y))

        if has_text:
            self._text_label = ctk.CTkLabel(
                bubble, text=self.item.content, anchor="w", justify="left",
                wraplength=self._wrap_width(), font=theme.font(FONT.md),
                text_color=ctk_color(text_color))
            self._text_label.pack(anchor="w", padx=BUBBLE_PAD_X,
                                  pady=(0 if (image is not None or self.item.image_name) else BUBBLE_PAD_Y,
                                        BUBBLE_PAD_Y))

    def _build_user(self, local_image_path) -> None:
        bubble = self._bubble(self, "bubble_user")
        bubble.pack(side="right", padx=(0, SPACING.sm), pady=SPACING.xs)
        self._fill_bubble(bubble, "bubble_user_text", local_image_path)

    def _build_assistant(self, *, proactive: bool, local_image_path) -> None:
        self._avatar_image = _avatar(SIZE.avatar_sm)
        ctk.CTkLabel(self, text="", image=self._avatar_image, width=SIZE.avatar_sm).pack(
            side="left", anchor="n", padx=(SPACING.sm, SPACING.sm), pady=(SPACING.xs, 0))

        column = ctk.CTkFrame(self, fg_color="transparent")
        column.pack(side="left", anchor="n", pady=SPACING.xs)

        header = ctk.CTkFrame(column, fg_color="transparent")
        header.pack(anchor="w")
        name_text = theme.PROACTIVE_LABEL if proactive else theme.CHARACTER_NAME
        name_color = ctk_color("primary") if proactive else ctk_color("text_secondary")
        ctk.CTkLabel(header, text=name_text, anchor="w", font=theme.font(FONT.sm),
                     text_color=name_color).pack(side="left", padx=(SPACING.xs, 0))
        self._time_label = ctk.CTkLabel(header, text="", anchor="w", font=theme.font(FONT.xs),
                                        text_color=ctk_color("text_muted"))
        if SHOW_MESSAGE_TIME:
            self.set_time(format_time(self.item.created_at))

        bubble = self._bubble(column, "bubble_assistant")
        bubble.pack(anchor="w", pady=(2, 0))
        self._fill_bubble(bubble, "bubble_assistant_text", local_image_path)

    def _build_system(self) -> None:
        bubble = self._bubble(self, "bubble_system", radius=RADIUS.sm)
        bubble.pack(anchor="center", pady=SPACING.xs)
        self._text_label = ctk.CTkLabel(
            bubble, text=self.item.content, justify="center", wraplength=self._wrap_width(),
            font=theme.font(FONT.sm), text_color=ctk_color("bubble_system_text"))
        self._text_label.pack(padx=BUBBLE_PAD_X, pady=SPACING.xs)

    # ------------------------------------------------------------------ #
    # 公共接口
    # ------------------------------------------------------------------ #
    def _wrap_width(self) -> int:
        return max(120, self._max_width - 2 * BUBBLE_PAD_X)

    def set_max_width(self, width: int) -> None:
        if width == self._max_width:
            return
        self._max_width = width
        if self._text_label is not None:
            self._text_label.configure(wraplength=self._wrap_width())

    def set_time(self, text: str) -> None:
        """时间信息预留接口：传空串隐藏。"""
        if self._time_label is None:
            return
        if text:
            self._time_label.configure(text=text)
            if not self._time_label.winfo_ismapped():
                self._time_label.pack(side="left", padx=(SPACING.sm, 0), pady=(1, 0))
        else:
            self._time_label.pack_forget()


class ThinkingBubble(ctk.CTkFrame):
    """「小悠正在想……」占位气泡；呼吸动画在 Phase 7 加入。"""

    def __init__(self, master, text: str | None = None, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self._avatar_image = _avatar(SIZE.avatar_sm)
        ctk.CTkLabel(self, text="", image=self._avatar_image, width=SIZE.avatar_sm).pack(
            side="left", anchor="n", padx=(SPACING.sm, SPACING.sm), pady=(SPACING.xs, 0))
        column = ctk.CTkFrame(self, fg_color="transparent")
        column.pack(side="left", anchor="n", pady=SPACING.xs)
        ctk.CTkLabel(column, text=theme.CHARACTER_NAME, anchor="w", font=theme.font(FONT.sm),
                     text_color=ctk_color("text_secondary")).pack(anchor="w", padx=(SPACING.xs, 0))
        bubble = ctk.CTkFrame(column, fg_color=ctk_color("bubble_assistant"), corner_radius=RADIUS.lg)
        bubble.pack(anchor="w", pady=(2, 0))
        row = ctk.CTkFrame(bubble, fg_color="transparent")
        row.pack(padx=BUBBLE_PAD_X, pady=BUBBLE_PAD_Y)
        self.text_label = ctk.CTkLabel(row, text=text or theme.THINKING_TEXT["default"],
                                       font=theme.font(FONT.md), text_color=ctk_color("text_secondary"))
        self.text_label.pack(side="left")
        self.dots_label = ctk.CTkLabel(row, text="● ● ●", font=theme.font(FONT.xs),
                                       text_color=ctk_color("text_muted"))
        self.dots_label.pack(side="left", padx=(SPACING.sm, 0))

    def set_text(self, text: str) -> None:
        self.text_label.configure(text=text)


__all__ = ["MessageBubble", "ThinkingBubble", "format_time", "SHOW_MESSAGE_TIME"]
