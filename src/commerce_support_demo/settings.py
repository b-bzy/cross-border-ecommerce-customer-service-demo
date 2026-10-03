from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

RouterMode = Literal["offline", "hybrid", "live_always"]
CommerceTransport = Literal["in_process", "mcp"]


@dataclass(frozen=True)
class Settings:
    router_mode: RouterMode
    commerce_transport: CommerceTransport
    claude_model: str
    action_ttl_seconds: int
    request_timeout_seconds: float
    data_dir: Path
    mcp_signing_key: str

    @classmethod
    def from_environment(cls) -> Settings:
        router_mode = os.getenv("DEMO_ROUTER_MODE", "offline")
        transport = os.getenv("DEMO_COMMERCE_TRANSPORT", "in_process")
        if router_mode not in {"offline", "hybrid", "live_always"}:
            raise ValueError("DEMO_ROUTER_MODE must be offline, hybrid, or live_always")
        if transport not in {"in_process", "mcp"}:
            raise ValueError("DEMO_COMMERCE_TRANSPORT must be in_process or mcp")
        project_root = Path(__file__).resolve().parents[2]
        return cls(
            router_mode=router_mode,  # type: ignore[arg-type]
            commerce_transport=transport,  # type: ignore[arg-type]
            claude_model=os.getenv("DEMO_CLAUDE_MODEL", "claude-opus-5"),
            action_ttl_seconds=int(os.getenv("DEMO_ACTION_TTL_SECONDS", "300")),
            request_timeout_seconds=float(os.getenv("DEMO_REQUEST_TIMEOUT_SECONDS", "15")),
            data_dir=project_root / "data" / "synthetic",
            mcp_signing_key=os.getenv("DEMO_MCP_SIGNING_KEY", secrets.token_urlsafe(32)),
        )
