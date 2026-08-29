import os
import shutil
import uuid
from pathlib import Path

from PIL import Image

SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
MAX_IMAGE_BYTES = 20 * 1024 * 1024


def image_root() -> Path:
    configured = os.getenv("MYAI_DATA_DIR")
    if configured:
        root = Path(configured).expanduser()
    else:
        local = os.getenv("LOCALAPPDATA")
        root = Path(local) / "MyAI" if local else Path.home() / ".myai"
    path = root / "images"
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_image(path_value: str | Path) -> Path:
    path = Path(path_value)
    if not path.is_file() or path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
        raise ValueError("请选择 PNG、JPG、JPEG、WEBP、GIF 或 BMP 图片。")
    if path.stat().st_size > MAX_IMAGE_BYTES:
        raise ValueError("图片不能超过 20 MB。")
    try:
        with Image.open(path) as image:
            image.verify()
    except Exception as exc:
        raise ValueError("图片文件已损坏或格式无法识别。") from exc
    return path


def persist_image(path_value: str | Path) -> str:
    source = validate_image(path_value)
    suffix = source.suffix.lower()
    if suffix == ".jpeg":
        suffix = ".jpg"
    if suffix in {".bmp", ".gif"}:
        suffix = ".png"
    filename = f"{uuid.uuid4().hex}{suffix}"
    target = image_root() / filename
    if source.suffix.lower() in {".bmp", ".gif"}:
        with Image.open(source) as image:
            image.seek(0)
            image.convert("RGBA").save(target, format="PNG")
    else:
        shutil.copy2(source, target)
    return filename


def resolve_image(relative_name: str | None) -> Path | None:
    if not relative_name:
        return None
    name = Path(relative_name).name
    candidate = image_root() / name
    return candidate if candidate.is_file() else None

