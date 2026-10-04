import logging
from fastapi import Request, Response, status
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import settings

logger = logging.getLogger("trustdesk.security")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if settings.ENFORCE_HTTPS:
            is_http = request.url.scheme == "http"
            forwarded_proto = request.headers.get("x-forwarded-proto", "").lower()
            if is_http or forwarded_proto == "http":
                secure_url = request.url.replace(scheme="https")
                logger.info(f"Redirecting plaintext HTTP request to secure HTTPS: {secure_url}")
                return RedirectResponse(
                    url=str(secure_url),
                    status_code=status.HTTP_301_MOVED_PERMANENTLY,
                )

        response: Response = await call_next(request)

        headers = response.headers
        headers["X-Content-Type-Options"] = "nosniff"
        headers["X-Frame-Options"] = "DENY"
        headers["X-XSS-Protection"] = "1; mode=block"
        headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "connect-src 'self' http://localhost:* https://* ws: wss:; "
            "frame-ancestors 'none';"
        )

        if settings.ENFORCE_HTTPS or (settings.ENVIRONMENT == "production"):
            headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        return response
