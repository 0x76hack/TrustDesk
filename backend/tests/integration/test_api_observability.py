import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.core.logging import log_ring_buffer, LogRecordEntry


@pytest.fixture
def admin_user():
    return User(
        id="admin-user-uuid",
        username="admin",
        name="Admin User",
        email="admin@trustdesk.local",
        role="admin",
    )


@pytest.fixture
def agent_user():
    return User(
        id="agent-user-uuid",
        username="agent1",
        name="Agent User",
        email="agent@trustdesk.local",
        role="agent",
    )


@pytest.fixture
def mock_db_session():
    mock = AsyncMock()

    mock_select1 = MagicMock()
    mock_status_counts = MagicMock()
    mock_status_counts.all.return_value = [("open", 5), ("resolved", 10)]
    mock_cat_counts = MagicMock()
    mock_cat_counts.all.return_value = [("refund", 3), ("shipping", 2)]
    mock_act_counts = MagicMock()
    mock_act_counts.all.return_value = [("pending_approval", 2), ("executed", 8)]
    mock_sec = MagicMock()
    mock_sec.scalar.return_value = 1

    mock_audit = MagicMock()
    mock_audit.scalars.return_value.all.return_value = []
    mock_audit_total = MagicMock()
    mock_audit_total.scalar.return_value = 0

    mock.execute.side_effect = [
        mock_select1,
        mock_status_counts,
        mock_cat_counts,
        mock_act_counts,
        mock_sec,
        mock_audit,
        mock_audit_total,
    ]
    return mock


class TestObservabilityAPI:
    @pytest.mark.asyncio
    async def test_unauthenticated_request_rejected(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/observability/stats")
            assert resp.status_code in [401, 403]

    @pytest.mark.asyncio
    async def test_agent_role_forbidden(self, agent_user):
        app.dependency_overrides[get_current_user] = lambda: agent_user
        transport = ASGITransport(app=app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/observability/stats")
                assert resp.status_code == 403
                assert "Insufficient permissions" in resp.text
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_admin_role_can_access_stats(self, admin_user, mock_db_session):
        app.dependency_overrides[get_current_user] = lambda: admin_user
        app.dependency_overrides[get_db] = lambda: mock_db_session
        transport = ASGITransport(app=app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/observability/stats")
                assert resp.status_code == 200
                data = resp.json()
                assert "system" in data
                assert "performance" in data
                perf = data["performance"]
                assert "processing_rates" in perf
                assert "ticket_resolution_time_seconds" in perf
                assert "p50" in perf["ticket_resolution_time_seconds"]
                assert "p95" in perf["ticket_resolution_time_seconds"]
                assert "p99" in perf["ticket_resolution_time_seconds"]
                assert "pipeline_latency_ms" in perf
                assert "http_latency_ms" in perf
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_admin_can_query_and_filter_live_logs(self, admin_user):
        import time

        with log_ring_buffer._lock:
            log_ring_buffer._buffer.append(
                LogRecordEntry(
                    level="INFO",
                    message="User signed in successfully",
                    logger_name="app.api",
                    timestamp=time.time(),
                    request_id="req-trace-abc-123",
                    user_id="user-1",
                )
            )
            log_ring_buffer._buffer.append(
                LogRecordEntry(
                    level="ERROR",
                    message="Payment gateway timeout",
                    logger_name="app.payment",
                    timestamp=time.time(),
                    request_id="req-trace-err-999",
                    user_id="user-2",
                )
            )

        app.dependency_overrides[get_current_user] = lambda: admin_user
        transport = ASGITransport(app=app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp_all = await client.get("/api/v1/observability/logs")
                assert resp_all.status_code == 200
                payload = resp_all.json()
                assert "logs" in payload
                assert isinstance(payload["logs"], list)

                resp_filtered = await client.get("/api/v1/observability/logs?request_id=req-trace-abc-123")
                assert resp_filtered.status_code == 200
                filtered_logs = resp_filtered.json()["logs"]
                assert len(filtered_logs) >= 1
                assert all(l["request_id"] == "req-trace-abc-123" for l in filtered_logs)

                resp_search = await client.get("/api/v1/observability/logs?search=gateway")
                assert resp_search.status_code == 200
                search_logs = resp_search.json()["logs"]
                assert len(search_logs) >= 1
                assert any("Payment gateway timeout" in l["message"] for l in search_logs)
        finally:
            app.dependency_overrides.clear()
