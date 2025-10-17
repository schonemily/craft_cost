# Scratch Pad — Week 3

Legend: [ ] Pending  [x] Completed  [-] In Progress

Scope: Read UX polish, recategorization, UI primitives, flags UI, and data fetching quality.

## Deliverables
- [x] Recategorization endpoint `POST /v1/transactions/{id}/recategorize` (or `PATCH`) → returns updated record
- [x] Spend UI polish
  - [x] Filters: category, date range (last 7/30/90 days)
  - [x] Cursor pagination “Load more” (wired to API)
  - [x] Totals panel reads from `/v1/spend/summary?period=<period>`
  - [x] Empty states + loading skeletons
- [x] React Query integration for data fetching + caching
- [x] UI primitives in `packages/ui`: Button, Card, Input, Table
- [x] Feature Flags page `/flags` using `/v1/flags` (toggle + persist)
- [x] Optional: Plaid mock toggle in Flags; stub Connect Plaid CTA
- [x] API tests for reads + recategorize; minimal worker ingest test
- [x] Docs: README snippets (filters, flags), RUNBOOK updates

## Implementation Notes
- API
  - Add route: `POST /v1/transactions/{id}/recategorize` with payload `{category: string}`
  - Validate category against existing enum `tx_category`
  - Return updated joined view `{id,user_id,category,merchant,date,amount,description}`
- Web
  - Use TanStack Query for `/v1/transactions` and `/v1/spend/summary`
  - Maintain `cursor` in component state; append pages
  - Filters persist to query params and refetch
  - Promote UI primitives from `apps/web` to `packages/ui`
- Flags UI
  - Read all flags via `GET /v1/flags`
  - Toggle posts `{ key, value }` to `/v1/flags`

## Milestones
- [x] M1: Recategorization endpoint + unit test
- [x] M2: Spend filters + pagination + skeletons
- [x] M3: React Query wired + primitives extracted
- [x] M4: Flags UI
- [x] Week 3 verified on 2025-10-07
