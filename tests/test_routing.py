from types import SimpleNamespace

import anthropic
import pytest

from commerce_support_demo.data import load_synthetic_data
from commerce_support_demo.models import RerankDecision, RouteCandidate
from commerce_support_demo.routing.rerankers import ClaudeReranker
from commerce_support_demo.routing.retriever import IntentRetriever


def test_synthetic_manifest_and_records_are_explicitly_marked(settings):
    data = load_synthetic_data(settings.data_dir)
    assert data["manifest"]["is_synthetic"] is True
    assert all(record["is_synthetic"] for record in data["orders"])


def test_order_lookup_is_recalled_in_top_three(settings):
    retriever = IntentRetriever(load_synthetic_data(settings.data_dir)["intent_catalog"])
    candidates = retriever.retrieve("Where is order ORD-DEMO-1001?", {"order_id": "ORD-DEMO-1001"})
    assert "order_status" in {candidate.intent for candidate in candidates}


def test_address_change_requires_both_order_and_new_address(settings):
    retriever = IntentRetriever(load_synthetic_data(settings.data_dir)["intent_catalog"])
    candidates = retriever.retrieve("修改收货地址", {})
    assert candidates[0].intent == "address_change"


def test_explicit_logistics_signal_outranks_generic_order_phrase(settings):
    retriever = IntentRetriever(load_synthetic_data(settings.data_dir)["intent_catalog"])
    candidates = retriever.retrieve("查订单 ORD-DEMO-1001 的物流", {"order_id": "ORD-DEMO-1001"})
    assert candidates[0].intent == "shipment_tracking"


@pytest.mark.asyncio
async def test_claude_reranker_uses_beta_structured_output(monkeypatch):
    captured = {}

    class FakeMessages:
        async def parse(self, **kwargs):
            captured["request"] = kwargs
            return SimpleNamespace(
                stop_reason="end_turn",
                parsed_output=RerankDecision(
                    selected_intent="order_status",
                    decision="select",
                    confidence=0.9,
                    reason_code="TEST_DECISION",
                ),
            )

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.beta = SimpleNamespace(messages=FakeMessages())

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

    monkeypatch.setattr(anthropic, "AsyncAnthropic", FakeClient)
    reranker = ClaudeReranker("claude-opus-5", 15)
    decision = await reranker.decide(
        message="Where is my order?",
        locale="en-SG",
        candidates=[RouteCandidate(intent="order_status", score=0.8)],
        safe_slots={"order_id": "ORD-DEMO-1001"},
    )

    assert decision.selected_intent == "order_status"
    assert captured["client"]["timeout"] == 15
    assert captured["request"]["output_format"] is RerankDecision
    assert captured["request"]["betas"] == ["server-side-fallback-2026-07-01"]
    assert captured["request"]["fallbacks"] == "default"
