"""不联网、不读取 .env 的 V1.3 基础冒烟测试。"""
import os
import sys
import tempfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm.base import LLMProvider, VisionNotSupportedError
from llm.config import LLMConfig, VisionConfig
from llm.deepseek import DeepSeekProvider
from llm.openai_vision import _prepare_messages
from media import persist_image, resolve_image


def main() -> None:
    assert LLMConfig().model == "deepseek-v4-flash"
    assert VisionConfig().model == "gpt-5.4-mini"
    # 显式构造无密钥配置，避免 from_env 与 .env。
    text_provider = DeepSeekProvider(LLMConfig(api_key=None))
    try:
        text_provider.chat([{
            "role": "user",
            "content": [{"type": "image_path", "path": "unused.png"}],
        }])
    except VisionNotSupportedError:
        pass
    else:
        raise AssertionError("DeepSeek Provider 必须明确拒绝图片内容块")

    assert VisionConfig(provider="openai", api_key=None).provider == "openai"
    with tempfile.TemporaryDirectory() as folder:
        os.environ["MYAI_DATA_DIR"] = folder
        source = Path(folder) / "sample.bmp"
        Image.new("RGB", (24, 16), "purple").save(source)
        stored = persist_image(source)
        resolved = resolve_image(stored)
        assert stored.endswith(".png") and resolved and resolved.is_file()
        messages = _prepare_messages([{
            "role": "user",
            "content": [
                {"type": "text", "text": "自然回应"},
                {"type": "image_path", "path": str(resolved)},
            ],
        }])
        url = messages[0]["content"][1]["image_url"]["url"]
        assert url.startswith("data:image/png;base64,")

        # 用临时数据库和假 Provider 跑通三类消息，不发网络请求。
        os.environ["MYAI_DB_PATH"] = str(Path(folder) / "memory.db")
        from ai import chat
        from llm import set_default_provider, set_vision_provider
        from memory import create_conversation, load_message_records

        class FakeProvider(LLMProvider):
            def __init__(self, vision: bool = False):
                self.vision = vision

            @property
            def supports_vision(self) -> bool:
                return self.vision

            def chat(self, messages, *, response_format=None, timeout=None):
                if response_format:
                    return ('{"happiness":0,"sadness":0,"anger":0,"trust":0,'
                            '"familiarity":0,"closeness":0}')
                return "我看到了，我们接着聊。" if self.vision else "纯文字回复。"

        set_default_provider(FakeProvider())
        set_vision_provider(FakeProvider(vision=True))
        conversation_id = create_conversation()
        assert chat("纯文字", conversation_id)[0] == "纯文字回复。"
        assert chat("", conversation_id, image_path=source)[0] == "我看到了，我们接着聊。"
        assert chat("这张图怎么样？", conversation_id, image_path=source)[0] == "我看到了，我们接着聊。"
        records = load_message_records(conversation_id)
        assert len(records) == 6
        assert [records[index]["message_type"] for index in (0, 2, 4)] == [
            "text", "image", "text_image"
        ]
    print("MyAI V1.3 smoke test: PASS")


if __name__ == "__main__":
    main()

