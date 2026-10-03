from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta


@dataclass
class ConversationState:
    customer_id: str
    locale: str
    active_order_id: str | None = None
    last_intent: str | None = None
    expires_at: datetime = field(default_factory=lambda: datetime.now(UTC) + timedelta(minutes=20))


class SessionStore:
    def __init__(self, ttl_minutes: int = 20) -> None:
        self._ttl = timedelta(minutes=ttl_minutes)
        self._states: dict[str, ConversationState] = {}

    def get(self, conversation_id: str, customer_id: str, locale: str) -> ConversationState:
        state = self._states.get(conversation_id)
        now = datetime.now(UTC)
        if state is None or state.expires_at < now or state.customer_id != customer_id:
            state = ConversationState(customer_id=customer_id, locale=locale)
            self._states[conversation_id] = state
        state.locale = locale
        state.expires_at = now + self._ttl
        return state
