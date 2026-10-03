from __future__ import annotations

from commerce_support_demo.service.commerce import CommerceService
from commerce_support_demo.settings import Settings


def build_server():
    from mcp.server.fastmcp import FastMCP

    settings = Settings.from_environment()
    service = CommerceService(settings.data_dir, settings.mcp_signing_key)
    mcp = FastMCP("synthetic-commerce-demo")

    @mcp.tool()
    def orders_get(order_id: str, customer_id: str) -> dict:
        """Read one synthetic order after customer ownership validation."""
        return service.orders_get(order_id, customer_id)

    @mcp.tool()
    def shipments_track(order_id: str, customer_id: str) -> dict:
        """Read synthetic shipment events and ETA for an owned order."""
        return service.shipments_track(order_id, customer_id)

    @mcp.tool()
    def refunds_get(order_id: str, customer_id: str) -> dict:
        """Read synthetic refund status for an owned order."""
        return service.refunds_get(order_id, customer_id)

    @mcp.tool()
    def policies_get(topic: str, market: str = "global") -> dict:
        """Read a versioned synthetic policy record."""
        return service.policies_get(topic, market)

    @mcp.tool()
    def returns_check_eligibility(order_id: str, customer_id: str) -> dict:
        """Evaluate synthetic return eligibility without creating a return."""
        return service.returns_check_eligibility(order_id, customer_id)

    @mcp.tool()
    def orders_update_address(
        order_id: str,
        customer_id: str,
        new_address: str,
        action_id: str,
        expected_version: int,
        idempotency_key: str,
        capability: str,
        capability_expires_at: int,
    ) -> dict:
        """Update an address only with a matching confirmation capability."""
        return service.orders_update_address(
            order_id=order_id,
            customer_id=customer_id,
            new_address=new_address,
            action_id=action_id,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            capability=capability,
            capability_expires_at=capability_expires_at,
        )

    @mcp.tool()
    def tickets_create_delivery_urge(
        order_id: str,
        customer_id: str,
        reason: str,
        action_id: str,
        expected_version: int,
        idempotency_key: str,
        capability: str,
        capability_expires_at: int,
    ) -> dict:
        """Create a synthetic delivery-urge ticket with a confirmation capability."""
        return service.tickets_create_delivery_urge(
            order_id=order_id,
            customer_id=customer_id,
            reason=reason,
            action_id=action_id,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            capability=capability,
            capability_expires_at=capability_expires_at,
        )

    @mcp.tool()
    def handoffs_create(customer_id: str, summary: str, category: str) -> dict:
        """Create a local synthetic human-handoff ticket."""
        return service.handoffs_create(customer_id, summary, category)

    return mcp


if __name__ == "__main__":
    build_server().run(transport="stdio")
