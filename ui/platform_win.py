"""Windows 专用的窗口外观适配（方案 A）。

保留原生标题栏与窗口行为，只通过 DwmSetWindowAttribute 把标题栏 / 边框染成主题色。
非 Windows 平台、旧版本 Windows 或任何失败都静默忽略，不影响程序运行。
"""
from __future__ import annotations

import sys

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36


def colorref(hex_color: str) -> int:
    """'#RRGGBB' → Win32 COLORREF (0x00BBGGRR)。"""
    value = hex_color.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"invalid hex color: {hex_color!r}")
    r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    return (b << 16) | (g << 8) | r


def _root_hwnd(window) -> int | None:
    try:
        import ctypes
        hwnd = window.winfo_id()
        parent = ctypes.windll.user32.GetParent(hwnd)
        return parent or hwnd
    except Exception:
        return None


VK_PROCESSKEY = 229
GCS_COMPSTR = 0x0008


def ime_is_composing(widget=None) -> bool:
    """当前焦点是否处于 Windows IME 组字中。

    查不到上下文、非 Windows 或调用失败时返回 False。
    组字检测失败时 Enter 可能在候选确认时被当成发送，这是已知限制。
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        user32 = ctypes.windll.user32
        imm32 = ctypes.windll.imm32
        hwnd = user32.GetFocus()
        if not hwnd and widget is not None:
            hwnd = int(widget.winfo_id())
        if not hwnd:
            return False
        himc = imm32.ImmGetContext(hwnd)
        if not himc:
            return False
        try:
            size = imm32.ImmGetCompositionStringW(himc, GCS_COMPSTR, None, 0)
            return int(size) > 0
        finally:
            imm32.ImmReleaseContext(hwnd, himc)
    except Exception:
        return False


def apply_window_theme(window, *, dark: bool, caption: str, text: str,
                       border: str | None = None) -> bool:
    """给已显示的 Tk 顶层窗口染色。返回是否成功调用了 DWM。"""
    if sys.platform != "win32":
        return False
    hwnd = _root_hwnd(window)
    if not hwnd:
        return False
    try:
        import ctypes
        from ctypes import wintypes
        dwm = ctypes.windll.dwmapi

        def set_attribute(attribute: int, value: int) -> None:
            data = ctypes.c_int(value)
            dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), ctypes.c_uint(attribute),
                                      ctypes.byref(data), ctypes.sizeof(data))

        set_attribute(DWMWA_USE_IMMERSIVE_DARK_MODE, 1 if dark else 0)
        set_attribute(DWMWA_CAPTION_COLOR, colorref(caption))
        set_attribute(DWMWA_TEXT_COLOR, colorref(text))
        set_attribute(DWMWA_BORDER_COLOR, colorref(border or caption))
        return True
    except Exception:
        return False


__all__ = ["apply_window_theme", "colorref", "ime_is_composing", "VK_PROCESSKEY"]
