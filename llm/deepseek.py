from typing import TYPE_CHECKING, Any, Mapping, Sequence
from .base import LLMProvider, Message, VisionNotSupportedError
from .config import LLMConfig
from .diagnostics import ProviderCallError

if TYPE_CHECKING:
    from openai import OpenAI


class DeepSeekProvider(LLMProvider):
    def __init__(self, config: LLMConfig):
        self.config = config
        self._client: "OpenAI | None" = None

    def _get_client(self) -> "OpenAI":
        if not self.config.api_key:
            raise RuntimeError("未设置 DEEPSEEK_API_KEY 环境变量。")
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError("缺少 openai 依赖，请先安装 requirements.txt。") from exc
            self._client = OpenAI(api_key=self.config.api_key, base_url=self.config.base_url)
        return self._client

    def chat(self, messages: Sequence[Message], *, response_format: Mapping[str, Any] | None = None,
             timeout: float | None = None) -> str:
        if any(isinstance(message.get("content"), list) for message in messages):
            raise VisionNotSupportedError(
                "当前 DeepSeek 文本 Provider 未配置图片能力，请设置独立的 Vision Provider。"
            )
        request: dict[str, Any] = {
            "model": self.config.model,
            "messages": list(messages),
            "timeout": timeout or self.config.timeout,
        }
        request["extra_body"] = {
    "thinking": {
        "type": "disabled"
            }
        }
        if response_format is not None:
            request["response_format"] = dict(response_format)
        response = self._get_client().chat.completions.create(**request)
        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError):
            raise ProviderCallError("DeepSeek 返回了无法识别的响应，请稍后重试。") from None
        if not isinstance(content, str) or not content.strip():
            raise ProviderCallError("DeepSeek 返回了空回复，请稍后重试。")
        return content.strip()
