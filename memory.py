import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from threading import RLock


DB_PATH = Path(os.getenv("MYAI_DB_PATH", str(Path(__file__).resolve().with_name("memory.db"))))
VALID_CATEGORIES = {
    "identity", "interest", "study", "work", "goal", "preference",
    "relationship", "other",
}
VALID_ROLES = {"user", "assistant"}
_conversation_lock = RLock()


def _now():
    return datetime.now().isoformat(timespec="microseconds")


def _normalize_category(category):
    value = str(category or "other").strip().lower()
    return value if value in VALID_CATEGORIES else "other"


def _state_value(value, default):
    """把旧数据库中的状态值安全转换到 0-100。"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    if number != number or number in (float("inf"), float("-inf")):
        return float(default)
    return max(0.0, min(100.0, number))


def get_connection():
    connection = sqlite3.connect(str(DB_PATH), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=10000")
    return connection


@contextmanager
def database_connection():
    connection = get_connection()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_database():
    """创建新表，并无损迁移旧版 memory.db。"""
    with database_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL DEFAULT 'other',
                created_at TEXT,
                updated_at TEXT
            )
        """)
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(memories)")}
        if "category" not in columns:
            conn.execute("ALTER TABLE memories ADD COLUMN category TEXT NOT NULL DEFAULT 'other'")
        if "created_at" not in columns:
            conn.execute("ALTER TABLE memories ADD COLUMN created_at TEXT")
        if "updated_at" not in columns:
            conn.execute("ALTER TABLE memories ADD COLUMN updated_at TEXT")

        now = datetime.now().isoformat(timespec="seconds")
        conn.execute("UPDATE memories SET category='other' WHERE category IS NULL OR TRIM(category)='' ")
        conn.execute("UPDATE memories SET created_at=? WHERE created_at IS NULL", (now,))
        conn.execute("UPDATE memories SET updated_at=created_at WHERE updated_at IS NULL")

        # v0.9 使用一行多列（happiness/sadness/...）；v1.0 改为
        # name/value 行结构。先读取旧值，再在同一事务中完成转换。
        emotion_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='emotion_state'"
        ).fetchone()
        legacy = {}
        if emotion_exists:
            emotion_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(emotion_state)")
            }
            if not {"name", "value"}.issubset(emotion_columns):
                old_row = conn.execute(
                    "SELECT * FROM emotion_state ORDER BY rowid DESC LIMIT 1"
                ).fetchone()
                if old_row is not None:
                    for key in ("happiness", "sadness", "anger", "trust", "affection"):
                        if key in emotion_columns:
                            legacy[key] = old_row[key]
                conn.execute("DROP TABLE emotion_state")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS emotion_state (
                name TEXT PRIMARY KEY,
                value REAL NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        existing_legacy = {
            row["name"]: row["value"]
            for row in conn.execute(
                "SELECT name,value FROM emotion_state "
                "WHERE name IN ('happiness','sadness','anger','trust','affection')"
            )
        }
        legacy.update(existing_legacy)
        for name, default in {"happiness": 50, "sadness": 10, "anger": 5}.items():
            conn.execute(
                "INSERT OR IGNORE INTO emotion_state(name,value,updated_at) VALUES(?,?,?)",
                (name, _state_value(legacy.get(name), default), now),
            )

        conn.execute("""
            CREATE TABLE IF NOT EXISTS relationship_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                trust REAL NOT NULL CHECK (trust BETWEEN 0 AND 100),
                familiarity REAL NOT NULL CHECK (familiarity BETWEEN 0 AND 100),
                closeness REAL NOT NULL CHECK (closeness BETWEEN 0 AND 100),
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            INSERT OR IGNORE INTO relationship_state
                (id,trust,familiarity,closeness,updated_at)
            VALUES (1,?,?,?,?)
        """, (
            _state_value(legacy.get("trust"), 50),
            0,
            _state_value(legacy.get("affection"), 40),
            now,
        ))

        # v1.1：只新增表和索引，不改写 v1.0 的记忆、情绪或关系数据。
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL DEFAULT '默认会话',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('user','assistant')),
                content TEXT NOT NULL,
                image_path TEXT,
                message_type TEXT NOT NULL DEFAULT 'text',
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        """)
        message_columns = {row["name"] for row in conn.execute("PRAGMA table_info(messages)")}
        if "image_path" not in message_columns:
            conn.execute("ALTER TABLE messages ADD COLUMN image_path TEXT")
        if "message_type" not in message_columns:
            conn.execute("ALTER TABLE messages ADD COLUMN message_type TEXT NOT NULL DEFAULT 'text'")
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_conversation_id_id
            ON messages(conversation_id, id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversations_updated_at
            ON conversations(updated_at DESC, id DESC)
        """)


def create_conversation(title="新对话"):
    title = str(title or "新对话").strip() or "新对话"
    now = _now()
    with _conversation_lock, database_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO conversations(title,created_at,updated_at) VALUES(?,?,?)",
            (title, now, now),
        )
        return cursor.lastrowid


def list_conversations():
    with _conversation_lock, database_connection() as conn:
        rows = conn.execute("""
            SELECT id,title,created_at,updated_at FROM conversations
            ORDER BY updated_at DESC,id DESC
        """).fetchall()
    return [tuple(row) for row in rows]


def get_conversation(conversation_id):
    try:
        conversation_id = int(conversation_id)
    except (TypeError, ValueError):
        return None
    with _conversation_lock, database_connection() as conn:
        row = conn.execute(
            "SELECT id,title,created_at,updated_at FROM conversations WHERE id=?",
            (conversation_id,),
        ).fetchone()
    return tuple(row) if row is not None else None


def rename_conversation(conversation_id, title, only_if_default=False):
    """重命名会话；自动标题可用 only_if_default 避免覆盖手动标题。"""
    try:
        conversation_id = int(conversation_id)
    except (TypeError, ValueError):
        return False
    title = " ".join(str(title or "").strip().split())
    if not title:
        return False
    title = title[:30]
    now = _now()
    with _conversation_lock, database_connection() as conn:
        if only_if_default:
            cursor = conn.execute("""
                UPDATE conversations SET title=?,updated_at=?
                WHERE id=? AND title IN ('新对话','默认会话')
            """, (title, now, conversation_id))
        else:
            cursor = conn.execute(
                "UPDATE conversations SET title=?,updated_at=? WHERE id=?",
                (title, now, conversation_id),
            )
    return cursor.rowcount > 0


def get_or_create_current_conversation():
    """取得最近更新的会话；首次启动时原子地创建默认会话。"""
    with _conversation_lock, database_connection() as conn:
        row = conn.execute("""
            SELECT id FROM conversations ORDER BY updated_at DESC,id DESC LIMIT 1
        """).fetchone()
        if row is not None:
            return row["id"]
        now = _now()
        cursor = conn.execute(
            "INSERT INTO conversations(title,created_at,updated_at) VALUES(?,?,?)",
            ("新对话", now, now),
        )
        return cursor.lastrowid


def load_messages(conversation_id, limit=None):
    """按聊天顺序加载消息；limit 指只取最近 N 条。"""
    try:
        conversation_id = int(conversation_id)
    except (TypeError, ValueError):
        return []
    with _conversation_lock, database_connection() as conn:
        if limit is None:
            rows = conn.execute("""
                SELECT id,conversation_id,role,content,created_at FROM messages
                WHERE conversation_id=? ORDER BY id
            """, (conversation_id,)).fetchall()
        else:
            try:
                limit = max(0, int(limit))
            except (TypeError, ValueError):
                return []
            if limit == 0:
                return []
            rows = conn.execute("""
                SELECT id,conversation_id,role,content,created_at FROM (
                    SELECT id,conversation_id,role,content,created_at FROM messages
                    WHERE conversation_id=? ORDER BY id DESC LIMIT ?
                ) ORDER BY id
            """, (conversation_id, limit)).fetchall()
    return [tuple(row) for row in rows]


def load_message_records(conversation_id, limit=None):
    """加载含图片元数据的消息；旧版 load_messages 的五元组保持兼容。"""
    try:
        conversation_id = int(conversation_id)
    except (TypeError, ValueError):
        return []
    params = (conversation_id,)
    query = """
        SELECT id,conversation_id,role,content,image_path,message_type,created_at
        FROM messages WHERE conversation_id=? ORDER BY id
    """
    if limit is not None:
        try:
            limit = max(0, int(limit))
        except (TypeError, ValueError):
            return []
        if limit == 0:
            return []
        query = """
            SELECT id,conversation_id,role,content,image_path,message_type,created_at FROM (
                SELECT id,conversation_id,role,content,image_path,message_type,created_at
                FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT ?
            ) ORDER BY id
        """
        params = (conversation_id, limit)
    with _conversation_lock, database_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def save_message(conversation_id, role, content, image_path=None):
    try:
        conversation_id = int(conversation_id)
    except (TypeError, ValueError):
        return None
    role = str(role or "").strip().lower()
    content = str(content or "").strip()
    image_path = Path(str(image_path)).name if image_path else None
    if role not in VALID_ROLES or (not content and not image_path):
        return None
    message_type = "text_image" if content and image_path else ("image" if image_path else "text")
    now = _now()
    with _conversation_lock, database_connection() as conn:
        if conn.execute("SELECT 1 FROM conversations WHERE id=?", (conversation_id,)).fetchone() is None:
            return None
        cursor = conn.execute("""
            INSERT INTO messages(conversation_id,role,content,image_path,message_type,created_at)
            VALUES(?,?,?,?,?,?)
        """, (conversation_id, role, content, image_path, message_type, now))
        conn.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now, conversation_id))
        return cursor.lastrowid


def delete_conversation(conversation_id):
    try:
        conversation_id = int(conversation_id)
    except (TypeError, ValueError):
        return False
    with _conversation_lock, database_connection() as conn:
        cursor = conn.execute("DELETE FROM conversations WHERE id=?", (conversation_id,))
    return cursor.rowcount > 0


def save_memory(content, category="other"):
    content = str(content or "").strip()
    if not content:
        return False
    now = datetime.now().isoformat(timespec="seconds")
    try:
        with database_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO memories(content,category,created_at,updated_at)
                SELECT ?,?,?,? WHERE NOT EXISTS(
                    SELECT 1 FROM memories WHERE content=?
                )
            """, (content, _normalize_category(category), now, now, content))
        return cursor.rowcount > 0
    except sqlite3.IntegrityError:
        return False


def update_memory(memory_id, content, category="other"):
    content = str(content or "").strip()
    try:
        memory_id = int(memory_id)
    except (TypeError, ValueError):
        return False
    if not content:
        return False
    try:
        with database_connection() as conn:
            if conn.execute("SELECT 1 FROM memories WHERE content=? AND id<>?", (content, memory_id)).fetchone():
                return False
            cursor = conn.execute("""
                UPDATE memories SET content=?,category=?,updated_at=? WHERE id=?
            """, (content, _normalize_category(category), datetime.now().isoformat(timespec="seconds"), memory_id))
        return cursor.rowcount > 0
    except sqlite3.IntegrityError:
        return False


def load_memories():
    with database_connection() as conn:
        rows = conn.execute("SELECT id,content,category,created_at,updated_at FROM memories ORDER BY id").fetchall()
    return [tuple(row) for row in rows]


def delete_memory(memory_id):
    try:
        memory_id = int(memory_id)
    except (TypeError, ValueError):
        return False
    with database_connection() as conn:
        cursor = conn.execute("DELETE FROM memories WHERE id=?", (memory_id,))
    return cursor.rowcount > 0


init_database()

