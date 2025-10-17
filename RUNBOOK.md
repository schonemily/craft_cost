# Runbook

## Services
- Web (Next.js) – port 3000
- API (FastAPI) – port 8000
- Worker (RQ) – background jobs
- PDF (Node) – port 4000 (placeholder)
- Postgres – port 5432
- Redis – port 6379
- MinIO – ports 9000/9001
- MailHog – port 8025

## Common Tasks
- Start: `npm run dev`
- Stop: `npm run down`
- Migrate DB: `npm run migrate`

## Webhook endpoints (to be added)
- Plaid: `/v1/plaid/webhook`
- Stripe: `/v1/stripe/webhook`

## Troubleshooting
- If API fails to start, ensure Postgres is healthy and `POSTGRES_URL` is reachable.
- On Windows, ensure Docker Desktop is running. Use `docker compose logs -f <service>` for details.
