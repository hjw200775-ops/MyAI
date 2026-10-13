"""小悠 UI Design Token。

本模块只包含纯数据与无副作用的辅助函数，不 import customtkinter / tkinter，
因此可以被离线测试、未来的 Web / Live2D / 移动端工具直接复用。

所有颜色均提供 Light / Dark 两套；`ctk_color(name)` 返回 CustomTkinter 需要的
`(light, dark)` 元组，这样运行时切换外观模式时 CustomTkinter 会自动取对应值。

规范来源：docs/UI_DESIGN.md。修改视觉只改这里，不要在视图代码中硬编码。
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Literal

AppearanceMode = Literal["light", "dark", "system"]
APPEARANCE_MODES: tuple[str, ...] = ("dark", "light", "system")
DEFAULT_APPEARANCE: str = "dark"


# --------------------------------------------------------------------------- #
# 颜色
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Palette:
    """一套完整的语义色板。字段名即 Token 名。"""

    # 画布 / 表面
    background: str          # 窗口底色
    surface: str             # 卡片、面板
    surface_alt: str         # 次级区域（侧栏、输入区底）
    surface_hover: str       # 可交互表面 hover
    surface_active: str      # 当前选中项背景

    # 强调色（低饱和蓝紫）
    primary: str
    primary_hover: str
    primary_soft: str        # 强调色的浅底（选中态、用户气泡）
    on_primary: str          # 放在 primary 上的文字

    # 文字
    text_primary: str
    text_secondary: str
    text_muted: str          # 占位符、时间戳
    text_on_soft: str        # 放在 primary_soft 上的文字

    # 线条
    border: str
    border_strong: str

    # 聊天气泡
    bubble_user: str
    bubble_user_text: str
    bubble_assistant: str
    bubble_assistant_text: str
    bubble_system: str
    bubble_system_text: str

    # 语义状态
    success: str
    warning: str
    error: str
    error_hover: str

    # 其它
    scrollbar: str
    scrollbar_hover: str
    titlebar: str            # DWM 标题栏染色 & 内部视觉标题区
    titlebar_text: str
    overlay: str             # 遮罩 / 弹层底


LIGHT = Palette(
    background="#F5F6FA",
    surface="#FFFFFF",
    surface_alt="#EEF0F5",
    surface_hover="#E8EAF1",
    surface_active="#E3E6F3",

    primary="#7B86C8",
    primary_hover="#6A75B8",
    primary_soft="#E9EBF8",
    on_primary="#FFFFFF",

    text_primary="#2D3038",
    text_secondary="#7A7F8C",
    text_muted="#A3A8B5",
    text_on_soft="#3B4160",

    border="#E2E4EB",
    border_strong="#CDD1DC",

    bubble_user="#E9EBF8",
    bubble_user_text="#2D3038",
    bubble_assistant="#EEF0F5",
    bubble_assistant_text="#2D3038",
    bubble_system="#F0F1F5",
    bubble_system_text="#7A7F8C",

    success="#6FB38A",
    warning="#D9A85B",
    error="#D47B7B",
    error_hover="#C46A6A",

    scrollbar="#D5D8E2",
    scrollbar_hover="#BFC4D3",
    titlebar="#F5F6FA",
    titlebar_text="#2D3038",
    overlay="#000000",
)

DARK = Palette(
    background="#17191F",
    surface="#20232B",
    surface_alt="#272B35",
    surface_hover="#2D3240",
    surface_active="#32384A",

    primary="#8D97D6",
    primary_hover="#9CA5E0",
    primary_soft="#2E3350",
    on_primary="#17191F",

    text_primary="#E7E9EE",
    text_secondary="#9AA0AE",
    text_muted="#6E7482",
    text_on_soft="#D6DAF2",

    border="#2F333E",
    border_strong="#3C4150",

    bubble_user="#2E3350",
    bubble_user_text="#E7E9EE",
    bubble_assistant="#272B35",
    bubble_assistant_text="#E7E9EE",
    bubble_system="#1F222A",
    bubble_system_text="#9AA0AE",

    success="#7FBF98",
    warning="#D9B36B",
    error="#D98A8A",
    error_hover="#E09A9A",

    scrollbar="#30343F",
    scrollbar_hover="#3C4150",
    titlebar="#17191F",
    titlebar_text="#E7E9EE",
    overlay="#000000",
)

COLOR_TOKENS: tuple[str, ...] = tuple(f.name for f in fields(Palette))


def ctk_color(name: str) -> tuple[str, str]:
    """返回 CustomTkinter 风格的 (light, dark) 颜色元组。"""
    return (getattr(LIGHT, name), getattr(DARK, name))


def palette_for(mode: str) -> Palette:
    """按解析后的实际模式（light/dark）取色板；system 需先由调用方解析。"""
    return DARK if mode == "dark" else LIGHT


# --------------------------------------------------------------------------- #
# 圆角 / 间距 / 尺寸
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class RadiusScale:
    xs: int = 6    # 小组件（标签、chip）
    sm: int = 8    # 按钮
    md: int = 12   # 输入框、卡片
    lg: int = 14   # 聊天气泡
    xl: int = 16   # 弹窗、大气泡


@dataclass(frozen=True)
class SpacingScale:
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 24
    xxl: int = 32


@dataclass(frozen=True)
class SizeScale:
    window_default: tuple[int, int] = (960, 700)
    window_min: tuple[int, int] = (780, 580)
    titlebar_height: int = 44
    sidebar_width: int = 72            # 图标导航栏
    conversation_panel_width: int = 220  # 对话页第二列（可折叠）
    content_max: int = 720               # 记忆 / 设置 / 视觉页阅读宽度上限
    nav_button: int = 44
    avatar_sm: int = 28               # 气泡旁头像
    avatar_md: int = 36
    avatar_lg: int = 72               # 侧栏 / 关于页
    input_min_height: int = 52
    input_max_height: int = 160
    input_preview: tuple[int, int] = (72, 48)  # 输入框上方待发送图片 chip
    send_button: int = 36
    bubble_max_ratio: float = 0.70    # 气泡最大宽度占聊天区比例
    thumbnail: tuple[int, int] = (160, 112)
    icon: int = 20


RADIUS = RadiusScale()
SPACING = SpacingScale()
SIZE = SizeScale()


# --------------------------------------------------------------------------- #
# 字体
# --------------------------------------------------------------------------- #
FONT_FAMILY_CJK = "Microsoft YaHei UI"
FONT_FAMILY_LATIN = "Segoe UI"
FONT_FAMILY_MONO = "Consolas"
FONT_FAMILY = FONT_FAMILY_CJK  # Tk 单字体族；YaHei UI 自带拉丁字形，视觉接近 Segoe UI


@dataclass(frozen=True)
class FontScale:
    xs: int = 11   # 时间戳、角标
    sm: int = 12   # 次级说明
    md: int = 14   # 正文 / 气泡
    lg: int = 16   # 输入框、强调正文
    xl: int = 20   # 页面标题
    xxl: int = 24  # 角色名


FONT = FontScale()

FontWeight = Literal["normal", "bold"]


def font(size: int = FONT.md, weight: FontWeight = "normal",
         family: str = FONT_FAMILY) -> tuple[str, int, str]:
    """返回 Tk 兼容的字体元组，视图层可直接传给 CTk 控件的 font 参数。"""
    return (family, size, weight)


# --------------------------------------------------------------------------- #
# 动效（毫秒）
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class MotionScale:
    hover: int = 120          # 按钮 hover 过渡
    fast: int = 150
    normal: int = 200         # 页面切换 fade / slide
    slow: int = 250
    message_in: int = 180     # 新消息 fade + 上浮
    thinking_period: int = 900  # 「小悠正在想……」呼吸周期
    frame_interval: int = 16  # after() 步进，约 60fps


MOTION = MotionScale()


# --------------------------------------------------------------------------- #
# 角色化文案（状态系统 / Thinking）
# --------------------------------------------------------------------------- #
CHARACTER_NAME = "小悠"
APP_VERSION_LABEL = "MyAI V1.6.1"

STATUS_TEXT = {
    "online": "● 小悠在线",
    "thinking": "◐ 思考中",
    "waiting": "◌ 等待",
    "resting": "☾ 休息",
    "proactive": "✦ 主动思考",
    "companion": "● 陪伴中",
}

# 侧栏状态指示器使用：文字 + 圆点颜色 Token（圆点由组件自己绘制）
STATUS_LABELS = {
    "online": ("在线", "success"),
    "thinking": ("思考中", "primary"),
    "waiting": ("等待", "text_muted"),
    "resting": ("休息", "text_muted"),
    "proactive": ("主动思考", "primary"),
    # 预留。当前侧栏仍显示在线 / 思考中，没有新的按钮或布局。
    "companion": ("陪伴中", "primary"),
}

MEMORY_SAVED_TEXT = "小悠记住了：{}"
LOAD_OLDER_TEXT = "加载更早的消息"
INPUT_PLACEHOLDER = "和小悠说点什么……"
ATTACH_IMAGE_LABEL = "上传图片"

THINKING_TEXT = {
    "default": "小悠正在想……",
    "vision": "小悠正在看图片……",
    "memory": "小悠正在回忆……",
    "screen": "小悠正在看看屏幕……",
}

PROACTIVE_LABEL = "小悠 · 刚刚想起你"


__all__ = [
    "APPEARANCE_MODES", "DEFAULT_APPEARANCE", "AppearanceMode",
    "Palette", "LIGHT", "DARK", "COLOR_TOKENS", "ctk_color", "palette_for",
    "RADIUS", "SPACING", "SIZE", "RadiusScale", "SpacingScale", "SizeScale",
    "FONT", "FONT_FAMILY", "FONT_FAMILY_CJK", "FONT_FAMILY_LATIN", "FONT_FAMILY_MONO",
    "FontScale", "font",
    "MOTION", "MotionScale",
    "CHARACTER_NAME", "APP_VERSION_LABEL", "STATUS_TEXT", "STATUS_LABELS", "THINKING_TEXT",
    "PROACTIVE_LABEL", "MEMORY_SAVED_TEXT", "LOAD_OLDER_TEXT",
    "INPUT_PLACEHOLDER", "ATTACH_IMAGE_LABEL",
]
