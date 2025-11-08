# Week 4 Scratch Pad

## Theme
- **Security & auth hardening** (BOLA coverage, admin gating, audit depth)
- **Magic link UX**: branded templates, deliverability checks
- **Observability**: consistent app+API logs, minimal metrics
- **Eventing**: Broadcast channel for user-facing export status

## Objectives
- **[auth/bearer]** Ensure all sensitive write endpoints enforce owner/admin checks.
- **[nextauth]** Make email magic-link the primary path, credentials as fallback.
- **[admin]** Guard feature flags and admin endpoints with role checks; surface basic admin UI.
- **[events]** Publish export status over Broadcast channel: queued → rendering → sent/failed.
- **[audit]** Expand audit events and add minimal retention/indices.

## Tasks
- **BOLA & Guards**
  - Expand owner checks to update/delete endpoints as they are added.
  - Add tests covering list filters (`/v1/transactions`, `/v1/debt/export` auth gating, recategorize already added).
  - Ensure `/v1/flags` POST requires admin (done); add admin tests.
- **Magic Link UX**
  - Configure NextAuth email templates with brand styling and site name.
  - Verify MailHog and clickable links; confirm token expiry (1h) works end-to-end.
  - Add success/failure toasts and link resend affordance on `/signin`.
- **Broadcast channel integration**
  - Channel ID: `4e918cb2-f239-4a23-9254-1dd495844ce4`.
  - In `/v1/debt/export`, publish events (best-effort):
    - `export_queued` (debts hash, email target)
    - `export_rendering`
    - `export_email_sent` | `export_failed` (include error)
  - Add small client hook to subscribe and show inline status on Debt page.
- **Audit & retention**
  - Index `audit_events(user_id, created_at)`.
  - Add daily job to cull low-value events after 30/60d if needed (configurable).
- **Admin UI**
  - Minimal page for flags (existing) and read-only audit feed.
  - Add `POST /v1/admin/users/{id}/plan` button (admin-only) in UI.

## Acceptance Criteria
- **BOLA**: Non-owners cannot mutate another user’s transactions; tests pass.
- **Admin gating**: Only admins can toggle flags or plans; tests pass.
- **Magic link**: Email arrives via MailHog with branded template; link works within expiry.
- **Broadcast**: Export flow emits status events; UI shows progress inline.
- **Audit**: New events written; query by `user_id` performant (index exists).

## Risks / Mitigations
- **Email deliverability**: Using MailHog in dev; prod will need SMTP/SES.
- **Eventing reliability**: Broadcast used best-effort; failures should not block core flow.
- **Role escalation**: Keep plan change/admin paths behind admin JWT; log all changes.

## Notes
- Keep Compose and `.env.example` authoritative; no secrets in repo.
- Prefer server-side checks over client-only gating.
