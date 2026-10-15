# TrustDesk

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19.2%2B-61DAFB.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6.svg)](https://www.typescriptlang.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20%2B%20pgvector-336791.svg)](https://github.com/pgvector/pgvector)
[![Redis](https://img.shields.io/badge/Redis-7.x-DC382D.svg)](https://redis.io/)

TrustDesk is an AI-assisted customer support operations platform designed for high-concurrency food delivery workflows. The platform integrates policy-grounded response generation, deterministic risk classification, human-in-the-loop approval workflows, and adversarial input fencing into a unified agent workspace.

---

## Table of Contents

- [System Overview](#system-overview)
- [System Architecture](#system-architecture)
- [Key Features](#key-features)
- [Technology Stack](#technology-stack)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Running with Docker Compose](#running-with-docker-compose)
  - [Local Development Setup](#local-development-setup)
  - [Environment Configuration](#environment-configuration)
- [Operational Workflows](#operational-workflows)
  - [Initial Administrator Setup](#initial-administrator-setup)
  - [Ticket Queue Management](#ticket-queue-management)
  - [Draft Generation and Citation Verification](#draft-generation-and-citation-verification)
  - [Approval Gating for Sensitive Actions](#approval-gating-for-sensitive-actions)
  - [Coupon Lifecycle and Concurrency Controls](#coupon-lifecycle-and-concurrency-controls)
  - [Automated Resolution and Escalation Boundaries](#automated-resolution-and-escalation-boundaries)
- [Observability and Telemetry](#observability-and-telemetry)
- [Evaluation Benchmark](#evaluation-benchmark)
- [API Reference](#api-reference)
- [Related Documentation](#related-documentation)

---

## System Overview

Large language models in automated customer operations introduce risks such as hallucinated policies, unauthorized concessions, and vulnerability to prompt injection. TrustDesk addresses these issues by decoupling generative text synthesis from business logic and transactional actions:

- **Policy Grounding**: Draft responses are generated strictly from authoritative policy documents indexed in PostgreSQL using `pgvector`. When retrieved context is insufficient, requests fall back to human intervention.
- **Controlled Action Execution**: AI services recommend operational actions, but execution is governed by deterministic business rules. High-risk actions (such as refunds and replacement orders) require supervisor review.
- **Transactional Integrity**: Financial operations, including refund coupon generation and redemption, are isolated using row-level database locks (`SELECT ... FOR UPDATE`) and composite idempotency keys.
- **Deterministic Time Windows**: Return and policy eligibility periods are evaluated against ticket creation timestamps rather than runtime execution clocks to ensure consistent outcomes.
- **Input and Output Security**: Input guardrails detect prompt injection, protocol delimiter tampering, and common web application attacks (SQL injection, XSS) before LLM or database processing.

---

## System Architecture

TrustDesk uses an asynchronous, service-oriented architecture:

```mermaid
flowchart TD
    subgraph ClientLayer["Client Layer (React / TypeScript SPA)"]
        AgentUI["Agent Operations Console"]
        AdminUI["Observability & Diagnostics Console"]
        CustUI["Customer Portal"]
    end

    subgraph Gateway["Perimeter & Middleware"]
        ReverseProxy["HTTPS / Security Headers"]
        CSRF["Double-Submit CSRF Middleware"]
        TraceContext["Request ID Correlation"]
    end

    subgraph BackendAPI["FastAPI Application Services"]
        AuthSvc["Authentication & MFA Service"]
        TicketSvc["Ticket Lifecycle & Event Streaming"]
        ApprovalSvc["Action Approval Service"]
        CouponSvc["Coupon & Concurrency Service"]
        TelemetrySvc["Observability & Logging Service"]
        GuardrailSvc["Input Fencing & Redaction"]
    end

    subgraph Workers["Asynchronous Worker Pipeline (ARQ)"]
        TriageWorker["Triage & Classification"]
        DraftWorker["RAG Draft Generation"]
        ActionWorker["Action Execution"]
    end

    subgraph DataStore["Data & State Persistence"]
        Postgres[("PostgreSQL 16 + pgvector")]
        Redis[("Redis 7 (Queues, Locks, Cache)")]
        Secrets[("Secrets Management Subsystem")]
    end

    ClientLayer --> Gateway
    Gateway --> BackendAPI
    BackendAPI --> GuardrailSvc
    BackendAPI --> DataStore
    BackendAPI -->|Enqueue Jobs| Workers
    Workers --> DataStore
```

---

## Key Features

### Ticket Lifecycle States
Tickets transition through four deterministic states:
- **Open**: New inbound tickets awaiting review or automated triage.
- **Working**: Claimed by an operative for active investigation, assisted drafting, and order tracking.
- **Escalated**: Flagged for supervisor review due to risk scores, policy ambiguity, or explicit transfer.
- **Resolved**: Completed tickets with immutable resolution notes and audit records.

### Domain Context Integration
Each ticket is automatically enriched with relevant food delivery context:
- Customer profile, tier status (e.g., Standard, Pro Tier), and interaction history.
- Order metadata: restaurant information, kitchen preparation state, delivery partner details, and itemized receipts.
- Real-time fulfillment telemetry: live delivery status, transit delays, and payment details.

### Security and Governance
- **Maker-Checker Protocol**: Operatives cannot approve their own proposed sensitive actions (`proposed_by_id != approver_id`).
- **Cumulative Refund Caps**: Validation rules ensure total refunds for an order never exceed the original transaction value.
- **Concurrency Isolation**: Database-level locks prevent race conditions during simultaneous coupon redemptions or ticket claims.

---

## Technology Stack

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Backend API** | Python 3.11+, FastAPI, Pydantic v2 | High-throughput asynchronous REST API |
| **Database** | PostgreSQL 16 + pgvector | Relational schema and vector similarity index |
| **ORM** | SQLAlchemy 2.0 (asyncpg), Alembic | Asynchronous persistence and schema migrations |
| **Cache & Task Queue** | Redis 7, ARQ | Background task processing, distributed locks, rate limiting |
| **AI Integration** | OpenRouter API, Abstract Provider Adapter | Multi-model routing with deterministic mock support for testing |
| **Frontend** | React 19, TypeScript 5, Vite, Tailwind CSS | Modular, accessible single-page application |
| **Testing** | pytest, pytest-asyncio, vitest | Unit, integration, and end-to-end evaluation suites |

---

## Getting Started

### Prerequisites
- [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/) v2+
- For local manual development: Python 3.11+, Node.js 20+, PostgreSQL 16 with pgvector, Redis 7

### Running with Docker Compose

1. **Clone the repository**:
   ```bash
   git clone https://github.com/0x76hack/TrustDesk.git
   cd TrustDesk
   ```

2. **Start the containers**:
   ```bash
   docker compose up --build -d
   ```
   This command starts:
   - PostgreSQL (pgvector) on port `5433` (mapped from `5432`)
   - Redis on port `6379`
   - FastAPI backend on port `8000`
   - ARQ background worker
   - Frontend application on port `5173`

3. **Initialize the database and knowledge base**:
   ```bash
   docker compose exec api python init_db.py
   ```

4. **Seed demonstration tickets**:
   ```bash
   docker compose exec api python seed_demo_tickets.py
   ```

5. **Access the application**:
   Open `http://localhost:5173` in your browser.

---

### Local Development Setup

#### Backend Setup
```bash
cd backend
python -m venv venv

# Windows
.\venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
cp ../.env.example .env

# Initialize database schema and policy documents
python init_db.py

# Seed sample tickets
python seed_demo_tickets.py

# Start the development server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

---

### Environment Configuration

Configuration templates are available in `.env.example`. Key settings include:

| Variable | Description | Default / Example |
| :--- | :--- | :--- |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://trustdesk:trustdesk_secret@localhost:5433/trustdesk` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `JWT_SECRET` | Secret key for signing session tokens | 32+ character random string |
| `OPENROUTER_API_KEY` | OpenRouter API key for live inference | Optional (falls back to mock provider if empty) |
| `SMTP_HOST`, `SMTP_PORT` | SMTP server settings for OTP delivery | `localhost`, `1025` |

---

## Operational Workflows

### Initial Administrator Setup
1. Open the application at `http://localhost:5173`.
2. On initial deployment, choose **Register First Admin**.
3. Provide your administrative email, name, and password.
4. Verify the 6-digit one-time password (OTP) sent to your email to initialize root privileges.

### Ticket Queue Management
- Inbound tickets are routed to the **Open** queue.
- Selecting **Assign to Me** updates the ticket to **Working** status. Database-level locking prevents duplicate assignments if multiple agents claim the same ticket simultaneously.
- The context panel displays live fulfillment telemetry, delivery partner status, and order details.

### Draft Generation and Citation Verification
- Selecting **Generate Draft** triggers context retrieval via `pgvector` and draft synthesis via the LLM pipeline.
- All drafted responses include verifiable policy citations (e.g., `[KB-SHIPPING-001]`, `[KB-REFUND-001]`).
- If evidence is below the required relevance threshold, the system automatically routes the ticket to the escalated queue for manual drafting.

### Approval Gating for Sensitive Actions
- Sensitive tool actions (e.g., `start_refund_review`, `create_replacement_order`) enter a `pending_approval` state.
- Supervisors review and act on pending items in the **Supervisor Review** section.
- Actions cannot be approved by the agent who initiated them.

### Coupon Lifecycle and Concurrency Controls
- When a refund is approved, a voucher code (`TRUST-REF-XXXXXXXX`) is generated and linked to the customer account.
- The conversation view renders a dedicated voucher card with a one-click copy utility.
- Concurrent redemption requests on the same coupon are serialized via `SELECT ... FOR UPDATE`; subsequent redemptions are rejected with `409 Conflict`.

### Automated Resolution and Escalation Boundaries
- **Automated Processing**: Standard informational inquiries (such as membership terms, live delivery tracking, weather delays) are resolved automatically with policy citations.
- **Human Routing**: Tickets involving meal defects, damaged packaging, missing items, or cancellation requests are routed to human operatives with an assigned risk tier.

---

## Observability and Telemetry

Administrative users can access the system telemetry console via the **Diagnostics** navigation link or `/#observability`:

1. **Infrastructure Health**: Real-time ping latency for PostgreSQL and Redis, host memory, CPU utilization, uptime, and database row counts.
2. **Model Metrics**: Inference counts, token usage (prompt and completion), estimated compute costs, and percentile latency distributions (p50, p90, p95, p99) per model.
3. **Distributed Tracing**: Searchable trace records across triage, draft, and action workflows with token usage, duration, and guardrail verdicts.
4. **Security Events**: Coupon redemption statistics, blocked replay attempts, and logged security interventions.
5. **System Logs**: Live circular buffer (1,000 recent events) supporting level filtering, search, and request ID correlation.

---

## Evaluation Benchmark

TrustDesk includes an automated evaluation benchmark that measures classification, grounding, safety, and escalation against a standardized dataset:

```bash
# Run locally
python backend/test_eval_metrics.py

# Run via Docker
docker compose exec api python test_eval_metrics.py
```

### Metrics Evaluated:
- **Triage Accuracy**: Measures accuracy of category and priority classification against the evaluation corpus.
- **Citation Grounding**: Evaluates citation precision against authoritative documents and verifies zero citation leakage from adversarial knowledge base entries.
- **Unsafe-Action Interception**: Verifies blocking of prompt injections, cumulative refund cap violations (422), closed-ticket mutations (400), and duplicate redemptions (409).
- **Escalation Accuracy**: Asserts correct routing of high-risk, ambiguous, or safety-flagged cases to human review queues.

---

## API Reference

Interactive OpenAPI documentation is available at `http://localhost:8000/docs`.

### Authentication (`/api/v1/auth`)
| Method | Endpoint | Description | Access |
| :--- | :--- | :--- | :---: |
| `GET` | `/api/v1/auth/setup-status` | Check if primary admin is configured | Public |
| `POST` | `/api/v1/auth/send-first-admin-otp` | Request initial administrator registration OTP | Public |
| `POST` | `/api/v1/auth/setup-first-admin` | Complete initial administrator registration | Public |
| `POST` | `/api/v1/auth/login` | Authenticate staff member and receive JWT | Public |
| `POST` | `/api/v1/auth/mfa/verify` | Verify email OTP code | Public |

### Ticket Operations (`/api/v1/tickets`)
| Method | Endpoint | Description | Access |
| :--- | :--- | :--- | :---: |
| `GET` | `/api/v1/tickets` | List tickets with pagination and filtering | Staff |
| `GET` | `/api/v1/tickets/{id}` | Retrieve ticket details, order context, and messages | Staff |
| `POST` | `/api/v1/tickets` | Create a new ticket with guardrail validation | Public / Staff |
| `POST` | `/api/v1/tickets/{id}/assign` | Claim ticket assignment | Staff |
| `POST` | `/api/v1/tickets/{id}/escalate` | Escalate ticket to supervisor queue | Staff |
| `POST` | `/api/v1/tickets/{id}/close` | Resolve ticket and cancel pending actions | Staff |
| `POST` | `/api/v1/tickets/{id}/refund` | Issue refund coupon | Staff |
| `GET` | `/api/v1/tickets/{id}/draft/stream` | Stream draft response via Server-Sent Events | Staff |

### Observability & Admin (`/api/v1/observability`, `/api/v1/admin`)
| Method | Endpoint | Description | Access |
| :--- | :--- | :--- | :---: |
| `GET` | `/api/v1/observability/stats` | System vitals, table counts, and model metrics | Admin |
| `GET` | `/api/v1/observability/traces` | Paginated execution traces with filtering | Admin |
| `GET` | `/api/v1/observability/security-summary` | Summary of blocked threats and incidents | Admin |
| `GET` | `/api/v1/observability/logs` | Queryable live log stream | Admin |
| `GET` | `/api/v1/admin/users` | List staff accounts | Admin |
| `POST` | `/api/v1/admin/users` | Provision new staff account | Admin |

---

## Areas for Extension and Learner Improvement

TrustDesk provides a production-grade baseline for safe, grounded customer operations with dense vector retrieval, guardrail fencing, and approval gating. Learners exploring or extending this architecture can build upon the system across several high-impact dimensions:

1. **Dynamic Embedding Fine-Tuning & Cross-Encoder Re-Ranking**:
   - While TrustDesk currently performs dense vector similarity search via PostgreSQL `pgvector` (`KBChunk.embedding <=> query_vector`) coupled with lexical scoring and a calibrated relevance cutoff (`0.35`), learners can implement a second-stage cross-encoder re-ranker (e.g. `bge-reranker-large` or Cohere Rerank). A cross-encoder joint-scores `(query, passage)` pairs, capturing subtle conversational nuances and complex grievance phrasing that dense retrieval alone might score borderline.

2. **Temporal Policy Version Matching**:
   - In production environments, corporate refund and cancellation terms evolve over time. Learners can extend `retrieval_service.py` to match the customer's historical order placed timestamp against `KBDocument.effective_at` and versioning intervals. This ensures that retrospective refund claims are adjudicated strictly against the exact policy terms in effect at the moment the transaction was booked, rather than subsequently modified terms.

3. **Automated Confidence Calibration via Conformal Prediction**:
   - The current triage and risk services score ticket urgency and categorize complaints using model confidence heuristics and weighted risk factors. Learners can apply conformal prediction algorithms to output mathematically bounded confidence intervals (e.g. 95% coverage guarantees), ensuring that automated resolutions are only triggered when the prediction set contains a singleton category with high statistical certainty.

4. **Multi-Modal Damage & Defect Image Inspection**:
   - Food delivery customer support often requires verifying physical food spillage, incorrect items, or carton tampering. Learners can integrate Vision Language Models (e.g. Gemini 1.5 Pro / Flash Vision) directly into the ticket ingestion pipeline to analyze uploaded customer photos against the restaurant's expected packaging standards, calculating tamper confidence scores before human or automated vouchers are granted.

5. **Enterprise Cloud KMS & Secret Vault Backends**:
   - TrustDesk's secrets management layer uses dynamic environment extraction and local encrypted keystores. For enterprise production deployments, learners can extend `manage_secrets.py` and `app/config.py` to integrate natively with hardware-backed Key Management Services (such as AWS KMS, HashiCorp Vault, or Google Cloud KMS) featuring automated cryptographic key rotation, fine-grained IAM resource policies, and immutable HSM access logs.

---

## Related Documentation

- [`ARCHITECTURE.md`](docs/ARCHITECTURE.md): Component topology, hybrid vector search, idempotency design, and concurrency controls.
- [`OPERATIONS.md`](docs/OPERATIONS.md): Operational procedures, observability diagnostics, and troubleshooting runbooks.
- [`SECURITY.md`](docs/SECURITY.md): Threat mitigation, authentication architecture, and secrets management.
