"""V1.4.1 latency-flow tests: visible reply is never blocked by auxiliary analysis."""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["MYAI_LOAD_DOTENV"] = "0"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai


class LatencyFlowTests(unittest.TestCase):
    def test_chat_only_makes_the_visible_reply_call(self):
        messages = [
            {"role": "system", "content": "persona-memory-emotion-relationship"},
            {"role": "user", "content": "你好"},
        ]
        with patch.object(ai, "save_message", return_value=1) as save, \
                patch.object(ai.default_context_builder, "build_messages", return_value=messages), \
                patch.object(ai, "_llm_chat", return_value="立即回复") as request, \
                patch.object(ai, "update_interaction_state") as old_state, \
                patch.object(ai, "auto_save_memory") as old_memory:
            reply, saved = ai.chat("你好", conversation_id=7)

        self.assertEqual((reply, saved), ("立即回复", None))
        request.assert_called_once_with(messages)
        old_state.assert_not_called()
        old_memory.assert_not_called()
        self.assertEqual(save.call_count, 2)

    def test_auxiliary_work_is_combined_into_one_short_call(self):
        response = {
            "state": {"happiness": 2, "sadness": 0, "anger": 0,
                      "trust": 0.5, "familiarity": 0.2, "closeness": 0.4},
            "memory": {"action": "add", "memory_id": None,
                       "content": "用户喜欢 Python", "category": "interest"},
            "title": "聊聊编程",
        }
        history = [
            (1, 7, "user", "我喜欢 Python", "time"),
            (2, 7, "assistant", "我记住啦。", "time"),
        ]
        with patch.object(ai, "load_memories", return_value=[]), \
                patch.object(ai, "get_conversation", return_value=(7, "新对话")), \
                patch.object(ai, "load_messages", return_value=history), \
                patch.object(ai, "_llm_chat", return_value=json.dumps(response)) as request, \
                patch.object(ai, "change_emotion") as emotion, \
                patch.object(ai, "change_relationship") as relationship, \
                patch.object(ai, "save_memory", return_value=True) as memory, \
                patch.object(ai, "rename_conversation", return_value=True) as rename:
            result = ai.process_post_reply_tasks(
                "我喜欢 Python", "我记住啦。", conversation_id=7
            )

        self.assertEqual(result, ("用户喜欢 Python", "聊聊编程"))
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.kwargs["timeout"], 15)
        self.assertEqual(request.call_args.kwargs["response_format"],
                         {"type": "json_object"})
        emotion.assert_called_once()
        relationship.assert_called_once()
        memory.assert_called_once_with("用户喜欢 Python", "interest")
        rename.assert_called_once_with(7, "聊聊编程", only_if_default=True)


if __name__ == "__main__":
    unittest.main()
