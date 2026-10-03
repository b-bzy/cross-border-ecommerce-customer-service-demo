from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

from commerce_support_demo.data import load_synthetic_data
from commerce_support_demo.mcp.gateway import InProcessCommerceGateway, MCPCommerceGateway
from commerce_support_demo.models import CancelActionRequest, ChatRequest, ConfirmActionRequest
from commerce_support_demo.routing.retriever import IntentRetriever
from commerce_support_demo.routing.service import RoutingService
from commerce_support_demo.service.actions import ActionStore
from commerce_support_demo.service.commerce import CommerceError, CommerceService
from commerce_support_demo.service.orchestrator import ConversationOrchestrator
from commerce_support_demo.service.session import SessionStore
from commerce_support_demo.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_environment()
    catalog = load_synthetic_data(settings.data_dir)["intent_catalog"]
    retriever = IntentRetriever(catalog)
    commerce_service = CommerceService(settings.data_dir, settings.mcp_signing_key)
    if settings.commerce_transport == "mcp":
        gateway = MCPCommerceGateway(settings)
    else:
        gateway = InProcessCommerceGateway(commerce_service)
    orchestrator = ConversationOrchestrator(
        retriever=retriever,
        router=RoutingService(retriever, settings),
        gateway=gateway,
        sessions=SessionStore(),
        actions=ActionStore(settings.mcp_signing_key, settings.action_ttl_seconds),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if isinstance(gateway, MCPCommerceGateway):
            await gateway.start()
        app.state.orchestrator = orchestrator
        app.state.settings = settings
        try:
            yield
        finally:
            await gateway.close()

    app = FastAPI(
        title="Synthetic Cross-Border Commerce Support Demo",
        version="0.1.0",
        description=(
            "Portfolio Demo using only synthetic data. It is not a Shopee production system."
        ),
        lifespan=lifespan,
    )

    @app.exception_handler(CommerceError)
    async def commerce_error_handler(_: Request, error: CommerceError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code, content={"code": error.code, "message": error.message}
        )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "service": "commerce-support-demo", "version": "0.1.0"}

    @app.get("/readyz")
    async def readyz() -> dict[str, str]:
        return {
            "status": "ready",
            "fixture_version": commerce_service.fixture_version,
            "commerce_transport": settings.commerce_transport,
            "router_mode": settings.router_mode,
            "claude_status": "disabled"
            if settings.router_mode == "offline"
            else "requested_not_probed",
        }

    @app.post("/v1/conversations/{conversation_id}/messages")
    async def message(conversation_id: str, body: ChatRequest):
        return await orchestrator.chat(conversation_id, body)

    @app.get("/v1/actions/{action_id}")
    async def get_action(
        action_id: str,
        customer_id: str = Query(pattern=r"^CUST-DEMO-\d{3}$"),
        conversation_id: str = Query(min_length=1, max_length=100),
    ) -> dict:
        return orchestrator.action(action_id, customer_id, conversation_id)

    @app.post("/v1/actions/{action_id}/confirm")
    async def confirm_action(action_id: str, body: ConfirmActionRequest) -> dict:
        return await orchestrator.confirm(action_id, body)

    @app.post("/v1/actions/{action_id}/cancel")
    async def cancel_action(action_id: str, body: CancelActionRequest) -> dict:
        return orchestrator.cancel(action_id, body.customer_id, body.conversation_id)

    return app


app = create_app()
