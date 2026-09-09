import base64
import io
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Sequence
from urllib.parse import urlsplit

from .base import LLMProvider, Message
from .config import VisionConfig
from .diagnostics import (LocalValidationError, ProviderCallError, report_error,
                          logger, configuration_summary)
from PIL import Image

if TYPE_CHECKING:
    from openai import OpenAI


def _as_data_url(path_value: str, max_dimension: int = 8192) -> str:
    path = Path(path_value)
    if not path.is_file():
        raise FileNotFoundError(f"图片资源不存在：{path.name}")
    if path.stat().st_size > 20 * 1024 * 1024:
        raise LocalValidationError("图片超过应用的 20 MiB 限制")
    data = path.read_bytes()
    with Image.open(io.BytesIO(data)) as image:
        if max(image.size) > max_dimension:
            raise LocalValidationError("图片尺寸超过接口限制，请缩小图片后重试")
        image.verify()
        fmt = image.format
    mime = {"JPEG": "image/jpeg", "PNG": "image/png", "GIF": "image/gif",
            "WEBP": "image/webp"}.get(fmt)
    if mime is None:
        with Image.open(io.BytesIO(data)) as image:
            output = io.BytesIO()
            image.convert("RGBA").save(output, format="PNG")
            data = output.getvalue()
        mime = "image/png"
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _prepare_messages(messages: Sequence[Message], *, image_detail: str | None = "auto") -> list[dict[str, Any]]:
    image_count = sum(part.get("type") in {"image_path", "image_url"}
                      for message in messages if isinstance(message.get("content"), list)
                      for part in message["content"])
    if image_count > 600:
        raise LocalValidationError("请求图片数量超过 600 张")
    max_dimension = 4096 if image_count >= 15 else 8192
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
                image_url = {"url": _as_data_url(str(part["path"]), max_dimension)}
                if image_detail is not None:
                    image_url["detail"] = image_detail
                parts.append({
                    "type": "image_url",
                    "image_url": image_url,
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
            raise LocalValidationError(f"未设置 {self.api_key_variable} 环境变量。")
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise LocalValidationError("缺少 openai 依赖，请先安装 requirements.txt。") from exc
            self._client = OpenAI(api_key=self.config.api_key, base_url=self.config.base_url,
                                  max_retries=0)
        return self._client

    def request_options(self):
        return {}

    def prepare_messages(self, messages: Sequence[Message]) -> list[dict[str, Any]]:
        return _prepare_messages(messages)

    def validate_config(self) -> None:
        pass

    def build_request(self, messages: Sequence[Message], *,
                      response_format: Mapping[str, Any] | None = None,
                      timeout: float | None = None) -> dict[str, Any]:
        self.validate_config()
        request: dict[str, Any] = {
            "model": self.config.model,
            "messages": self.prepare_messages(messages),
            "timeout": timeout if timeout is not None else self.config.timeout,
            **self.request_options(),
        }
        if response_format is not None:
            request["response_format"] = dict(response_format)
        return request

    def chat(self, messages: Sequence[Message], *, response_format: Mapping[str, Any] | None = None,
             timeout: float | None = None) -> str:
        try:
            url = urlsplit(self.config.base_url)
            if (url.scheme not in {"https", "http"} or not url.hostname or url.username
                    or url.password or url.query or url.fragment
                    or url.path.rstrip("/").endswith(("/chat/completions", "/responses", "/anthropic"))):
                raise LocalValidationError("base_url 应是 API 根地址，不得包含凭据、查询参数或完整接口路径")
            if not self.config.model.strip():
                raise LocalValidationError("视觉模型名不能为空，请检查 Vision 模型环境变量")
            request = self.build_request(messages, response_format=response_format, timeout=timeout)
            if len(json.dumps(request).encode("utf-8")) > 47 * 1024 * 1024:
                raise LocalValidationError("图片历史导致请求过大，请新建会话或使用较小图片")
            logger.info("%s timeout=%s", configuration_summary(self.config), request["timeout"])
            response = self._get_client().chat.completions.create(**request)
            result = str(response.choices[0].message.content or "").strip()
            if not result:
                raise LocalValidationError("模型返回空正文，请重试或检查输出限制")
            return result
        except Exception as exc:
            raise ProviderCallError(report_error(exc, self.config)) from None
