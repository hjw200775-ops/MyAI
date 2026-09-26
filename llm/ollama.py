"""Ollama's local /api/chat transport for V1.4.2 text generation only."""
import json
import socket
from typing import Any, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .base import LLMProvider, Message, VisionNotSupportedError
from .config import LLMConfig
from .diagnostics import ProviderCallError, safe_label


class OllamaProvider(LLMProvider):
    def __init__(self, config: LLMConfig):
        self.config = config

    def _endpoint(self) -> str:
        base_url = self.config.base_url.rstrip("/")
        parsed = urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ProviderCallError(
                "Ollama 地址无效，请检查 OLLAMA_BASE_URL（例如 http://127.0.0.1:11434）。"
            )
        return f"{base_url}/api/chat"

    @staticmethod
    def _format(response_format: Mapping[str, Any] | None) -> Any:
        if response_format is None:
            return None
        # The existing context analyzers use OpenAI's json_object marker.
        # Ollama's native API expresses the same request as format="json".
        if response_format.get("type") == "json_object":
            return "json"
        return dict(response_format)

    def chat(self, messages: Sequence[Message], *,
             response_format: Mapping[str, Any] | None = None,
             timeout: float | None = None) -> str:
        if any(isinstance(message.get("content"), list) for message in messages):
            raise VisionNotSupportedError(
                "Ollama 在 MyAI V1.4.2 中只处理纯文字；图片仍由 DeepSeek Vision 处理。"
            )
        if not self.config.model:
            raise ProviderCallError("未设置 OLLAMA_MODEL，请在 .env 中填写已安装的模型名。")

        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [dict(message) for message in messages],
            "stream": False,
            "think": self.config.think,
            "keep_alive": self.config.keep_alive,
            "options": {"num_ctx": self.config.num_ctx},
        }
        output_format = self._format(response_format)
        if output_format is not None:
            payload["format"] = output_format
        request = Request(
            self._endpoint(),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        request_timeout = timeout or self.config.timeout
        try:
            with urlopen(request, timeout=request_timeout) as response:
                raw = response.read()
        except HTTPError as exc:
            if exc.code == 404:
                model = safe_label(self.config.model, self.config)
                raise ProviderCallError(
                    f"Ollama 未找到模型 {model}。请先运行：ollama pull {model}"
                ) from None
            raise ProviderCallError(
                f"Ollama 返回 HTTP {exc.code}，请确认服务与模型配置正确。"
            ) from None
        except (URLError, ConnectionError, OSError) as exc:
            if isinstance(exc, (TimeoutError, socket.timeout)) or isinstance(
                    getattr(exc, "reason", None), (TimeoutError, socket.timeout)):
                raise ProviderCallError(
                    "Ollama 请求超时。首次加载模型可能较慢，可增大 OLLAMA_TIMEOUT。"
                ) from None
            raise ProviderCallError(
                "无法连接 Ollama。请确认 Ollama 已启动，且 OLLAMA_BASE_URL 可访问。"
            ) from None

        try:
            body = json.loads(raw.decode("utf-8"))
            content = body["message"]["content"]
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
            raise ProviderCallError("Ollama 返回了无法识别的响应，请更新 Ollama 后重试。") from None
        if not isinstance(content, str) or not content.strip():
            raise ProviderCallError("Ollama 返回了空回复，请确认模型可以正常运行。")
        return content.strip()
