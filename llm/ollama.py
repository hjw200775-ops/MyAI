"""Ollama local text transport and V1.5 connection diagnostics."""
import json
import socket
from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .base import LLMProvider, Message, VisionNotSupportedError
from .config import LLMConfig
from .diagnostics import ProviderCallError, safe_label


@dataclass(frozen=True)
class OllamaStatus:
    code: str
    message: str


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

    def _tags_endpoint(self) -> str:
        return f"{self._endpoint().rsplit('/', 1)[0]}/tags"

    def check_status(self, timeout: float = 3.0) -> OllamaStatus:
        """Check the local service and configured model without generating text."""
        try:
            request = Request(self._tags_endpoint(), method="GET")
            with urlopen(request, timeout=timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
            models = body.get("models", [])
            names = {
                str(item.get("name", "")) for item in models if isinstance(item, dict)
            }
        except HTTPError as exc:
            return OllamaStatus("http_error", f"连接失败：Ollama 返回 HTTP {exc.code}")
        except (URLError, ConnectionError, OSError) as exc:
            reason = getattr(exc, "reason", None)
            if isinstance(exc, (TimeoutError, socket.timeout)) or isinstance(
                    reason, (TimeoutError, socket.timeout)):
                return OllamaStatus("timeout", "连接超时：请检查 Ollama 地址")
            return OllamaStatus("unavailable", "服务未启动或无法连接")
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError, TypeError):
            return OllamaStatus("invalid_response", "连接成功，但服务响应无法识别")
        if self.config.model not in names:
            return OllamaStatus(
                "model_missing", f"已连接，但未安装模型：{self.config.model}"
            )
        return OllamaStatus("ok", f"已连接，模型可用：{self.config.model}")

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
                "Ollama 在 MyAI V1.5 中只处理纯文字；图片仍由 DeepSeek Vision 处理。"
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
