"""Opt-in category-aware memory writes; legacy categories remain unchanged."""
import json
from datetime import timedelta
from foundation_time import foundation_clock, timestamp, number
from time_context import parse_timestamp
from contextlib import contextmanager

@contextmanager
def database_connection():
    from memory import database_connection as connect
    with connect() as conn:
        yield conn

def _normalize_category(value):
    from memory import _normalize_category as normalize
    return normalize(value)

CATEGORIES = {'explicit_fact', 'preference', 'temporary_state_or_plan',
              'inferred_trait_or_value', 'sensitive_inference'}


def migrate(conn):
    columns = {row['name'] for row in conn.execute('PRAGMA table_info(memories)')}
    additions = {'retention_category': "TEXT NOT NULL DEFAULT 'explicit_fact'",
                 'confidence': 'REAL', 'expires_at': 'TEXT',
                 'retention_status': "TEXT NOT NULL DEFAULT 'active'",
                 'metadata': "TEXT NOT NULL DEFAULT '{}'"}
    for name, declaration in additions.items():
        if name not in columns:
            conn.execute(f'ALTER TABLE memories ADD COLUMN {name} {declaration}')
    # Historical records are preserved; no speculative reclassification.


class MemoryRetentionService:
    def __init__(self, clock=None):
        self.clock = clock or foundation_clock

    def save(self, content, retention_category, *, category='other', confidence=None,
             ttl_seconds=None, expires_at=None, metadata=None):
        if retention_category not in CATEGORIES:
            raise ValueError('Unknown retention category')
        # Abstain before any write, including metadata or candidate storage.
        if retention_category == 'sensitive_inference':
            return None
        content = str(content or '').strip()
        if not content:
            return None
        confidence = None if confidence is None else number(confidence, 0, 1)
        now = self.clock.now()
        if ttl_seconds is not None and expires_at is not None:
            raise ValueError('Use TTL or expires_at, not both')
        expiry = timestamp(expires_at) if expires_at is not None else None
        if ttl_seconds is not None:
            expiry = now + timedelta(seconds=number(ttl_seconds, 0.000001, 315360000))
        if retention_category == 'temporary_state_or_plan' and expiry is None:
            raise ValueError('Temporary memory requires expiry')
        if expiry is not None and expiry <= now:
            raise ValueError('Expiry must be in the future')
        status = 'candidate' if retention_category == 'inferred_trait_or_value' else 'active'
        encoded = json.dumps(metadata or {}, ensure_ascii=False, allow_nan=False)
        with database_connection() as conn:
            cursor = conn.execute('''INSERT OR IGNORE INTO memories
                (content,category,created_at,updated_at,retention_category,
                 confidence,expires_at,retention_status,metadata) VALUES(?,?,?,?,?,?,?,?,?)''',
                (content, _normalize_category(category), now.isoformat(), now.isoformat(),
                 retention_category, confidence, expiry.isoformat() if expiry else None, status, encoded))
            return cursor.lastrowid if cursor.rowcount else None

    def list(self, include_candidates=False):
        now = self.clock.now()
        with database_connection() as conn:
            rows = conn.execute('SELECT * FROM memories ORDER BY id').fetchall()
            result = []
            for row in rows:
                row = dict(row)
                expiry = parse_timestamp(row['expires_at'])
                if row['expires_at'] is not None and (expiry is None or expiry <= now):
                    conn.execute("UPDATE memories SET retention_status='expired',updated_at=? WHERE id=?",
                                 (now.isoformat(), row['id']))
                    continue
                if row['retention_category'] == 'sensitive_inference':
                    continue
                if row['retention_status'] == 'active' or (include_candidates and row['retention_status'] == 'candidate'):
                    result.append(row)
            return result


def classify_automatic_memory(content, category):
    """Conservative rules for the legacy analyzer; not a psychological classifier.

    The typed service is authoritative for callers with known provenance.
    Sensitive/trait cues are deliberately blocked from legacy active writes.
    """
    text = str(content)
    if any(cue in text for cue in ('抑郁', '精神疾病', '性取向', '政治倾向', '宗教信仰', '创伤', '心理疾病')):
        return 'sensitive_inference'
    if any(cue in text for cue in ('可能', '推测', '似乎', '性格', '价值观', '内向', '外向', '孤独', '人格')):
        return 'inferred_trait_or_value'
    if any(cue in text for cue in ('今天', '明天', '今晚', '本周', '最近', '暂时', '计划')):
        return 'temporary_state_or_plan'
    return 'preference' if category == 'preference' else 'explicit_fact'
