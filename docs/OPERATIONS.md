# TrustDesk Operational & Observability Guide

This guide covers operational maintenance, live production debugging, queue telemetry, and system monitoring for TrustDesk administrators.

---

## 1. Administration Observability Dashboard

TrustDesk provides a dedicated **5-Tab Observability & Diagnostics Dashboard** accessible exclusively to administrators. It is isolated from standard agent queue navigation to maintain an uncluttered workspace.

### Accessing the Dashboard:
1. Log in with an administrator account (`role: admin`).
2. Click the **Diagnostics** button in the top navigation bar, or navigate directly to `/#observability`.
3. Non-admin users attempting to query `/api/v1/observability/*` or access the dashboard are rejected with `403 Forbidden`.

### 5-Tab Architecture:

1. **Infrastructure & Vitals**:
   - Live socket connectivity and ping latency for PostgreSQL (`db_latency_ms`) and Redis (`redis_latency_ms`).
   - Memory metrics: Host RSS process memory (`memory_mb`) and Redis used memory (`redis_memory_mb`).
   - Host CPU utilization (`cpu_percent`) and system uptime.
   - Comprehensive Database Inventory: Exact real-time row counts across all 9 primary relational tables (`tickets`, `messages`, `orders`, `customers`, `coupons`, `audit_logs`, `traces`, `kb_chunks`, `users`).

2. **AI & LLM Telemetry**:
   - Total inference runs and unique models deployed across the cluster.
   - Aggregate token consumption: total prompt tokens, completion tokens, and total tokens.
   - Estimated inference cost tracking (USD) calculated based on real token usage.
   - Per-Model Latency Percentile Matrix: `p50`, `p90`, `p95`, `p99`, `avg`, `min`, `max` durations for each active model.

3. **Distributed Traces Explorer**:
   - Filterable trace query interface with support for `run_type` (`triage`, `draft`, `action`), `risk_level` (`low`, `medium`, `high`, `critical`), `model_used`, and `ticket_id`.
   - Displays execution latency, token counts, guardrail verdicts, retrieved document counts, and final completion status.

4. **Fraud & Security Intelligence**:
   - Pure server-side coupon tracking: total issued, active, redeemed, expired, and cumulative refund volume (INR).
   - Duplicate coupon replay concurrency mitigation counters.
   - 24-hour critical incident tracking: prompt injection interceptions and unauthorized access attempts.

5. **System Logs**:
   - Real-time in-memory circular ring buffer (`MemoryRingBufferHandler`) retaining the most recent 1,000 log events.
   - Filter by severity: `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `ALL`.
   - Full-text search and request ID isolation.
   - Secret & PII auto-redaction before events enter the buffer.

---

## 2. Health Checks & Diagnostic Endpoints

| Endpoint | Method | Role | Description |
|---|---|---|---|
| `/api/v1/health` | GET | Public | Shallow liveness probe verifying PostgreSQL and Redis socket connectivity. |
| `/api/v1/observability/stats` | GET | Admin | System telemetry, vitals, table row inventory, AI token usage, costs, and coupon stats. |
| `/api/v1/observability/traces` | GET | Admin | Paginated distributed execution traces with multi-factor filtering. |
| `/api/v1/observability/security-summary` | GET | Admin | 24-hour security summary of critical threats and blocked replays. |
| `/api/v1/observability/logs` | GET | Admin | Queryable live log stream with level, search, and `request_id` filters. |
| `/api/v1/observability/audit-stream` | GET | Admin | Paginated immutable audit trail of operational decisions. |

---

## 3. Runbook: Incident Triage & Live Production Debugging

### Symptom 1: Spike in Escalated Tickets
1. Navigate to `/#observability`.
2. Review the **Fraud & Security Intelligence** tab for prompt injection detections and critical events.
3. In the **System Logs** tab, select **Level: WARNING** and search for `guardrail` or `adversarial`.
4. If an adversarial campaign is detected, retrieve the originating `customer_id` or `request_id` from the log entry and verify associated audit records in `/audit-stream`.

### Symptom 2: Stuck or Degraded Actions
1. In the **Infrastructure & Vitals** tab, inspect table row counts and queue distribution.
2. In the **System Logs** tab, filter by component `app.services.action_service`.
3. Check for Maker-Checker violations (`action.proposed_by_id == reviewer.id`) or concurrency lock timeouts.
4. Supervisors can review pending actions directly in the standard queue interface under the **Supervisor Review** tab.

### Symptom 3: Duplicate Coupon Replay Warning
1. Open the **Fraud & Security Intelligence** tab.
2. Inspect the **Duplicate Replay Blocks** card.
3. When concurrent requests attempt to redeem the same coupon across different orders, the system automatically accepts one and auto-closes the competing ticket with `duplicate_coupon_rejected` and `risk_level: critical`.

---

## 4. Evaluation Benchmark Suite (Zero Forged Numbers)

TrustDesk includes a standalone evaluation benchmark script that evaluates real triage accuracy, citation coverage, unsafe-action blocking, and escalation behavior against live services and database records:

```bash
# Run locally:
python backend/test_eval_metrics.py

# Or inside container:
docker compose exec api python test_eval_metrics.py
```

### Measured Dimensions:
- **Triage Accuracy**: Measures classification accuracy across all evaluation scenarios.
- **Citation Grounding Coverage**: Validates that grounded queries cite authoritative knowledge base chunks and verifies 0% adversarial citation leakage.
- **Unsafe-Action Blocking Rate**: Verifies 100% interception of prompt injection, over-refund limits (422), closed-ticket action blocks (400), human approval gating, web exploits (SQLi, XSS), and concurrency replay abuse (409).
- **Escalation Behavior Accuracy**: Asserts that all high-risk, security, legal, or ambiguous tickets are routed to senior queues, while routine tickets proceed through standard workflows.

---

## 5. Live Idempotency & Concurrency Verification Runbook

To verify concurrent coupon redemption isolation in a running cluster:

1. **Launch Live Verification**:
   ```bash
   python backend/tests/test_live_idempotency.py
   ```
2. **Interactive Flow**:
   - The test script inserts a sample damaged-order ticket into the database.
   - It outputs the Ticket ID and pauses with a 2-second polling loop.
   - An operator opens the TrustDesk workspace UI, selects the ticket, and clicks **Issue Refund**.
   - The script immediately detects the newly issued coupon code (`SWIGGY-REF-XXXXXXXX`).
   - It fires two simultaneous requests (`asyncio.gather`):
     - Request 1 attempts redemption on Order A.
     - Request 2 attempts redemption on Order B.
   - Order A succeeds (`201 Created` or `is_replay=False`).
   - Order B is strictly rejected with `409 Conflict` (`COUPON_ALREADY_REDEEMED`).
   - Replaying Request 1 with the identical idempotency key returns `is_replay=True`.

---

## 6. Demo Queue Reset & Maintenance

When resetting the demonstration environment for testing:

```bash
# Cleanly flush all tickets, drafts, messages, and coupons without dropping tables:
python backend/seed_demo_tickets.py --clear

# Seed fresh 16-scenario demo suite:
python backend/seed_demo_tickets.py
```
