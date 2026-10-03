from __future__ import annotations

from commerce_support_demo.models import RouteDecision
from commerce_support_demo.routing.rerankers import (
    ClaudeReranker,
    HeuristicReranker,
    RerankerUnavailable,
)
from commerce_support_demo.routing.retriever import IntentRetriever
from commerce_support_demo.settings import Settings


class RoutingService:
    def __init__(self, retriever: IntentRetriever, settings: Settings) -> None:
        self._retriever = retriever
        self._settings = settings
        self._offline = HeuristicReranker(retriever)
        self._claude = ClaudeReranker(settings.claude_model, settings.request_timeout_seconds)

    async def route(self, message: str, locale: str, safe_slots: dict[str, str]) -> RouteDecision:
        candidates = self._retriever.retrieve(message, safe_slots)
        top = candidates[0]
        second_score = candidates[1].score if len(candidates) > 1 else 0.0
        direct_route = top.score >= 0.76 and (top.score - second_score) >= 0.18
        should_use_claude = self._settings.router_mode == "live_always" or (
            self._settings.router_mode == "hybrid" and not direct_route
        )

        if should_use_claude:
            try:
                reranked = await self._claude.decide(
                    message=message,
                    locale=locale,
                    candidates=candidates,
                    safe_slots=safe_slots,
                )
                definition = self._retriever.definition(reranked.selected_intent)
                return RouteDecision(
                    intent=reranked.selected_intent,
                    route=definition.route,
                    stage="claude_rerank",
                    confidence=reranked.confidence,
                    candidates=candidates,
                    missing_slots=reranked.missing_slots,
                    reason_code=reranked.reason_code,
                )
            except RerankerUnavailable as error:
                if self._settings.router_mode == "live_always":
                    return RouteDecision(
                        intent="human_handoff",
                        route="HANDOFF",
                        stage="claude_unavailable",
                        confidence=0.0,
                        candidates=candidates,
                        reason_code=str(error),
                    )

        reranked = await self._offline.decide(
            message=message,
            locale=locale,
            candidates=candidates,
            safe_slots=safe_slots,
        )
        definition = self._retriever.definition(reranked.selected_intent)
        return RouteDecision(
            intent=reranked.selected_intent,
            route=definition.route,
            stage="stage1_direct" if direct_route else "offline_heuristic",
            confidence=reranked.confidence,
            candidates=candidates,
            missing_slots=reranked.missing_slots,
            reason_code=reranked.reason_code,
        )
