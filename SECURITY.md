# Security Baseline

Updated: 2025-10-30

## Implemented

- **Authentication & Authorization**
  - NextAuth.js with JWT session strategy; providers: Email (magic link), Credentials, Google OAuth, GitHub OAuth.
  - API JWT (HS256) with `sub`, `role`, `exp`; minted via internal `/v1/auth/mint` protected by `X-Internal-Secret`.
  - Admin allowlist via `ADMIN_EMAILS` for role assignment at mint/login.

- **API Security**
  - CORS via FastAPI `CORSMiddleware`; origins from `CORS_ALLOW_ORIGINS`; credentials allowed.
  - Internal-only mint endpoint uses `MINT_TOKEN_SECRET` header.

- **Data Protection & Secrets**
  - Password hashing with bcrypt (passlib) for credentials auth.
  - Secrets managed via environment variables (`.env` and docker-compose); OAuth, JWT, NextAuth, SMTP, Stripe.

- **Payments/Webhooks**
  - Stripe webhook signature verification with `STRIPE_WEBHOOK_SECRET` using `stripe.Webhook.construct_event`.

- **Frontend Security Headers** (apps/web/next.config.js)
  - CSP, HSTS, Referrer-Policy, X-Frame-Options, X-Content-Type-Options, Permissions-Policy.

- **Email Transport Security**
  - SMTP TLS/SSL toggles via `SMTP_USE_TLS` / `SMTP_USE_SSL`; EmailProvider respects secure transport settings.

- **Deployment/Runtime**
  - Docker Compose per-service env isolation; `.env` is git-ignored; minimal build-time env set in CI.

## Planned / Open Items

- **Rate Limiting**
  - Add per-endpoint limits for suggestion runs; add global API rate-limits.

- **Data Retention & Privacy**
  - Retain raw transactions for 90 days; add user delete/export endpoints.

- **App-layer Encryption for PII (AES-GCM)**
  - Encrypt sensitive fields at rest; dev keys via env; production keys via KMS.

- **CSP hardening**
  - Reduce `'unsafe-inline'`/`'unsafe-eval'` allowances where possible; review third‑party sources.
