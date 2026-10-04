import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import HTTPException

from app.models.ticket import Ticket
from app.models.order import Order
from app.models.tool import ToolAction
from app.services.refund_service import issue_refund_coupon, generate_coupon_code


class TestRefundService:
    def test_coupon_format(self):
        code = generate_coupon_code()
        assert code.startswith("TRUST-REF-")
        assert len(code) == 18

    @pytest.mark.asyncio
    async def test_negative_or_zero_amount_rejected(self):
        mock_db = AsyncMock()
        with pytest.raises(HTTPException) as exc:
            await issue_refund_coupon(
                ticket_id="tick-1",
                amount=0.0,
                db=mock_db,
            )
        assert exc.value.status_code == 422
        assert "Refund amount must be positive" in exc.value.detail

        with pytest.raises(HTTPException) as exc2:
            await issue_refund_coupon(
                ticket_id="tick-1",
                amount=-15.0,
                db=mock_db,
            )
        assert exc2.value.status_code == 422

    @pytest.mark.asyncio
    async def test_ticket_not_found(self):
        mock_db = AsyncMock()
        mock_db.get.return_value = None
        with patch("app.services.refund_service.check_idempotency", AsyncMock(return_value=(False, None))):
            with pytest.raises(HTTPException) as exc:
                await issue_refund_coupon(
                    ticket_id="nonexistent-ticket",
                    amount=50.0,
                    db=mock_db,
                )
            assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_exceeding_order_total_rejected(self):
        ticket = Ticket(id="tick-1", order_id="ord-1", customer_id="cust-1")
        order = Order(id="ord-1", customer_id="cust-1", restaurant="Food Place", status="delivered", total=100.0)

        mock_db = AsyncMock()
        mock_db.get.side_effect = lambda model, pk: ticket if model == Ticket else (order if model == Order else None)

        mock_res_prev = MagicMock()
        mock_res_prev.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_res_prev

        with patch("app.services.refund_service.check_idempotency", AsyncMock(return_value=(False, None))):
            with pytest.raises(HTTPException) as exc:
                await issue_refund_coupon(
                    ticket_id="tick-1",
                    amount=150.0,
                    db=mock_db,
                )
            assert exc.value.status_code == 422
            assert "Cumulative refund limit exceeded" in exc.value.detail

    @pytest.mark.asyncio
    async def test_exceeding_cumulative_refund_ceiling_rejected(self):
        ticket = Ticket(id="tick-1", order_id="ord-1", customer_id="cust-1")
        order = Order(id="ord-1", customer_id="cust-1", restaurant="Food Place", status="delivered", total=100.0)

        prior_action = ToolAction(
            id="act-prior",
            ticket_id="tick-old",
            status="executed",
            idempotency_key="refund_tick-old_TRUST",
            payload={"category": "refund", "amount": 70.0, "coupon_code": "TRUST-REF-11111111"},
        )

        mock_db = AsyncMock()
        mock_db.get.side_effect = lambda model, pk: ticket if model == Ticket else (order if model == Order else None)

        mock_res_prev = MagicMock()
        mock_res_prev.scalars.return_value.all.return_value = [prior_action]
        mock_db.execute.return_value = mock_res_prev

        with patch("app.services.refund_service.check_idempotency", AsyncMock(return_value=(False, None))):
            with pytest.raises(HTTPException) as exc:
                await issue_refund_coupon(
                    ticket_id="tick-1",
                    amount=40.0,
                    db=mock_db,
                )
            assert exc.value.status_code == 422
            assert "Cumulative refund limit exceeded" in exc.value.detail

    @pytest.mark.asyncio
    async def test_successful_coupon_issuance_and_idempotency(self):
        ticket = Ticket(id="tick-1", order_id="ord-1", customer_id="cust-1")
        order = Order(id="ord-1", customer_id="cust-1", restaurant="Food Place", status="delivered", total=200.0)

        mock_db = AsyncMock()
        mock_db.get.side_effect = lambda model, pk: ticket if model == Ticket else (order if model == Order else None)

        mock_res_prev = MagicMock()
        mock_res_prev.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_res_prev

        with patch("app.services.refund_service.check_idempotency", AsyncMock(return_value=(False, None))), \
             patch("app.services.refund_service.store_idempotency", AsyncMock()) as mock_store, \
             patch("app.services.refund_service.log_audit", AsyncMock()) as mock_audit:

            resp, is_replay = await issue_refund_coupon(
                ticket_id="tick-1",
                amount=50.0,
                db=mock_db,
                idempotency_key="test-key-123",
                actor_id="user-1",
                reason="Cold food",
            )

            assert is_replay is False
            assert resp["coupon_code"].startswith("TRUST-REF-")
            assert resp["amount"] == 50.0
            assert resp["ticket_id"] == "tick-1"
            assert resp["order_id"] == "ord-1"
            assert resp["status"] == "issued"
            assert order.status == "refunded"
            assert mock_store.called
            assert mock_audit.called

    @pytest.mark.asyncio
    async def test_idempotent_replay_returns_cached_coupon(self):
        mock_db = AsyncMock()
        cached_data = {
            "coupon_code": "TRUST-REF-A1B2C3D4",
            "amount": 75.0,
            "ticket_id": "tick-1",
            "order_id": "ord-1",
            "status": "issued",
            "message": "Refund coupon TRUST-REF-A1B2C3D4 issued successfully.",
        }

        with patch("app.services.refund_service.check_idempotency", AsyncMock(return_value=(True, cached_data))):
            resp, is_replay = await issue_refund_coupon(
                ticket_id="tick-1",
                amount=75.0,
                db=mock_db,
                idempotency_key="replayed-key-999",
            )
            assert is_replay is True
            assert resp["coupon_code"] == "TRUST-REF-A1B2C3D4"
            assert resp["amount"] == 75.0

    @pytest.mark.asyncio
    async def test_linked_order_not_found_raises_404(self):
        ticket = Ticket(id="tick-1", order_id="ord-missing", customer_id="cust-1")
        mock_db = AsyncMock()
        mock_db.get.side_effect = lambda model, pk: ticket if model == Ticket else None

        with patch("app.services.refund_service.check_idempotency", AsyncMock(return_value=(False, None))):
            with pytest.raises(HTTPException) as exc:
                await issue_refund_coupon(
                    ticket_id="tick-1",
                    amount=50.0,
                    db=mock_db,
                )
            assert exc.value.status_code == 404
            assert "not found" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_float_precision_exact_boundary_permitted(self):
        ticket = Ticket(id="tick-1", order_id="ord-1", customer_id="cust-1")
        order = Order(id="ord-1", customer_id="cust-1", restaurant="Food Place", status="delivered", total=0.30)
        prior_action = ToolAction(
            id="act-prior",
            ticket_id="tick-1",
            status="executed",
            payload={"category": "refund", "amount": 0.10},
        )
        mock_db = AsyncMock()
        mock_db.get.side_effect = lambda model, pk: ticket if model == Ticket else (order if model == Order else None)
        mock_res_prev = MagicMock()
        mock_res_prev.scalars.return_value.all.return_value = [prior_action]
        mock_db.execute.return_value = mock_res_prev

        with patch("app.services.refund_service.check_idempotency", AsyncMock(return_value=(False, None))), \
             patch("app.services.refund_service.store_idempotency", AsyncMock()), \
             patch("app.services.refund_service.log_audit", AsyncMock()):
            resp, _ = await issue_refund_coupon(
                ticket_id="tick-1",
                amount=0.20,
                db=mock_db,
            )
            assert resp["amount"] == 0.20
            assert resp["status"] == "issued"
