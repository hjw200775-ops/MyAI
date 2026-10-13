"""Phase 2 UI foundation tests: theme tokens, ui_prefs, models, assets, ChatController.

Run through the isolated entry so the real database / settings are never touched:

    python tests/run_offline.py tests/ui_foundation_test.py
"""
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["MYAI_LOAD_DOTENV"] = "0"
_PREFS_DIR = tempfile.TemporaryDirectory()
os.environ.setdefault("MYAI_UI_PREFS_PATH", str(Path(_PREFS_DIR.name) / "ui_prefs.json"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai
import memory
from ui import assets, controller as controller_module, theme
from ui.controller import ChatController, REQUEST_FAILED_PREFIX
from ui.models import MessageItem, MessageKind
from ui.ui_prefs import UIPrefs, UIPrefsService

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
TK_IMPORT = re.compile(r"^\s*(?:import|from)\s+(?:custom)?tkinter\b", re.MULTILINE)


class ImmediateThread:
    """Runs the worker synchronously so queue ordering is deterministic."""

    def __init__(self, target, args=(), kwargs=None, daemon=True):
        self._target, self._args, self._kwargs = target, args, kwargs or {}

    def start(self):
        self._target(*self._args, **self._kwargs)


def immediate_thread_factory(**kwargs):
    return ImmediateThread(**kwargs)


class ThemeTokenTests(unittest.TestCase):
    def test_every_token_has_valid_light_and_dark_hex(self):
        for name in theme.COLOR_TOKENS:
            light, dark = theme.ctk_color(name)
            self.assertRegex(light, HEX, name)
            self.assertRegex(dark, HEX, name)

    def test_dark_background_is_not_pure_black(self):
        self.assertNotEqual(theme.DARK.background.upper(), "#000000")
        self.assertNotEqual(theme.DARK.surface.upper(), "#000000")

    def test_spacing_scale_only_uses_allowed_steps(self):
        values = {theme.SPACING.xs, theme.SPACING.sm, theme.SPACING.md,
                  theme.SPACING.lg, theme.SPACING.xl, theme.SPACING.xxl}
        self.assertEqual(values, {4, 8, 12, 16, 24, 32})

    def test_radius_scale_matches_design_document(self):
        self.assertEqual((theme.RADIUS.xs, theme.RADIUS.sm, theme.RADIUS.md,
                          theme.RADIUS.lg, theme.RADIUS.xl), (6, 8, 12, 14, 16))

    def test_font_helper_is_tk_compatible(self):
        self.assertEqual(theme.font(14, "bold"), (theme.FONT_FAMILY, 14, "bold"))
        self.assertEqual(theme.FONT_FAMILY_CJK, "Microsoft YaHei UI")

    def test_default_appearance_is_dark_and_three_modes_exist(self):
        self.assertEqual(theme.DEFAULT_APPEARANCE, "dark")
        self.assertEqual(set(theme.APPEARANCE_MODES), {"dark", "light", "system"})

    def test_theme_module_does_not_import_tkinter(self):
        from ui import chat_history
        for module in (theme, controller_module, chat_history):
            source = Path(module.__file__).read_text(encoding="utf-8")
            self.assertIsNone(TK_IMPORT.search(source), module.__name__)


class UIPrefsTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "ui_prefs.json"
        self.service = UIPrefsService(self.path)

    def tearDown(self):
        self.folder.cleanup()

    def test_missing_file_returns_dark_default(self):
        self.assertEqual(self.service.load(), UIPrefs(appearance="dark"))

    def test_save_then_load_roundtrip_and_file_contains_only_ui_fields(self):
        saved = self.service.save(UIPrefs(appearance="light", conversation_panel_collapsed=True))
        self.assertEqual(self.service.load(), saved)
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(set(payload), {"appearance", "conversation_panel_collapsed"})
        self.assertFalse(list(self.path.parent.glob(".ui_prefs.json.*.tmp")))

    def test_invalid_values_and_corrupt_json_fall_back(self):
        self.path.write_text('{"appearance": "neon", "conversation_panel_collapsed": "yes"}',
                             encoding="utf-8")
        self.assertEqual(self.service.load(), UIPrefs())
        self.path.write_text("{not json", encoding="utf-8")
        self.assertEqual(self.service.load(), UIPrefs())

    def test_system_mode_is_accepted(self):
        self.assertEqual(self.service.save(UIPrefs(appearance="system")).appearance, "system")

    def test_settings_module_is_untouched(self):
        import settings
        self.assertEqual(set(settings.UserSettings.__dataclass_fields__),
                         {"text_provider", "ollama_model", "ollama_base_url"})


class ModelTests(unittest.TestCase):
    def test_message_kind_from_role(self):
        self.assertIs(MessageKind.from_role("user"), MessageKind.USER)
        self.assertIs(MessageKind.from_role("assistant"), MessageKind.ASSISTANT)
        self.assertIs(MessageKind.from_role(None), MessageKind.ASSISTANT)

    def test_message_item_from_record(self):
        item = MessageItem.from_record({"id": 3, "role": "user", "content": "hi",
                                        "image_path": "a.png", "created_at": "t"})
        self.assertEqual((item.kind, item.content, item.image_name, item.message_id, item.persisted),
                         (MessageKind.USER, "hi", "a.png", 3, True))
        self.assertFalse(MessageItem.system("x").persisted)
        self.assertIs(MessageItem.system("x").kind, MessageKind.SYSTEM)


class AssetTests(unittest.TestCase):
    def test_avatar_circular_crop(self):
        image = assets.avatar_image(28)
        self.assertEqual((image.size, image.mode), ((28, 28), "RGBA"))
        self.assertEqual(image.getpixel((0, 0))[3], 0)      # corner is transparent
        self.assertGreater(image.getpixel((14, 14))[3], 200)  # centre is opaque

    def test_avatar_square_keeps_corners(self):
        image = assets.avatar_image(72, circular=False)
        self.assertEqual(image.size, (72, 72))
        self.assertEqual(image.getpixel((0, 0))[3], 255)


class IconAndPlatformTests(unittest.TestCase):
    def test_every_icon_renders_with_visible_pixels(self):
        from ui.icons import ICON_DRAWERS, icon_image
        for name in ICON_DRAWERS:
            image = icon_image(name, 20, "#8D97D6")
            self.assertEqual((image.size, image.mode), ((20, 20), "RGBA"), name)
            alpha = image.getchannel("A").getbbox()
            self.assertIsNotNone(alpha, name)             # something was drawn
            self.assertEqual(image.getpixel((0, 0))[3], 0, name)  # padding stays transparent

    def test_colorref_is_bgr(self):
        from ui.platform_win import colorref
        self.assertEqual(colorref("#FF0000"), 0x0000FF)
        self.assertEqual(colorref("#0000FF"), 0xFF0000)
        self.assertEqual(colorref("#17191F"), 0x1F1917)
        with self.assertRaises(ValueError):
            colorref("#123")

    def test_nav_items_match_outline_and_have_icons(self):
        source = Path(__file__).resolve().parents[1] / "ui" / "sidebar.py"
        text = source.read_text(encoding="utf-8")
        self.assertNotIn("overrideredirect", text)
        from ui.icons import ICON_DRAWERS
        import ast
        tree = ast.parse(text)
        items = next(node for node in ast.walk(tree)
                     if isinstance(node, ast.AnnAssign)
                     and getattr(node.target, "id", "") == "NAV_ITEMS")
        keys = [elt.elts[0].value for elt in items.value.elts]
        icons = [elt.elts[2].value for elt in items.value.elts]
        self.assertEqual(keys, ["chat", "memory", "vision", "settings"])
        self.assertTrue(set(icons) <= set(ICON_DRAWERS))

    def test_no_module_uses_overrideredirect(self):
        ui_dir = Path(__file__).resolve().parents[1] / "ui"
        for path in ui_dir.glob("*.py"):
            self.assertNotIn("overrideredirect(", path.read_text(encoding="utf-8"), path.name)


class _FakeHistory:
    """Mimics ChatController.history(cid, limit): latest N in chronological order."""

    def __init__(self, count):
        self.rows = [MessageItem(kind=MessageKind.USER if i % 2 else MessageKind.ASSISTANT,
                                 content=f"m{i}", message_id=i) for i in range(1, count + 1)]
        self.calls = []

    def history(self, conversation_id=None, limit=None):
        self.calls.append(limit)
        return list(self.rows if limit is None else self.rows[-limit:])

    def add(self, *kinds):
        for kind in kinds:
            next_id = (self.rows[-1].message_id + 1) if self.rows else 1
            self.rows.append(MessageItem(kind=kind, content=f"m{next_id}", message_id=next_id))


class MessageWindowTests(unittest.TestCase):
    def test_load_latest_renders_only_last_page(self):
        from ui.chat_history import MessageWindow
        source = _FakeHistory(95)
        window = MessageWindow(source, 1, page_size=40)
        items = window.load_latest()
        self.assertEqual(len(items), 40)
        self.assertEqual((items[0].message_id, items[-1].message_id), (56, 95))
        self.assertTrue(window.has_more)
        self.assertEqual(source.calls, [41])          # never loads everything

    def test_load_older_prepends_pages_until_exhausted(self):
        from ui.chat_history import MessageWindow
        source = _FakeHistory(95)
        window = MessageWindow(source, 1, page_size=40)
        window.load_latest()
        older = window.load_older()
        self.assertEqual([m.message_id for m in older][::39], [16, 55])
        self.assertEqual(len(older), 40)
        self.assertTrue(window.has_more)
        older = window.load_older()
        self.assertEqual([m.message_id for m in older], list(range(1, 16)))
        self.assertFalse(window.has_more)
        self.assertEqual(window.load_older(), [])
        self.assertEqual([m.message_id for m in window.items], list(range(1, 96)))

    def test_fetch_new_returns_only_unseen_messages(self):
        from ui.chat_history import MessageWindow
        source = _FakeHistory(10)
        window = MessageWindow(source, 1, page_size=40)
        window.load_latest()
        source.add(MessageKind.USER, MessageKind.ASSISTANT)
        new = window.fetch_new()
        self.assertEqual([m.message_id for m in new], [11, 12])
        self.assertEqual(window.last_id, 12)
        self.assertEqual(window.fetch_new(), [])

    def test_fetch_new_on_empty_conversation(self):
        from ui.chat_history import MessageWindow
        source = _FakeHistory(0)
        window = MessageWindow(source, 1)
        self.assertEqual(window.load_latest(), [])
        self.assertFalse(window.has_more)
        source.add(MessageKind.USER)                   # reply failed after saving user text
        self.assertEqual([m.kind for m in window.fetch_new()], [MessageKind.USER])

    def test_format_time_is_tolerant(self):
        from ui.message_bubble import format_time
        self.assertEqual(format_time("2026-10-12T23:05:09.123456"), "23:05")
        self.assertEqual(format_time("garbage"), "")
        self.assertEqual(format_time(None), "")

    def test_no_text_prefix_rendering_left_in_chat_view(self):
        source = (Path(__file__).resolve().parents[1] / "ui" / "chat_view.py").read_text(encoding="utf-8")
        self.assertNotIn("小悠：", source)
        self.assertNotIn("你：", source)
        self.assertNotIn("CTkTextbox", source)
        from ui.theme import PROACTIVE_LABEL, MEMORY_SAVED_TEXT
        self.assertNotIn("AI主动", PROACTIVE_LABEL)
        self.assertIn("小悠", PROACTIVE_LABEL)
        self.assertIn("小悠记住了", MEMORY_SAVED_TEXT)


class InputDecisionTests(unittest.TestCase):
    def test_enter_sends_only_when_not_shift_or_composing(self):
        from ui.input_panel import should_send_on_return
        from ui.platform_win import VK_PROCESSKEY
        self.assertTrue(should_send_on_return(False, 13, False))
        self.assertFalse(should_send_on_return(True, 13, False))
        self.assertFalse(should_send_on_return(False, 13, True))
        self.assertFalse(should_send_on_return(False, VK_PROCESSKEY, False))

    def test_long_filename_is_truncated_and_keeps_suffix(self):
        from ui.input_panel import shorten_filename
        self.assertEqual(shorten_filename("a.png"), "a.png")
        shortened = shorten_filename("very_long_image_file_name_that_overflows.png")
        self.assertLessEqual(len(shortened), 28)
        self.assertTrue(shortened.endswith(".png"))
        self.assertIn("…", shortened)

    def test_chat_view_delegates_input_to_panel(self):
        root = Path(__file__).resolve().parents[1] / "ui"
        source = (root / "chat_view.py").read_text(encoding="utf-8")
        self.assertIn("InputPanel", source)
        self.assertNotIn("CTkEntry", source)
        self.assertNotIn("输入消息...", source)
        panel = (root / "input_panel.py").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"#[0-9A-Fa-f]{3,8}\b", panel))


class PageHelperTests(unittest.TestCase):
    def test_filter_memories_matches_content_or_category(self):
        from ui.models import MemoryItem
        from ui.pages import filter_memories
        items = [
            MemoryItem(1, "喜欢喝茶", "preference", "偏好"),
            MemoryItem(2, "正在学数学", "study", "学习"),
        ]
        self.assertEqual([item.id for item in filter_memories(items, "  ")], [1, 2])
        self.assertEqual([item.id for item in filter_memories(items, "茶")], [1])
        self.assertEqual([item.id for item in filter_memories(items, "学习")], [2])
        self.assertEqual(filter_memories(items, "没有"), [])

    def test_provider_switch_keeps_saved_ollama_fields(self):
        from settings import UserSettings
        current = UserSettings("deepseek", "qwen2.5", "http://127.0.0.1:11434")
        draft = ChatController.draft_settings("ollama", current.ollama_model, current.ollama_base_url)
        self.assertEqual((draft.text_provider, draft.ollama_model, draft.ollama_base_url),
                         ("ollama", "qwen2.5", "http://127.0.0.1:11434"))

    def test_chat_toolbar_is_model_selector_and_pages_have_no_hex(self):
        root = Path(__file__).resolve().parents[1] / "ui"
        for name in ("pages.py", "model_selector.py"):
            source = (root / name).read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"#[0-9A-Fa-f]{3,8}\b", source), name)
        chat = (root / "chat_view.py").read_text(encoding="utf-8")
        pages = (root / "pages.py").read_text(encoding="utf-8")
        self.assertIn("ModelSelector", chat)
        self.assertNotIn("AI 设置", chat)
        self.assertNotIn("show_memories", chat)
        self.assertIn("角色状态 · 调试", pages)
        self.assertNotIn("摄像头", pages)
        self.assertIn("ui_prefs", (root / "main_window.py").read_text(encoding="utf-8"))


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.apply = patch.object(controller_module, "apply_text_settings").start()
        self.addCleanup(patch.stopall)
        self.controller = ChatController(thread_factory=immediate_thread_factory)
        self.cid = self.controller.new_conversation("新对话")

    def _fake_chat_persisting(self, reply, provider_sentinel, seen):
        def fake_chat(user_text, conversation_id, image_path=None):
            seen.append(ai._request_provider.get())
            memory.save_message(conversation_id, "user", user_text, image_path)
            memory.save_message(conversation_id, "assistant", reply)
            return reply, None
        return fake_chat

    def test_send_runs_chat_inside_provider_scope_and_triggers_background(self):
        sentinel = object()
        seen = []

        def fake_post(user_text, reply, conversation_id):
            seen.append(ai._request_provider.get())
            return ("用户喜欢蛋糕", "聊蛋糕")

        with patch.object(controller_module, "get_default_provider", return_value=sentinel), \
                patch.object(controller_module, "chat",
                             side_effect=self._fake_chat_persisting("好呀", sentinel, seen)), \
                patch.object(controller_module, "process_post_reply_tasks",
                             side_effect=fake_post) as post:
            self.assertTrue(self.controller.send("你好"))
            self.assertTrue(self.controller.request_in_progress)  # cleared only by poll()
            result = self.controller.poll()

        self.assertEqual(seen, [sentinel, sentinel])  # chat + background both scoped
        self.assertEqual(len(result.replies), 1)
        reply = result.replies[0]
        self.assertEqual((reply.conversation_id, reply.reply, reply.persisted), (self.cid, "好呀", True))
        self.assertEqual(len(result.background), 1)
        self.assertEqual((result.background[0].saved_memory, result.background[0].generated_title),
                         ("用户喜欢蛋糕", "聊蛋糕"))
        post.assert_called_once_with("你好", "好呀", self.cid)
        self.assertFalse(self.controller.request_in_progress)
        self.assertEqual([m.kind for m in self.controller.history()],
                         [MessageKind.USER, MessageKind.ASSISTANT])

    def test_unsaved_error_reply_is_not_persisted_and_skips_background(self):
        with patch.object(controller_module, "get_default_provider", return_value=object()), \
                patch.object(controller_module, "chat",
                             return_value=("连接服务时发生错误：network", None)), \
                patch.object(controller_module, "process_post_reply_tasks") as post:
            self.controller.send("你好")
            result = self.controller.poll()
        self.assertFalse(result.replies[0].persisted)
        self.assertEqual(result.background, [])
        post.assert_not_called()

    def test_worker_exception_becomes_failure_event(self):
        with patch.object(controller_module, "get_default_provider", return_value=object()), \
                patch.object(controller_module, "chat", side_effect=RuntimeError("boom")):
            self.controller.send("你好")
            result = self.controller.poll()
        self.assertTrue(result.replies[0].reply.startswith(REQUEST_FAILED_PREFIX))
        self.assertFalse(self.controller.request_in_progress)

    def test_image_only_message_skips_background_even_when_persisted(self):
        seen = []
        with tempfile.TemporaryDirectory() as folder:
            from PIL import Image
            picture = Path(folder) / "p.png"
            Image.new("RGB", (4, 4), "white").save(picture)
            self.controller.select_image(str(picture))
            self.assertEqual(self.controller.selected_image_path, str(picture))
            with patch.object(controller_module, "get_default_provider", return_value=object()), \
                    patch.object(controller_module, "chat",
                                 side_effect=self._fake_chat_persisting("看到了", None, seen)), \
                    patch.object(controller_module, "process_post_reply_tasks") as post:
                self.assertTrue(self.controller.send(""))
                result = self.controller.poll()
        self.assertIsNone(self.controller.selected_image_path)  # cleared on send
        self.assertTrue(result.replies[0].persisted)
        post.assert_not_called()

    def test_send_is_ignored_when_empty_or_busy(self):
        self.assertFalse(self.controller.send("   "))
        self.controller.request_in_progress = True
        self.assertFalse(self.controller.can_send("hi"))
        self.assertFalse(self.controller.send("hi"))

    def test_invalid_image_is_rejected_without_changing_selection(self):
        with self.assertRaises(ValueError):
            self.controller.select_image("missing.txt")
        self.assertIsNone(self.controller.selected_image_path)

    def test_conversation_lifecycle(self):
        other = self.controller.new_conversation("第二个")
        self.assertEqual(self.controller.conversation_id, other)
        titles = {c.id: (c.title, c.selected) for c in self.controller.conversations()}
        self.assertEqual(titles[other], ("第二个", True))
        self.assertEqual(titles[self.cid][1], False)
        self.assertTrue(self.controller.rename_conversation(other, "改名"))
        self.assertTrue(self.controller.delete_conversation(other))   # current changed
        self.assertNotEqual(self.controller.conversation_id, other)
        self.assertFalse(self.controller.delete_conversation(99999))

    def test_switch_conversation_clears_pending_image(self):
        self.controller.set_image("x.png")
        self.controller.switch_conversation(self.cid)
        self.assertIsNone(self.controller.selected_image_path)

    def test_memory_edits_refresh_system_prompt(self):
        with patch.object(controller_module, "refresh_system_prompt") as refresh:
            self.assertTrue(self.controller.add_memory("用户喜欢蛋糕", "preference"))
            item = next(m for m in self.controller.memories() if m.content == "用户喜欢蛋糕")
            self.assertEqual(item.category_label, "偏好")
            self.assertTrue(self.controller.update_memory(item.id, "用户很喜欢蛋糕", "preference"))
            self.assertTrue(self.controller.delete_memory(item.id))
            self.assertFalse(self.controller.add_memory("   "))
        self.assertEqual(refresh.call_count, 3)

    def test_connection_check_without_ollama_returns_safe_message(self):
        draft = ChatController.draft_settings("DeepSeek 云端", "qwen3.5:2b", "http://127.0.0.1:11434")
        self.assertEqual(draft.text_provider, "deepseek")
        self.controller.check_connection(draft)
        result = self.controller.poll()
        self.assertEqual(len(result.connection_checks), 1)
        self.assertEqual(result.connection_checks[0].draft, draft)
        self.assertIn("检查失败", result.connection_checks[0].message)
        self.assertEqual(result.replies, [])

    def test_save_settings_applies_and_updates_labels(self):
        draft = ChatController.draft_settings("ollama", "qwen3.5:2b", "http://127.0.0.1:11434")
        saved = self.controller.save_settings(draft)
        self.assertEqual(saved.text_provider, "ollama")
        self.apply.assert_called_with(saved)
        self.assertEqual(self.controller.provider_label, "Ollama 本地")
        self.assertEqual(self.controller.model_display_name, "qwen3.5:2b")
        back = self.controller.save_settings(ChatController.draft_settings("deepseek", "", ""))
        self.assertEqual((back.text_provider, self.controller.model_display_name),
                         ("deepseek", "DeepSeek Flash"))

    def test_state_helpers(self):
        self.assertEqual(set(self.controller.emotion_state()), {"happiness", "sadness", "anger"})
        rel = self.controller.relationship_state()
        self.assertIn(rel["stage_label"], {"刚认识", "熟悉", "亲近"})



if __name__ == "__main__":
    unittest.main()
