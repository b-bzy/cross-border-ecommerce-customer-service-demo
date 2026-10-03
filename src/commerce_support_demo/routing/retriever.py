from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from commerce_support_demo.models import RouteCandidate

ORDER_ID_PATTERN = re.compile(r"\bORD-DEMO-\d{4}\b", re.IGNORECASE)


@dataclass(frozen=True)
class IntentDefinition:
    intent: str
    route: str
    operation: str | None
    required_slots: tuple[str, ...]
    write: bool
    examples: tuple[str, ...]


class IntentRetriever:
    def __init__(self, catalog: list[dict[str, Any]]) -> None:
        self._intents = [
            IntentDefinition(
                intent=item["intent"],
                route=item["route"],
                operation=item["operation"],
                required_slots=tuple(item["required_slots"]),
                write=item["write"],
                examples=tuple(item["examples"]),
            )
            for item in catalog
        ]
        self._by_intent = {item.intent: item for item in self._intents}

    @staticmethod
    def normalize(text: str) -> str:
        return unicodedata.normalize("NFKC", text).casefold().strip()

    @staticmethod
    def extract_order_id(text: str) -> str | None:
        match = ORDER_ID_PATTERN.search(text)
        return match.group(0).upper() if match else None

    def definition(self, intent: str) -> IntentDefinition:
        return self._by_intent[intent]

    def retrieve(self, message: str, slots: dict[str, str], limit: int = 3) -> list[RouteCandidate]:
        normalized = self.normalize(message)
        has_order_id = bool(slots.get("order_id") or self.extract_order_id(message))
        has_shipment_exception = any(
            word in normalized
            for word in ("delay", "delayed", "stuck", "customs", "延误", "卡住", "清关")
        )
        has_shipment_signal = any(
            word in normalized
            for word in ("track", "tracking", "parcel", "package", "shipment", "物流", "包裹")
        )
        candidates: list[RouteCandidate] = []
        for definition in self._intents:
            signals: list[str] = []
            score = 0.0
            for example in definition.examples:
                phrase = self.normalize(example)
                if phrase and phrase in normalized:
                    score += 0.58
                    signals.append(example)
                else:
                    phrase_tokens = [
                        token for token in re.findall(r"[\w-]+", phrase) if len(token) > 2
                    ]
                    if phrase_tokens:
                        overlap = sum(token in normalized for token in phrase_tokens) / len(
                            phrase_tokens
                        )
                        if overlap >= 0.5:
                            score += 0.18 * overlap
                            signals.append(example)
            if has_order_id and "order_id" in definition.required_slots:
                score += 0.18
                signals.append("order_id")
            if definition.intent == "shipment_exception" and has_shipment_exception:
                score += 0.64
                signals.append("exception_signal")
            if definition.intent == "shipment_tracking" and has_shipment_signal:
                score += 0.64
                signals.append("shipment_signal")
            if definition.intent == "human_handoff" and any(
                word in normalized for word in ("human", "agent", "人工", "投诉")
            ):
                score += 0.35
                signals.append("handoff_signal")
            candidates.append(
                RouteCandidate(
                    intent=definition.intent, score=min(score, 1.0), matched_signals=signals
                )
            )
        return sorted(candidates, key=lambda candidate: candidate.score, reverse=True)[:limit]
