# Week 5 Scratch Pad

## Theme
- **Product polish and reliability**
- **Reporting & Exports**: multi-format, retries, and UX improvements
- **Performance**: DB indexes, pagination polish, caching
- **Security**: finalize audit/retention and review

## Objectives
- **Exports**: Add CSV export for spend/transactions. Improve PDF (branding, page breaks, summaries).
- **Retries**: Add retry/backoff for PDF render + SMTP send; user notifications on failure.
- **Reports**: Monthly/Quarterly spend summaries with comparison deltas.
- **Performance**: Add indexes, paginate everywhere, cache common aggregates.
- **Security & Audit**: Final BOLA sweep, admin-only areas validated, audit dashboards.

## Tasks
- **Exports**
  - API: `GET /v1/spend/export.csv?period=...` and `GET /v1/transactions/export.csv` (owner-scoped).
  - Web: Download buttons; progress UI via Broadcast events.
  - PDF: Improve typography, add cover and per-strategy summary tables.
- **Retries & Robustness**
  - Wrap PDF and SMTP calls with retry (3 attempts, exponential backoff).
  - Persist export job state (queued, rendering, emailing, failed, sent) with timestamps.
  - Send a fallback plaintext email if HTML render fails.
- **Reports**
  - API: `GET /v1/spend/summary?period=monthly|quarterly&compare=true`.
  - Web: Charts with diffs vs previous period; hover tooltips.
- **Performance**
  - Add DB indexes: `transactions_raw(user_id, date)`, `transactions(user_id, id)`, `audit_events(user_id, created_at)`.
  - Cursor-based pagination standardization; ensure stable orderings.
  - Cache `spend/summary` with short TTL; cache-bust on updates.
- **Security & Admin**
  - Final BOLA audit; add more unit tests for edge cases.
  - Admin page for audits with filters; CSV export for audits.
  - Add soft limits and rate-limits for heavy endpoints.

## Acceptance Criteria
- **Exports**: CSV and PDF working with retries; UI status visible; files open correctly.
- **Performance**: P95 latencies under targets; DB scans reduced; charts load fast.
- **Security**: BOLA and admin gating validated by tests.
- **Stability**: No crash loops; retries surface errors usefully.

## Stretch
- **Background workers**: move export pipeline fully async with job queue status API.
- **Scheduled digests**: weekly/monthly email summaries with opt-in.
- **Feature flags**: progressive rollouts for export/report changes.

## Notes
- Keep production secrets out of repo (.env or secret manager).
- Re-run alembic for any new indexes; ensure safe migrations.
