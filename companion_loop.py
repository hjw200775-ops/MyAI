"""Deterministic companionship evaluation. No sender or model dependency."""
import logging
from dataclasses import dataclass, asdict
from datetime import timedelta
from threading import RLock
from foundation_time import foundation_clock
from time_context import default_time_service, elapsed, parse_timestamp
from affect_state import ShortTermAffect
from proactive_timeline import ProactiveTimelineService, ReviewDecision, database_connection
from user_activity import WindowsActivityProvider, ActivityState

@dataclass(frozen=True)
class CompanionConfig:
    tick_seconds: int = 300
    active_seconds: int = 60
    recent_chat_seconds: int = 600
    quiet_chat_seconds: int = 3600
    cooldown_seconds: int = 7200
    delay_seconds: int = 600
    expiry_seconds: int = 3600
    evening_hour: int = 22
    morning_hour: int = 5
    affect_confidence: float = 0.5
    affect_valence: float = -0.4

    def __post_init__(self):
        from foundation_time import number
        for field in ('tick_seconds', 'active_seconds', 'recent_chat_seconds',
                      'quiet_chat_seconds', 'cooldown_seconds', 'delay_seconds', 'expiry_seconds'):
            number(getattr(self, field), 1, 315360000)
        number(self.evening_hour, 0, 23)
        number(self.morning_hour, 0, 23)
        number(self.affect_confidence, 0, 1)
        number(self.affect_valence, -1, 1)
        if self.delay_seconds >= self.expiry_seconds:
            raise ValueError('Delay must precede expiry')

@dataclass(frozen=True)
class ActionCandidate:
    action_type: str
    reason: str

class DecisionEngine:
    def __init__(self, config):
        self.config = config

    def decide(self, temporal, activity, affect, now):
        silence = elapsed(now, temporal.last_interaction)
        if not activity.available or silence is None or silence < self.config.quiet_chat_seconds:
            return None
        if now.hour >= self.config.evening_hour or now.hour < self.config.morning_hour:
            return ActionCandidate('rest_reminder', 'late_local_time')
        if affect.confidence >= self.config.affect_confidence and affect.valence <= self.config.affect_valence:
            return ActionCandidate('gentle_checkin', 'short_term_affect')
        return None

class ActionReviewer:
    def __init__(self, config):
        self.config = config

    def decide(self, action, temporal, activity, now, cooling=False):
        expires = parse_timestamp(action['expires_at'])
        if expires is None or now >= expires:
            return 'EXPIRE'
        silence = elapsed(now, temporal.last_interaction)
        if silence is not None and silence < self.config.recent_chat_seconds:
            return 'CANCEL'
        if cooling:
            return 'CANCEL'
        if silence is None or not activity.available or activity.busy or activity.user_active:
            return 'DEFER' if now + timedelta(seconds=self.config.delay_seconds) < expires else 'CANCEL'
        if action['action_type'] == 'rest_reminder' and self.config.morning_hour <= now.hour < self.config.evening_hour:
            return 'CANCEL'
        return 'APPROVE'

class CompanionLoop:
    def __init__(self, clock=None, time_service=None, activity_provider=None, affect=None, config=None):
        self.clock = clock or foundation_clock
        self.time_service = time_service or default_time_service
        self.config = config or CompanionConfig()
        self.activity_provider = activity_provider or WindowsActivityProvider(self.config.active_seconds)
        self.affect = affect or ShortTermAffect(self.clock)
        self.timeline = ProactiveTimelineService(self.clock)
        self.engine = DecisionEngine(self.config)
        self.reviewer = ActionReviewer(self.config)
        self._lock = RLock()
        self._snapshot = {}

    def _cooling(self, action_type, now, exclude=None):
        with database_connection() as conn:
            rows = conn.execute('SELECT * FROM pending_actions WHERE action_type=?', (action_type,)).fetchall()
        for row in rows:
            if row['id'] == exclude:
                continue
            created = parse_timestamp(row['updated_at'] if row['status'] not in ('pending', 'deferred') else row['created_at'])
            if row['status'] in ('pending', 'deferred'):
                return True
            if created is None or elapsed(now, created) < self.config.cooldown_seconds:
                return True
        return False

    def tick(self, conversation_id=None, user_busy=False, provider=None):
        with self._lock:
            now = self.clock.now()
            temporal = self.time_service.capture(conversation_id, establish_session=False)
            try:
                activity = self.activity_provider.read(now)
                if not isinstance(activity, ActivityState):
                    activity = ActivityState()
            except Exception:
                activity = ActivityState()
            if user_busy:
                activity = ActivityState(activity.idle_duration, activity.last_input_time,
                                         activity.active_window, activity.user_active, True, activity.available)
            affect = self.affect.get()
            expired = self.timeline.expire()
            reviews = []
            for action in self.timeline.list_due_actions():
                outcome = self.reviewer.decide(action, temporal, activity, now,
                           self._cooling(action['action_type'], now, action['id']))
                # Existing eligible semantics are preserved; reviewed_ready is diagnostic only.
                decision = ReviewDecision('eligible' if outcome == 'APPROVE' else
                            'defer' if outcome == 'DEFER' else 'cancel',
                            now + timedelta(seconds=self.config.delay_seconds))
                result = self.timeline.review(action['id'], None, lambda row, ctx: decision)
                if result is not None:
                    with database_connection() as conn:
                        conn.execute('UPDATE pending_actions SET reviewed_ready=?,review_outcome=? WHERE id=?',
                                     (int(outcome == 'APPROVE'), outcome, action['id']))
                    reviews.append({'id': action['id'], 'outcome': outcome})
            candidate = self.engine.decide(temporal, activity, affect, now)
            created = None
            if candidate and not self._cooling(candidate.action_type, now):
                created = self.timeline.create(candidate.action_type, 'companion',
                    now + timedelta(seconds=self.config.delay_seconds),
                    now + timedelta(seconds=self.config.expiry_seconds),
                    payload={'source': 'companion_loop'}, created_reason=candidate.reason)
            with database_connection() as conn:
                count = conn.execute("SELECT COUNT(*) FROM pending_actions WHERE status IN ('pending','deferred')").fetchone()[0]
            self._snapshot = {'local_time': temporal.current_datetime.isoformat(),
                'evaluation_time': now.isoformat(), 'activity': asdict(activity),
                'affect': asdict(affect), 'pending_count': count, 'provider': provider,
                'created_id': created, 'reviews': reviews, 'expired_count': expired}
            logging.getLogger(__name__).debug('companion tick pending=%s created=%s expired=%s', count, created, expired)
            return self.debug_snapshot()

    def debug_snapshot(self):
        import copy
        with self._lock:
            return copy.deepcopy(self._snapshot)
