from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RouteCandidate(StrictModel):
    intent: str
    score: float = Field(ge=0, le=1)
    matched_signals: list[str] = Field(default_factory=list)


class RouteDecision(StrictModel):
    intent: str
    route: Literal["TASK", "FAQ", "CHITCHAT", "HANDOFF"]
    stage: str
    confidence: float = Field(ge=0, le=1)
    candidates: list[RouteCandidate]
    missing_slots: list[str] = Field(default_factory=list)
    reason_code: str | None = None


class RerankDecision(StrictModel):
    selected_intent: str
    decision: Literal["select", "clarify", "handoff"]
    confidence: float = Field(ge=0, le=1)
    missing_slots: list[str] = Field(default_factory=list)
    reason_code: str


class ToolEvent(StrictModel):
    tool_name: str
    operation: Literal["read", "write", "handoff"]
    status: Literal["success", "pending", "error"]
    source_ids: list[str] = Field(default_factory=list)


class PendingAction(StrictModel):
    action_id: str
    conversation_id: str
    customer_id: str
    tool_name: str
    arguments: dict[str, Any]
    resource_version: int
    action_digest: str
    expires_at: datetime
    status: Literal["pending", "executing", "executed", "cancelled", "expired", "failed"]
    idempotency_key: str
    result: dict[str, Any] | None = None


class ChatRequest(StrictModel):
    customer_id: str = Field(pattern=r"^CUST-DEMO-\d{3}$")
    locale: Literal["zh-CN", "en-SG", "en-US"] = "en-SG"
    message: str = Field(min_length=1, max_length=1000)
    slots: dict[str, str] = Field(default_factory=dict)

    @field_validator("slots")
    @classmethod
    def validate_slots(cls, slots: dict[str, str]) -> dict[str, str]:
        limits = {"order_id": 13, "new_address": 300, "reason": 300}
        unknown = set(slots) - limits.keys()
        if unknown:
            raise ValueError(f"Unsupported slot keys: {', '.join(sorted(unknown))}")
        normalized = dict(slots)
        if order_id := normalized.get("order_id"):
            normalized["order_id"] = order_id.upper()
            if re.fullmatch(r"ORD-DEMO-\d{4}", normalized["order_id"]) is None:
                raise ValueError("order_id must use the synthetic ORD-DEMO-#### format")
        for name, value in normalized.items():
            if not value.strip() or len(value) > limits[name]:
                raise ValueError(f"{name} must contain 1 to {limits[name]} characters")
        return normalized


class ChatResponse(StrictModel):
    request_id: str
    conversation_id: str
    message: str
    route: RouteDecision
    sources: list[str] = Field(default_factory=list)
    tool_events: list[ToolEvent] = Field(default_factory=list)
    pending_action: PendingAction | None = None
    handoff: dict[str, str] | None = None


class ConfirmActionRequest(StrictModel):
    customer_id: str = Field(pattern=r"^CUST-DEMO-\d{3}$")
    conversation_id: str = Field(min_length=1, max_length=100)
    decision: Literal["confirm"]
    action_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class CancelActionRequest(StrictModel):
    customer_id: str = Field(pattern=r"^CUST-DEMO-\d{3}$")
    conversation_id: str = Field(min_length=1, max_length=100)
