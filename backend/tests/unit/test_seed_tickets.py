from unittest.mock import AsyncMock, MagicMock, patch
import pytest

import seed_demo_tickets


class TestSeedTicketsGenerator:
    def test_seed_tickets_spec_coverage(self):
        assert hasattr(seed_demo_tickets, "seed_demo")
        assert hasattr(seed_demo_tickets, "deterministic_uuid")

    @pytest.mark.asyncio
    async def test_seed_demo_execution(self):
        mock_session = AsyncMock()
        mock_agent_res = MagicMock()
        mock_agent_res.scalars.return_value.first.return_value = None

        mock_empty_res = MagicMock()
        mock_empty_res.scalars.return_value.first.return_value = None
        mock_empty_res.scalars.return_value.all.return_value = []

        mock_session.execute.return_value = mock_empty_res

        mock_session.get.return_value = None

        mock_session_factory = MagicMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session
        mock_session_factory.return_value.__aexit__.return_value = None

        with patch("seed_demo_tickets.AsyncSessionLocal", mock_session_factory):
            await seed_demo_tickets.seed_demo()

        assert mock_session.commit.called
        assert mock_session.add.call_count >= 15
