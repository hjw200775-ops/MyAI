"""Offline SDK transport tests. No dotenv, real credentials or network."""
import os
os.environ["MYAI_LOAD_DOTENV"] = "0"
import base64
import io
import json
import logging
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import httpx2 as httpx
except ImportError:
    import httpx
from openai import OpenAI
from PIL import Image
from llm.config import DEEPSEEK_VISION_MODEL, VisionConfig
from llm.deepseek_vision import DeepSeekVisionProvider
from llm.openai_vision import OpenAIVisionProvider, _prepare_messages
from llm.diagnostics import ProviderCallError, logger, report_error


class VisionTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"MYAI_LOAD_DOTENV": "0"}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.net = patch.object(socket.socket, "connect", side_effect=AssertionError("network forbidden"))
        self.net.start()
        self.addCleanup(self.net.stop)
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "wrong-extension.jpg"
        Image.new("RGB", (20, 12), "red").save(self.path, format="PNG")
        self.messages = [{"role": "system", "content": "persona"},
                         {"role": "user", "content": [{"type": "text", "text": "look"},
                          {"type": "image_path", "path": str(self.path)}]}]

    def provider(self, handler, cls=DeepSeekVisionProvider):
        config = VisionConfig(api_key="arbitrary-fake-secret", timeout=177)
        provider = cls(config)
        provider._client = OpenAI(api_key=config.api_key, base_url=config.base_url,
                                 max_retries=0, http_client=httpx.Client(
                                     transport=httpx.MockTransport(handler)))
        self.addCleanup(provider._client.close)
        return provider

    def test_sdk_request_and_mime(self):
        def handle(request):
            self.assertEqual(str(request.url), "https://api.deepseek.com/chat/completions")
            data = json.loads(request.content)
            self.assertEqual(set(data), {"model", "messages"})
            self.assertEqual(data["model"], "deepseek-flash")
            self.assertEqual(request.extensions["timeout"]["read"], 177)
            url = data["messages"][1]["content"][1]["image_url"]["url"]
            self.assertEqual(set(data["messages"][1]["content"][1]["image_url"]), {"url"})
            self.assertTrue(url.startswith("data:image/png;base64,"))
            self.assertEqual(base64.b64decode(url.split(",", 1)[1], validate=True), self.path.read_bytes())
            for message in data["messages"]:
                if isinstance(message["content"], list):
                    has_image = any(part["type"] == "image_url" for part in message["content"])
                    if has_image:
                        self.assertEqual(message["role"], "user")
            return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "ok"}}]})
        provider = self.provider(handle)
        self.assertEqual(provider.chat(self.messages), "ok")
        self.assertEqual(self.messages[1]["content"][1]["type"], "image_path")
        self.assertNotIn("arbitrary-fake-secret", repr(provider.config))

    def test_http_errors_redacted(self):
        for status in (400, 401, 402, 403, 404, 413, 422, 429, 500, 503):
            with self.subTest(status=status):
                def handle(request):
                    return httpx.Response(status, json={"error": {"message":
                        "arbitrary-fake-secret Bearer unrelated-secret data:image/png;base64,PRIVATE",
                        "type": "remote-private-type", "code": "private-code"}})
                with self.assertLogs(logger, level="ERROR") as logs:
                    with self.assertRaises(ProviderCallError) as caught:
                        self.provider(handle).chat(self.messages)
                output = str(caught.exception) + str(logs.output)
                self.assertIn(f"HTTP {status}", output)
                for secret in ("arbitrary-fake-secret", "unrelated-secret", "PRIVATE", "private-code"):
                    self.assertNotIn(secret, output)

    def test_known_remote_error_is_specific_but_safe(self):
        def handle(request):
            return httpx.Response(400, json={"error": {
                "message": "This model does not support image: private-user-text",
                "type": "invalid_request_error",
            }})
        with self.assertRaises(ProviderCallError) as caught:
            self.provider(handle).chat(self.messages)
        output = str(caught.exception)
        self.assertIn("remote=model_does_not_support_image", output)
        self.assertNotIn("private-user-text", output)

    def test_timeout_and_connection(self):
        for error, expected in ((httpx.ReadTimeout, "APITimeoutError"),
                                (httpx.ConnectError, "APIConnectionError")):
            def handle(request):
                raise error("secret details", request=request)
            with self.assertRaises(ProviderCallError) as caught:
                self.provider(handle).chat(self.messages)
            self.assertIn(expected, str(caught.exception))
            self.assertNotIn("secret details", str(caught.exception))

    def test_openai_does_not_receive_deepseek_options(self):
        self.assertEqual(OpenAIVisionProvider(VisionConfig()).request_options(), {})

    def test_non_user_rejected(self):
        for role in ("assistant", "system"):
            with self.assertRaises(ValueError):
                _prepare_messages([{**self.messages[1], "role": role}])

    def test_missing_image_and_empty_response(self):
        provider = self.provider(lambda request: httpx.Response(200, json={
            "choices": [{"message": {"role": "assistant", "content": ""}}]}))
        with self.assertRaisesRegex(ProviderCallError, "空正文"):
            provider.chat(self.messages)
        self.path.unlink()
        with self.assertRaisesRegex(ProviderCallError, "FileNotFoundError"):
            provider.chat(self.messages)

    def test_config_timeout_and_legacy_selection(self):
        with patch.dict(os.environ, {"MYAI_VISION_TIMEOUT": "222", "MYAI_VISION_PROVIDER": "openai"}):
            self.assertEqual(VisionConfig.from_env().timeout, 222)
            self.assertEqual(VisionConfig.from_env().provider, "openai")
        for invalid in ("nan", "inf", "-1", "bad"):
            with patch.dict(os.environ, {"MYAI_VISION_TIMEOUT": invalid}):
                self.assertEqual(VisionConfig.from_env().timeout, 120)
        for invalid_model in ("typo-model", "sk-secret-accidentally-pasted"):
            with patch.dict(os.environ, {"MYAI_VISION_PROVIDER": "deepseek",
                                         "DEEPSEEK_VISION_MODEL": invalid_model,
                                         "DEEPSEEK_API_KEY": "sk-secret-accidentally-pasted"}):
                config = VisionConfig.from_env()
                self.assertEqual(config.model, DEEPSEEK_VISION_MODEL)
                self.assertNotIn(config.api_key, repr(config))

    def test_direct_invalid_deepseek_model_fails_locally(self):
        provider = DeepSeekVisionProvider(VisionConfig(api_key="fake", model="typo-model"))
        with self.assertRaisesRegex(ProviderCallError, "模型名无效"):
            provider.chat(self.messages)

    def test_unknown_exception_not_echoed(self):
        self.assertNotIn("hidden-key", report_error(RuntimeError("hidden-key")))

    def test_invalid_endpoint_is_local_failure(self):
        provider = DeepSeekVisionProvider(VisionConfig(api_key="fake",
            base_url="https://api.deepseek.com/chat/completions"))
        with self.assertRaisesRegex(ProviderCallError, "base_url"):
            provider.chat(self.messages)

    def test_image_dimensions_checked(self):
        Image.new("RGB", (8193, 1)).save(self.path, format="PNG")
        with self.assertRaisesRegex(ValueError, "尺寸"):
            _prepare_messages(self.messages)


if __name__ == "__main__":
    unittest.main()
