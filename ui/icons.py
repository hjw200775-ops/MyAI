"""用 PIL 绘制的单色线性图标。

不依赖 emoji 字体（Tk 8.6 在 Windows 上对彩色 emoji 渲染不稳定），
所有图标在 4x 尺寸上绘制后缩小，边缘平滑。颜色由调用方按 Theme 传入。
"""
from __future__ import annotations

import math
from functools import lru_cache
from typing import Callable

from PIL import Image, ImageDraw

SUPERSAMPLE = 4


def _begin(size: int):
    edge = size * SUPERSAMPLE
    image = Image.new("RGBA", (edge, edge), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    stroke = max(SUPERSAMPLE, round(edge * 0.085))
    return image, draw, edge, stroke


def _finish(image: Image.Image, size: int) -> Image.Image:
    return image.resize((size, size), Image.Resampling.LANCZOS)


def _chat(size: int, color: str) -> Image.Image:
    image, draw, edge, stroke = _begin(size)
    pad = edge * 0.12
    body = (pad, pad + edge * 0.04, edge - pad, edge * 0.72)
    draw.rounded_rectangle(body, radius=edge * 0.2, outline=color, width=stroke)
    # 气泡尾巴：从底边左侧向下延伸的小三角，覆盖掉底边一小段
    tail = [(edge * 0.30, edge * 0.70), (edge * 0.24, edge * 0.90), (edge * 0.46, edge * 0.70)]
    draw.polygon(tail, fill=color)
    inner = [(edge * 0.33, edge * 0.70), (edge * 0.31, edge * 0.74), (edge * 0.40, edge * 0.70)]
    draw.polygon(inner, fill=(0, 0, 0, 0))
    return _finish(image, size)


def _memory(size: int, color: str) -> Image.Image:
    image, draw, edge, stroke = _begin(size)
    pad = edge * 0.14
    draw.rounded_rectangle((pad, pad, edge - pad, edge - pad), radius=edge * 0.18,
                           outline=color, width=stroke)
    for ratio in (0.38, 0.52, 0.66):
        y = edge * ratio
        x1 = edge * (0.70 if ratio == 0.66 else 0.72)
        draw.line((edge * 0.30, y, x1, y), fill=color, width=stroke)
    return _finish(image, size)


def _vision(size: int, color: str) -> Image.Image:
    image, draw, edge, stroke = _begin(size)
    cx, cy = edge / 2, edge / 2
    w, h = edge * 0.40, edge * 0.26
    # 杏仁形眼眶：两段圆弧
    r = (w * w + h * h) / (2 * h)
    # 上眼睑：圆心在 (cx, cy + r - h)，顶点在 (cx, cy - h)；下眼睑对称
    top_box = (cx - r, cy - h, cx + r, cy - h + 2 * r)
    bottom_box = (cx - r, cy + h - 2 * r, cx + r, cy + h)
    half = math.degrees(math.asin(w / r))
    draw.arc(top_box, 270 - half, 270 + half, fill=color, width=stroke)
    draw.arc(bottom_box, 90 - half, 90 + half, fill=color, width=stroke)
    pr = edge * 0.11
    draw.ellipse((cx - pr, cy - pr, cx + pr, cy + pr), outline=color, width=stroke)
    return _finish(image, size)


def _settings(size: int, color: str) -> Image.Image:
    image, draw, edge, stroke = _begin(size)
    cx, cy = edge / 2, edge / 2
    outer, inner = edge * 0.40, edge * 0.32
    points = []
    teeth = 8
    segment = math.pi / teeth  # 齿与齿槽交替，每段 22.5°
    for i in range(teeth * 2):
        angle = segment * i
        radius = outer if i % 2 == 0 else inner
        # 每段两点：形成平顶齿与平底槽，侧边自然倾斜
        for offset in (-0.38, 0.38):
            a = angle + offset * segment
            points.append((cx + radius * math.cos(a), cy + radius * math.sin(a)))
    draw.polygon(points, outline=color, width=stroke)
    hr = edge * 0.12
    draw.ellipse((cx - hr, cy - hr, cx + hr, cy + hr), outline=color, width=stroke)
    return _finish(image, size)


def _panel(size: int, color: str) -> Image.Image:
    image, draw, edge, stroke = _begin(size)
    pad = edge * 0.14
    draw.rounded_rectangle((pad, pad + edge * 0.04, edge - pad, edge - pad - edge * 0.04),
                           radius=edge * 0.16, outline=color, width=stroke)
    x = edge * 0.40
    draw.line((x, pad + edge * 0.04, x, edge - pad - edge * 0.04), fill=color, width=stroke)
    return _finish(image, size)


def _plus(size: int, color: str) -> Image.Image:
    image, draw, edge, stroke = _begin(size)
    c, half = edge / 2, edge * 0.28
    draw.line((c - half, c, c + half, c), fill=color, width=stroke)
    draw.line((c, c - half, c, c + half), fill=color, width=stroke)
    return _finish(image, size)


def _send(size: int, color: str) -> Image.Image:
    image, draw, edge, stroke = _begin(size)
    pts = [(edge * 0.18, edge * 0.20), (edge * 0.84, edge * 0.50),
           (edge * 0.18, edge * 0.80), (edge * 0.30, edge * 0.50)]
    draw.polygon(pts, fill=color)
    return _finish(image, size)


ICON_DRAWERS: dict[str, Callable[[int, str], Image.Image]] = {
    "chat": _chat,
    "memory": _memory,
    "vision": _vision,
    "settings": _settings,
    "panel": _panel,
    "plus": _plus,
    "send": _send,
}


@lru_cache(maxsize=128)
def icon_image(name: str, size: int, color: str) -> Image.Image:
    return ICON_DRAWERS[name](size, color)


def ctk_icon(name: str, size: int, colors: tuple[str, str]):
    """返回 CTkImage（light / dark 各一张）。延迟 import 以便本模块可离线测试。"""
    import customtkinter as ctk
    light, dark = colors
    return ctk.CTkImage(light_image=icon_image(name, size, light),
                        dark_image=icon_image(name, size, dark), size=(size, size))


__all__ = ["ICON_DRAWERS", "icon_image", "ctk_icon"]
