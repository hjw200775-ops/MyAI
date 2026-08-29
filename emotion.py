from datetime import datetime
from threading import RLock

from memory import database_connection


DEFAULTS = {"happiness": 50.0, "sadness": 10.0, "anger": 5.0}
_lock = RLock()


def clamp(value):
    return max(0.0, min(100.0, float(value)))


def get_emotion():
    with _lock, database_connection() as conn:
        rows = conn.execute(
            "SELECT name,value FROM emotion_state WHERE name IN ('happiness','sadness','anger')"
        ).fetchall()
    values = DEFAULTS.copy()
    values.update({row["name"]: clamp(row["value"]) for row in rows})
    return values


def change_emotion(happiness=0, sadness=0, anger=0):
    deltas = {"happiness": happiness, "sadness": sadness, "anger": anger}
    now = datetime.now().isoformat(timespec="seconds")
    with _lock, database_connection() as conn:
        current = get_emotion()
        for name, delta in deltas.items():
            value = clamp(current[name] + float(delta))
            conn.execute("""
                INSERT INTO emotion_state(name,value,updated_at) VALUES(?,?,?)
                ON CONFLICT(name) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at
            """, (name, value, now))
    return get_emotion()

