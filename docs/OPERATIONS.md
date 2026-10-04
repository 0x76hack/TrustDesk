# Operations and Runbook Guide

This guide provides operational runbooks, diagnostic procedures, telemetry specifications, and incident response workflows for TrustDesk.

---

## 1. System Observability Console

The administrative console (`/#observability`) provides operational visibility into infrastructure health, model execution, distributed traces, and audit logs. Access requires the `admin` role.

### Telemetry Modules:

1. **Infrastructure Health**:
   - Connection status and ping latency for PostgreSQL (`db_latency_ms`) and Redis (`redis_latency_ms`).
   - Host process RSS memory (`memory_mb`) and Redis memory usage (`redis_memory_mb`).
   - Host CPU utilization (`cpu_percent`) and process uptime.
   - Relational table record counts across core tables (`tickets`, `messages`, `orders`, `customers`, `coupons`, `audit_logs`, `traces`, `kb_chunks`, `users`).

2. **Model Metrics & Token Telemetry**:
   - Aggregate execution count and active model inventory.
   - Token expenditure tracking: prompt, completion, and total tokens.
   - Estimated compute costs calculated per model token rates.
   - Per-model latency percentiles: `p50`, `p90`, `p95`, `p99`, average, minimum, and maximum execution durations.

3. **Distributed Trace Explorer**:
   - Searchable execution traces filtered by `run_type` (`triage`, `draft`, `action`), `risk_level` (`low`, `medium`, `high`, `critical`), `model_used`, and `ticket_id`.
   - Displays execution latency, token counts, guardrail evaluations, retrieved policy references, and completion status.

4. **Security & Voucher Tracking**:
   - Voucher status metrics: total issued, active, redeemed, expired, and cumulative refund value.
   - Counters for duplicate redemption attempts blocked by concurrency controls.
   - Logged security events, including prompt injection attempts and authentication failures.

5. **System Log Stream**:
   - In-memory circular buffer (`MemoryRingBufferHandler`) retaining the most recent 1,000 log records.
   - Filterable by level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) and correlation search (`request_id`, component name).
   - Automatic redaction of credentials, authorization tokens, and OTP codes.

---

## 2. Health and Diagnostic Endpoints

| Endpoint | Method | Role | Description |
| :--- | :--- | :--- | :--- |
| `/api/v1/health` | GET | Public | Liveness probe verifying PostgreSQL and Redis socket connectivity. |
| `/api/v1/observability/stats` | GET | Admin | System vitals, table counts, model usage, and voucher summary. |
| `/api/v1/observability/traces` | GET | Admin | Paginated execution traces with multi-field filtering. |
| `/api/v1/observability/security-summary` | GET | Admin | Summary of security events and blocked duplicate operations. |
| `/api/v1/observability/logs` | GET | Admin | Live log buffer supporting level and search filters. |
| `/api/v1/observability/audit-stream` | GET | Admin | Paginated audit trail of administrative and supervisor actions. |

---

## 3. Incident Response Runbooks

### Runbook A: Elevated Escalation Rate
1. Access the diagnostics console at `/#observability`.
2. Inspect the **Security** tab to verify whether an adversarial prompt injection campaign is active.
3. In the **System Logs** view, filter by `WARNING` or `ERROR` and search for `guardrail` or `retrieval`.
4. If policy retrieval scores are below the confidence threshold, inspect the Knowledge Base document index for missing or outdated policy documents.

### Runbook B: Action Execution Failures
1. Inspect the **System Logs** filtering by component `app.services.action_service`.
2. Check for Maker-Checker violations (`proposed_by_id == approver_id`) or lock acquisition timeouts.
3. Verify that the supervisor reviewing the action has appropriate permissions and is distinct from the initiating agent.

### Runbook C: Concurrent Voucher Collision
1. In the **Security** tab, monitor the **Duplicate Replay Blocks** counter.
2. When concurrent redemption requests target the same voucher across different orders, row-level locking ensures only the first request succeeds.
3. The competing transaction receives `409 Conflict`, and the secondary ticket is updated with resolution status `duplicate_coupon_rejected`.

---

## 4. Evaluation Suite Execution

The repository provides an automated evaluation runner to validate classification, citation grounding, guardrail interception, and escalation logic against standard test scenarios:

```bash
# Local execution
python backend/test_eval_metrics.py

# Container execution
docker compose exec api python test_eval_metrics.py
```

### Evaluated Dimensions:
- **Triage Accuracy**: Classification accuracy of ticket category and priority against expected baselines.
- **Citation Grounding**: Accuracy of policy citations and verification that adversarial documents are excluded from grounded outputs.
- **Unsafe-Action Interception**: Verification of rejection rules for prompt injections, cumulative refund cap violations (422), closed-ticket mutations (400), and duplicate redemptions (409).
- **Escalation Precision**: Verification that high-risk, ambiguous, or security-sensitive tickets route to supervisor queues.

---

## 5. Concurrency Verification Procedure

To verify concurrent voucher redemption isolation in a test environment:

1. **Start the verification script**:
   ```bash
   python backend/tests/test_live_idempotency.py
   ```
2. **Procedure**:
   - The script creates a test ticket requiring a refund and outputs the Ticket ID.
   - An operator opens the workspace UI, selects the ticket, and approves the refund.
   - The script detects the issued voucher code (`TRUST-REF-XXXXXXXX`).
   - The script executes two simultaneous redemption requests via `asyncio.gather`:
     - Request 1 targets Order A.
     - Request 2 targets Order B.
   - Verification checks:
     - Exactly one request receives `201 Created`.
     - The competing request receives `409 Conflict` (`COUPON_ALREADY_REDEEMED`).
     - A replayed request using the identical idempotency key returns the cached result with `Idempotent-Replay: true`.

---

## 6. Test Data Management

To reset or seed test tickets in non-production environments:

```bash
# Clear tickets, messages, drafts, and vouchers while preserving schema and knowledge base:
python backend/seed_demo_tickets.py --clear

# Seed standard test scenarios:
python backend/seed_demo_tickets.py
```
