import uuid
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.logging import setup_logging, request_id_var
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.csrf import CSRFMiddleware
from app.routes import (
    auth,
    admin,
    tickets,
    approvals,
    runs,
    evaluation as eval_routes,
    health,
    customer_portal,
    observability,
    coupons,
)

setup_logging(log_level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)
logger = logging.getLogger("trustdesk.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"TrustDesk API initialized in {settings.ENVIRONMENT} mode.")
    yield
    logger.info("TrustDesk API service shutting down.")


app = FastAPI(
    title="TrustDesk API",
    description="TrustDesk Production Backend Service",
    version="1.0.0",
    lifespan=lifespan,
)

allowed_origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "Idempotent-Replay", "X-CSRF-Token"],
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFMiddleware)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    import time
    from app.core.logging import record_http_duration

    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = req_id
    token = request_id_var.set(req_id)
    t0 = time.perf_counter()

    try:
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        record_http_duration(duration_ms)
        response.headers["X-Request-ID"] = req_id
        response.headers["X-Response-Time"] = f"{duration_ms}ms"
        return response
    finally:
        request_id_var.reset(token)


app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(tickets.router, prefix="/api/v1/tickets", tags=["tickets"])
app.include_router(customer_portal.router, prefix="/api/v1/customer-portal", tags=["customer-portal"])
app.include_router(approvals.router, prefix="/api/v1/approvals", tags=["approvals"])
app.include_router(runs.router, prefix="/api/v1/runs", tags=["runs"])
app.include_router(eval_routes.router, prefix="/api/v1/eval", tags=["eval"])
app.include_router(observability.router, prefix="/api/v1/observability", tags=["observability"])
app.include_router(coupons.router, prefix="/api/v1/coupons", tags=["coupons"])


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", "unknown")
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "request_id": req_id},
        )

    logger.exception(
        f"Unhandled exception on {request.method} {request.url.path} [request_id={req_id}]: {exc}"
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error.", "request_id": req_id},
    )
