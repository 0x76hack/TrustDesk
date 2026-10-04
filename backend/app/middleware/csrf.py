import hmac
import secrets
import logging
from typing import Set
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import settings

logger = logging.getLogger("trustdesk.csrf")

SAFE_METHODS: Set[str] = {"GET", "HEAD", "OPTIONS", "TRACE"}
EXEMPT_PATHS: Set[str] = {
    "/api/v1/health",
    "/docs",
    "/openapi.json",
    "/redoc",
}


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        is_safe_method = request.method in SAFE_METHODS
        cookie_token = request.cookies.get(settings.CSRF_COOKIE_NAME)
        csrf_to_set = None

        if not cookie_token:
            csrf_to_set = generate_csrf_token()
            request.state.csrf_token = csrf_to_set
        else:
            request.state.csrf_token = cookie_token

        if path in EXEMPT_PATHS:
            response = await call_next(request)
            if csrf_to_set and is_safe_method:
                is_secure = settings.ENFORCE_HTTPS or (settings.ENVIRONMENT == "production")
                response.set_cookie(
                    key=settings.CSRF_COOKIE_NAME,
                    value=csrf_to_set,
                    httponly=False,
                    secure=is_secure,
                    samesite="strict",
                    path="/",
                    max_age=86400,
                )
            return response

        if not is_safe_method:
            auth_header = request.headers.get("Authorization", "")
            has_bearer_token = auth_header.startswith("Bearer ") and len(auth_header) > 10

            if not has_bearer_token:
                if not cookie_token:
                    logger.warning(
                        f"CSRF cookie missing on {request.method} {path} from {getattr(request.client, 'host', 'unknown')}"
                    )
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={
                            "code": "CSRF_COOKIE_MISSING",
                            "message": "CSRF cookie missing. Send a safe request (e.g. GET) first to obtain a CSRF token.",
                        },
                    )

                header_token = request.headers.get("X-CSRF-Token", "")
                if not header_token or not hmac.compare_digest(cookie_token, header_token):
                    logger.warning(
                        f"CSRF validation failed on {request.method} {path} from {getattr(request.client, 'host', 'unknown')}"
                    )
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={
                            "code": "CSRF_VERIFICATION_FAILED",
                            "message": "Cross-Site Request Forgery (CSRF) token verification failed. Missing or invalid X-CSRF-Token header.",
                        },
                    )

        response = await call_next(request)

        if csrf_to_set:
            is_secure = settings.ENFORCE_HTTPS or (settings.ENVIRONMENT == "production")
            response.set_cookie(
                key=settings.CSRF_COOKIE_NAME,
                value=csrf_to_set,
                httponly=False,
                secure=is_secure,
                samesite="strict",
                path="/",
                max_age=86400,
            )

        return response
