from .base import LLMProvider, Message, VisionNotSupportedError
from .config import LLMConfig, VisionConfig
from .deepseek import DeepSeekProvider
from .openai_vision import OpenAIVisionProvider

_default_provider: LLMProvider | None = None
_vision_provider: LLMProvider | None = None


def create_provider(config: LLMConfig | None = None) -> LLMProvider:
    config = config or LLMConfig.from_env()
    if config.provider == "deepseek":
        return DeepSeekProvider(config)
    raise ValueError(f"不支持的 LLM Provider：{config.provider}。V1.2 仅实现 deepseek；以后可在这里注册 Ollama。")


def get_default_provider() -> LLMProvider:
    global _default_provider
    if _default_provider is None:
        _default_provider = create_provider()
    return _default_provider


def create_vision_provider(config: VisionConfig | None = None) -> LLMProvider:
    config = config or VisionConfig.from_env()
    if config.provider == "openai":
        return OpenAIVisionProvider(config)
    if config.provider in {"", "none", "disabled"}:
        raise VisionNotSupportedError(
            "尚未配置图片理解服务。请在 .env 设置 MYAI_VISION_PROVIDER=openai 和 OPENAI_API_KEY。"
        )
    raise ValueError(f"不支持的 Vision Provider：{config.provider}")


def get_vision_provider() -> LLMProvider:
    global _vision_provider
    if _vision_provider is None:
        _vision_provider = create_vision_provider()
    return _vision_provider


def set_default_provider(provider: LLMProvider | None) -> None:
    """供测试或未来设置界面替换 Provider，不触碰 ai.py。"""
    global _default_provider
    _default_provider = provider


def set_vision_provider(provider: LLMProvider | None) -> None:
    global _vision_provider
    _vision_provider = provider


__all__ = ["LLMConfig", "VisionConfig", "LLMProvider", "Message",
           "VisionNotSupportedError", "create_provider", "create_vision_provider",
           "get_default_provider", "get_vision_provider", "set_default_provider",
           "set_vision_provider"]

