from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commerce_support_demo.main import create_app
from commerce_support_demo.settings import Settings


@pytest.fixture
def settings() -> Settings:
    project_root = Path(__file__).resolve().parents[1]
    return Settings(
        router_mode="offline",
        commerce_transport="in_process",
        claude_model="claude-opus-5",
        action_ttl_seconds=300,
        request_timeout_seconds=15,
        data_dir=project_root / "data" / "synthetic",
        mcp_signing_key="test-signing-key",
    )


@pytest.fixture
def client(settings: Settings):
    with TestClient(create_app(settings)) as test_client:
        yield test_client
