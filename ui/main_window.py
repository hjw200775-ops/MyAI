"""MainWindow：标题区 + 左侧导航 + 页面容器，并负责主线程轮询与事件分发。

布局（grid）：
    row 0  TitleBar（跨两列）
    row 1  Sidebar | 页面容器（ChatPage / MemoryPage / VisionPage / SettingsPage 叠放，tkraise 切换）
"""
from __future__ import annotations

import customtkinter as ctk

from . import platform_win, theme
from .chat_view import ChatPage
from .controller import POLL_INTERVAL_MS, ChatController
from .dialogs import ConnectionListener
from .pages import MemoryPage, SettingsPage, VisionPage
from .sidebar import Sidebar
from .theme import SIZE, SPACING, ctk_color
from .titlebar import TitleBar
from .ui_prefs import UIPrefs, UIPrefsService

WINDOW_TITLE = "MyAI v1.6.1"


def resolve_appearance(mode: str) -> str:
    """把 dark / light / system 解析为实际生效的 'dark' 或 'light'。"""
    if mode in ("dark", "light"):
        return mode
    return "dark" if ctk.get_appearance_mode().lower() == "dark" else "light"


class MainWindow(ctk.CTk):
    def __init__(self, controller: ChatController, prefs_service: UIPrefsService, prefs: UIPrefs):
        super().__init__(fg_color=ctk_color("background"))
        self.controller = controller
        self.prefs_service = prefs_service
        self.prefs = prefs
        self._connection_listeners: list[ConnectionListener] = []
        self._current_page: str | None = None

        self.title(WINDOW_TITLE)
        self.geometry(f"{SIZE.window_default[0]}x{SIZE.window_default[1]}")
        self.minsize(*SIZE.window_min)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.titlebar = TitleBar(self)
        self.titlebar.grid(row=0, column=0, columnspan=2, sticky="ew")

        self.sidebar = Sidebar(self, on_select=self.show_page)
        self.sidebar.grid(row=1, column=0, sticky="ns")

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.grid(row=1, column=1, sticky="nsew",
                            padx=(SPACING.lg, SPACING.lg), pady=(SPACING.md, SPACING.lg))
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        self.chat_page = ChatPage(
            self.container, controller,
            add_listener=self.add_connection_listener,
            remove_listener=self.remove_connection_listener,
            panel_collapsed=prefs.conversation_panel_collapsed,
            on_panel_toggle=self._on_panel_toggle,
            on_status=self.set_status)
        self.memory_page = MemoryPage(self.container, controller)
        self.vision_page = VisionPage(self.container, controller)
        self.settings_page = SettingsPage(
            self.container, controller,
            add_listener=self.add_connection_listener,
            remove_listener=self.remove_connection_listener,
            on_provider_saved=self.chat_page.refresh_provider_label,
            appearance=prefs.appearance,
            on_appearance=self.set_appearance)
        self.pages = {
            "chat": self.chat_page, "memory": self.memory_page,
            "vision": self.vision_page, "settings": self.settings_page,
        }
        for page in self.pages.values():
            page.grid(row=0, column=0, sticky="nsew")

        self.show_page("chat")
        self.after(POLL_INTERVAL_MS, self._poll)
        self.after(50, self.apply_native_theme)
        self.chat_page.input_box.focus()

    # ------------------------------------------------------------------ #
    # 页面切换
    # ------------------------------------------------------------------ #
    def show_page(self, key: str) -> None:
        page = self.pages[key]
        page.tkraise()
        self.sidebar.set_active(key)
        self._current_page = key
        if hasattr(page, "on_show"):
            page.on_show()

    @property
    def current_page(self) -> str | None:
        return self._current_page

    def set_status(self, key: str) -> None:
        """角色状态（侧栏左下角）：online / thinking / waiting / resting / proactive。"""
        text, color_token = theme.STATUS_LABELS.get(key, theme.STATUS_LABELS["online"])
        self.sidebar.set_status(text, ctk_color(color_token))

    # ------------------------------------------------------------------ #
    # 外观
    # ------------------------------------------------------------------ #
    def apply_native_theme(self) -> None:
        mode = resolve_appearance(self.prefs.appearance)
        palette = theme.palette_for(mode)
        platform_win.apply_window_theme(
            self, dark=(mode == "dark"), caption=palette.titlebar, text=palette.titlebar_text,
            border=palette.titlebar)

    # ------------------------------------------------------------------ #
    # 偏好
    # ------------------------------------------------------------------ #
    def set_appearance(self, mode: str) -> None:
        if mode not in theme.APPEARANCE_MODES:
            return
        ctk.set_appearance_mode(mode)
        self.prefs = UIPrefs(appearance=mode, conversation_panel_collapsed=self.prefs.conversation_panel_collapsed)
        try:
            self.prefs_service.save(self.prefs)
        except OSError:
            pass
        self.apply_native_theme()

    def _on_panel_toggle(self, collapsed: bool) -> None:
        self.prefs = UIPrefs(appearance=self.prefs.appearance, conversation_panel_collapsed=collapsed)
        try:
            self.prefs_service.save(self.prefs)
        except OSError:
            pass  # 偏好写入失败不影响使用

    # ------------------------------------------------------------------ #
    # 连接检查监听（AI 设置弹窗注册）
    # ------------------------------------------------------------------ #
    def add_connection_listener(self, listener: ConnectionListener) -> None:
        self._connection_listeners.append(listener)

    def remove_connection_listener(self, listener: ConnectionListener) -> None:
        if listener in self._connection_listeners:
            self._connection_listeners.remove(listener)

    # ------------------------------------------------------------------ #
    # 轮询：worker 结果回到主线程
    # ------------------------------------------------------------------ #
    def _poll(self) -> None:
        result = self.controller.poll()
        for event in result.replies:
            self.chat_page.on_reply(event)
        for event in result.background:
            self.chat_page.on_background(event)
        for event in result.connection_checks:
            for listener in list(self._connection_listeners):
                listener(event)
        self.after(POLL_INTERVAL_MS, self._poll)


__all__ = ["MainWindow", "resolve_appearance", "WINDOW_TITLE"]
