import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
except ImportError:  # 基础导入/离线测试不强制要求第三方依赖。
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()


def _positive_float(raw: str | None, default: float) -> float:
    try:
        value = float(raw) if raw is not None else default
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


@dataclass(frozen=True)
class LLMConfig:
    provider: str = "deepseek"
    api_key: str | None = None
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-flash"
    timeout: float = 30.0

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            provider=os.getenv("MYAI_LLM_PROVIDER", "deepseek").strip().lower(),
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip(),
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash").strip(),
            timeout=_positive_float(os.getenv("MYAI_LLM_TIMEOUT"), 30.0),
        )


@dataclass(frozen=True)
class VisionConfig:
    provider: str = "none"
    api_key: str | None = None
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-5.4-mini"
    timeout: float = 45.0

    @classmethod
    def from_env(cls) -> "VisionConfig":
        return cls(
            provider=os.getenv("MYAI_VISION_PROVIDER", "none").strip().lower(),
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip(),
            model=os.getenv("OPENAI_VISION_MODEL", "gpt-5.4-mini").strip(),
            timeout=_positive_float(os.getenv("MYAI_VISION_TIMEOUT"), 45.0),
        )

