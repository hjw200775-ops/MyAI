"""不联网、不读取 .env 的 V1.4.2 基础冒烟测试。"""
import os
import sys
import tempfile
from pathlib import Path
from copy import deepcopy
from contextlib import closing
from types import SimpleNamespace
from unittest.mock import patch

# Must precede any llm/ai imports, even if python-dotenv is installed.
os.environ["MYAI_LOAD_DOTENV"] = "0"

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm.base import LLMProvider, VisionNotSupportedError
from llm.config import LLMConfig, VisionConfig
from llm.deepseek import DeepSeekProvider
from llm.deepseek_vision import DeepSeekVisionProvider
from llm import create_vision_provider
from llm.openai_vision import _prepare_messages
from media import persist_image, resolve_image


def main() -> None:
    assert LLMConfig().model == "deepseek-v4-flash"
    assert VisionConfig().model == "deepseek-v4-flash-vision-exp"
    with patch.dict(os.environ, {"MYAI_LOAD_DOTENV": "0", "DEEPSEEK_API_KEY": "offline-test"}, clear=True), \
            patch("llm.config.load_dotenv", side_effect=AssertionError("dotenv must not load")):
        config = VisionConfig.from_env()
        assert config.provider == "deepseek"
        assert config.api_key == LLMConfig.from_env().api_key == "offline-test"
        assert config.base_url == LLMConfig.from_env().base_url == "https://api.deepseek.com"
        assert isinstance(create_vision_provider(), DeepSeekVisionProvider)
        with patch.dict(os.environ, {"DEEPSEEK_VISION_MODEL": "custom-vision",
                                     "DEEPSEEK_BASE_URL": "https://example.invalid"}):
            assert VisionConfig.from_env().model == "deepseek-v4-flash-vision-exp"
            assert VisionConfig.from_env().base_url == LLMConfig.from_env().base_url
        with patch.dict(os.environ, {"MYAI_VISION_PROVIDER": "openai", "OPENAI_API_KEY": "offline-openai"}):
            fallback = VisionConfig.from_env()
            assert fallback.api_key == "offline-openai"
            assert fallback.model == "gpt-5.4-mini"
            assert fallback.base_url == "https://api.openai.com/v1"
        for disabled in ("none", "disabled", ""):
            try:
                create_vision_provider(VisionConfig(provider=disabled))
            except VisionNotSupportedError:
                pass
            else:
                raise AssertionError("Disabled vision must not make requests")
    try:
        DeepSeekVisionProvider(VisionConfig(api_key=None)).chat([])
    except RuntimeError as exc:
        assert "DEEPSEEK_API_KEY" in str(exc)
    else:
        raise AssertionError("Missing key must fail locally")
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

        # Exercise the actual Provider request boundary without any SDK/network.
        captured = []
        def complete(**request):
            captured.append(request)
            return SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content="  vision reply  "))])
        vision = DeepSeekVisionProvider(VisionConfig(api_key="offline-test"))
        vision._client = SimpleNamespace(chat=SimpleNamespace(
            completions=SimpleNamespace(create=complete)))
        original = [{"role": "user", "content": [
            {"type": "text", "text": "Look"},
            {"type": "image_path", "path": str(resolved)}]}]
        snapshot = deepcopy(original)
        assert vision.chat(original, timeout=12, response_format={"type": "json_object"}) == "vision reply"
        assert original == snapshot
        assert captured[-1]["model"] == "deepseek-v4-flash-vision-exp"
        assert captured[-1]["timeout"] == 12
        assert "extra_body" not in captured[-1]
        assert captured[-1]["response_format"] == {"type": "json_object"}
        assert captured[-1]["messages"][0]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
        assert "detail" not in captured[-1]["messages"][0]["content"][1]["image_url"]
        external = [{"role": "user", "content": [{"type": "image_url",
                    "image_url": {"url": "https://example.invalid/photo.png"}}]}]
        assert _prepare_messages(external) == external
        try:
            _prepare_messages([{**original[0], "role": "assistant"}])
        except ValueError:
            pass
        else:
            raise AssertionError("Images must be restricted to user messages")

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
        source.unlink()
        from context import default_context_builder
        from memory import get_connection
        for row in records:
            assert "base64," not in str(dict(row))
            if row["image_path"]:
                assert Path(row["image_path"]).name == row["image_path"]
                assert resolve_image(row["image_path"]) is not None
        with closing(get_connection()) as connection:
            assert connection.execute("SELECT count(*) FROM messages").fetchone()[0] == 6
        restored = default_context_builder.build_messages(conversation_id)
        assert sum(isinstance(m["content"], list) for m in restored) == 2
        # A text follow-up with historical images must still use vision.
        set_vision_provider(vision)
        assert chat("再看看之前的图片", conversation_id)[0] == "vision reply"
        assert captured[-1]["timeout"] == vision.config.timeout
        assert sum(isinstance(m["content"], list) for m in captured[-1]["messages"]) == 2
        # Failed API calls preserve user input, but never save a fake assistant reply.
        def fail(**request):
            raise RuntimeError("offline-secret-that-must-not-appear")
        vision._client.chat.completions.create = fail
        before = len(load_message_records(conversation_id))
        failure = chat("再试一次", conversation_id)[0]
        assert "HTTP N/A" in failure and "offline-secret" not in failure
        after = load_message_records(conversation_id)
        assert len(after) == before + 1 and after[-1]["role"] == "user"
        for row in records:
            if row["image_path"]:
                resolve_image(row["image_path"]).unlink()
        assert not any(isinstance(m["content"], list) for m in
                       default_context_builder.build_messages(conversation_id))
        set_default_provider(None)
        set_vision_provider(None)
    print("MyAI V1.4.2 smoke test: PASS")


if __name__ == "__main__":
    main()
