"""Companion core: state, time facts, proactive decisions, events.

Run through tests/run_offline.py so the real database is not touched.
"""
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import emotion
import relationship
from core.companion_state import CompanionState
from core.events import CompanionEvent, CompanionEventKind, EventLog
from core.proactive import ProactiveManager
from core.time_awareness import observe
from ui.controller import ChatController
import ui.controller as controller_module


def at(year, month, day, hour, minute):
    return datetime(year, month, day, hour, minute).astimezone()


class CompanionStateTests(unittest.TestCase):
    def test_capture_reads_existing_emotion_and_relationship(self):
        state = CompanionState.capture()
        self.assertEqual(state.mood["happiness"], emotion.get_emotion()["happiness"])
        self.assertEqual(state.relationship["trust"], relationship.get_relationship()["trust"])
        self.assertEqual(state.current_activity, "idle")
        self.assertTrue(state.proactive_enabled)

    def test_update_and_save_roundtrip_without_replacing_emotion(self):
        when = at(2026, 10, 12, 23, 30)
        state = CompanionState.capture().update(
            last_interaction_time=when, current_activity="chatting",
            user_presence="present", proactive_enabled=False)
        saved = state.save()
        emotion.change_emotion(happiness=3)
        restored = CompanionState.load(saved)
        self.assertEqual(restored.current_activity, "chatting")
        self.assertEqual(restored.user_presence, "present")
        self.assertFalse(restored.proactive_enabled)
        self.assertEqual(restored.last_interaction_time.replace(microsecond=0), when.replace(microsecond=0))
        self.assertEqual(restored.mood["happiness"], emotion.get_emotion()["happiness"])
        self.assertNotEqual(restored.mood["happiness"], saved["mood"]["happiness"])

    def test_refresh_follows_relationship_module(self):
        before = CompanionState.capture()
        relationship.change_relationship(trust=1)
        refreshed = before.refresh()
        self.assertEqual(refreshed.relationship["trust"], relationship.get_relationship()["trust"])
        self.assertEqual(refreshed.current_activity, before.current_activity)


class TimeAwarenessTests(unittest.TestCase):
    def test_current_time_and_overnight_gap_are_facts(self):
        last = at(2026, 10, 12, 23, 30)
        now = at(2026, 10, 13, 9, 0)
        seen = observe(now=now, last_seen=last)
        self.assertEqual(seen.time, "09:00")
        self.assertEqual(seen.date, "2026-10-13")
        self.assertEqual(seen.current_period, "上午")
        self.assertEqual(seen.gap_kind, "overnight")
        self.assertIn("昨天 23:30", seen.fact)
        self.assertIn("今天 09:00", seen.fact)
        self.assertIn("隔了一夜", seen.fact)
        self.assertNotIn("主人", seen.fact)


class ProactiveManagerTests(unittest.TestCase):
    def setUp(self):
        self.manager = ProactiveManager()
        self.now = at(2026, 10, 13, 18, 0)

    def _state(self, last, **changes):
        return CompanionState.capture().update(last_interaction_time=last, user_presence="away", **changes)

    def test_recent_chat_does_not_speak(self):
        last = self.now - timedelta(minutes=4)
        decision = self.manager.decide(self._state(last), observe(now=self.now, last_seen=last), scheduled_due=1)
        self.assertFalse(decision.should_reply)
        self.assertEqual(decision.reason, "用户刚刚离开不到5分钟")

    def test_long_absence_can_suggest_a_reply(self):
        last = self.now - timedelta(hours=12)
        decision = self.manager.decide(self._state(last), observe(now=self.now, last_seen=last))
        self.assertTrue(decision.should_reply)
        self.assertEqual(decision.reason, "用户12小时未互动")

    def test_chatting_or_disabled_blocks_even_after_long_absence(self):
        last = self.now - timedelta(hours=20)
        awareness = observe(now=self.now, last_seen=last)
        chatting = self.manager.decide(self._state(last, current_activity="chatting"), awareness)
        disabled = self.manager.decide(self._state(last, proactive_enabled=False), awareness)
        self.assertFalse(chatting.should_reply)
        self.assertFalse(disabled.should_reply)


class EventTests(unittest.TestCase):
    def test_publish_and_consume_in_order(self):
        log = EventLog()
        first = log.publish(CompanionEvent.create(CompanionEventKind.APP_START, created_at=at(2026, 10, 13, 9, 0)))
        second = log.publish(CompanionEvent.create(
            CompanionEventKind.LONG_ABSENCE, {"elapsed_seconds": 12 * 3600},
            created_at=at(2026, 10, 13, 21, 0)))
        self.assertEqual(log.pending(), 2)
        self.assertIs(log.consume(), first)
        self.assertEqual(log.consume().kind, second.kind)
        self.assertIsNone(log.consume())
        self.assertEqual(log.pending(), 0)


class _IdleThread:
    def start(self) -> None:
        return None


class ControllerHookTests(unittest.TestCase):
    def test_app_start_and_user_message_are_recorded_without_sending_proactively(self):
        with patch.object(controller_module, "apply_text_settings"), \
                patch.object(controller_module, "get_default_provider", return_value=object()):
            controller = ChatController(thread_factory=lambda **_kw: _IdleThread())
            started = controller.events.consume()
            self.assertEqual(started.kind, CompanionEventKind.APP_START)
            self.assertTrue(controller.send("你好"))
            noted = controller.events.consume()
            self.assertEqual(noted.kind, CompanionEventKind.USER_MESSAGE)
            self.assertFalse(controller.proactive_decision().should_reply)


if __name__ == "__main__":
    unittest.main()
