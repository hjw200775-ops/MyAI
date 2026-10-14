"""Separate shared milestones, never automatic chat ingestion."""
import json
from foundation_time import foundation_clock, number
from proactive_timeline import database_connection

def migrate(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS companion_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL,
        title TEXT NOT NULL, description TEXT NOT NULL, timestamp TEXT NOT NULL,
        importance REAL NOT NULL, metadata TEXT NOT NULL)''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_companion_events_time ON companion_events(timestamp)')

class CompanionEventRepository:
    def __init__(self, clock=None):
        self.clock = clock or foundation_clock
        with database_connection() as conn:
            migrate(conn)

    def create(self, event_type, title, description='', importance=0.5, metadata=None):
        if not str(event_type).strip() or not str(title).strip():
            raise ValueError('Event type and title required')
        importance = number(importance, 0, 1)
        metadata = json.dumps(metadata or {}, ensure_ascii=False, allow_nan=False)
        with database_connection() as conn:
            return conn.execute('INSERT INTO companion_events(event_type,title,description,timestamp,importance,metadata) VALUES(?,?,?,?,?,?)',
                (event_type, title, description, self.clock.now().isoformat(), importance, metadata)).lastrowid

    def list(self, event_type=None, limit=100):
        limit = int(number(limit, 1, 1000))
        with database_connection() as conn:
            rows = conn.execute('SELECT * FROM companion_events WHERE (? IS NULL OR event_type=?) ORDER BY timestamp DESC,id DESC LIMIT ?',
                                (event_type, event_type, limit)).fetchall()
        return [dict(row) for row in rows]

    query = list

    def get(self, event_id):
        with database_connection() as conn:
            row = conn.execute('SELECT * FROM companion_events WHERE id=?', (event_id,)).fetchone()
        return dict(row) if row else None

    def update(self, event_id, title, description):
        if not str(title).strip():
            raise ValueError('Title required')
        with database_connection() as conn:
            return bool(conn.execute('UPDATE companion_events SET title=?,description=? WHERE id=?', (title, description, event_id)).rowcount)

    def delete(self, event_id):
        with database_connection() as conn:
            return bool(conn.execute('DELETE FROM companion_events WHERE id=?', (event_id,)).rowcount)
