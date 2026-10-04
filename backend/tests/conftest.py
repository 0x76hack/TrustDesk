import pytest
import pytest_asyncio
import httpx
from httpx import ASGITransport
from app.main import app
from app.database import engine
from app.ai.model_router import ModelRouter

@pytest.fixture
def model_router():
    return ModelRouter()

@pytest_asyncio.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
    await engine.dispose()

