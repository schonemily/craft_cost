# Security Baseline

- Secrets via environment variables; `.env.example` provided; do not commit real secrets.
- App‑layer encryption for PII (AES‑GCM). Keys are provided via env in dev; plan for KMS in prod.
- Headers: CSP, HSTS, Referrer‑Policy, Permissions‑Policy; secure, HttpOnly, SameSite cookies.
- Logging: JSON logs, redact PII; avoid logging raw payloads; audit key events.
- Rate limiting to be added (Week 4) for suggestion runs; global API rate‑limits later.
- Data retention: raw transactions 90 days; implement delete/export endpoints in Week 5.
