import base64
import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from .base import LLMProvider, Message
from .config import VisionConfig

if TYPE_CHECKING:
    from openai import OpenAI


def _as_data_url(path_value: str) -> str:
    path = Path(path_value)
    if not path.is_file():
        raise FileNotFoundError(f"图片资源不存在：{path.name}")
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _prepare_messages(messages: Sequence[Message]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            prepared.append({"role": message["role"], "content": content})
            continue
        parts: list[dict[str, Any]] = []
        for part in content:
            if part.get("type") in {"image_path", "image_url"} and message["role"] != "user":
                raise ValueError("图片内容块只能出现在 user 消息中。")
            if part.get("type") == "image_path":
                parts.append({
                    "type": "image_url",
                    "image_url": {"url": _as_data_url(str(part["path"])), "detail": "auto"},
                })
            elif part.get("type") == "text":
                parts.append({"type": "text", "text": str(part.get("text", ""))})
            elif part.get("type") == "image_url":
                parts.append({"type": "image_url", "image_url": dict(part["image_url"])})
            else:
                raise ValueError("不支持的视觉消息内容块。")
        prepared.append({"role": message["role"], "content": parts})
    return prepared


class OpenAIVisionProvider(LLMProvider):
    api_key_variable = "OPENAI_API_KEY"
    def __init__(self, config: VisionConfig):
        self.config = config
        self._client: "OpenAI | None" = None

    @property
    def supports_vision(self) -> bool:
        return True

    def _get_client(self) -> "OpenAI":
        if not self.config.api_key:
            raise RuntimeError(f"未设置 {self.api_key_variable} 环境变量。")
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError("缺少 openai 依赖，请先安装 requirements.txt。") from exc
            self._client = OpenAI(api_key=self.config.api_key, base_url=self.config.base_url)
        return self._client

    def chat(self, messages: Sequence[Message], *, response_format: Mapping[str, Any] | None = None,
             timeout: float | None = None) -> str:
        request: dict[str, Any] = {
            "model": self.config.model,
            "messages": _prepare_messages(messages),
            "timeout": timeout or self.config.timeout,
        }
        if response_format is not None:
            request["response_format"] = dict(response_format)
        response = self._get_client().chat.completions.create(**request)
        return str(response.choices[0].message.content or "").strip()
