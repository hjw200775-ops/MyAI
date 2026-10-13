"""聊天页底部输入区。

只负责输入、预览和按钮状态。选图校验、发送、会话切换仍由 ChatPage 调用 Controller。
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

import customtkinter as ctk
from PIL import Image

from . import platform_win, theme
from .icons import ctk_icon
from .theme import FONT, RADIUS, SIZE, SPACING, ctk_color

NAME_LIMIT = 28
_SHIFT_MASK = 0x0001
# 候选确认后，Windows 有时会再投递一次普通 Enter。这段时间内不发送。
_IME_ECHO_SECONDS = 0.25


def should_send_on_return(shift: bool, keycode: int | None, composing: bool) -> bool:
    """Enter 是否应该发送。Shift、IME 组字、VK_PROCESSKEY 都不发送。"""
    if shift or composing or keycode == platform_win.VK_PROCESSKEY:
        return False
    return True


def shorten_filename(name: str, limit: int = NAME_LIMIT) -> str:
    if len(name) <= limit:
        return name
    suffix = Path(name).suffix
    keep = limit - len(suffix) - 1
    if keep < 1:
        return name[: max(1, limit - 1)] + "…"
    return Path(name).stem[:keep] + "…" + suffix


class InputPanel(ctk.CTkFrame):
    """多行输入 + 附件菜单 + 图片 chip + 圆形发送按钮。"""

    def __init__(self, master, *, on_send: Callable[[], None],
                 on_pick_image: Callable[[], None], **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self._on_send = on_send
        self._on_pick_image = on_pick_image
        self._enabled = True
        self._menu_open = False
        self._preview_image: ctk.CTkImage | None = None
        self._return_composing = False
        self._ime_echo_until = 0.0
        self._text_before_return = ""
        self._text_height = SIZE.input_min_height - 2 * SPACING.sm
        self._min_text_height = SIZE.input_min_height - 2 * SPACING.sm
        self._max_text_height = SIZE.input_max_height - 2 * SPACING.sm

        self._chip = ctk.CTkFrame(self, fg_color=ctk_color("surface_alt"), corner_radius=RADIUS.md)
        self._thumb = ctk.CTkLabel(self._chip, text="")
        self._thumb.pack(side="left", padx=SPACING.sm, pady=SPACING.sm)
        self._name = ctk.CTkLabel(self._chip, text="", anchor="w", font=theme.font(FONT.sm),
                                  text_color=ctk_color("text_secondary"))
        self._name.pack(side="left", fill="x", expand=True, padx=(0, SPACING.sm))
        self._remove = ctk.CTkButton(
            self._chip, text="×", width=28, height=28, corner_radius=RADIUS.sm,
            fg_color="transparent", hover_color=ctk_color("surface_hover"),
            text_color=ctk_color("text_secondary"), font=theme.font(FONT.md),
            command=self._request_remove)
        self._remove.pack(side="right", padx=SPACING.sm, pady=SPACING.sm)
        self._on_remove: Callable[[], None] | None = None

        self._menu = ctk.CTkFrame(self, fg_color=ctk_color("surface_alt"), corner_radius=RADIUS.sm)
        self._image_action = ctk.CTkButton(
            self._menu, text=theme.ATTACH_IMAGE_LABEL, anchor="w", height=32,
            corner_radius=RADIUS.sm, fg_color="transparent",
            hover_color=ctk_color("surface_hover"), text_color=ctk_color("text_primary"),
            font=theme.font(FONT.sm), command=self._pick_image)
        self._image_action.pack(fill="x", padx=SPACING.xs, pady=SPACING.xs)

        self._bar = ctk.CTkFrame(self, fg_color=ctk_color("surface_alt"), corner_radius=RADIUS.md)
        self._bar.pack(fill="x")
        self._bar.grid_columnconfigure(1, weight=1)

        self._plus_icon = ctk_icon("plus", SIZE.icon, ctk_color("text_secondary"))
        self.attach_button = ctk.CTkButton(
            self._bar, text="", image=self._plus_icon, width=SIZE.send_button, height=SIZE.send_button,
            corner_radius=RADIUS.sm, fg_color="transparent", hover_color=ctk_color("surface_hover"),
            command=self._toggle_menu)
        self.attach_button.grid(row=0, column=0, sticky="sw", padx=(SPACING.sm, 0), pady=SPACING.sm)

        self.textbox = ctk.CTkTextbox(
            self._bar, height=self._min_text_height, wrap="word",
            corner_radius=0, border_width=0, border_spacing=0,
            fg_color="transparent", font=theme.font(FONT.md),
            text_color=ctk_color("text_primary"),
            scrollbar_button_color=ctk_color("scrollbar"),
            scrollbar_button_hover_color=ctk_color("scrollbar_hover"))
        self.textbox.grid(row=0, column=1, sticky="ew", padx=SPACING.sm, pady=SPACING.sm)
        self._placeholder = ctk.CTkLabel(
            self._bar, text=theme.INPUT_PLACEHOLDER, anchor="w",
            font=theme.font(FONT.md), text_color=ctk_color("text_muted"), fg_color="transparent")
        self._placeholder.place(in_=self.textbox, x=SPACING.sm, y=SPACING.xs)
        self._placeholder.bind("<Button-1>", lambda _event: self.focus_input())

        self._send_icon = ctk_icon("send", SIZE.icon - 4, ctk_color("on_primary"))
        self._send_icon_disabled = ctk_icon("send", SIZE.icon - 4, ctk_color("text_muted"))
        self.send_button = ctk.CTkButton(
            self._bar, text="", image=self._send_icon, width=SIZE.send_button, height=SIZE.send_button,
            corner_radius=SIZE.send_button // 2, fg_color=ctk_color("primary"),
            hover_color=ctk_color("primary_hover"), command=self._emit_send)
        self.send_button.grid(row=0, column=2, sticky="se", padx=(0, SPACING.sm), pady=SPACING.sm)

        self.textbox.bind("<KeyPress-Return>", self._on_return_press)
        self.textbox.bind("<KeyRelease-Return>", self._on_return_release)
        self.textbox.bind("<KeyRelease>", self._on_key_release)

    # ------------------------------------------------------------------ #
    def set_remove_handler(self, handler: Callable[[], None]) -> None:
        """删除预览时通知 ChatPage 清掉 Controller 里的已选图片。"""
        self._on_remove = handler

    def get_text(self) -> str:
        return self.textbox.get("1.0", "end-1c")

    def clear_text(self) -> None:
        self.textbox.delete("1.0", "end")
        self._sync_placeholder()
        self._fit_height()

    def focus_input(self) -> None:
        if self._enabled:
            self.textbox.focus()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        state = "normal" if enabled else "disabled"
        self.textbox.configure(state=state)
        self.attach_button.configure(state=state)
        self.send_button.configure(
            state=state,
            image=self._send_icon if enabled else self._send_icon_disabled,
            fg_color=ctk_color("primary") if enabled else ctk_color("surface_hover"),
            hover_color=ctk_color("primary_hover") if enabled else ctk_color("surface_hover"))
        self._remove.configure(state=state)
        if not enabled:
            self._hide_menu()
        if enabled:
            self.focus_input()

    def show_preview(self, image: Image.Image, filename: str) -> None:
        self.clear_preview()
        self._preview_image = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
        self._thumb.configure(image=self._preview_image, text="")
        self._name.configure(text=shorten_filename(filename))
        self._chip.pack(fill="x", pady=(0, SPACING.sm), before=self._bar)

    def clear_preview(self) -> None:
        # CTkLabel.configure(image=None) 不会清掉内部 tk.Label 仍持有的 PhotoImage。
        # 必须在 CTkImage 还活着时先把这层引用换成空，再释放 Python 对象，否则下次
        # configure 会 TclError: image "pyimageN" doesn't exist。
        self._thumb._label.configure(image="")
        current = getattr(self._thumb, "_image", None)
        if isinstance(current, ctk.CTkImage):
            current.remove_configure_callback(self._thumb._update_image)
        self._thumb._image = None
        self._thumb._text = ""
        self._thumb._label.configure(text="")
        self._preview_image = None
        self._name.configure(text="")
        self._chip.pack_forget()

    # ------------------------------------------------------------------ #
    def _request_remove(self) -> None:
        if not self._enabled:
            return
        if self._on_remove is not None:
            self._on_remove()
        else:
            self.clear_preview()

    def _toggle_menu(self) -> None:
        if not self._enabled:
            return
        if self._menu_open:
            self._hide_menu()
        else:
            self._menu.pack(anchor="w", pady=(0, SPACING.xs), before=self._bar)
            self._menu_open = True

    def _hide_menu(self) -> None:
        self._menu.pack_forget()
        self._menu_open = False

    def _pick_image(self) -> None:
        self._hide_menu()
        if self._enabled:
            self._on_pick_image()

    def _emit_send(self) -> None:
        if not self._enabled:
            return
        self._hide_menu()
        self._on_send()

    def _on_return_press(self, event):
        shift = bool(event.state & _SHIFT_MASK)
        keysym = str(getattr(event, "keysym", "") or "")
        composing = platform_win.ime_is_composing(self.textbox)
        ime_key = (not should_send_on_return(False, event.keycode, composing)
                   or keysym in {"Process", "??"})
        now = time.monotonic()
        self._text_before_return = self.get_text()
        if shift:
            self._return_composing = False
            return None
        if ime_key:
            # 组字中的 Enter 交给输入法。随后一小段时间里的回车也不发送。
            self._return_composing = True
            self._ime_echo_until = now + _IME_ECHO_SECONDS
            return None
        if now < self._ime_echo_until:
            self._return_composing = True
            self._ime_echo_until = 0.0
            return "break"
        self._return_composing = False
        return "break"

    def _on_return_release(self, event):
        if event.state & _SHIFT_MASK:
            self._fit_height()
            return None
        if self._return_composing:
            # IME 确认候选时，Text 的默认绑定可能多插入一个换行。只删这一处。
            current = self.get_text()
            before = self._text_before_return
            if current.endswith("\n") and not before.endswith("\n") and current[:-1].startswith(before):
                self.textbox.delete("end-2c", "end-1c")
            self._sync_placeholder()
            self._fit_height()
            return None
        self._emit_send()
        return "break"

    def _on_key_release(self, _event=None) -> None:
        self._sync_placeholder()
        self._fit_height()

    def _sync_placeholder(self) -> None:
        if self.get_text():
            self._placeholder.place_forget()
        elif not self._placeholder.winfo_ismapped():
            self._placeholder.place(in_=self.textbox, x=SPACING.sm, y=SPACING.xs)

    def _fit_height(self) -> None:
        self._sync_placeholder()
        text = self.textbox._textbox
        try:
            self.textbox.update_idletasks()
            counted = text.count("1.0", "end-1c", "displaylines")
            # displaylines 统计的是行与行之间的间隔数，所以要加回最后一行。
            lines = 1 if not counted else int(counted[0]) + 1
            info = text.dlineinfo("1.0")
            line_px = int(info[3]) if info else FONT.md + SPACING.sm
        except Exception:
            lines = max(1, self.get_text().count("\n") + 1)
            line_px = FONT.md + SPACING.sm
        height = min(self._max_text_height, max(self._min_text_height, lines * line_px + SPACING.xs))
        if height != self._text_height:
            self._text_height = height
            self.textbox.configure(height=height)


__all__ = ["InputPanel", "should_send_on_return", "shorten_filename"]
