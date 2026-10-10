"""Persistent, non-secret desktop preferences for MyAI V1.5."""
from __future__ import annotations

import json
import os
import tempfile
import re
from urllib.parse import urlsplit
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping


DEFAULT_OLLAMA_MODEL = "qwen3.5:2b"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
ALLOWED_TEXT_PROVIDERS = {"deepseek", "ollama"}


def default_settings_path() -> Path:
    override = os.getenv("MYAI_SETTINGS_PATH", "").strip()
    if override:
        return Path(override).expanduser()
    app_data = os.getenv("APPDATA", "").strip()
    if app_data:
        return Path(app_data) / "MyAI" / "settings.json"
    return Path.home() / ".config" / "MyAI" / "settings.json"


def _clean_provider(value: object, fallback: str = "deepseek") -> str:
    provider = str(value or "").strip().lower()
    return provider if provider in ALLOWED_TEXT_PROVIDERS else fallback


def _clean_text(value: object, fallback: str) -> str:
    text = value.strip() if isinstance(value, str) else ""
    return text or fallback


def _clean_model(value, fallback):
    text = _clean_text(value, fallback)
    return text if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}", text) else fallback


def _clean_url(value, fallback):
    text = _clean_text(value, fallback).rstrip("/")
    try:
        url = urlsplit(text)
        port = url.port
        valid = (url.scheme in {"http", "https"} and url.hostname and
                 not url.username and not url.password and not url.query and
                 not url.fragment and not url.path and
                 not any(c.isspace() or ord(c) < 32 for c in text))
        return text if valid else fallback
    except ValueError:
        return fallback


@dataclass(frozen=True)
class UserSettings:
    text_provider: str = "deepseek"
    ollama_model: str = DEFAULT_OLLAMA_MODEL
    ollama_base_url: str = DEFAULT_OLLAMA_BASE_URL

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "UserSettings":
        env = os.environ if environ is None else environ
        provider = env.get("TEXT_PROVIDER", env.get("MYAI_LLM_PROVIDER", "deepseek"))
        return cls(
            text_provider=_clean_provider(provider),
            ollama_model=_clean_model(env.get("OLLAMA_MODEL"), DEFAULT_OLLAMA_MODEL),
            ollama_base_url=_clean_url(
                env.get("OLLAMA_BASE_URL"), DEFAULT_OLLAMA_BASE_URL
            ).rstrip("/"),
        )

    @classmethod
    def from_mapping(cls, values: object, defaults: "UserSettings") -> "UserSettings":
        if not isinstance(values, dict):
            return defaults
        return cls(
            text_provider=_clean_provider(
                values.get("text_provider"), defaults.text_provider
            ),
            ollama_model=_clean_model(
                values.get("ollama_model"), defaults.ollama_model
            ),
            ollama_base_url=_clean_url(
                values.get("ollama_base_url"), defaults.ollama_base_url
            ).rstrip("/"),
        )


class SettingsService:
    """Loads safe defaults and atomically stores only non-secret preferences."""

    def __init__(self, path: str | Path | None = None,
                 environ: Mapping[str, str] | None = None):
        self.path = Path(path) if path is not None else default_settings_path()
        self.environ = os.environ if environ is None else environ

    def defaults(self) -> UserSettings:
        return UserSettings.from_env(self.environ)

    def load(self) -> UserSettings:
        defaults = self.defaults()
        try:
            values = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
            return defaults
        return UserSettings.from_mapping(values, defaults)

    def save(self, settings: UserSettings) -> UserSettings:
        clean = UserSettings.from_mapping(asdict(settings), self.defaults())
        secrets = [v for k, v in self.environ.items() if v and
                   any(word in k.upper() for word in ("KEY", "TOKEN", "SECRET", "PASSWORD"))]
        if any(secret in value for secret in secrets for value in asdict(clean).values()):
            raise ValueError("模型设置不能包含 API Key 或其他凭据。")
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


_default_service: SettingsService | None = None


def get_settings_service() -> SettingsService:
    global _default_service
    expected = default_settings_path()
    if _default_service is None or _default_service.path != expected:
        _default_service = SettingsService(expected)
    return _default_service


__all__ = ["SettingsService", "UserSettings", "get_settings_service",
           "default_settings_path", "DEFAULT_OLLAMA_MODEL",
           "DEFAULT_OLLAMA_BASE_URL"]
