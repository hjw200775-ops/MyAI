"""独立的 UI 偏好持久化（外观模式等）。

与 settings.py / UserSettings 完全分离：
- 不写入 settings.json，不扩展 UserSettings 字段；
- 默认位于 %APPDATA%\\MyAI\\ui_prefs.json，可用 MYAI_UI_PREFS_PATH 覆盖（离线测试用）；
- 缺失 / 损坏 / 非法值一律回退默认，不阻止程序启动；
- 写入与 settings.py 相同：同目录临时文件 + fsync + 原子替换。
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from .theme import APPEARANCE_MODES, DEFAULT_APPEARANCE


def default_ui_prefs_path() -> Path:
    override = os.getenv("MYAI_UI_PREFS_PATH", "").strip()
    if override:
        return Path(override).expanduser()
    app_data = os.getenv("APPDATA", "").strip()
    if app_data:
        return Path(app_data) / "MyAI" / "ui_prefs.json"
    return Path.home() / ".config" / "MyAI" / "ui_prefs.json"


def _clean_appearance(value: object, fallback: str) -> str:
    text = str(value or "").strip().lower()
    return text if text in APPEARANCE_MODES else fallback


def _clean_bool(value: object, fallback: bool) -> bool:
    return value if isinstance(value, bool) else fallback


@dataclass(frozen=True)
class UIPrefs:
    appearance: str = DEFAULT_APPEARANCE          # dark / light / system
    conversation_panel_collapsed: bool = False    # 对话页第二列折叠状态

    @classmethod
    def from_mapping(cls, values: object, defaults: "UIPrefs") -> "UIPrefs":
        if not isinstance(values, dict):
            return defaults
        return cls(
            appearance=_clean_appearance(values.get("appearance"), defaults.appearance),
            conversation_panel_collapsed=_clean_bool(
                values.get("conversation_panel_collapsed"),
                defaults.conversation_panel_collapsed),
        )


class UIPrefsService:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else default_ui_prefs_path()

    def defaults(self) -> UIPrefs:
        return UIPrefs()

    def load(self) -> UIPrefs:
        defaults = self.defaults()
        try:
            values = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
            return defaults
        return UIPrefs.from_mapping(values, defaults)

    def save(self, prefs: UIPrefs) -> UIPrefs:
        clean = UIPrefs.from_mapping(asdict(prefs), self.defaults())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                    "w", encoding="utf-8", dir=self.path.parent,
                    prefix=f".{self.path.name}.", suffix=".tmp", delete=False) as handle:
                temporary_path = Path(handle.name)
                json.dump(asdict(clean), handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                try:
                    temporary_path.unlink()
                except OSError:
                    pass
        return clean


_default_service: UIPrefsService | None = None


def get_ui_prefs_service() -> UIPrefsService:
    global _default_service
    expected = default_ui_prefs_path()
    if _default_service is None or _default_service.path != expected:
        _default_service = UIPrefsService(expected)
    return _default_service


__all__ = ["UIPrefs", "UIPrefsService", "get_ui_prefs_service", "default_ui_prefs_path"]
