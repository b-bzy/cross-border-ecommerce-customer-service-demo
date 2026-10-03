from __future__ import annotations

import hashlib
import hmac
import json
from copy import deepcopy
from datetime import UTC, date, datetime
from typing import Any

from commerce_support_demo.data import load_synthetic_data


class CommerceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class CommerceService:
    """A process-local synthetic commerce backend shared by HTTP and MCP adapters."""

    def __init__(self, data_dir: Any, capability_secret: str) -> None:
        data = load_synthetic_data(data_dir)
        self.fixture_version = data["manifest"]["fixture_version"]
        self.orders = {record["order_id"]: record for record in data["orders"]}
        self.shipments = {record["order_id"]: record for record in data["shipments"]}
        self.refunds = {record["order_id"]: record for record in data["refunds"]}
        self.policies = data["policies"]
        self.tickets: dict[str, dict[str, Any]] = {}
        self._capability_secret = capability_secret.encode("utf-8")

    def _owned_order(self, order_id: str, customer_id: str) -> dict[str, Any]:
        order = self.orders.get(order_id)
        if order is None:
            raise CommerceError("not_found", "The synthetic order was not found.", 404)
        if order["customer_id"] != customer_id:
            raise CommerceError(
                "not_authorized", "This demo customer cannot access that order.", 403
            )
        return order

    def _verify_capability(
        self,
        *,
        action_id: str,
        customer_id: str,
        tool_name: str,
        frozen_arguments: dict[str, Any],
        expected_version: int,
        expires_at: int,
        capability: str,
    ) -> None:
        if datetime.now(UTC).timestamp() > expires_at:
            raise CommerceError(
                "confirmation_expired", "The confirmation capability has expired.", 410
            )
        payload = {
            "action_id": action_id,
            "arguments": frozen_arguments,
            "customer_id": customer_id,
            "expected_version": expected_version,
            "expires_at": expires_at,
            "tool_name": tool_name,
        }
        expected = hmac.new(
            self._capability_secret,
            canonical_json(payload).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(capability, expected):
            raise CommerceError("invalid_confirmation", "The write confirmation is invalid.", 403)

    def orders_get(self, order_id: str, customer_id: str) -> dict[str, Any]:
        order = deepcopy(self._owned_order(order_id, customer_id))
        return {
            "schema_version": "1.0",
            "source_id": order["source_id"],
            "resource_version": order["version"],
            "order": order,
        }

    def shipments_track(self, order_id: str, customer_id: str) -> dict[str, Any]:
        self._owned_order(order_id, customer_id)
        shipment = self.shipments.get(order_id)
        if shipment is None:
            raise CommerceError("not_found", "No synthetic shipment exists for this order.", 404)
        return {
            "schema_version": "1.0",
            "source_id": shipment["source_id"],
            "shipment": deepcopy(shipment),
        }

    def refunds_get(self, order_id: str, customer_id: str) -> dict[str, Any]:
        self._owned_order(order_id, customer_id)
        refund = self.refunds.get(order_id)
        if refund is None:
            raise CommerceError("not_found", "No synthetic refund exists for this order.", 404)
        return {
            "schema_version": "1.0",
            "source_id": refund["source_id"],
            "refund": deepcopy(refund),
        }

    def policies_get(self, topic: str, market: str = "global") -> dict[str, Any]:
        for policy in self.policies:
            if policy["topic"] == topic and policy["market"] in {market, "global"}:
                return {
                    "schema_version": "1.0",
                    "source_id": policy["source_id"],
                    "policy": deepcopy(policy),
                }
        raise CommerceError("not_found", "No synthetic policy matches this question.", 404)

    def returns_check_eligibility(self, order_id: str, customer_id: str) -> dict[str, Any]:
        order = self._owned_order(order_id, customer_id)
        policy = self.policies_get("return_eligibility")["policy"]
        if order["status"] != "delivered":
            return {
                "schema_version": "1.0",
                "source_id": policy["source_id"],
                "eligible": False,
                "reason": "The order has not been delivered in this synthetic scenario.",
            }
        delivered = date.fromisoformat(order["delivered_at"][:10])
        days_since_delivery = (date(2026, 10, 2) - delivered).days
        eligible = days_since_delivery <= policy["facts"]["return_window_days"]
        return {
            "schema_version": "1.0",
            "source_id": policy["source_id"],
            "eligible": eligible,
            "days_since_delivery": days_since_delivery,
            "return_window_days": policy["facts"]["return_window_days"],
        }

    def orders_update_address(
        self,
        *,
        order_id: str,
        customer_id: str,
        new_address: str,
        action_id: str,
        expected_version: int,
        idempotency_key: str,
        capability: str,
        capability_expires_at: int,
    ) -> dict[str, Any]:
        order = self._owned_order(order_id, customer_id)
        frozen_arguments = {"new_address": new_address, "order_id": order_id}
        self._verify_capability(
            action_id=action_id,
            customer_id=customer_id,
            tool_name="orders_update_address",
            frozen_arguments=frozen_arguments,
            expected_version=expected_version,
            expires_at=capability_expires_at,
            capability=capability,
        )
        if order["version"] != expected_version:
            raise CommerceError(
                "stale_resource", "The order changed after the preview. Prepare a new request.", 409
            )
        if order["status"] != "processing":
            raise CommerceError(
                "policy_denied",
                "This synthetic order is no longer eligible for an address change.",
                409,
            )
        order["address"] = new_address
        order["version"] += 1
        return {
            "schema_version": "1.0",
            "source_id": order["source_id"],
            "idempotency_key": idempotency_key,
            "resource_version": order["version"],
            "message": "Synthetic delivery address updated.",
        }

    def tickets_create_delivery_urge(
        self,
        *,
        order_id: str,
        customer_id: str,
        reason: str,
        action_id: str,
        expected_version: int,
        idempotency_key: str,
        capability: str,
        capability_expires_at: int,
    ) -> dict[str, Any]:
        order = self._owned_order(order_id, customer_id)
        frozen_arguments = {"order_id": order_id, "reason": reason}
        self._verify_capability(
            action_id=action_id,
            customer_id=customer_id,
            tool_name="tickets_create_delivery_urge",
            frozen_arguments=frozen_arguments,
            expected_version=expected_version,
            expires_at=capability_expires_at,
            capability=capability,
        )
        if order["version"] != expected_version:
            raise CommerceError(
                "stale_resource", "The order changed after the preview. Prepare a new request.", 409
            )
        if order["status"] not in {"processing", "in_transit"}:
            raise CommerceError(
                "policy_denied",
                "A delivery-urge request is not available for this order state.",
                409,
            )
        ticket_id = f"TICKET-DEMO-{len(self.tickets) + 1:04d}"
        ticket = {
            "ticket_id": ticket_id,
            "order_id": order_id,
            "category": "delivery_urge",
            "reason": reason,
            "source_id": f"ticket:{ticket_id}",
        }
        self.tickets[ticket_id] = ticket
        return {
            "schema_version": "1.0",
            "source_id": ticket["source_id"],
            "idempotency_key": idempotency_key,
            "ticket": deepcopy(ticket),
        }

    def handoffs_create(self, customer_id: str, summary: str, category: str) -> dict[str, Any]:
        ticket_id = f"HANDOFF-DEMO-{len(self.tickets) + 1:04d}"
        ticket = {
            "ticket_id": ticket_id,
            "customer_id": customer_id,
            "category": category,
            "summary": summary[:240],
            "source_id": f"handoff:{ticket_id}",
        }
        self.tickets[ticket_id] = ticket
        return {
            "schema_version": "1.0",
            "source_id": ticket["source_id"],
            "ticket": deepcopy(ticket),
        }
