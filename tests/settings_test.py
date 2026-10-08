"""Offline V1.5 settings and hot-switch regression tests."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["MYAI_LOAD_DOTENV"] = "0"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm import (apply_text_settings, get_default_provider, get_vision_provider,
                 set_default_provider, set_vision_provider)
from llm.deepseek import DeepSeekProvider
from llm.ollama import OllamaProvider
from settings import SettingsService, UserSettings


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "settings.json"
        self.env = {
            "TEXT_PROVIDER": "ollama",
            "OLLAMA_MODEL": "env-model:latest",
            "OLLAMA_BASE_URL": "http://127.0.0.1:23456/",
        }
        self.service = SettingsService(self.path, self.env)

    def tearDown(self):
        set_default_provider(None)
        set_vision_provider(None)

    def test_missing_file_uses_environment_defaults(self):
        settings = self.service.load()
        self.assertEqual(settings.text_provider, "ollama")
        self.assertEqual(settings.ollama_model, "env-model:latest")
        self.assertEqual(settings.ollama_base_url, "http://127.0.0.1:23456")
        self.assertFalse(self.path.exists())

    def test_save_and_reload(self):
        wanted = UserSettings("deepseek", "qwen-test:4b", "http://localhost:11434/")
        saved = self.service.save(wanted)
        self.assertEqual(saved.ollama_base_url, "http://localhost:11434")
        self.assertEqual(self.service.load(), saved)
        leftovers = list(self.path.parent.glob(".settings.json.*.tmp"))
        self.assertEqual(leftovers, [])

    def test_corrupt_or_incomplete_json_falls_back_safely(self):
        self.path.write_text("{ broken", encoding="utf-8")
        self.assertEqual(self.service.load(), self.service.defaults())
        self.path.write_text(json.dumps({"text_provider": "unknown"}), encoding="utf-8")
        loaded = self.service.load()
        self.assertEqual(loaded.text_provider, "ollama")
        self.assertEqual(loaded.ollama_model, "env-model:latest")

    def test_api_keys_are_never_persisted(self):
        secret = "offline-api-key-value-never-write"
        service = SettingsService(self.path, {**self.env, "DEEPSEEK_API_KEY": secret})
        service.save(UserSettings("deepseek", "model", "http://localhost:11434"))
        output = self.path.read_text(encoding="utf-8")
        self.assertNotIn(secret, output)
        self.assertNotIn("api_key", output.lower())
        self.assertEqual(set(json.loads(output)), {
            "text_provider", "ollama_model", "ollama_base_url"
        })

    def test_provider_hot_switch_and_ollama_updates_leave_vision_unchanged(self):
        vision = object()
        set_vision_provider(vision)
        with patch.dict(os.environ, {
            "MYAI_LOAD_DOTENV": "0",
            "DEEPSEEK_API_KEY": "offline-only",
            "DEEPSEEK_MODEL": "deepseek-flash",
        }, clear=True):
            deepseek = apply_text_settings(UserSettings(
                "deepseek", "unused", "http://127.0.0.1:11434"))
            self.assertIsInstance(deepseek, DeepSeekProvider)
            self.assertIs(get_default_provider(), deepseek)

            ollama = apply_text_settings(UserSettings(
                "ollama", "qwen-custom:7b", "http://localhost:22110"))
            self.assertIsInstance(ollama, OllamaProvider)
            self.assertEqual(ollama.config.model, "qwen-custom:7b")
            self.assertEqual(ollama.config.base_url, "http://localhost:22110")
            self.assertIs(get_default_provider(), ollama)
            self.assertIs(get_vision_provider(), vision)

            deepseek_again = apply_text_settings(UserSettings(
                "deepseek", "qwen-custom:7b", "http://localhost:22110"))
            self.assertIsInstance(deepseek_again, DeepSeekProvider)
            self.assertEqual(deepseek_again.config.model, "deepseek-flash")
            self.assertIs(get_vision_provider(), vision)


if __name__ == "__main__":
    unittest.main()
