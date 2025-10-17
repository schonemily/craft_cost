# craft_cost monorepo

Services
- apps/api (FastAPI + Alembic + Redis RQ)
- apps/worker (Python worker for background jobs)
- apps/web (Next.js 14, Tailwind, React Query)
- apps/pdf (Node service scaffold)
- packages/ui (shared UI primitives)

## Prereqs
- Docker + Docker Compose
- Node 20 (optional for local dev of apps/web)

## Quick start (Docker)
```powershell
# From repo root
docker compose up -d db redis minio
Start-Sleep -Seconds 10

docker compose up -d --build api worker web

# Apply DB migrations
docker compose run --rm api alembic upgrade head

# Open
# API: http://localhost:8000/healthz
# Web: http://localhost:3000/
```

## Week 2 features (implemented)
- Upload CSV → enqueue job → poll status
  - POST /v1/transactions/csv → { job_id }
  - GET /v1/jobs/{id}
- Read endpoints
  - GET /v1/transactions?limit=&cursor=&category=
  - GET /v1/spend/summary?period=last_7d|last_30d|last_90d
- Feature Flags (persistent)
  - GET /v1/flags, POST /v1/flags { key, value }
- Web UI
  - Upload page with progress + toasts; flags gating
  - Spend page with React Query, pagination, skeletons
  - Navbar API health indicator and CSV-off badge

## Week 3 kick-off (in repo)
- Recategorize API: POST /v1/transactions/{id}/recategorize {category}
- Spend page inline recategorization + 90d filter
- UI primitives package: @dea/ui (Button, Card, Input, Table)

## Local verification
```powershell
# Ensure migrations applied
npm --prefix apps/web install    # optional for IDE types

docker compose build api worker web

docker compose up -d db redis minio
Start-Sleep -Seconds 10

docker compose up -d api worker web

docker compose run --rm api alembic upgrade head

# Set CSV flag
Invoke-RestMethod -Method Post -ContentType application/json -Body '{"key":"csv_ingestion_enabled","value":true}' -Uri http://localhost:8000/v1/flags

# Upload sample CSV and poll job
$csv = "date,description,amount,merchant`n2025-01-05,Groceries,-54.32,Local Market`n2025-01-06,Internet,-60.00,ISP Co`n2025-01-07,Transport,-15.75,Metro"
$client = New-Object System.Net.Http.HttpClient
$fd = New-Object System.Net.Http.MultipartFormDataContent
$bytes = [System.Text.Encoding]::UTF8.GetBytes($csv)
$byteContent = New-Object System.Net.Http.ByteArrayContent($bytes)
$byteContent.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse("text/csv")
$fd.Add($byteContent, "file", "sample.csv")
$res = $client.PostAsync("http://localhost:8000/v1/transactions/csv", $fd).Result
$body = $res.Content.ReadAsStringAsync().Result
$jobId = (ConvertFrom-Json $body).job_id
for ($i=0; $i -lt 12; $i++) { Start-Sleep -Seconds 1; $jres = $client.GetStringAsync("http://localhost:8000/v1/jobs/$jobId").Result; Write-Host "Job: $jres"; if ($jres -match '"status"\s*:\s*"finished"') { break } }

# Read APIs
Invoke-RestMethod -UseBasicParsing http://localhost:8000/v1/transactions?limit=5 | ConvertTo-Json -Depth 5
Invoke-RestMethod -UseBasicParsing http://localhost:8000/v1/spend/summary?period=last_90d | ConvertTo-Json -Depth 5

# Web pages
(Invoke-WebRequest -UseBasicParsing http://localhost:3000/).StatusCode
(Invoke-WebRequest -UseBasicParsing http://localhost:3000/upload).StatusCode
(Invoke-WebRequest -UseBasicParsing http://localhost:3000/spend).StatusCode
(Invoke-WebRequest -UseBasicParsing http://localhost:3000/flags).StatusCode
```

## UI package (@dea/ui)
- Exports: Button, Card, Input, Table from `packages/ui/src/`
- Next.js config includes `transpilePackages: ['@dea/ui']`
- Usage (example):
```tsx
import { Button, Card, CardBody } from '@dea/ui'
```

## Notes
- In Docker, apps/web builds only its own package; @dea/ui is not yet imported by web. When you import it, ensure the web Dockerfile copies workspace or publish the package.
- CORS is permissive in dev; secure for prod in later weeks.
