"""静态资源：小悠头像的加载、圆形裁剪与缓存。

PIL 层函数不依赖 tkinter，可离线测试；`avatar_ctk_image()` 是可选的 CTkImage 包装，
只在视图层调用（Tk 根窗口创建之后）。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw

BASE_DIR = Path(__file__).resolve().parents[1]
AVATAR_PATH = BASE_DIR / "assets" / "character" / "xiaoyou_avatar.png"


def ensure_avatar_exists() -> Path:
    """与原 gui.py 一致：头像缺失时在启动阶段直接报错，而不是静默显示空白。"""
    if not AVATAR_PATH.is_file():
        raise FileNotFoundError(f"找不到小悠头像资源：{AVATAR_PATH}")
    return AVATAR_PATH


@lru_cache(maxsize=1)
def _avatar_source() -> Image.Image:
    with Image.open(ensure_avatar_exists()) as source:
        return source.convert("RGBA")


def avatar_image(size: int, *, circular: bool = True) -> Image.Image:
    """返回指定边长的方形头像；circular=True 时裁成圆形（透明角）。"""
    source = _avatar_source()
    edge = min(source.size)
    left = (source.width - edge) // 2
    top = (source.height - edge) // 2
    square = source.crop((left, top, left + edge, top + edge))
    # 先在 4x 尺寸上画圆再缩小，边缘更平滑。
    supersample = max(size * 4, 64)
    square = square.resize((supersample, supersample), Image.Resampling.LANCZOS)
    if circular:
        mask = Image.new("L", (supersample, supersample), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, supersample - 1, supersample - 1), fill=255)
        square.putalpha(mask)
    return square.resize((size, size), Image.Resampling.LANCZOS)


def make_thumbnail(path_value: str | Path, box: tuple[int, int]) -> Image.Image:
    """为待发送图片生成预览（复制后缩放，不保留文件句柄）。"""
    with Image.open(path_value) as source:
        image = source.copy()
    image.thumbnail(box, Image.Resampling.LANCZOS)
    return image


def hosted_image_thumbnail(image_name: str | None, box: tuple[int, int]) -> Image.Image | None:
    """按 messages.image_path 中保存的托管文件名生成缩略图；文件缺失或损坏返回 None。"""
    from media import resolve_image
    path = resolve_image(image_name)
    if path is None:
        return None
    try:
        return make_thumbnail(path, box)
    except (OSError, ValueError):
        return None


def avatar_ctk_image(size: int, *, circular: bool = True):
    """CTkImage 包装；延迟 import 以保持本模块可离线测试。"""
    import customtkinter as ctk
    image = avatar_image(size, circular=circular)
    return ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))


__all__ = ["AVATAR_PATH", "ensure_avatar_exists", "avatar_image", "make_thumbnail",
           "hosted_image_thumbnail", "avatar_ctk_image"]
