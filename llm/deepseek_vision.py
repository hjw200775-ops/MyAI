"""DeepSeek Vision uses the shared OpenAI-compatible multimodal transport.

Local image encoding occurs only while preparing the outbound request; the
caller's path-based context and persistent history remain unchanged.
"""
from typing import Any, Sequence

from .base import Message
from .config import DEEPSEEK_VISION_MODEL
from .diagnostics import LocalValidationError
from .openai_vision import OpenAIVisionProvider, _prepare_messages


class DeepSeekVisionProvider(OpenAIVisionProvider):
    api_key_variable = "DEEPSEEK_API_KEY"

    def validate_config(self) -> None:
        if self.config.model != DEEPSEEK_VISION_MODEL:
            raise LocalValidationError(
                "DeepSeek 视觉模型名无效；请将 DEEPSEEK_VISION_MODEL 设为 deepseek-flash"
            )

    def prepare_messages(self, messages: Sequence[Message]) -> list[dict[str, Any]]:
        # Keep the DeepSeek request identical to the minimal official example.
        # `detail` and thinking controls are supported today, but neither is
        # needed for image recognition and omitting them avoids compatibility
        # surprises across API/SDK rollouts.
        return _prepare_messages(messages, image_detail=None)
