from abc import ABC, abstractmethod
from typing import Any, Mapping, Sequence

Message = Mapping[str, Any]


class LLMProvider(ABC):
    """所有云端或本地模型 Provider 必须实现的最小接口。"""

    @abstractmethod
    def chat(self, messages: Sequence[Message], *, response_format: Mapping[str, Any] | None = None,
             timeout: float | None = None) -> str:
        """发送兼容 OpenAI messages 结构的请求并返回纯文本。"""
        raise NotImplementedError

    @property
    def supports_vision(self) -> bool:
        return False


class VisionNotSupportedError(RuntimeError):
    """当前 Provider 无法诚实处理图片输入。"""

