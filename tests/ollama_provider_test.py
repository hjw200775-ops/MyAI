"""Offline Ollama V1.4 tests. No dotenv, Ollama, or DeepSeek network calls."""
import io
import json
import os
import socket
import sys
import unittest
from pathlib import Path
from urllib.error import HTTPError, URLError
from unittest.mock import patch

os.environ["MYAI_LOAD_DOTENV"] = "0"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from context import ContextBuilder
from llm import create_provider, create_vision_provider
from llm.config import LLMConfig, VisionConfig
from llm.deepseek import DeepSeekProvider
from llm.deepseek_vision import DeepSeekVisionProvider
from llm.diagnostics import ProviderCallError
from llm.ollama import OllamaProvider
from llm.base import VisionNotSupportedError


class FakeResponse:
    def __init__(self, body):
        self.body = json.dumps(body, ensure_ascii=False).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


class OllamaProviderTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"MYAI_LOAD_DOTENV": "0"}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.config = LLMConfig(
            provider="ollama", base_url="http://127.0.0.1:11434",
            model="qwen3.5:4b", timeout=61,
        )

    def test_request_construction_and_json_mode(self):
        captured = {}

        def fake_open(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeResponse({"message": {"role": "assistant", "content": "  本地回复  "}})

        messages = [{"role": "system", "content": "小悠的人格"},
                    {"role": "user", "content": "你好"}]
        snapshot = json.loads(json.dumps(messages, ensure_ascii=False))
        with patch("llm.ollama.urlopen", side_effect=fake_open):
            result = OllamaProvider(self.config).chat(
                messages, response_format={"type": "json_object"}, timeout=12
            )
        self.assertEqual(result, "本地回复")
        self.assertEqual(messages, snapshot)
        self.assertEqual(captured["url"], "http://127.0.0.1:11434/api/chat")
        self.assertEqual(captured["timeout"], 12)
        self.assertEqual(captured["body"], {
            "model": "qwen3.5:4b", "messages": messages,
            "stream": False, "think": False, "keep_alive": "10m",
            "options": {"num_ctx": 4096}, "format": "json",
        })
        self.assertEqual(captured["headers"]["Content-type"], "application/json")

    def test_context_builder_output_is_passed_unchanged(self):
        records = [
            {"role": "user", "content": "之前聊过的内容", "image_path": None},
            {"role": "assistant", "content": "我记得。", "image_path": None},
        ]
        with patch("context.build_character_prompt", return_value="角色：小悠"), \
                patch("context.get_emotion", return_value={
                    "happiness": 60, "sadness": 2, "anger": 1}), \
                patch("context.build_relationship_prompt", return_value="信任且熟悉"), \
                patch("context.load_memories", return_value=[
                    (1, "用户喜欢 Python", "interest", None, None)]), \
                patch("context.load_message_records", return_value=records):
            messages = ContextBuilder().build_messages(123)

        captured = {}
        def fake_open(request, timeout):
            captured.update(json.loads(request.data.decode("utf-8")))
            return FakeResponse({"message": {"content": "好的"}})
        with patch("llm.ollama.urlopen", side_effect=fake_open):
            OllamaProvider(self.config).chat(messages)

        self.assertEqual(captured["messages"], messages)
        system = captured["messages"][0]["content"]
        for expected in ("角色：小悠", "用户喜欢 Python", "开心：60.0", "信任且熟悉"):
            self.assertIn(expected, system)
        self.assertEqual(captured["messages"][1:], [
            {"role": "user", "content": "之前聊过的内容"},
            {"role": "assistant", "content": "我记得。"},
        ])

    def test_provider_selection_and_legacy_compatibility(self):
        with patch.dict(os.environ, {
            "TEXT_PROVIDER": "ollama", "OLLAMA_BASE_URL": "http://localhost:11434/",
            "OLLAMA_MODEL": "test-model", "OLLAMA_TIMEOUT": "77",
            "OLLAMA_KEEP_ALIVE": "20m", "OLLAMA_NUM_CTX": "8192",
            "OLLAMA_THINK": "true",
        }):
            config = LLMConfig.from_env()
            self.assertEqual((config.provider, config.model, config.timeout),
                             ("ollama", "test-model", 77))
            self.assertEqual((config.keep_alive, config.num_ctx, config.think),
                             ("20m", 8192, True))
            self.assertIsInstance(create_provider(config), OllamaProvider)
        with patch.dict(os.environ, {
            "MYAI_LLM_PROVIDER": "deepseek", "DEEPSEEK_API_KEY": "offline-key"
        }):
            self.assertIsInstance(create_provider(), DeepSeekProvider)
        # TEXT_PROVIDER only controls text. Vision remains independently DeepSeek.
        self.assertIsInstance(create_vision_provider(VisionConfig(
            provider="deepseek", api_key="offline-key")), DeepSeekVisionProvider)

    def test_clear_offline_and_model_errors(self):
        provider = OllamaProvider(self.config)
        with patch("llm.ollama.urlopen", side_effect=URLError(ConnectionRefusedError())):
            with self.assertRaisesRegex(ProviderCallError, "无法连接 Ollama"):
                provider.chat([{"role": "user", "content": "hello"}])
        with patch("llm.ollama.urlopen", side_effect=URLError(socket.timeout())):
            with self.assertRaisesRegex(ProviderCallError, "请求超时"):
                provider.chat([{"role": "user", "content": "hello"}])
        missing = HTTPError("http://127.0.0.1:11434/api/chat", 404, "not found", {}, io.BytesIO())
        self.addCleanup(missing.close)
        with patch("llm.ollama.urlopen", side_effect=missing):
            with self.assertRaisesRegex(ProviderCallError, "ollama pull qwen3.5:4b"):
                provider.chat([{"role": "user", "content": "hello"}])
        with patch("llm.ollama.urlopen", return_value=FakeResponse({"unexpected": True})):
            with self.assertRaisesRegex(ProviderCallError, "无法识别"):
                provider.chat([{"role": "user", "content": "hello"}])

    def test_v14_ollama_rejects_images_without_network(self):
        provider = OllamaProvider(self.config)
        with patch("llm.ollama.urlopen", side_effect=AssertionError("network forbidden")):
            with self.assertRaisesRegex(VisionNotSupportedError, "DeepSeek Vision"):
                provider.chat([{"role": "user", "content": [
                    {"type": "image_path", "path": "unused.png"}]}])


if __name__ == "__main__":
    unittest.main()
