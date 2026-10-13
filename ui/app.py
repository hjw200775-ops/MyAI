"""应用入口：读取 UI 偏好 → 设置外观 → 创建 Controller 与 MainWindow → mainloop。"""
from __future__ import annotations

import customtkinter as ctk

from .assets import ensure_avatar_exists
from .controller import ChatController
from .main_window import MainWindow
from .theme import DEFAULT_APPEARANCE
from .ui_prefs import get_ui_prefs_service


def create_app() -> MainWindow:
    prefs_service = get_ui_prefs_service()
    prefs = prefs_service.load()
    ctk.set_appearance_mode(prefs.appearance or DEFAULT_APPEARANCE)
    ctk.set_default_color_theme("blue")
    ensure_avatar_exists()
    controller = ChatController()
    return MainWindow(controller, prefs_service, prefs)


def run() -> None:
    app = create_app()
    app.mainloop()


__all__ = ["create_app", "run"]
