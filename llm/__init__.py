from threading import RLock
from functools import wraps

_provider_lock = RLock()

def _synchronized(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with _provider_lock:
            return function(*args, **kwargs)
    return wrapped

from .base import LLMProvider, Message, VisionNotSupportedError
from .config import LLMConfig, VisionConfig
from .deepseek import DeepSeekProvider
from .deepseek_vision import DeepSeekVisionProvider
from .ollama import OllamaProvider
from .openai_vision import OpenAIVisionProvider
from settings import UserSettings, get_settings_service

_default_provider: LLMProvider | None = None
_vision_provider: LLMProvider | None = None


def create_provider(config: LLMConfig | None = None) -> LLMProvider:
    config = config or LLMConfig.from_env()
    if config.provider == "deepseek":
        return DeepSeekProvider(config)
    if config.provider == "ollama":
        return OllamaProvider(config)
    raise ValueError(
        f"不支持的文本 Provider：{config.provider}。请将 TEXT_PROVIDER 设为 deepseek 或 ollama。"
    )


@_synchronized
def get_default_provider() -> LLMProvider:
    global _default_provider
    if _default_provider is None:
        settings = get_settings_service().load()
        _default_provider = create_provider(LLMConfig.from_settings(settings))
    return _default_provider


@_synchronized
def apply_text_settings(settings: UserSettings) -> LLMProvider:
    """Hot-swap text generation for subsequent calls; Vision stays untouched."""
    config = LLMConfig.from_settings(settings)
    if _default_provider is not None and getattr(_default_provider, "config", None) == config:
        return _default_provider
    provider = create_provider(config)
    set_default_provider(provider)
    return provider


def create_vision_provider(config: VisionConfig | None = None) -> LLMProvider:
    config = config or VisionConfig.from_env()
    if config.provider == "deepseek":
        return DeepSeekVisionProvider(config)
    if config.provider == "openai":
        return OpenAIVisionProvider(config)
    if config.provider in {"", "none", "disabled"}:
        raise VisionNotSupportedError(
            "图片理解服务已禁用。请设置 MYAI_VISION_PROVIDER=deepseek 和 DEEPSEEK_API_KEY。"
        )
    raise ValueError(f"不支持的 Vision Provider：{config.provider}")


@_synchronized
def get_vision_provider() -> LLMProvider:
    global _vision_provider
    if _vision_provider is None:
        _vision_provider = create_vision_provider()
    return _vision_provider


@_synchronized
def set_default_provider(provider: LLMProvider | None) -> None:
    """供测试或未来设置界面替换 Provider，不触碰 ai.py。"""
    global _default_provider
    _default_provider = provider


@_synchronized
def set_vision_provider(provider: LLMProvider | None) -> None:
    global _vision_provider
    _vision_provider = provider


__all__ = ["LLMConfig", "VisionConfig", "LLMProvider", "Message", "OllamaProvider",
           "VisionNotSupportedError", "create_provider", "create_vision_provider",
           "get_default_provider", "get_vision_provider", "set_default_provider",
           "set_vision_provider", "apply_text_settings"]
