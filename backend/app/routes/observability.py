import time
import os
try:
    import psutil
except ImportError:
    psutil = None
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text

from app.database import get_db
from app.dependencies import require_role
from app.models.user import User
from app.models.ticket import Ticket
from app.models.message import Message
from app.models.customer import Customer
from app.models.order import Order
from app.models.kb import KBChunk
from app.models.coupon import Coupon
from app.models.tool import ToolAction
from app.models.audit_log import AuditLog
from app.models.run import Run
from app.models.trace import Trace
from app.config import settings
from app.core.secrets import secrets_manager
from app.core.logging import log_ring_buffer, get_http_durations
from app.services.otp_service import get_redis_client

router = APIRouter()

PROCESS_START_TIME = time.time()


def compute_percentiles(values: List[float | int]) -> Dict[str, Any]:
    if not values:
        return {
            "p50": 0.0,
            "p90": 0.0,
            "p95": 0.0,
            "p99": 0.0,
            "avg": 0.0,
            "min": 0.0,
            "max": 0.0,
            "sample_count": 0,
        }
    sorted_vals = sorted(values)
    n = len(sorted_vals)

    def p(pct: float) -> float:
        idx = max(0, min(n - 1, int(round((pct / 100.0) * n - 0.5))))
        return round(float(sorted_vals[idx]), 2)

    return {
        "p50": p(50),
        "p90": p(90),
        "p95": p(95),
        "p99": p(99),
        "avg": round(sum(sorted_vals) / n, 2),
        "min": round(float(sorted_vals[0]), 2),
        "max": round(float(sorted_vals[-1]), 2),
        "sample_count": n,
    }


@router.get("/stats")
async def get_observability_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    now = datetime.now(timezone.utc)
    uptime_seconds = int(time.time() - PROCESS_START_TIME)

    db_connected = False
    db_latency_ms = 0.0
    try:
        t0 = time.perf_counter()
        await db.execute(text("SELECT 1"))
        db_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        db_connected = True
    except Exception:
        db_connected = False

    redis_connected = False
    redis_latency_ms = 0.0
    redis_memory_mb = 0.0
    try:
        r = await get_redis_client()
        if r:
            t0 = time.perf_counter()
            await r.ping()
            redis_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            redis_connected = True
            info = await r.info("memory")
            redis_memory_mb = round(info.get("used_memory", 0) / (1024 * 1024), 2)
    except Exception:
        redis_connected = False

    try:
        if psutil:
            process = psutil.Process(os.getpid())
            mem_info = process.memory_info()
            memory_mb = round(mem_info.rss / (1024 * 1024), 2)
            cpu_percent = process.cpu_percent(interval=None)
        else:
            memory_mb = 0.0
            cpu_percent = 0.0
    except Exception:
        memory_mb = 0.0
        cpu_percent = 0.0

    table_counts = {}
    for table_name, model in [
        ("tickets", Ticket),
        ("messages", Message),
        ("orders", Order),
        ("customers", Customer),
        ("coupons", Coupon),
        ("audit_logs", AuditLog),
        ("traces", Trace),
        ("kb_chunks", KBChunk),
        ("users", User),
    ]:
        try:
            cnt_stmt = select(func.count(model.id if hasattr(model, "id") else model.key if hasattr(model, "key") else text("1")))
            res = await db.execute(cnt_stmt)
            table_counts[table_name] = res.scalar() or 0
        except Exception:
            table_counts[table_name] = 0

    status_map = {}
    try:
        status_counts_stmt = select(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status)
        status_counts_res = await db.execute(status_counts_stmt)
        status_map = {row[0]: row[1] for row in status_counts_res.all()}
    except Exception:
        pass

    category_map = {}
    try:
        category_counts_stmt = select(Ticket.category, func.count(Ticket.id)).group_by(Ticket.category)
        category_counts_res = await db.execute(category_counts_stmt)
        category_map = {row[0]: row[1] for row in category_counts_res.all()}
    except Exception:
        pass

    action_map = {}
    try:
        action_counts_stmt = select(ToolAction.status, func.count(ToolAction.id)).group_by(ToolAction.status)
        action_counts_res = await db.execute(action_counts_stmt)
        action_map = {row[0]: row[1] for row in action_counts_res.all()}
    except Exception:
        pass

    yesterday = now - timedelta(days=1)
    security_event_count = 0
    threat_injection_count = 0
    threat_bypass_count = 0
    try:
        security_events_stmt = (
            select(func.count(AuditLog.id))
            .where(
                AuditLog.created_at >= yesterday,
                (AuditLog.risk_level.in_(["high", "critical"])) | (AuditLog.guardrail_result.isnot(None)),
            )
        )
        sec_res = await db.execute(security_events_stmt)
        security_event_count = sec_res.scalar() or 0

        inj_stmt = select(func.count(AuditLog.id)).where(
            AuditLog.created_at >= yesterday,
            AuditLog.action.like("%injection%"),
        )
        inj_res = await db.execute(inj_stmt)
        threat_injection_count = inj_res.scalar() or 0

        byp_stmt = select(func.count(AuditLog.id)).where(
            AuditLog.created_at >= yesterday,
            AuditLog.action.like("%conflict%") | AuditLog.action.like("%denied%"),
        )
        byp_res = await db.execute(byp_stmt)
        threat_bypass_count = byp_res.scalar() or 0
    except Exception:
        pass

    secrets_health = secrets_manager.validate_security(settings.ENVIRONMENT)

    ticket_resolution_stats = compute_percentiles([])
    try:
        res_stmt = (
            select(Ticket.created_at, Ticket.updated_at)
            .where(
                Ticket.status.in_(["resolved", "closed"]),
                Ticket.updated_at.isnot(None),
            )
            .order_by(Ticket.updated_at.desc())
            .limit(500)
        )
        res_res = await db.execute(res_stmt)
        resolution_durations_sec = []
        for row in res_res.all():
            c_at, u_at = row[0], row[1]
            if c_at and u_at and u_at >= c_at:
                resolution_durations_sec.append((u_at - c_at).total_seconds())
        if resolution_durations_sec:
            ticket_resolution_stats = compute_percentiles(resolution_durations_sec)
    except Exception:
        pass

    pipeline_overall = compute_percentiles([])
    pipeline_by_type: Dict[str, Any] = {}
    models_used_map: Dict[str, int] = {}
    by_model_lats: Dict[str, List[float]] = {}
    total_prompt_tokens = 0
    total_completion_tokens = 0

    try:
        trace_stmt = (
            select(Trace.latency_ms, Trace.run_type, Trace.model_used, Trace.token_usage)
            .where(Trace.latency_ms.isnot(None))
            .order_by(Trace.created_at.desc())
            .limit(1000)
        )
        trace_res = await db.execute(trace_stmt)
        all_trace_lats: List[float] = []
        by_type_lats: Dict[str, List[float]] = {}

        for row in trace_res.all():
            lat, rtype, model_used, tok_usage = row[0], row[1] or "general", row[2] or "default", row[3]
            if lat is not None:
                all_trace_lats.append(float(lat))
                by_type_lats.setdefault(rtype, []).append(float(lat))
                by_model_lats.setdefault(model_used, []).append(float(lat))
            models_used_map[model_used] = models_used_map.get(model_used, 0) + 1
            if isinstance(tok_usage, dict):
                total_prompt_tokens += tok_usage.get("prompt_tokens", 0)
                total_completion_tokens += tok_usage.get("completion_tokens", 0)

        if all_trace_lats:
            pipeline_overall = compute_percentiles(all_trace_lats)
            pipeline_by_type = {rtype: compute_percentiles(lats) for rtype, lats in by_type_lats.items()}
    except Exception:
        pass

    pipeline_by_model = {m: compute_percentiles(lats) for m, lats in by_model_lats.items()}
    estimated_cost_usd = round(
        (total_prompt_tokens * 0.000000075) + (total_completion_tokens * 0.00000030), 4
    )

    coupon_stats = {
        "total_issued": 0,
        "active": 0,
        "redeemed": 0,
        "expired": 0,
        "total_refund_value_inr": 0.0,
    }
    try:
        c_stmt = select(Coupon.status, func.count(Coupon.id), func.sum(Coupon.amount)).group_by(Coupon.status)
        c_res = await db.execute(c_stmt)
        for row in c_res.all():
            st, cnt, amt = row[0], row[1], row[2] or 0.0
            coupon_stats["total_issued"] += cnt
            coupon_stats["total_refund_value_inr"] += float(amt)
            if st == "active":
                coupon_stats["active"] = cnt
            elif st == "redeemed":
                coupon_stats["redeemed"] = cnt
            elif st == "expired":
                coupon_stats["expired"] = cnt
        coupon_stats["total_refund_value_inr"] = round(coupon_stats["total_refund_value_inr"], 2)
    except Exception:
        pass

    http_lats = get_http_durations()
    http_percentiles = compute_percentiles(http_lats)

    tickets_resolved_24h = 0
    tickets_resolved_1h = 0
    total_runs_24h = 0
    completed_runs_24h = 0
    run_success_rate = 100.0

    try:
        one_hour_ago = now - timedelta(hours=1)
        proc_24h_stmt = select(func.count(Ticket.id)).where(
            Ticket.status.in_(["resolved", "closed"]),
            Ticket.updated_at >= yesterday,
        )
        p24_res = await db.execute(proc_24h_stmt)
        tickets_resolved_24h = p24_res.scalar() or 0

        proc_1h_stmt = select(func.count(Ticket.id)).where(
            Ticket.status.in_(["resolved", "closed"]),
            Ticket.updated_at >= one_hour_ago,
        )
        p1_res = await db.execute(proc_1h_stmt)
        tickets_resolved_1h = p1_res.scalar() or 0

        runs_24h_stmt = select(Run.status, func.count(Run.id)).where(Run.created_at >= yesterday).group_by(Run.status)
        runs_res = await db.execute(runs_24h_stmt)
        run_counts = dict(runs_res.all())
        total_runs_24h = sum(run_counts.values())
        completed_runs_24h = run_counts.get("completed", 0)
        run_success_rate = round((completed_runs_24h / total_runs_24h) * 100, 1) if total_runs_24h > 0 else 100.0
    except Exception:
        pass

    return {
        "system": {
            "status": "healthy" if (db_connected and redis_connected) else "degraded",
            "uptime_seconds": uptime_seconds,
            "environment": settings.ENVIRONMENT,
            "enforce_https": settings.ENFORCE_HTTPS,
            "database_connected": db_connected,
            "database_latency_ms": db_latency_ms,
            "redis_connected": redis_connected,
            "redis_latency_ms": redis_latency_ms,
            "redis_memory_mb": redis_memory_mb,
            "memory_usage_mb": memory_mb,
            "cpu_percent": cpu_percent,
        },
        "database_inventory": table_counts,
        "queues": {
            "open": status_map.get("open", 0),
            "working": status_map.get("working", 0),
            "escalated": status_map.get("escalated", 0),
            "resolved": status_map.get("resolved", 0),
            "total": sum(status_map.values()),
        },
        "categories": category_map,
        "actions": {
            "pending_approval": action_map.get("pending_approval", 0),
            "executed": action_map.get("executed", 0),
            "rejected": action_map.get("rejected", 0),
            "total": sum(action_map.values()),
        },
        "ai_telemetry": {
            "total_runs": sum(models_used_map.values()),
            "models_used": models_used_map,
            "total_prompt_tokens": total_prompt_tokens,
            "total_completion_tokens": total_completion_tokens,
            "total_tokens": total_prompt_tokens + total_completion_tokens,
            "estimated_cost_usd": estimated_cost_usd,
            "latency_by_model": pipeline_by_model,
            "guardrail_threats_blocked": {
                "prompt_injection": threat_injection_count,
                "conflict_or_bypass": threat_bypass_count,
                "total": threat_injection_count + threat_bypass_count,
            },
        },
        "fraud_mitigation": {
            "coupon_stats": coupon_stats,
            "duplicate_replay_blocks": threat_bypass_count,
        },
        "security": {
            "critical_events_24h": security_event_count,
            "secrets_manager": secrets_health,
        },
        "performance": {
            "processing_rates": {
                "tickets_resolved_24h": tickets_resolved_24h,
                "tickets_resolved_1h": tickets_resolved_1h,
                "velocity_per_hour": round(tickets_resolved_24h / 24.0, 1),
                "runs_completed_24h": completed_runs_24h,
                "total_runs_24h": total_runs_24h,
                "run_success_rate_percent": run_success_rate,
            },
            "ticket_resolution_time_seconds": ticket_resolution_stats,
            "pipeline_latency_ms": {
                "overall": pipeline_overall,
                "by_type": pipeline_by_type,
            },
            "http_latency_ms": http_percentiles,
        },
    }


@router.get("/traces")
async def get_observability_traces(
    run_type: Optional[str] = Query(None, description="Filter by run type (triage, draft, action, eval)"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level (low, medium, high, critical)"),
    model_used: Optional[str] = Query(None, description="Filter by model name"),
    ticket_id: Optional[str] = Query(None, description="Filter by ticket ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    stmt = select(Trace).order_by(Trace.created_at.desc())
    if run_type:
        stmt = stmt.where(Trace.run_type == run_type)
    if risk_level:
        stmt = stmt.where(Trace.risk_level == risk_level)
    if model_used:
        stmt = stmt.where(Trace.model_used == model_used)
    if ticket_id:
        stmt = stmt.where(Trace.ticket_id == ticket_id)

    count_stmt = select(func.count(Trace.id))
    if run_type:
        count_stmt = count_stmt.where(Trace.run_type == run_type)
    if risk_level:
        count_stmt = count_stmt.where(Trace.risk_level == risk_level)
    if model_used:
        count_stmt = count_stmt.where(Trace.model_used == model_used)
    if ticket_id:
        count_stmt = count_stmt.where(Trace.ticket_id == ticket_id)

    total_res = await db.execute(count_stmt)
    total_count = total_res.scalar() or 0

    res = await db.execute(stmt.limit(limit).offset(offset))
    records = res.scalars().all()

    trace_items = []
    for r in records:
        doc_count = len(r.retrieved_doc_ids) if isinstance(r.retrieved_doc_ids, list) else 0
        trace_items.append({
            "id": r.id,
            "ticket_id": r.ticket_id,
            "run_id": r.run_id,
            "run_type": r.run_type,
            "model_used": r.model_used or "fast_rule_engine",
            "latency_ms": r.latency_ms,
            "token_usage": r.token_usage or {},
            "risk_level": r.risk_level,
            "risk_factors": r.risk_factors or [],
            "guardrail_result": r.guardrail_result or {},
            "retrieved_doc_count": doc_count,
            "final_status": r.final_status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    return {
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "traces": trace_items,
    }


@router.get("/security-summary")
async def get_security_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)

    crit_stmt = select(func.count(AuditLog.id)).where(
        AuditLog.created_at >= yesterday,
        AuditLog.risk_level.in_(["high", "critical"]),
    )
    crit_res = await db.execute(crit_stmt)
    critical_audit_count = crit_res.scalar() or 0

    inj_stmt = select(func.count(AuditLog.id)).where(
        AuditLog.created_at >= yesterday,
        AuditLog.action.like("%injection%"),
    )
    inj_res = await db.execute(inj_stmt)
    prompt_injections = inj_res.scalar() or 0

    conf_stmt = select(func.count(AuditLog.id)).where(
        AuditLog.created_at >= yesterday,
        AuditLog.action.like("%conflict%") | AuditLog.action.like("%denied%"),
    )
    conf_res = await db.execute(conf_stmt)
    duplicate_blocks = conf_res.scalar() or 0

    recent_threats_stmt = (
        select(AuditLog)
        .where(AuditLog.risk_level.in_(["high", "critical"]))
        .order_by(AuditLog.created_at.desc())
        .limit(20)
    )
    threats_res = await db.execute(recent_threats_stmt)
    recent_threats = [
        {
            "id": r.id,
            "actor_id": r.actor_id,
            "action": r.action,
            "resource_type": r.resource_type,
            "resource_id": r.resource_id,
            "outcome": r.outcome,
            "risk_level": r.risk_level,
            "guardrail_result": r.guardrail_result,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in threats_res.scalars().all()
    ]

    return {
        "critical_events_24h": critical_audit_count,
        "prompt_injections_blocked_24h": prompt_injections,
        "idempotency_conflicts_prevented_24h": duplicate_blocks,
        "secrets_manager": secrets_manager.validate_security(settings.ENVIRONMENT),
        "recent_threats": recent_threats,
    }


@router.get("/logs")
async def get_observability_logs(
    level: Optional[str] = Query("ALL", description="Filter by log level (DEBUG, INFO, WARNING, ERROR, ALL)"),
    search: Optional[str] = Query(None, description="Full-text search in log messages"),
    request_id: Optional[str] = Query(None, description="Filter logs by exact Request ID / Trace ID"),
    component: Optional[str] = Query(None, description="Filter logs by component"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_role(["admin"])),
):
    logs = log_ring_buffer.query(
        level=level,
        search=search,
        request_id=request_id,
        component=component,
        limit=limit,
        offset=offset,
    )
    return {
        "count": len(logs),
        "total_in_buffer": len(log_ring_buffer._buffer),
        "logs": logs,
    }


@router.get("/audit-stream")
async def get_audit_stream(
    action: Optional[str] = None,
    risk_level: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if risk_level:
        stmt = stmt.where(AuditLog.risk_level == risk_level)

    res = await db.execute(stmt)
    records = res.scalars().all()

    return [
        {
            "id": r.id,
            "actor_id": r.actor_id,
            "action": r.action,
            "resource_type": r.resource_type,
            "resource_id": r.resource_id,
            "outcome": r.outcome,
            "risk_level": r.risk_level,
            "guardrail_result": r.guardrail_result,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]
