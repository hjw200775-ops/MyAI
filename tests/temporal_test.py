"""Fake clock and fake providers only; run through run_offline.py."""
import sys
import unittest
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ai
import llm
import memory
import json
from types import SimpleNamespace
from llm.config import LLMConfig
from llm.deepseek import DeepSeekProvider
from llm.ollama import OllamaProvider
from time_context import TimeContextService, get_time_period, describe_duration, parse_timestamp


class TemporalTests(unittest.TestCase):
    def setUp(self):
        with memory.database_connection() as conn:
            conn.execute('DELETE FROM messages')
            conn.execute('DELETE FROM conversations')
        self.cid = memory.create_conversation()
        self.now = datetime(2026, 10, 8, 23, 50).astimezone()
        self.service = TimeContextService(lambda: self.now)

    def add(self, stamp, role='user', text='hi', image=None, cid=None):
        mid = memory.save_message(cid or self.cid, role, text, image)
        with memory.database_connection() as conn:
            conn.execute('UPDATE messages SET created_at=? WHERE id=?', (stamp, mid))

    def test_calendar_and_boundaries(self):
        t = self.service.capture(self.cid)
        self.assertEqual((t.date, t.weekday, t.hour, t.current_period), ('2026-10-08', 3, 23, '深夜'))
        self.assertIn('星期四', t.to_prompt())
        for h, p in [(0,'深夜'),(4,'深夜'),(5,'清晨'),(8,'清晨'),(9,'上午'),(11,'上午'),(12,'中午'),(13,'中午'),(14,'下午'),(17,'下午'),(18,'晚上'),(22,'晚上'),(23,'深夜')]:
            self.assertEqual(get_time_period(h), p)
        self.now += timedelta(minutes=20)
        self.assertEqual(self.service.capture(self.cid).date, '2026-10-09')
        self.assertEqual(self.service.capture(self.cid).session_duration, 1200)
        self.now = self.now.replace(hour=5)
        self.assertEqual(self.service.capture(self.cid).current_period, '清晨')

    def test_no_history_intervals_and_corruption(self):
        self.assertIsNone(self.service.capture(self.cid).idle_duration)
        for seconds, expected in [(10,'不足1分钟'),(120,'约2分钟'),(7200,'约2小时'),(252000,'约2天22小时')]:
            self.add((self.now-timedelta(seconds=seconds)).isoformat())
            self.assertEqual(self.service.capture(self.cid).idle_duration, seconds)
            self.assertEqual(describe_duration(seconds), expected)
        for value in [None, '', 'bad', '2026-99-99']:
            self.assertIsNone(parse_timestamp(value))
        self.add('bad')
        self.assertIsNone(self.service.capture(self.cid).idle_duration)
        self.add((self.now+timedelta(days=1)).isoformat())
        self.assertEqual(self.service.capture(self.cid).idle_duration, 0)
        self.now -= timedelta(days=2)
        self.assertEqual(self.service.capture(self.cid).session_duration, 0)

    def test_global_local_and_image_input(self):
        other = memory.create_conversation()
        self.add((self.now-timedelta(hours=3)).isoformat())
        self.add((self.now-timedelta(hours=1)).isoformat(), text='', image='fake.png', cid=other)
        self.add(self.now.isoformat(), role='assistant', cid=other)
        memory.rename_conversation(other, 'title')
        t = self.service.capture(self.cid)
        self.assertEqual((t.idle_duration, t.last_message_duration), (3600, 10800))

    def test_pre_save_snapshot_and_provider_switch(self):
        self.add((self.now-timedelta(hours=6)).isoformat())
        captured = []
        class FakeProvider:
            def chat(self, messages, **kwargs):
                captured.append(messages[0]['content'])
                return 'offline reply'
        try:
            with patch.object(ai, 'default_time_service', self.service):
                for name in ['deepseek', 'ollama']:
                    with memory.database_connection() as conn:
                        conn.execute('DELETE FROM messages WHERE id > (SELECT MIN(id) FROM messages)')
                    llm.set_default_provider(FakeProvider())
                    self.assertEqual(ai.chat('hello', self.cid)[0], 'offline reply')
                self.assertEqual(captured[0], captured[1])
                self.assertIn('约6小时', captured[0])
                started = self.service.capture(self.cid).session_started_at
                self.now += timedelta(minutes=12)
                llm.set_default_provider(FakeProvider())
                t = self.service.capture(self.cid)
                self.assertEqual(t.session_started_at, started)
                self.assertEqual(t.session_duration, 720)
                self.assertEqual(ai.chat('hello again', self.cid)[0], 'offline reply')
                self.assertIn('本次会话持续：约12分钟', captured[-1])
        finally:
            llm.set_default_provider(None)

    def test_optional_history_failure(self):
        with patch('memory.load_temporal_history', side_effect=ValueError('bad')):
            self.assertIsNone(self.service.capture(self.cid).idle_duration)

    def test_actual_provider_request_payloads_and_legacy_schema(self):
        self.add((self.now-timedelta(minutes=18)).replace(tzinfo=None).isoformat())
        captured = []
        def create(**kwargs):
            captured.append(kwargs['messages'][0]['content'])
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='reply'))])
        deepseek = DeepSeekProvider(LLMConfig(api_key='offline-test'))
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return b'{"message":{"content":"reply"}}'
        def fake_open(request, timeout):
            captured.append(json.loads(request.data)['messages'][0]['content'])
            return Response()
        with memory.database_connection() as conn:
            before = [tuple(row) for row in conn.execute('PRAGMA table_info(messages)')]
        memory.init_database()
        try:
            with patch.object(ai, 'default_time_service', self.service), patch.object(deepseek, '_get_client', return_value=client), patch('llm.ollama.urlopen', side_effect=fake_open):
                for provider in [deepseek, OllamaProvider(LLMConfig(provider='ollama', base_url='http://localhost:11434', model='offline'))]:
                    with memory.database_connection() as conn:
                        conn.execute('DELETE FROM messages WHERE id > (SELECT MIN(id) FROM messages)')
                    llm.set_default_provider(provider)
                    self.assertEqual(ai.chat('hello', self.cid)[0], 'reply')
                self.assertEqual(captured[0], captured[1])
                self.assertIn('约18分钟', captured[0])
        finally:
            llm.set_default_provider(None)
        with memory.database_connection() as conn:
            self.assertEqual(before, [tuple(row) for row in conn.execute('PRAGMA table_info(messages)')])


if __name__ == '__main__':
    unittest.main()
