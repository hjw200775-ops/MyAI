"""Replannable candidates only. This module has NO sender, timer or worker."""
import json
from dataclasses import dataclass
from typing import Any
from foundation_time import foundation_clock, timestamp
from time_context import parse_timestamp
from contextlib import contextmanager

@contextmanager
def database_connection():
    from memory import database_connection as connect
    with connect() as conn:
        yield conn

ACTIVE = ('pending', 'deferred')
TERMINAL = ('cancelled', 'completed', 'expired')


def migrate(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS pending_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action_type TEXT NOT NULL, topic TEXT NOT NULL, payload TEXT NOT NULL,
        earliest_at TEXT NOT NULL, expires_at TEXT NOT NULL,
        created_reason TEXT NOT NULL, cancel_conditions TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending'
            CHECK(status IN ('pending','deferred','cancelled','completed','expired')),
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        last_reviewed_at TEXT, review_count INTEGER NOT NULL DEFAULT 0)''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_pending_actions_status ON pending_actions(status)')


@dataclass(frozen=True)
class ReviewContext:
    latest_context: Any = None
    idle_duration: float | None = None
    last_proactive_at: Any = None
    user_is_typing: bool | None = None
    fullscreen: bool | None = None


@dataclass(frozen=True)
class ReviewDecision:
    outcome: str = 'eligible'  # eligible is NOT authorization to send
    earliest_at: Any = None


class PendingActionRepository:
    def __init__(self, clock=None):
        self.clock = clock or foundation_clock
        with database_connection() as conn:
            migrate(conn)

    def get(self, action_id):
        with database_connection() as conn:
            row = conn.execute('SELECT * FROM pending_actions WHERE id=?', (action_id,)).fetchone()
        return dict(row) if row else None

    def create(self, action_type, topic, earliest_at, expires_at, *, payload=None,
               created_reason='', cancel_conditions=None):
        earliest, expires = timestamp(earliest_at), timestamp(expires_at)
        now = self.clock.now()
        if expires <= earliest or expires <= now:
            raise ValueError('Expiry must follow earliest time and current time')
        if not isinstance(action_type, str) or not action_type.strip():
            raise ValueError('action_type required')
        if not isinstance(topic, str):
            raise ValueError('topic must be text')
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        conditions = json.dumps(cancel_conditions or [], ensure_ascii=False, allow_nan=False)
        with database_connection() as conn:
            cursor = conn.execute('''INSERT INTO pending_actions
                (action_type,topic,payload,earliest_at,expires_at,created_reason,
                 cancel_conditions,status,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,'pending',?,?)''',
                (action_type, topic, encoded, earliest.isoformat(), expires.isoformat(),
                 str(created_reason), conditions, now.isoformat(), now.isoformat()))
            return cursor.lastrowid

    schedule = create

    def expire(self):
        now = self.clock.now()
        count = 0
        with database_connection() as conn:
            for row in conn.execute("SELECT * FROM pending_actions WHERE status IN ('pending','deferred')").fetchall():
                earliest = parse_timestamp(row['earliest_at'])
                expires = parse_timestamp(row['expires_at'])
                # Corrupt timestamps fail closed: never eligible.
                if earliest is None or expires is None or expires <= earliest or expires <= now:
                    count += conn.execute("UPDATE pending_actions SET status='expired',updated_at=? WHERE id=?",
                                          (now.isoformat(), row['id'])).rowcount
        return count

    def list_due_actions(self):
        self.expire()
        now = self.clock.now()
        with database_connection() as conn:
            rows = conn.execute("SELECT * FROM pending_actions WHERE status IN ('pending','deferred')").fetchall()
        due = []
        for row in rows:
            earliest, expires = parse_timestamp(row['earliest_at']), parse_timestamp(row['expires_at'])
            if earliest is not None and expires is not None and earliest <= now < expires:
                due.append(dict(row))
        return sorted(due, key=lambda row: (timestamp(row['earliest_at']), row['id']))

    get_due_actions = list_due_actions

    def _transition(self, action_id, status, earliest_at=None):
        self.expire()
        now = self.clock.now()
        with database_connection() as conn:
            row = conn.execute('SELECT * FROM pending_actions WHERE id=?', (action_id,)).fetchone()
            if not row or row['status'] not in ACTIVE:
                return False
            earliest = row['earliest_at']
            if status == 'deferred':
                new_time = timestamp(earliest_at)
                if not now < new_time < timestamp(row['expires_at']) or new_time <= timestamp(earliest):
                    raise ValueError('Defer must move later, after now and before expiry')
                earliest = new_time.isoformat()
            conn.execute('UPDATE pending_actions SET status=?,earliest_at=?,updated_at=? WHERE id=?',
                         (status, earliest, now.isoformat(), action_id))
            return True

    def defer(self, action_id, earliest_at):
        return self._transition(action_id, 'deferred', earliest_at)

    def cancel(self, action_id):
        return self._transition(action_id, 'cancelled')

    def mark_completed(self, action_id):
        """Explicit external bookkeeping only; does not execute the action."""
        return self._transition(action_id, 'completed')


class ProactiveTimelineService(PendingActionRepository):
    def review(self, action_id, context, hook):
        """Re-read eligibility and invoke caller's latest-context policy; never send.

        Hook exceptions leave the action pending. No positive review token is
        persisted: a future V1.7 executor must reconsider again immediately.
        """
        due = {row['id']: row for row in self.list_due_actions()}
        if action_id not in due:
            return None
        now = self.clock.now().isoformat()
        with database_connection() as conn:
            conn.execute('''UPDATE pending_actions SET last_reviewed_at=?,
                review_count=review_count+1,updated_at=? WHERE id=?''', (now, now, action_id))
        decision = hook(dict(due[action_id]), context)
        if not isinstance(decision, ReviewDecision) or decision.outcome not in ('eligible', 'defer', 'cancel'):
            raise ValueError('Invalid review decision')
        # The hook may take time or cancel the action: check state again.
        if action_id not in {row['id'] for row in self.list_due_actions()}:
            return None
        if decision.outcome == 'defer':
            self.defer(action_id, decision.earliest_at)
        elif decision.outcome == 'cancel':
            self.cancel(action_id)
        return decision

    reconsider = review
