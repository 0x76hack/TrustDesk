import uuid
from unittest.mock import AsyncMock, MagicMock
import pytest
from fastapi import HTTPException
from app.models.user import User
from app.models.ticket import Ticket
from app.models.order import Order
from app.models.tool import ToolAction, ToolDefinition
from app.services.action_service import approve_action, recommend_action


class TestBusinessLogicSecurity:
    @pytest.mark.asyncio
    async def test_non_approver_role_blocked(self):
        agent_user = User(id="user-agent-1", role="agent", username="agent1")
        mock_db = AsyncMock()

        with pytest.raises(HTTPException) as exc:
            await approve_action(
                action_id="act-1",
                approver_user=agent_user,
                decision="approved",
                reason="Looks good",
                db=mock_db,
            )
        assert exc.value.status_code == 403
        assert "Only users with 'senior_agent' or 'admin' role" in exc.value.detail

    @pytest.mark.asyncio
    async def test_action_not_in_pending_approval_raises_conflict(self):
        approver = User(id="user-appr-1", role="senior_agent", username="approver1")
        action = ToolAction(
            id="act-1",
            ticket_id="tick-1",
            status="draft",
            risk_level="high",
        )

        mock_db = AsyncMock()
        mock_scalar = MagicMock()
        mock_scalar.scalar_one_or_none.return_value = action
        mock_db.execute.return_value = mock_scalar

        with pytest.raises(HTTPException) as exc:
            await approve_action(
                action_id="act-1",
                approver_user=approver,
                decision="approved",
                reason="Looks good",
                db=mock_db,
            )
        assert exc.value.status_code == 409
        assert "not 'pending_approval'" in exc.value.detail

    @pytest.mark.asyncio
    async def test_closed_ticket_action_approval_blocked(self):
        approver = User(id="user-appr-1", role="senior_agent", username="approver1")
        action = ToolAction(
            id="act-1",
            ticket_id="tick-1",
            status="pending_approval",
            risk_level="high",
            proposed_by_id="user-other-agent",
        )
        resolved_ticket = Ticket(id="tick-1", status="resolved")

        mock_db = AsyncMock()
        mock_scalar = MagicMock()
        mock_scalar.scalar_one_or_none.return_value = action
        mock_db.execute.return_value = mock_scalar
        mock_db.get.return_value = resolved_ticket

        with pytest.raises(HTTPException) as exc:
            await approve_action(
                action_id="act-1",
                approver_user=approver,
                decision="approved",
                reason="Approving resolved",
                db=mock_db,
            )
        assert exc.value.status_code == 400
        assert "Cannot approve actions for a resolved or closed ticket" in exc.value.detail

    @pytest.mark.asyncio
    async def test_maker_checker_violation_self_approval_blocked(self):
        approver_who_proposed = User(id="user-123", role="senior_agent", username="proposer_and_approver")
        action = ToolAction(
            id="act-1",
            ticket_id="tick-1",
            status="pending_approval",
            risk_level="high",
            proposed_by_id="user-123",
        )
        open_ticket = Ticket(id="tick-1", status="open")

        mock_db = AsyncMock()
        mock_scalar = MagicMock()
        mock_scalar.scalar_one_or_none.return_value = action
        mock_db.execute.return_value = mock_scalar
        mock_db.get.return_value = open_ticket

        with pytest.raises(HTTPException) as exc:
            await approve_action(
                action_id="act-1",
                approver_user=approver_who_proposed,
                decision="approved",
                reason="Self approving",
                db=mock_db,
            )
        assert exc.value.status_code == 403
        assert "Maker-Checker policy violation" in exc.value.detail

    @pytest.mark.asyncio
    async def test_maker_checker_segregated_approval_succeeds(self):
        proposer_id = "user-proposer-999"
        different_approver = User(id="user-approver-888", role="senior_agent", username="independent_reviewer")
        action = ToolAction(
            id="act-1",
            ticket_id="tick-1",
            status="pending_approval",
            risk_level="high",
            proposed_by_id=proposer_id,
        )
        open_ticket = Ticket(id="tick-1", status="open")

        mock_db = AsyncMock()
        mock_scalar = MagicMock()
        mock_scalar.scalar_one_or_none.return_value = action
        mock_db.execute.return_value = mock_scalar
        mock_db.get.return_value = open_ticket

        approval = await approve_action(
            action_id="act-1",
            approver_user=different_approver,
            decision="approved",
            reason="Verified and approved by independent supervisor",
            db=mock_db,
        )
        assert approval is not None
        assert approval.decision == "approved"
        assert approval.approver_id == "user-approver-888"
        assert action.status == "executed"

    @pytest.mark.asyncio
    async def test_cumulative_refund_ceiling_enforced(self):
        ticket = Ticket(id="tick-1", subject="Refund please", order_id="ord-1")
        order = Order(id="ord-1", total=500.0, customer_id="cust-1")

        mock_db = AsyncMock()
        mock_db.get.return_value = order

        prior_refund_action = ToolAction(
            id="act-prior-1",
            ticket_id="tick-old",
            status="executed",
            idempotency_key="action_tick-old_refund",
            payload={"category": "refund", "amount": 500.0},
        )

        mock_res_idemp = MagicMock()
        mock_res_idemp.scalar_one_or_none.return_value = None

        mock_res_prior = MagicMock()
        mock_res_prior.scalars.return_value.all.return_value = [prior_refund_action]

        mock_db.execute.side_effect = [mock_res_idemp, mock_res_prior]

        triage_result = {"category": "refund"}
        risk_result = {"risk_level": "medium"}

        with pytest.raises(HTTPException) as exc:
            await recommend_action(
                ticket=ticket,
                triage_result=triage_result,
                risk_result=risk_result,
                db=mock_db,
                proposed_by_id="user-1",
            )
        assert exc.value.status_code == 422
        assert "Cumulative refund limit exceeded" in exc.value.detail
