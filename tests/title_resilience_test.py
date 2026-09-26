"""V1.4.2 regression tests for empty auxiliary responses and title fallback."""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["MYAI_LOAD_DOTENV"] = "0"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai


class TitleCleaningTests(unittest.TestCase):
    def test_empty_values_are_safe(self):
        self.assertEqual(ai._clean_title(None), "")
        self.assertEqual(ai._clean_title(""), "")
        self.assertEqual(ai._clean_title(" \t\r\n "), "")

    def test_multiline_and_normal_titles_keep_existing_cleanup(self):
        self.assertEqual(ai._clean_title("标题：第一行\n第二行"), "第一行")
        self.assertEqual(ai._clean_title("“聊聊编程。”"), "聊聊编程")


class PostReplyResilienceTests(unittest.TestCase):
    def _run(self, payload, user_input="今天学习 Python"):
        history = [(1, 7, "user", user_input, "time")]
        with patch.object(ai, "load_memories", return_value=[]), \
                patch.object(ai, "get_conversation", return_value=(7, "新对话")), \
                patch.object(ai, "load_messages", return_value=history), \
                patch.object(ai, "_llm_chat", return_value=json.dumps(payload)), \
                patch.object(ai, "rename_conversation", return_value=True) as rename:
            result = ai.process_post_reply_tasks(user_input, "好的", 7)
        return result, rename

    def test_empty_model_title_falls_back_to_user_first_line(self):
        payload = {"state": {}, "memory": {}, "title": "  \n "}
        result, rename = self._run(payload, "今天学习 Python\n补充内容")
        self.assertEqual(result, (None, "今天学习 Python"))
        rename.assert_called_once_with(7, "今天学习 Python", only_if_default=True)

    def test_missing_and_empty_auxiliary_fields_do_not_raise(self):
        for payload in ({}, {"state": None}, {"memory": []},
                        {"state": {}, "memory": {}, "title": None}):
            with self.subTest(payload=payload):
                result, rename = self._run(payload)
                self.assertEqual(result, (None, "今天学习 Python"))
                rename.assert_called_once()

    def test_valid_model_title_is_unchanged(self):
        result, rename = self._run({"title": "模型生成标题"})
        self.assertEqual(result, (None, "模型生成标题"))
        rename.assert_called_once_with(7, "模型生成标题", only_if_default=True)

    def test_fully_empty_analysis_response_still_uses_safe_fallback(self):
        history = [(1, 7, "user", "一句话", "time")]
        with patch.object(ai, "load_memories", return_value=[]), \
                patch.object(ai, "get_conversation", return_value=(7, "新对话")), \
                patch.object(ai, "load_messages", return_value=history), \
                patch.object(ai, "_llm_chat", return_value=""), \
                patch.object(ai, "rename_conversation", return_value=True):
            self.assertEqual(ai.process_post_reply_tasks("一句话", "回复", 7),
                             (None, "一句话"))


if __name__ == "__main__":
    unittest.main()
