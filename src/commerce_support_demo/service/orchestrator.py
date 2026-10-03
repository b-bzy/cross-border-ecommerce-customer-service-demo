from __future__ import annotations

from typing import Any
from uuid import uuid4

from commerce_support_demo.mcp.gateway import CommerceGateway
from commerce_support_demo.models import (
    ChatRequest,
    ChatResponse,
    ConfirmActionRequest,
    RouteDecision,
    ToolEvent,
)
from commerce_support_demo.routing.retriever import IntentRetriever
from commerce_support_demo.routing.service import RoutingService
from commerce_support_demo.service.actions import ActionStore
from commerce_support_demo.service.commerce import CommerceError
from commerce_support_demo.service.session import SessionStore


class ConversationOrchestrator:
    def __init__(
        self,
        *,
        retriever: IntentRetriever,
        router: RoutingService,
        gateway: CommerceGateway,
        sessions: SessionStore,
        actions: ActionStore,
    ) -> None:
        self._retriever = retriever
        self._router = router
        self._gateway = gateway
        self._sessions = sessions
        self._actions = actions

    @staticmethod
    def _is_zh(locale: str) -> bool:
        return locale.startswith("zh")

    @staticmethod
    def _source_ids(*payloads: dict[str, Any]) -> list[str]:
        return [payload["source_id"] for payload in payloads if payload.get("source_id")]

    def _reply(self, locale: str, english: str, chinese: str) -> str:
        return chinese if self._is_zh(locale) else english

    def _clarification(
        self, request_id: str, conversation_id: str, locale: str, route: RouteDecision
    ) -> ChatResponse:
        missing = ", ".join(route.missing_slots)
        return ChatResponse(
            request_id=request_id,
            conversation_id=conversation_id,
            message=self._reply(
                locale,
                f"I need {missing} before I can continue with this synthetic Demo request.",
                f"继续处理这个合成 Demo 请求前，我需要补充：{missing}。",
            ),
            route=route,
        )

    async def chat(self, conversation_id: str, request: ChatRequest) -> ChatResponse:
        request_id = f"req_{uuid4().hex[:12]}"
        state = self._sessions.get(conversation_id, request.customer_id, request.locale)
        normalized = self._retriever.normalize(request.message)
        if normalized in {"confirm", "yes", "确认", "确定", "同意"}:
            route = RouteDecision(
                intent="human_handoff",
                route="HANDOFF",
                stage="confirmation_boundary",
                confidence=1.0,
                candidates=[],
                reason_code="EXPLICIT_CONFIRMATION_ENDPOINT_REQUIRED",
            )
            return ChatResponse(
                request_id=request_id,
                conversation_id=conversation_id,
                message=self._reply(
                    request.locale,
                    (
                        "For safety, chat messages never execute writes. Confirm the displayed "
                        "pending action through its confirmation endpoint."
                    ),
                    "为安全起见，聊天消息不会执行写操作。请通过待确认操作显示的确认接口完成确认。",
                ),
                route=route,
            )

        safe_slots = dict(request.slots)
        extracted_order_id = self._retriever.extract_order_id(request.message)
        if extracted_order_id:
            safe_slots["order_id"] = extracted_order_id
        elif state.active_order_id:
            safe_slots.setdefault("order_id", state.active_order_id)
        route = await self._router.route(request.message, request.locale, safe_slots)
        if safe_slots.get("order_id"):
            state.active_order_id = safe_slots["order_id"]
        state.last_intent = route.intent

        if route.missing_slots:
            return self._clarification(request_id, conversation_id, request.locale, route)
        if route.route == "CHITCHAT":
            return ChatResponse(
                request_id=request_id,
                conversation_id=conversation_id,
                message=self._reply(
                    request.locale,
                    (
                        "I can help with this Demo's synthetic orders, shipments, returns, "
                        "refunds, and human handoff."
                    ),
                    "我可以协助处理本 Demo 中的合成订单、物流、退货、退款和人工转接问题。",
                ),
                route=route,
            )
        if route.route == "HANDOFF":
            handoff = await self._gateway.call(
                "handoffs_create",
                customer_id=request.customer_id,
                category="buyer_requested_handoff",
                summary=request.message,
            )
            return ChatResponse(
                request_id=request_id,
                conversation_id=conversation_id,
                message=self._reply(
                    request.locale,
                    "I created a synthetic human-handoff ticket for this Demo.",
                    "我已为此合成 Demo 创建人工转接工单。",
                ),
                route=route,
                sources=self._source_ids(handoff),
                tool_events=[
                    ToolEvent(
                        tool_name="handoffs_create",
                        operation="handoff",
                        status="success",
                        source_ids=self._source_ids(handoff),
                    )
                ],
                handoff={
                    "ticket_id": handoff["ticket"]["ticket_id"],
                    "reason": route.reason_code or "HANDOFF",
                },
            )
        return await self._handle_task(request_id, conversation_id, request, route, safe_slots)

    async def _handle_task(
        self,
        request_id: str,
        conversation_id: str,
        request: ChatRequest,
        route: RouteDecision,
        safe_slots: dict[str, str],
    ) -> ChatResponse:
        order_id = safe_slots.get("order_id")
        if route.intent == "customs_duties":
            policy = await self._gateway.call("policies_get", topic="customs_duties", market="DE")
            return ChatResponse(
                request_id=request_id,
                conversation_id=conversation_id,
                message=policy["policy"]["facts"]["message"],
                route=route,
                sources=self._source_ids(policy),
                tool_events=[
                    ToolEvent(
                        tool_name="policies_get",
                        operation="read",
                        status="success",
                        source_ids=self._source_ids(policy),
                    )
                ],
            )
        if not order_id:
            route.missing_slots = ["order_id"]
            return self._clarification(request_id, conversation_id, request.locale, route)
        if route.intent == "order_status":
            result = await self._gateway.call(
                "orders_get", order_id=order_id, customer_id=request.customer_id
            )
            order = result["order"]
            return ChatResponse(
                request_id=request_id,
                conversation_id=conversation_id,
                message=self._reply(
                    request.locale,
                    (
                        f"Synthetic order {order_id} is {order['status']} "
                        f"(version {order['version']})."
                    ),
                    (
                        f"合成订单 {order_id} 当前状态为 {order['status']}"
                        f"（版本 {order['version']}）。"
                    ),
                ),
                route=route,
                sources=self._source_ids(result),
                tool_events=[
                    ToolEvent(
                        tool_name="orders_get",
                        operation="read",
                        status="success",
                        source_ids=self._source_ids(result),
                    )
                ],
            )
        if route.intent in {"shipment_tracking", "shipment_exception"}:
            result = await self._gateway.call(
                "shipments_track", order_id=order_id, customer_id=request.customer_id
            )
            shipment = result["shipment"]
            detail = (
                shipment["status"]
                if route.intent == "shipment_tracking"
                else f"{shipment['status']} — Demo escalation may be needed"
            )
            return ChatResponse(
                request_id=request_id,
                conversation_id=conversation_id,
                message=self._reply(
                    request.locale,
                    (
                        f"Synthetic shipment {shipment['shipment_id']} is {detail}. "
                        f"ETA: {shipment['eta'] or 'not available'}."
                    ),
                    (
                        f"合成物流单 {shipment['shipment_id']} 当前为 {detail}，"
                        f"预计送达：{shipment['eta'] or '暂无'}。"
                    ),
                ),
                route=route,
                sources=self._source_ids(result),
                tool_events=[
                    ToolEvent(
                        tool_name="shipments_track",
                        operation="read",
                        status="success",
                        source_ids=self._source_ids(result),
                    )
                ],
            )
        if route.intent == "refund_status":
            result = await self._gateway.call(
                "refunds_get", order_id=order_id, customer_id=request.customer_id
            )
            refund = result["refund"]
            return ChatResponse(
                request_id=request_id,
                conversation_id=conversation_id,
                message=self._reply(
                    request.locale,
                    (
                        f"Synthetic refund {refund['refund_id']} is {refund['status']}; "
                        f"expected completion: {refund['expected_completion']}."
                    ),
                    (
                        f"合成退款 {refund['refund_id']} 当前为 {refund['status']}，"
                        f"预计完成时间：{refund['expected_completion']}。"
                    ),
                ),
                route=route,
                sources=self._source_ids(result),
                tool_events=[
                    ToolEvent(
                        tool_name="refunds_get",
                        operation="read",
                        status="success",
                        source_ids=self._source_ids(result),
                    )
                ],
            )
        if route.intent == "return_eligibility":
            result = await self._gateway.call(
                "returns_check_eligibility", order_id=order_id, customer_id=request.customer_id
            )
            eligibility = "eligible" if result["eligible"] else "not eligible"
            return ChatResponse(
                request_id=request_id,
                conversation_id=conversation_id,
                message=self._reply(
                    request.locale,
                    f"This synthetic order is {eligibility} for return under the Demo policy.",
                    (
                        "根据 Demo 政策，该合成订单当前"
                        f"{'符合' if result['eligible'] else '不符合'}退货条件。"
                    ),
                ),
                route=route,
                sources=self._source_ids(result),
                tool_events=[
                    ToolEvent(
                        tool_name="returns_check_eligibility",
                        operation="read",
                        status="success",
                        source_ids=self._source_ids(result),
                    )
                ],
            )
        if route.intent in {"address_change", "delivery_urge"}:
            return await self._prepare_write(
                request_id, conversation_id, request, route, safe_slots
            )
        raise CommerceError(
            "unsupported_intent", "The selected Demo intent has no operation mapping.", 500
        )

    async def _prepare_write(
        self,
        request_id: str,
        conversation_id: str,
        request: ChatRequest,
        route: RouteDecision,
        safe_slots: dict[str, str],
    ) -> ChatResponse:
        order_id = safe_slots["order_id"]
        order_result = await self._gateway.call(
            "orders_get", order_id=order_id, customer_id=request.customer_id
        )
        order = order_result["order"]
        if route.intent == "address_change":
            new_address = safe_slots.get("new_address")
            if not new_address:
                route.missing_slots = ["new_address"]
                return self._clarification(request_id, conversation_id, request.locale, route)
            tool_name = "orders_update_address"
            arguments = {"order_id": order_id, "new_address": new_address}
            preview = self._reply(
                request.locale,
                f"Preview: change synthetic order {order_id} delivery address to {new_address}.",
                f"预览：将合成订单 {order_id} 的收货地址改为 {new_address}。",
            )
        else:
            tool_name = "tickets_create_delivery_urge"
            arguments = {
                "order_id": order_id,
                "reason": safe_slots.get("reason", "buyer requested delivery follow-up"),
            }
            preview = self._reply(
                request.locale,
                f"Preview: create a synthetic delivery-urge ticket for order {order_id}.",
                f"预览：为合成订单 {order_id} 创建催发货服务单。",
            )
        action = self._actions.prepare(
            conversation_id=conversation_id,
            customer_id=request.customer_id,
            tool_name=tool_name,
            arguments=arguments,
            resource_version=order["version"],
        )
        return ChatResponse(
            request_id=request_id,
            conversation_id=conversation_id,
            message=self._reply(
                request.locale,
                (
                    f"{preview} No change has been made. Confirm it with the action endpoint "
                    f"before {action.expires_at.isoformat()}."
                ),
                (
                    f"{preview} 尚未执行任何修改。请在 {action.expires_at.isoformat()} 前"
                    "通过操作确认接口确认。"
                ),
            ),
            route=route,
            sources=self._source_ids(order_result),
            tool_events=[
                ToolEvent(
                    tool_name="orders_get",
                    operation="read",
                    status="success",
                    source_ids=self._source_ids(order_result),
                )
            ],
            pending_action=action,
        )

    async def confirm(self, action_id: str, request: ConfirmActionRequest) -> dict[str, Any]:
        action = self._actions.claim(
            action_id, request.customer_id, request.conversation_id, request.action_digest
        )
        if action.status == "executed":
            return {
                "action": action.model_dump(mode="json"),
                "result": action.result,
                "idempotent_replay": True,
            }
        try:
            current = await self._gateway.call(
                "orders_get", order_id=action.arguments["order_id"], customer_id=action.customer_id
            )
            if current["resource_version"] != action.resource_version:
                raise CommerceError(
                    "stale_resource",
                    "The order changed after the preview. Prepare a new request.",
                    409,
                )
            capability, capability_expires_at = self._actions.capability(action)
            result = await self._gateway.call(
                action.tool_name,
                **action.arguments,
                customer_id=action.customer_id,
                action_id=action.action_id,
                expected_version=action.resource_version,
                idempotency_key=action.idempotency_key,
                capability=capability,
                capability_expires_at=capability_expires_at,
            )
        except Exception:
            self._actions.fail(action)
            raise
        completed = self._actions.complete(action, result)
        return {
            "action": completed.model_dump(mode="json"),
            "result": result,
            "idempotent_replay": False,
        }

    def cancel(self, action_id: str, customer_id: str, conversation_id: str) -> dict[str, Any]:
        action = self._actions.cancel(action_id, customer_id, conversation_id)
        return {"action": action.model_dump(mode="json")}

    def action(self, action_id: str, customer_id: str, conversation_id: str) -> dict[str, Any]:
        action = self._actions.get(action_id, customer_id, conversation_id)
        return {"action": action.model_dump(mode="json")}
