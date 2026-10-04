import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import AsyncClient, ASGITransport
from app.middleware.csrf import CSRFMiddleware, generate_csrf_token
from app.config import settings


@pytest.fixture
def csrf_test_app():
    test_app = FastAPI()
    test_app.add_middleware(CSRFMiddleware)

    @test_app.get("/test/safe")
    async def safe_endpoint():
        return {"status": "ok"}

    @test_app.post("/test/mutate")
    async def mutate_endpoint():
        return {"status": "created"}

    @test_app.get("/api/v1/health")
    async def health_endpoint():
        return {"status": "healthy"}

    return test_app


class TestCSRFMiddleware:
    def test_generate_csrf_token(self):
        token1 = generate_csrf_token()
        token2 = generate_csrf_token()
        assert len(token1) >= 32
        assert token1 != token2

    @pytest.mark.asyncio
    async def test_get_request_sets_csrf_cookie(self, csrf_test_app):
        transport = ASGITransport(app=csrf_test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/test/safe")
            assert resp.status_code == 200
            assert settings.CSRF_COOKIE_NAME in resp.cookies
            cookie_val = resp.cookies[settings.CSRF_COOKIE_NAME]
            assert len(cookie_val) >= 32

    @pytest.mark.asyncio
    async def test_post_with_cookie_but_missing_header_rejected_403(self, csrf_test_app):
        transport = ASGITransport(app=csrf_test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            get_resp = await client.get("/test/safe")
            csrf_token = get_resp.cookies[settings.CSRF_COOKIE_NAME]

            post_resp = await client.post(
                "/test/mutate",
                cookies={settings.CSRF_COOKIE_NAME: csrf_token},
            )
            assert post_resp.status_code == 403
            data = post_resp.json()
            assert data["code"] == "CSRF_VERIFICATION_FAILED"

    @pytest.mark.asyncio
    async def test_post_with_mismatched_token_rejected_403(self, csrf_test_app):
        transport = ASGITransport(app=csrf_test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            post_resp = await client.post(
                "/test/mutate",
                cookies={settings.CSRF_COOKIE_NAME: "valid_cookie_token_1234567890"},
                headers={"X-CSRF-Token": "tampered_token_999999999"},
            )
            assert post_resp.status_code == 403
            assert post_resp.json()["code"] == "CSRF_VERIFICATION_FAILED"

    @pytest.mark.asyncio
    async def test_post_with_matching_cookie_and_header_succeeds(self, csrf_test_app):
        transport = ASGITransport(app=csrf_test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            token = generate_csrf_token()
            post_resp = await client.post(
                "/test/mutate",
                cookies={settings.CSRF_COOKIE_NAME: token},
                headers={"X-CSRF-Token": token},
            )
            assert post_resp.status_code == 200
            assert post_resp.json() == {"status": "created"}

    @pytest.mark.asyncio
    async def test_post_with_bearer_token_exempt_from_csrf(self, csrf_test_app):
        transport = ASGITransport(app=csrf_test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            token = generate_csrf_token()
            post_resp = await client.post(
                "/test/mutate",
                cookies={settings.CSRF_COOKIE_NAME: token},
                headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummy.sig"},
            )
            assert post_resp.status_code == 200
            assert post_resp.json() == {"status": "created"}

    @pytest.mark.asyncio
    async def test_exempt_path_skips_validation(self, csrf_test_app):
        transport = ASGITransport(app=csrf_test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/health")
            assert resp.status_code == 200
            assert resp.json() == {"status": "healthy"}

    @pytest.mark.asyncio
    async def test_post_with_no_cookie_and_no_bearer_rejected_403(self, csrf_test_app):
        transport = ASGITransport(app=csrf_test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            post_resp = await client.post("/test/mutate")
            assert post_resp.status_code == 403
            data = post_resp.json()
            assert data["code"] == "CSRF_COOKIE_MISSING"

