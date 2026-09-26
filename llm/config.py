import os
from pathlib import Path
from dataclasses import dataclass, field
import math

DEEPSEEK_VISION_MODEL = "deepseek-v4-flash-vision-exp"

try:
    from dotenv import load_dotenv
except ImportError:  # 基础导入/离线测试不强制要求第三方依赖。
    load_dotenv = None

def _load_environment() -> None:
    # Explicit project path avoids discovering unrelated parent .env files.
    if load_dotenv is not None and os.getenv("MYAI_LOAD_DOTENV", "1") != "0":
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")


# Preserve startup configuration loading; tests explicitly disable it.
_load_environment()


def _positive_float(raw: str | None, default: float) -> float:
    try:
        value = float(raw) if raw is not None else default
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) and value > 0 else default


def _bounded_int(raw: str | None, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(raw) if raw is not None else default
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))


def _boolean(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


@dataclass(frozen=True)
class LLMConfig:
    provider: str = "deepseek"
    api_key: str | None = field(default=None, repr=False)
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-flash"
    timeout: float = 30.0
    keep_alive: str = "10m"
    num_ctx: int = 4096
    think: bool = False

    @classmethod
    def from_env(cls) -> "LLMConfig":
        _load_environment()
        # TEXT_PROVIDER is the V1.4 public setting. Keep the old name as a
        # fallback so an existing V1.3 .env continues to select DeepSeek.
        provider = os.getenv("TEXT_PROVIDER")
        if provider is None:
            provider = os.getenv("MYAI_LLM_PROVIDER", "deepseek")
        provider = provider.strip().lower()
        if provider == "ollama":
            return cls(
                provider=provider,
                api_key=None,
                base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip(),
                model=os.getenv("OLLAMA_MODEL", "qwen3.5:2b").strip(),
                timeout=_positive_float(
                    os.getenv("OLLAMA_TIMEOUT", os.getenv("MYAI_LLM_TIMEOUT")), 60.0
                ),
                keep_alive=os.getenv("OLLAMA_KEEP_ALIVE", "10m").strip() or "10m",
                num_ctx=_bounded_int(os.getenv("OLLAMA_NUM_CTX"), 4096, 512, 32768),
                think=_boolean(os.getenv("OLLAMA_THINK"), False),
            )
        return cls(
            provider=provider,
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip(),
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash").strip(),
            timeout=_positive_float(os.getenv("MYAI_LLM_TIMEOUT"), 30.0),
        )


@dataclass(frozen=True)
class VisionConfig:
    provider: str = "deepseek"
    api_key: str | None = field(default=None, repr=False)
    base_url: str = "https://api.deepseek.com"
    model: str = DEEPSEEK_VISION_MODEL
    timeout: float = 120.0

    @classmethod
    def from_env(cls) -> "VisionConfig":
        _load_environment()
        provider = os.getenv("MYAI_VISION_PROVIDER", "deepseek").strip().lower()
        is_openai = provider == "openai"
        api_key = os.getenv("OPENAI_API_KEY" if is_openai else "DEEPSEEK_API_KEY")
        raw_model = os.getenv("OPENAI_VISION_MODEL" if is_openai else "DEEPSEEK_VISION_MODEL")
        if is_openai:
            model = (raw_model or "gpt-5.4-mini").strip()
        else:
            # DeepSeek currently exposes one Chat Completions vision model.  A
            # typo here (or accidentally pasting the API key into this field)
            # otherwise reaches the server as a misleading HTTP 400.  Keep the
            # secret untouched in the environment, but never use it as a model.
            candidate = (raw_model or DEEPSEEK_VISION_MODEL).strip()
            model = candidate if candidate == DEEPSEEK_VISION_MODEL else DEEPSEEK_VISION_MODEL
        return cls(
            provider=provider,
            api_key=api_key,
            base_url=os.getenv("OPENAI_BASE_URL" if is_openai else "DEEPSEEK_BASE_URL",
                               "https://api.openai.com/v1" if is_openai else "https://api.deepseek.com").strip(),
            model=model,
            timeout=_positive_float(os.getenv("MYAI_VISION_TIMEOUT"), 120.0),
        )
