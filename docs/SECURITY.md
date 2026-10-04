# TrustDesk Security Architecture & Vulnerability Mitigation

This document details the enterprise security controls, cryptographic standards, and business logic vulnerability mitigations implemented across TrustDesk.

---

## 1. Secrets Management Subsystem

TrustDesk separates application source code from sensitive runtime credentials using a dedicated, pluggable `SecretsManager` (`backend/app/core/secrets.py`):

```
+-------------------------------------------------------------------+
|                        SecretsManager                             |
|                                                                   |
|   1. Environment Provider (OS Variables / Container Env)          |
|      ▲                                                            |
|      │ Fallback if key missing or unconfigured                    |
|   2. Encrypted Provider (Fernet / AES-256 with Master Key)        |
+-------------------------------------------------------------------+
```

- **Pluggable Architecture**: Implements `BaseSecretsProvider` interface, allowing plug-and-play integration with AWS Secrets Manager, HashiCorp Vault, or encrypted local vaults.
- **Fail-Fast in Production**: In production mode (`ENVIRONMENT=production`), failure to decrypt the encrypted secrets store raises a `RuntimeError` immediately rather than silently falling back to insecure defaults.
- **Zero Plaintext Leakage**: The manager redacts credentials in string representations (`<SecretsManager: secured>`) and provides a `mask_secret` utility (`supe...21`) for safe display in administrative dashboards.
- **Repository Hygiene**: Repositories ship with clean, unpopulated `.env.example` templates containing comprehensive documentation and zero active credentials, personal passwords, or hardcoded API keys.

---

## 2. Authentication & Cryptography Hardening

### 2.1 First-Admin Dynamic Onboarding
- **Uninitialized Root State**: On initial startup, the primary administrator account is uninitialized (`mfa_setup_completed = False`, `is_primary_admin = False`).
- **Dynamic Email Binding**: The onboarding flow requires an administrator to enter a new operational email address.
- **Email OTP Verification**: The backend dispatches a cryptographic 6-digit OTP code to the provided email address, verifies the code via `POST /api/v1/auth/setup-first-admin`, establishes the root credentials, and marks `is_primary_admin = True`.
- **Zero Pre-Filled Admin Credentials**: No hardcoded or pre-bound administrative email addresses are assumed by the frontend or backend.

### 2.2 Zero-Plaintext One-Time Passwords (OTP)
- **HMAC-SHA256 Storage**: Rather than storing OTP codes in plaintext inside Redis or memory, codes are cryptographically hashed using HMAC-SHA256 keyed with `JWT_SECRET`.
- **Timing-Safe Comparison**: Verification utilizes constant-time `hmac.compare_digest` to eliminate timing side-channel attacks.
- **Rate-Limiting & Lockout**: Enforces a strict 30-second resend cooldown and locks out verification after 5 consecutive incorrect attempts.
- **Split-Brain Prevention**: In production, if Redis is unavailable, the authentication subsystem fails fast with HTTP 503 instead of falling back to per-process in-memory stores.

### 2.3 Double-Submit Cookie CSRF Defense
- State-modifying requests (`POST`, `PUT`, `DELETE`, `PATCH`) originating from browsers require an `X-CSRF-Token` header that matches the cryptographically random `csrf_token` cookie.
- **Mandatory Cookie Enforcement**: If a request without a Bearer token lacks the `csrf_token` cookie, the middleware rejects the request with `403 CSRF_COOKIE_MISSING` before inspection.
- Programmatic API requests providing `Authorization: Bearer <token>` headers are safely exempted.

### 2.4 HTTPS / TLS & Transport Security
- **HTTPS Enforcement**: Requests arriving over unencrypted HTTP are redirected with HTTP 301 to `https://`.
- **HSTS**: `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload` header guarantees browser transport encryption.
- **Security Headers**: Standard response headers include `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, and `Content-Security-Policy`.

---

## 3. Pure Server-Side Coupon Concurrency & Replay Defense

TrustDesk enforces strict server-side authority over refund coupons:

1. **Cryptographic Server Minting**: Coupon codes (`SWIGGY-REF-XXXXXXXX`) are generated exclusively on the backend via cryptographically secure random tokens.
2. **Account Ownership Binding**: Each coupon is strictly bound to `customer_id`. Redeeming a coupon issued to another customer is rejected with `HTTP 403 Forbidden` (`COUPON_ACCOUNT_MISMATCH`).
3. **Row-Level Concurrency Isolation**:
   - Redemptions execute `SELECT ... FROM coupons WHERE code = :code FOR UPDATE`.
   - Per-coupon async locks serialize concurrent attempts.
4. **Duplicate Abuse Auto-Closure**:
   - If two tickets for different orders attempt to redeem the same coupon concurrently, exactly one ticket succeeds (`201 Created`).
   - The competing request receives `HTTP 409 Conflict` (`COUPON_ALREADY_REDEEMED`).
   - The competing ticket is automatically persisted in the database as **auto-closed** (`status: resolved`, `close_reason: duplicate_coupon_rejected`, `coupon_abuse_flag: True`, `risk_level: critical`).
5. **Single Coupon Issuance per Ticket**:
   - Only one refund coupon may be issued per ticket or order.
   - Any secondary issuance attempt returns `HTTP 409 Conflict` (`REFUND_COUPON_ALREADY_ISSUED`) and preserves the existing coupon.

---

## 4. Non-AI Web Security Attack Auto-Closure

Inbound ticket creation is fenced against web exploits:
- Inbound subjects and messages containing SQL injection (`' OR 1=1 --`, `UNION SELECT`), Cross-Site Scripting (`<script>`, `javascript:`), Path Traversal (`../../etc/passwd`), Null Byte injection (`%00`), Command injection (`; rm -rf`), or SSRF payloads are rejected with `HTTP 400 Bad Request` (`SECURITY_ATTACK_BLOCKED`).
- The system automatically creates a critical auto-closed ticket in the database (`status: resolved`, `close_reason: security_attack_blocked: <vector>`, `risk_level: critical`), records structured audit logs, and alerts administrators.

---

## 5. Adversarial Input Fencing & Guardrails

TrustDesk intercepts inbound and outbound conversational payloads (`app/services/guardrail_service.py`):
1. **Protocol Breakout Detection**: Detects delimiter tokens such as `<|im_start|>`, `[SYSTEM_PROMPT]`, `<<SYS>>`, and markdown image exfiltration payloads (`![exfil](https://attacker.com/...)`).
2. **Identity & Authority Usurpation**: Neutralizes roleplay prompts attempting to masquerade as platform executives, system administrators, or support supervisors.
3. **PII Scrubbing**: Inbound tickets and generated drafts are automatically sanitized to remove phone numbers, email addresses, and national identity numbers before external persistence or model transit.

---

## 6. Idempotent Ticket Assignment & Race Condition Defense

- When multiple operatives navigate the Open Queue and attempt to claim or assign the same ticket simultaneously, backend routing acquires a row lock (`SELECT ... FROM tickets WHERE id = :id FOR UPDATE`).
- If Operative A locks the ticket first, it transitions to `working` assigned to Operative A.
- When Operative B's request executes, the backend verifies existing assignment:
  - If already assigned to the requesting operative, the call succeeds idempotently.
  - If assigned to another operative, Operative B receives `HTTP 409 Conflict` (`Ticket is already assigned to {Operative A}`) without overwriting assignment state.

---

## 7. Food Quality & Defect Safety Barrier

- Inbound tickets containing defect indicators (e.g. `spoil`, `rancid`, `sour`, `curdle`, `rotten`, `inedible`, `damage`, `spill`, `burst`, `missing`, `refund`) are forced to a minimum risk score of 35 (`Medium Risk`).
- The AI background worker is strictly forbidden from auto-resolving or auto-closing quality defect tickets.
- Defect tickets remain in the Open Queue for human agent review, physical inspection validation, and policy compliance verification.
