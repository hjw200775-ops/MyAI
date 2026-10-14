import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import memory
from time_context import TimeContextService
from foundation_time import FoundationClock
from user_activity import ActivityState, WindowsActivityProvider
from companion_loop import CompanionLoop
from companion_events import CompanionEventRepository
from affect_state import ShortTermAffect

class FakeActivity:
    state = ActivityState(120, None, 'fake-app', False, False, True)
    def read(self, now):
        return self.state

class CompanionTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 13, 23, 50).astimezone()
        self.time = TimeContextService(lambda: self.now)
        self.clock = FoundationClock(self.time)
        memory.init_database()
        with memory.database_connection() as conn:
            conn.execute('DELETE FROM pending_actions')
            conn.execute('DELETE FROM companion_events')
        self.activity = FakeActivity()
        self.loop = CompanionLoop(self.clock, self.time, self.activity)
        self.last = self.now - timedelta(hours=2)
        self.history = patch('memory.load_temporal_history', side_effect=lambda cid: (self.last, self.last))
        self.history.start()
        self.addCleanup(self.history.stop)

    def candidate(self):
        return self.loop.tick()['created_id']

    def test_candidate_dedup_and_provider_switch(self):
        aid = self.candidate()
        self.assertIsNotNone(aid)
        self.assertIsNone(self.loop.tick(provider='ollama')['created_id'])
        self.assertEqual(self.loop.tick(provider='deepseek')['pending_count'], 1)
        self.assertEqual(self.loop.timeline.get(aid)['status'], 'pending')

    def test_due_approve_never_sends(self):
        aid = self.candidate()
        self.now += timedelta(minutes=10)
        with patch('ai.chat', side_effect=AssertionError('never send')), patch('ai._llm_chat', side_effect=AssertionError('offline')):
            snapshot = self.loop.tick()
        self.assertEqual(snapshot['reviews'][0]['outcome'], 'APPROVE')
        row = self.loop.timeline.get(aid)
        self.assertEqual(row['status'], 'pending')
        self.assertEqual(row['reviewed_ready'], 1)
        self.activity.state = ActivityState(0, None, 'busy', True, True, True)
        self.assertEqual(self.loop.tick()['reviews'][0]['outcome'], 'DEFER')
        self.assertEqual(self.loop.timeline.get(aid)['reviewed_ready'], 0)

    def test_busy_and_gui_input_defer(self):
        aid = self.candidate()
        self.now += timedelta(minutes=10)
        self.assertEqual(self.loop.tick(user_busy=True)['reviews'][0]['outcome'], 'DEFER')
        self.assertEqual(self.loop.timeline.get(aid)['status'], 'deferred')

    def test_recent_chat_cancel_and_no_candidate(self):
        aid = self.candidate()
        self.now += timedelta(minutes=10)
        self.last = self.now
        snap = self.loop.tick()
        self.assertEqual(snap['reviews'][0]['outcome'], 'CANCEL')
        self.assertIsNone(snap['created_id'])
        self.assertEqual(self.loop.timeline.get(aid)['status'], 'cancelled')

    def test_expiry_and_cooldown(self):
        aid = self.candidate()
        self.now += timedelta(hours=1)
        self.assertEqual(self.loop.tick()['expired_count'], 1)
        row = self.loop.timeline.get(aid)
        self.assertEqual(row['status'], 'expired')
        self.assertEqual(row['review_outcome'], 'EXPIRE')
        self.assertIsNone(self.candidate())

    def test_failure_closed(self):
        aid = self.candidate()
        self.now += timedelta(minutes=10)
        with patch.object(self.activity, 'read', side_effect=OSError('private text')):
            snap = self.loop.tick()
        self.assertFalse(snap['activity']['available'])
        self.assertEqual(snap['reviews'][0]['outcome'], 'DEFER')
        self.assertEqual(self.loop.timeline.get(aid)['reviewed_ready'], 0)

    def test_midnight_and_rollback(self):
        aid = self.candidate()
        self.now += timedelta(minutes=20)
        self.assertEqual(self.loop.tick()['reviews'][0]['outcome'], 'APPROVE')
        reviewed = self.loop.timeline.get(aid)['last_reviewed_at']
        self.now -= timedelta(hours=2)
        self.loop.tick()
        self.assertEqual(self.loop.timeline.get(aid)['last_reviewed_at'], reviewed)
        self.assertIsNone(self.candidate())

    def test_morning_cancel(self):
        action = {'expires_at': (self.now + timedelta(days=1)).isoformat(), 'action_type':'rest_reminder'}
        self.now += timedelta(hours=8)
        self.assertEqual(self.loop.reviewer.decide(action, self.time.capture(None), self.activity.state, self.now), 'CANCEL')
        action['expires_at'] = (self.now-timedelta(seconds=1)).isoformat()
        self.assertEqual(self.loop.reviewer.decide(action, self.time.capture(None), self.activity.state, self.now), 'EXPIRE')

    def test_event_crud_is_separate(self):
        repo = CompanionEventRepository(self.clock)
        before = memory.load_memories()
        eid = repo.create('milestone', 'MyAI', metadata={'version':'1.6.2'})
        self.assertEqual(repo.query('milestone')[0]['id'], eid)
        self.assertTrue(repo.update(eid, 'new title', 'description'))
        self.assertEqual(repo.get(eid)['title'], 'new title')
        self.assertTrue(repo.delete(eid))
        self.assertIsNone(repo.get(eid))
        self.assertEqual(memory.load_memories(), before)

    def test_affect_ttl(self):
        affect = ShortTermAffect(self.clock)
        affect.set(-0.8, 0.8, 0.9, ttl_seconds=10)
        self.now += timedelta(seconds=10)
        self.assertEqual(affect.get().valence, 0)
        self.now -= timedelta(hours=1)
        self.assertEqual(affect.get().confidence, 0)

    def test_tick_does_not_start_chat_session(self):
        self.loop.tick(42)
        self.assertNotIn(42, self.time._sessions)
        self.time.capture(42)
        started = self.time._sessions[42]
        self.now += timedelta(minutes=10)
        self.loop.tick(42, provider='ollama')
        self.assertEqual(self.time._sessions[42], started)

    def test_config_rejects_invalid_thresholds(self):
        from companion_loop import CompanionConfig
        with self.assertRaises(ValueError):
            CompanionConfig(delay_seconds=3600)
        with self.assertRaises(ValueError):
            CompanionConfig(tick_seconds=0)

    def test_windows_adapter_active_idle_wrap(self):
        from types import SimpleNamespace
        class Function:
            def __init__(self, fn): self.fn = fn
            def __call__(self, *args): return self.fn(*args)
        idle_ms = [0]
        def last_input(pointer):
            pointer._obj.dwTime = (1000-idle_ms[0]) & 0xffffffff
            return 1
        def process(hwnd, pointer):
            pointer._obj.value = 123
            return 1
        user = SimpleNamespace(GetLastInputInfo=Function(last_input),
            GetForegroundWindow=Function(lambda: 1), GetWindowThreadProcessId=Function(process))
        kernel = SimpleNamespace(GetTickCount=Function(lambda: 1000))
        with patch('user_activity.sys.platform', 'win32'), patch('ctypes.WinDLL', side_effect=lambda name, **kw: user if name == 'user32' else kernel):
            provider = WindowsActivityProvider()
            active = provider.read(self.now)
            self.assertTrue(active.available)
            self.assertTrue(active.user_active)
            self.assertEqual(active.active_window, 'pid:123')
            idle_ms[0] = 120000
            idle = provider.read(self.now)
            self.assertFalse(idle.user_active)
            self.assertEqual(idle.idle_duration,120)
            self.assertEqual(idle.last_input_time,(self.now-timedelta(seconds=120)).isoformat())

    def test_os_failure_and_nonwindows(self):
        with patch('user_activity.sys.platform', 'linux'):
            self.assertFalse(WindowsActivityProvider().read(self.now).available)
        with patch('user_activity.sys.platform', 'win32'), patch('ctypes.WinDLL', side_effect=OSError):
            self.assertTrue(WindowsActivityProvider().read(self.now).busy)
        self.activity.state = ActivityState(0, None, 'fake', True, True, True)
        self.assertTrue(self.loop.tick()['activity']['user_active'])
        self.activity.state = ActivityState(120, None, 'fake', False, False, True)
        self.assertFalse(self.loop.tick()['activity']['user_active'])

    def test_old_schema_migration_idempotent(self):
        import sqlite3, tempfile
        from proactive_timeline import migrate
        from companion_events import migrate as migrate_events
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'old.db'
            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            conn.execute('''CREATE TABLE pending_actions(id INTEGER PRIMARY KEY, action_type TEXT, topic TEXT, payload TEXT,
                earliest_at TEXT, expires_at TEXT, created_reason TEXT, cancel_conditions TEXT,
                status TEXT CHECK(status IN ('pending','deferred','cancelled','completed','expired')),
                created_at TEXT, updated_at TEXT, last_reviewed_at TEXT, review_count INTEGER DEFAULT 0)''')
            conn.execute("INSERT INTO pending_actions(id,action_type,status) VALUES(42,'legacy','pending')")
            migrate(conn); migrate_events(conn); migrate(conn); migrate_events(conn)
            self.assertEqual(conn.execute('SELECT action_type,reviewed_ready FROM pending_actions WHERE id=42').fetchone()[0], 'legacy')
            conn.commit(); conn.close()
            with patch.object(memory, 'DB_PATH', path):
                memory.init_database(); memory.init_database()
                with memory.database_connection() as db:
                    self.assertEqual(db.execute('SELECT COUNT(*) FROM pending_actions').fetchone()[0],1)

if __name__ == '__main__':
    unittest.main()
