from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from commerce_support_demo.models import PendingAction
from commerce_support_demo.service.commerce import CommerceError, canonical_json


class ActionStore:
    def __init__(self, secret: str, ttl_seconds: int) -> None:
        self._secret = secret.encode("utf-8")
        self._ttl_seconds = ttl_seconds
        self._actions: dict[str, PendingAction] = {}

    def prepare(
        self,
        *,
        conversation_id: str,
        customer_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        resource_version: int,
    ) -> PendingAction:
        expires_at = datetime.now(UTC) + timedelta(seconds=self._ttl_seconds)
        action_id = f"ACT-DEMO-{uuid4().hex[:12].upper()}"
        digest_payload = {
            "action_id": action_id,
            "arguments": arguments,
            "conversation_id": conversation_id,
            "customer_id": customer_id,
            "expires_at": int(expires_at.timestamp()),
            "resource_version": resource_version,
            "tool_name": tool_name,
        }
        action = PendingAction(
            action_id=action_id,
            conversation_id=conversation_id,
            customer_id=customer_id,
            tool_name=tool_name,
            arguments=arguments,
            resource_version=resource_version,
            action_digest=hashlib.sha256(
                canonical_json(digest_payload).encode("utf-8")
            ).hexdigest(),
            expires_at=expires_at,
            status="pending",
            idempotency_key=f"idem-{uuid4().hex}",
        )
        self._actions[action.action_id] = action
        return action

    def get(self, action_id: str, customer_id: str, conversation_id: str) -> PendingAction:
        action = self._actions.get(action_id)
        if (
            action is None
            or action.customer_id != customer_id
            or action.conversation_id != conversation_id
        ):
            raise CommerceError("not_found", "The pending Demo action was not found.", 404)
        if action.status == "pending" and action.expires_at < datetime.now(UTC):
            action.status = "expired"
        return action

    def cancel(self, action_id: str, customer_id: str, conversation_id: str) -> PendingAction:
        action = self.get(action_id, customer_id, conversation_id)
        if action.status != "pending":
            raise CommerceError(
                "invalid_action_state", "Only a pending action can be cancelled.", 409
            )
        action.status = "cancelled"
        return action

    def claim(
        self, action_id: str, customer_id: str, conversation_id: str, digest: str
    ) -> PendingAction:
        action = self.get(action_id, customer_id, conversation_id)
        if action.status == "executed":
            return action
        if action.status == "expired":
            raise CommerceError("action_expired", "The pending action has expired.", 410)
        if action.status != "pending":
            raise CommerceError(
                "invalid_action_state", "This action can no longer be confirmed.", 409
            )
        if not hmac.compare_digest(action.action_digest, digest):
            raise CommerceError(
                "digest_mismatch", "The confirmation digest does not match the preview.", 409
            )
        action.status = "executing"
        return action

    def capability(self, action: PendingAction) -> tuple[str, int]:
        expires_at = int(action.expires_at.timestamp())
        payload = {
            "action_id": action.action_id,
            "arguments": action.arguments,
            "customer_id": action.customer_id,
            "expected_version": action.resource_version,
            "expires_at": expires_at,
            "tool_name": action.tool_name,
        }
        return (
            hmac.new(
                self._secret, canonical_json(payload).encode("utf-8"), hashlib.sha256
            ).hexdigest(),
            expires_at,
        )

    def complete(self, action: PendingAction, result: dict[str, Any]) -> PendingAction:
        action.status = "executed"
        action.result = result
        return action

    def fail(self, action: PendingAction) -> None:
        if action.status == "executing":
            action.status = "failed"
