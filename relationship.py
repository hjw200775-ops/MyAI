from datetime import datetime
from threading import RLock

from memory import database_connection


DEFAULTS = {"trust": 50.0, "familiarity": 0.0, "closeness": 40.0}
_lock = RLock()


def clamp(value):
    return max(0.0, min(100.0, float(value)))


def get_stage(state=None):
    state = state or get_relationship()
    # 阶段由三个维度共同决定，不代表恋爱或任何预设身份。
    if state["familiarity"] >= 65 and state["trust"] >= 60 and state["closeness"] >= 55:
        return "close"
    if state["familiarity"] >= 25 and state["trust"] >= 40:
        return "familiar"
    return "new"


def get_relationship():
    with _lock, database_connection() as conn:
        row = conn.execute(
            "SELECT trust,familiarity,closeness FROM relationship_state WHERE id=1"
        ).fetchone()
    state = DEFAULTS.copy() if row is None else {
        "trust": clamp(row["trust"]),
        "familiarity": clamp(row["familiarity"]),
        "closeness": clamp(row["closeness"]),
    }
    state["stage"] = get_stage(state)
    return state


def change_relationship(trust=0, familiarity=0, closeness=0):
    # 二次限幅防止调用方或模型造成单轮大幅波动。
    limits = {"trust": 2.0, "familiarity": 1.0, "closeness": 2.0}
    requested = {"trust": trust, "familiarity": familiarity, "closeness": closeness}
    current = get_relationship()
    updated = {}
    for name, delta in requested.items():
        delta = max(-limits[name], min(limits[name], float(delta)))
        updated[name] = clamp(current[name] + delta)
    with _lock, database_connection() as conn:
        conn.execute("""
            UPDATE relationship_state
            SET trust=?,familiarity=?,closeness=?,updated_at=? WHERE id=1
        """, (updated["trust"], updated["familiarity"], updated["closeness"],
              datetime.now().isoformat(timespec="seconds")))
    return get_relationship()


def build_relationship_prompt():
    state = get_relationship()
    guidance = {
        "new": "保持自然但不过分熟络；少主动引用旧记忆，表达意见时保留适当距离。",
        "familiar": "可以在相关时偶尔引用记忆，语气更放松，也可以更直接地表达不同意见。",
        "close": "你们已经很熟悉；可以自然联系过去的交流并更坦率，但不要肉麻、占有或预设恋爱关系。",
    }[state["stage"]]
    return f"""当前关系阶段：{state['stage']}（仅表示交流熟悉度，不代表恋爱身份）
信任：{state['trust']:.1f}；熟悉：{state['familiarity']:.1f}；亲近：{state['closeness']:.1f}
{guidance}
这些数值只用于内部调节称呼距离、记忆引用频率、直接程度和熟悉感，禁止向用户报出。"""

