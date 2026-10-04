# Security Architecture and Threat Mitigation

This document details the security controls, cryptographic standards, and threat mitigations implemented across the TrustDesk platform.

---

## 1. Secrets Management Subsystem

TrustDesk decouples application code from runtime credentials using a tiered `SecretsManager` (`backend/app/core/secrets.py`):

```
+-------------------------------------------------------------------+
|                        SecretsManager                             |
|                                                                   |
|   1. Environment Provider (Container / OS Environment)            |
|      ▲                                                            |
|      │ Fallback if key is missing or unconfigured                 |
|   2. Encrypted Provider (Fernet / AES-256 with Master Key)        |
+-------------------------------------------------------------------+
```

- **Pluggable Architecture**: Implements `BaseSecretsProvider`, allowing integration with external KMS providers (such as AWS Secrets Manager or HashiCorp Vault) or encrypted local keystores.
- **Fail-Fast Initialization**: In production (`ENVIRONMENT=production`), failure to decrypt the encrypted keystore raises a `RuntimeError` on startup to prevent running with incomplete configuration.
- **Credential Masking**: String representations of the secrets manager mask secret values in memory and application logs.
- **Configuration Templates**: The repository provides unpopulated `.env.example` templates containing configuration descriptions without committed credentials.

---

## 2. Authentication and Cryptographic Controls

### 2.1 First-Admin Dynamic Onboarding
- **Uninitialized Baseline**: On initial deployment, the primary administrator account remains uninitialized (`mfa_setup_completed = False`, `is_primary_admin = False`).
- **Dynamic Email Registration**: The onboarding workflow requires the operator to provide an administrative email address.
- **One-Time Password Verification**: The backend generates a 6-digit OTP, sends it to the provided address, and validates it via `POST /api/v1/auth/setup-first-admin` before elevating the account to primary administrator.

### 2.2 One-Time Password (OTP) Protection
- **HMAC-SHA256 Storage**: OTP codes stored in Redis are hashed using HMAC-SHA256 with `JWT_SECRET` as the key.
- **Constant-Time Verification**: OTP verification uses `hmac.compare_digest` to mitigate timing analysis side-channels.
- **Rate-Limiting**: Enforces a 30-second cooldown between resend requests and locks out verification after 5 consecutive failed attempts.
- **Persistence Availability**: In production environments, if Redis is unavailable, the authentication subsystem fails closed (`HTTP 503 Service Unavailable`).

### 2.3 Cross-Site Request Forgery (CSRF) Mitigation
- State-changing browser requests (`POST`, `PUT`, `DELETE`, `PATCH`) require an `X-CSRF-Token` header matching a cryptographically generated `csrf_token` cookie.
- If a request lacks a Bearer token and does not provide a CSRF cookie, the middleware rejects it with `403 Forbidden`.
- Bearer-authenticated API calls are exempt from the double-submit cookie requirement.

### 2.4 Transport Security & HTTP Headers
- **HTTPS Enforcement**: Inbound HTTP requests redirect to `https://` with status 301.
- **HSTS**: Includes `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`.
- **Standard Security Headers**: Includes `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, and `Content-Security-Policy`.

---

## 3. Voucher Concurrency Control and Replay Mitigation

The platform manages the voucher lifecycle to prevent double-spending and race conditions:

1. **Cryptographic Voucher Minting**: Voucher codes (`TRUST-REF-XXXXXXXX`) are generated on the server using cryptographically secure pseudorandom tokens.
2. **Account Binding**: Each voucher is linked to a specific `customer_id`. Redemptions by mismatched customer accounts return `403 Forbidden` (`COUPON_ACCOUNT_MISMATCH`).
3. **Row-Level Concurrency Isolation**:
   - Redemptions execute `SELECT ... FROM coupons WHERE code = :code FOR UPDATE`.
   - Concurrent requests are serialized at the database transaction level.
4. **Duplicate Redemption Handling**:
   - If concurrent transactions attempt to redeem the same voucher across different orders, exactly one transaction succeeds (`201 Created`).
   - Competing transactions receive `409 Conflict` (`COUPON_ALREADY_REDEEMED`), and the associated ticket is resolved as `duplicate_coupon_rejected`.
5. **Single Issuance Invariant**:
   - Only one refund voucher may be generated per ticket or order.
   - Subsequent issuance attempts return `409 Conflict` (`REFUND_COUPON_ALREADY_ISSUED`) and preserve the existing voucher.

---

## 4. Web Application Threat Mitigation

Inbound ticket creation is sanitized against standard web application vulnerabilities:
- Inbound subjects and messages containing SQL injection (`' OR 1=1 --`), Cross-Site Scripting (`<script>`, `javascript:`), Path Traversal (`../../etc/passwd`), Null Byte injection (`%00`), or command injection patterns are rejected with `HTTP 400 Bad Request` (`SECURITY_ATTACK_BLOCKED`).
- The system persists an auto-closed record (`status: resolved`, `close_reason: security_attack_blocked: <vector>`) and logs an audit record for security review.

---

## 5. Adversarial Input Fencing and Guardrails

TrustDesk screens conversational inputs and generated drafts (`app/services/guardrail_service.py`):
1. **Protocol Delimiter Detection**: Identifies delimiter patterns such as `<|im_start|>`, `[SYSTEM_PROMPT]`, `<<SYS>>`, and image-based data exfiltration patterns (`![exfil](https://attacker.com/...)`).
2. **Roleplay & Authority Usurpation**: Identifies prompt patterns that attempt to simulate administrative authority or override system instructions.
3. **PII Redaction**: Redacts sensitive personal information (such as phone numbers, email addresses, and national identifiers) from inbound text and drafts before model processing and long-term logging.

---

## 6. Ticket Assignment Concurrency Control

- Simultaneous ticket claims in the Open Queue use database row locking (`SELECT ... FROM tickets WHERE id = :id FOR UPDATE`).
- The first transaction to acquire the lock updates the ticket status to `working` with the claiming operative as assignee.
- Subsequent transactions evaluate the current assignee:
  - If the requesting operative is already the assignee, the request returns `200 OK` idempotently.
  - If assigned to another operative, the request returns `409 Conflict` without modifying the existing assignment.

---

## 7. Quality Defect Routing and Triage Boundaries

- Inbound tickets containing defect indicators (such as `spoil`, `rancid`, `sour`, `curdle`, `rotten`, `inedible`, `damage`, `spill`, `burst`, `missing`, `refund`) receive a minimum risk score of 35 (`Medium Risk`).
- The automated background worker does not auto-resolve tickets flagged with defect indicators.
- Defect tickets remain in the Open Queue for operative review, validation, and policy compliance handling.
