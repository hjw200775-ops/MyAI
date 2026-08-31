"""DeepSeek Vision uses the shared OpenAI-compatible multimodal transport.

Local image encoding occurs only while preparing the outbound request; the
caller's path-based context and persistent history remain unchanged.
"""
from .openai_vision import OpenAIVisionProvider


class DeepSeekVisionProvider(OpenAIVisionProvider):
    api_key_variable = "DEEPSEEK_API_KEY"
