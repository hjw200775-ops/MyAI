import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import memory
import llm
from time_context import TimeContextService
from foundation_time import FoundationClock
from proactive_timeline import ProactiveTimelineService, ReviewContext, ReviewDecision
from memory_retention import MemoryRetentionService
from affect_state import ShortTermAffect, AffectState


class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)
        self.clock = FoundationClock(TimeContextService(lambda: self.now))
        memory.init_database()
        with memory.database_connection() as conn:
            conn.execute('DELETE FROM pending_actions')
            conn.execute('DELETE FROM memories')
        self.timeline = ProactiveTimelineService(self.clock)
        self.retention = MemoryRetentionService(self.clock)

    def schedule(self):
        return self.timeline.schedule('proactive_message', '休息', self.now + timedelta(seconds=10),
            self.now + timedelta(seconds=100), payload={'text': '休息'},
            created_reason='测试', cancel_conditions=['已休息'])

    def test_eligible_never_sends_or_completes(self):
        aid = self.schedule()
        self.assertEqual(self.timeline.list_due_actions(), [])
        with patch('ai._llm_chat', side_effect=AssertionError('No provider calls')):
            self.now += timedelta(seconds=10)
            self.assertEqual([a['id'] for a in self.timeline.get_due_actions()], [aid])
            ctx = ReviewContext(latest_context='用户正在输入', idle_duration=30)
            seen = []
            decision = self.timeline.review(aid, ctx, lambda row, context:
                (seen.append((row, context)) or ReviewDecision()))
            self.assertEqual(decision.outcome, 'eligible')
        self.assertIs(seen[0][1], ctx)
        row = self.timeline.get(aid)
        self.assertEqual(row['status'], 'pending')
        self.assertEqual(row['review_count'], 1)
        self.assertIsNotNone(row['last_reviewed_at'])

    def test_transitions_and_terminals(self):
        aid = self.schedule()
        self.now += timedelta(seconds=10)
        self.timeline.defer(aid, self.now + timedelta(seconds=20))
        self.assertEqual(self.timeline.get(aid)['status'], 'deferred')
        self.assertEqual(self.timeline.list_due_actions(), [])
        self.now += timedelta(seconds=20)
        self.assertEqual(len(self.timeline.list_due_actions()), 1)
        self.assertTrue(self.timeline.cancel(aid))
        self.assertFalse(self.timeline.mark_completed(aid))
        completed = self.schedule()
        self.assertTrue(self.timeline.mark_completed(completed))
        expired = self.schedule()
        self.now += timedelta(seconds=100)
        self.assertEqual(self.timeline.expire(), 1)
        self.assertEqual(self.timeline.get(expired)['status'], 'expired')
        self.assertFalse(self.timeline.cancel(expired))

    def test_review_replans_and_failure_does_not_execute(self):
        aid = self.schedule()
        self.now += timedelta(seconds=10)
        self.timeline.reconsider(aid, ReviewContext(), lambda *_: ReviewDecision('defer', self.now + timedelta(seconds=10)))
        self.now += timedelta(seconds=10)
        with self.assertRaises(RuntimeError):
            self.timeline.review(aid, ReviewContext(), lambda *_: (_ for _ in ()).throw(RuntimeError()))
        self.assertEqual(self.timeline.get(aid)['status'], 'deferred')
        self.timeline.review(aid, ReviewContext(), lambda *_: ReviewDecision('cancel'))
        self.assertEqual(self.timeline.get(aid)['status'], 'cancelled')

    def test_review_expiry_during_hook(self):
        aid = self.schedule()
        self.now += timedelta(seconds=10)
        def hook(*_):
            self.now += timedelta(seconds=100)
            return ReviewDecision()
        self.assertIsNone(self.timeline.review(aid, ReviewContext(), hook))
        self.assertEqual(self.timeline.get(aid)['status'], 'expired')

    def test_bad_timestamps_invalid_ranges_and_rollback(self):
        for start, end in [('bad', self.now), (self.now, 'bad'), (self.now, self.now)]:
            with self.assertRaises(ValueError):
                self.timeline.create('x', 'x', start, end)
        aid = self.schedule()
        with self.assertRaises(ValueError):
            self.timeline.defer(aid, self.now)
        self.now += timedelta(seconds=20)
        self.assertEqual(len(self.timeline.list_due_actions()), 1)
        self.now -= timedelta(hours=1)
        self.assertEqual(len(self.timeline.list_due_actions()), 1)
        with memory.database_connection() as conn:
            conn.execute("UPDATE pending_actions SET earliest_at='corrupt' WHERE id=?", (aid,))
        self.assertEqual(self.timeline.list_due_actions(), [])
        self.assertEqual(self.timeline.get(aid)['status'], 'expired')
        self.now = 'invalid'
        with self.assertRaises(ValueError):
            self.timeline.list_due_actions()

    def test_provider_switch_keeps_timeline(self):
        aid = self.schedule()
        try:
            llm.set_default_provider(object())
            self.now += timedelta(seconds=10)
            first = self.timeline.list_due_actions()
            llm.set_default_provider(object())
            self.assertEqual(first, self.timeline.list_due_actions())
            self.assertEqual(self.timeline.get(aid)['status'], 'pending')
        finally:
            llm.set_default_provider(None)

    def test_retention_categories_and_context_isolation(self):
        fact = self.retention.save('姓名小明', 'explicit_fact', confidence=.9)
        self.retention.save('喜欢音乐', 'preference', category='preference')
        temporary = self.retention.save('明天旅行', 'temporary_state_or_plan', ttl_seconds=10)
        candidate = self.retention.save('可能重视独处', 'inferred_trait_or_value', confidence=1)
        self.assertIsNone(self.retention.save('敏感猜测', 'sensitive_inference'))
        self.assertEqual(len(self.retention.list()), 3)
        self.assertEqual(len(self.retention.list(True)), 4)
        with patch('foundation_time.foundation_clock.time_service.clock', lambda: self.now):
            import foundation_time
            with patch('memory_retention.foundation_clock', self.clock):
                self.assertNotIn(candidate, [row[0] for row in memory.load_memories()])
                self.assertFalse(memory.update_memory(candidate, '不应提升'))
                self.now += timedelta(seconds=10)
                self.assertNotIn(temporary, [row[0] for row in memory.load_memories()])
        with memory.database_connection() as conn:
            self.assertEqual(conn.execute('SELECT retention_status FROM memories WHERE id=?', (temporary,)).fetchone()[0], 'expired')
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM memories WHERE content=?', ('敏感猜测',)).fetchone()[0], 0)
            conn.execute("UPDATE memories SET expires_at='broken' WHERE id=?", (fact,))
        self.assertNotIn(fact, [row['id'] for row in self.retention.list()])
        with self.assertRaises(ValueError):
            self.retention.save('临时', 'temporary_state_or_plan')
        with self.assertRaises(ValueError):
            self.retention.save('无效', 'explicit_fact', confidence=float('nan'))

    def test_affect_decay_expiry_rollback_and_corruption(self):
        affect = ShortTermAffect(self.clock)
        self.assertEqual(affect.get(), AffectState())
        affect.set(-.6, .8, .5, 100)
        self.now += timedelta(seconds=50)
        self.assertAlmostEqual(affect.get().valence, -.3)
        self.now -= timedelta(seconds=30)
        self.assertAlmostEqual(affect.get().valence, -.3)
        self.now += timedelta(seconds=80)
        self.assertEqual(affect.get(), AffectState())
        affect._state = AffectState(1, 1, 1, 'broken', 'broken')
        self.assertEqual(affect.get(), AffectState())
        for values in [(2, .5, .5, 10), (0, float('nan'), .5, 10), (0, .5, .5, -1)]:
            with self.assertRaises(ValueError):
                affect.set(*values)

    def test_legacy_automatic_retention_guard(self):
        import ai
        with patch('memory_retention.foundation_clock', self.clock):
            self.assertFalse(ai._retain_automatic_memory('用户可能患有抑郁', 'other'))
            self.assertFalse(ai._retain_automatic_memory('用户可能内向', 'other'))
            self.assertTrue(ai._retain_automatic_memory('用户明天计划旅行', 'goal'))
            self.assertTrue(ai._retain_automatic_memory('用户喜欢音乐', 'preference'))
            rows = self.retention.list(True)
            self.assertEqual([row['retention_status'] for row in rows], ['candidate', 'active', 'active'])
            self.assertEqual(rows[-1]['retention_category'], 'preference')
            self.now += timedelta(days=1)
            self.assertEqual(len(self.retention.list()), 1)

    def test_legacy_schema_idempotent_migration(self):
        with memory.database_connection() as conn:
            conn.execute('DROP TABLE memories')
            conn.execute('DROP TABLE pending_actions')
            conn.execute('CREATE TABLE memories(id INTEGER PRIMARY KEY,content TEXT UNIQUE,category TEXT,created_at TEXT,updated_at TEXT)')
            conn.execute("INSERT INTO memories VALUES(17,'旧记忆','interest','2026-01-01','2026-01-02')")
        memory.init_database()
        memory.init_database()
        self.assertEqual(memory.load_memories(), [(17, '旧记忆', 'interest', '2026-01-01', '2026-01-02')])
        with memory.database_connection() as conn:
            row = dict(conn.execute('SELECT * FROM memories').fetchone())
            self.assertEqual(row['retention_status'], 'active')
            self.assertEqual(row['metadata'], '{}')
        self.assertIsInstance(self.schedule(), int)

if __name__ == '__main__':
    unittest.main()

