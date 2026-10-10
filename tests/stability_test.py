"""Offline settings, client lifetime and in-flight switch regressions."""
import gc
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ['MYAI_LOAD_DOTENV'] = '0'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_folder = tempfile.TemporaryDirectory()
os.environ['MYAI_DB_PATH'] = str(Path(_folder.name) / 'memory.db')
import ai
import llm
from settings import SettingsService, UserSettings
from llm.config import LLMConfig
from llm.deepseek import DeepSeekProvider
from llm.ollama import OllamaProvider


class StabilityTests(unittest.TestCase):
    def tearDown(self):
        llm.set_default_provider(None)
        llm.set_vision_provider(None)

    def test_invalid_settings_types_and_urls(self):
        with tempfile.TemporaryDirectory() as folder:
            service = SettingsService(Path(folder) / 'settings.json', {})
            for value in [True, 12, [], {}, ' ', 'bad\nmodel']:
                service.path.write_text(json.dumps({'ollama_model': value, 'ollama_base_url': value}))
                self.assertEqual(service.load(), service.defaults())
            for url in ['http://user:pass@localhost', 'http://localhost:bad',
                        'http://[broken', 'http://localhost/api/chat',
                        'http://localhost?token=secret', 'ftp://localhost', '///']:
                service.path.write_text(json.dumps({'ollama_base_url': url}))
                self.assertEqual(service.load().ollama_base_url, service.defaults().ollama_base_url)
                self.assertEqual(OllamaProvider(LLMConfig(base_url=url)).check_status().code, 'invalid_config')

    def test_secret_paste_and_failed_atomic_write(self):
        with tempfile.TemporaryDirectory() as folder:
            service = SettingsService(Path(folder) / 'settings.json', {'DEEPSEEK_API_KEY': 'private-key-value'})
            service.save(UserSettings())
            original = service.path.read_bytes()
            with self.assertRaises(ValueError):
                service.save(UserSettings(ollama_model='private-key-value'))
            with patch('settings.os.replace', side_effect=OSError('offline failure')):
                with self.assertRaises(OSError):
                    service.save(UserSettings(text_provider='ollama'))
            self.assertEqual(service.path.read_bytes(), original)
            self.assertEqual(list(service.path.parent.glob('*.tmp')), [])

    def test_singleton_creation_and_same_config_reuse(self):
        barrier = threading.Barrier(8)
        providers = []
        def worker():
            barrier.wait()
            providers.append(llm.get_default_provider())
        with patch('llm.create_provider', return_value=object()) as create:
            threads = [threading.Thread(target=worker) for _ in range(8)]
            for t in threads: t.start()
            for t in threads: t.join(3)
            create.assert_called_once()
            self.assertEqual(len(providers), 8)
        llm.set_default_provider(None)
        first = llm.apply_text_settings(UserSettings())
        self.assertIs(first, llm.apply_text_settings(UserSettings()))

    def test_inflight_switch_retains_provider_for_auxiliary_call(self):
        entered, release = threading.Event(), threading.Event()
        calls, errors = [], []
        class Old:
            def chat(self, *args, **kwargs):
                calls.append('old')
                entered.set()
                if not release.wait(3): raise AssertionError('timeout')
                return 'old'
        class New:
            def chat(self, *args, **kwargs):
                calls.append('new')
                return 'new'
        old = Old()
        llm.set_default_provider(old)
        vision = object()
        llm.set_vision_provider(vision)
        def worker():
            try:
                with ai.text_provider_scope(old):
                    ai._llm_chat([])
                    ai._llm_chat([], response_format={'type': 'json_object'})
            except Exception as exc: errors.append(exc)
        t = threading.Thread(target=worker); t.start()
        self.assertTrue(entered.wait(3))
        llm.set_default_provider(New())
        self.assertEqual(ai._llm_chat([]), 'new')
        release.set(); t.join(3)
        self.assertFalse(t.is_alive()); self.assertEqual(errors, [])
        self.assertEqual(calls, ['old', 'new', 'old'])
        self.assertIs(llm.get_vision_provider(), vision)

    def test_client_created_once_and_closed_after_provider_release(self):
        from unittest.mock import Mock
        client = Mock()
        provider = DeepSeekProvider(LLMConfig(api_key='offline'))
        with patch.dict(sys.modules, {'openai': SimpleNamespace(OpenAI=Mock(return_value=client))}):
            threads = [threading.Thread(target=provider._get_client) for _ in range(8)]
            for t in threads: t.start()
            for t in threads: t.join(3)
            sys.modules['openai'].OpenAI.assert_called_once()
        del threads, t
        client.close.assert_not_called()
        del provider
        gc.collect()
        client.close.assert_called_once()

    def test_relationship_concurrent_updates_accumulate(self):
        import relationship
        from memory import database_connection
        with database_connection() as conn:
            conn.execute('UPDATE relationship_state SET trust=50,familiarity=0,closeness=40 WHERE id=1')
        barrier = threading.Barrier(8)
        errors = []
        def worker():
            try:
                barrier.wait()
                relationship.change_relationship(1, 1, 1)
            except Exception as exc: errors.append(exc)
        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads: t.start()
        for t in threads: t.join(3)
        self.assertTrue(all(not t.is_alive() for t in threads))
        self.assertEqual(errors, [])
        state = relationship.get_relationship()
        self.assertEqual((state['trust'], state['familiarity'], state['closeness']), (58, 8, 48))

    def test_status_accepts_default_latest_tag(self):
        import io
        response = io.BytesIO(b'{"models":[{"name":"qwen:latest"}]}')
        with patch('llm.ollama.urlopen', return_value=response):
            status = OllamaProvider(LLMConfig(model='qwen')).check_status()
        self.assertEqual(status.code, 'ok')


if __name__ == '__main__':
    unittest.main()
