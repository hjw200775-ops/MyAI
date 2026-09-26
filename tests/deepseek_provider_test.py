"""Offline DeepSeek text response-shape tests for V1.4.2."""
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ["MYAI_LOAD_DOTENV"] = "0"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm.config import LLMConfig
from llm.deepseek import DeepSeekProvider
from llm.diagnostics import ProviderCallError


class DeepSeekProviderTests(unittest.TestCase):
    def setUp(self):
        self.provider = DeepSeekProvider(LLMConfig(
            provider="deepseek", base_url="https://offline.invalid",
            model="deepseek-flash", api_key="offline-key",
        ))

    @staticmethod
    def _client(response):
        create = unittest.mock.Mock(return_value=response)
        return SimpleNamespace(chat=SimpleNamespace(
            completions=SimpleNamespace(create=create)))

    def test_normal_text_response_is_unchanged(self):
        response = SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content="  正常回复  "))])
        with patch.object(self.provider, "_get_client",
                          return_value=self._client(response)):
            self.assertEqual(self.provider.chat([{"role": "user", "content": "你好"}]),
                             "正常回复")

    def test_empty_or_malformed_response_has_clear_error(self):
        responses = [
            SimpleNamespace(choices=[]),
            SimpleNamespace(choices=None),
            SimpleNamespace(choices=[SimpleNamespace(message=None)]),
            SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content=None))]),
            SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content="   "))]),
        ]
        for response in responses:
            with self.subTest(response=response), \
                    patch.object(self.provider, "_get_client",
                                 return_value=self._client(response)):
                with self.assertRaisesRegex(ProviderCallError, "无法识别|空回复"):
                    self.provider.chat([{"role": "user", "content": "你好"}])


if __name__ == "__main__":
    unittest.main()
