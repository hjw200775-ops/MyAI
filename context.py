from dataclasses import dataclass
from typing import Any
from character import build_character_prompt
from emotion import get_emotion
from media import resolve_image
from memory import load_memories, load_message_records
from relationship import build_relationship_prompt

CONTEXT_MESSAGE_LIMIT = 30


@dataclass(frozen=True)
class ContextOptions:
    recent_message_limit: int = CONTEXT_MESSAGE_LIMIT
    conversation_summary: str | None = None
    time_context: str | None = None
    vision_context: str | None = None


class ContextBuilder:
    """集中构建模型上下文；不负责调用模型或写数据库。"""

    def build_system_prompt(self, options: ContextOptions | None = None) -> str:
        options = options or ContextOptions()
        memories = load_memories()
        memory_text = "\n".join(f"- [{category}] {content}" for _, content, category, _, _ in memories) or "目前没有长期记忆。"
        emotion = get_emotion()
        sections = [
            build_character_prompt(),
            f"【当前情绪】\n开心：{emotion['happiness']:.1f}；难过：{emotion['sadness']:.1f}；生气：{emotion['anger']:.1f}\n让情绪克制地影响措辞，不要直接报告数值或过度表演。",
            f"【与用户的关系】\n{build_relationship_prompt()}",
            f"【关于用户的长期记忆】\n{memory_text}\n只在当前话题确实相关时自然使用记忆，不要为了证明有记忆而复述或罗列资料。",
            "【图片对话原则】\n图片是用户当前表达的一部分。直接结合图中内容、聊天语境和你的人格自然回应；不要输出机械的图片描述报告，也不要声称看到了无法确认的细节。",
        ]
        # V1.2 仅提供槽位；摘要、时间与视觉内容由以后版本传入。
        if options.conversation_summary:
            sections.append(f"【较早会话摘要】\n{options.conversation_summary}")
        if options.time_context:
            sections.append(f"【时间上下文】\n{options.time_context}")
        if options.vision_context:
            sections.append(f"【视觉上下文】\n{options.vision_context}")
        return "\n\n".join(sections).strip() + "\n"

    def build_recent_messages(self, conversation_id: int, limit: int = CONTEXT_MESSAGE_LIMIT) -> list[dict[str, Any]]:
        history = load_message_records(conversation_id, limit=max(0, int(limit)))
        messages: list[dict[str, Any]] = []
        for row in history:
            image = resolve_image(row["image_path"])
            if image is None:
                messages.append({"role": row["role"], "content": row["content"] or "[图片资源已不可用]"})
                continue
            parts: list[dict[str, Any]] = []
            if row["content"]:
                parts.append({"type": "text", "text": row["content"]})
            else:
                parts.append({"type": "text", "text": "请看看这张图片，并自然回应。"})
            parts.append({"type": "image_path", "path": str(image)})
            messages.append({"role": row["role"], "content": parts})
        return messages

    def build_messages(self, conversation_id: int, options: ContextOptions | None = None) -> list[dict[str, Any]]:
        options = options or ContextOptions()
        return [{"role": "system", "content": self.build_system_prompt(options)},
                *self.build_recent_messages(conversation_id, options.recent_message_limit)]


default_context_builder = ContextBuilder()

