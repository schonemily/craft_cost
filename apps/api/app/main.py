import os
import redis
from rq import Queue
from rq.job import Job
from fastapi import FastAPI, UploadFile, File, HTTPException, status, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from typing import List, Optional, Literal
import httpx
import smtplib
from email.message import EmailMessage
from .debt_simulator import Debt as SimDebt, simulate as simulate_debts
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session
from .db import get_session
from .models import Transactions, TransactionsRaw, Flag
from .suggestions_engine import generate_suggestions

app = FastAPI(title="craft_cost API")

# CORS: configurable via env; default to localhost for dev
cors_env = os.getenv("CORS_ALLOW_ORIGINS")
if cors_env:
    allowed = [o.strip() for o in cors_env.split(",") if o.strip()]
else:
    # Dev default
    allowed = ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "craft_cost API"}

def _queue() -> Queue:
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    return Queue("default", connection=redis.from_url(redis_url))


# Week 2: enqueue CSV ingestion job (no DB writes yet)
@app.post("/v1/transactions/csv")
async def upload_csv(file: UploadFile = File(...)):
    data = await file.read()
    q = _queue()
    # pass function path so worker can import its own code
    job = q.enqueue_call(
        func="worker.jobs.csv_ingest_db.ingest_csv",
        args=(data,),
        kwargs={},
        timeout=300,
    )
    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={"job_id": job.id})


@app.get("/v1/jobs/{job_id}")
async def job_status(job_id: str):
    q = _queue()
    job = Job.fetch(job_id, connection=q.connection)
    state = job.get_status()  # queued, started, finished, failed, deferred
    resp = {"job_id": job.id, "status": state}
    if state == "finished":
        resp["result"] = job.result
    if state == "failed":
        resp["error"] = str(job.exc_info)[-1000:]
    return resp

@app.get("/v1/transactions")
async def list_transactions(
    cursor: int | None = Query(None, description="Return items with id < cursor (pagination)"),
    limit: int = Query(50, ge=1, le=200),
    category: str | None = Query(None),
    db: Session = Depends(get_session),
):
    # Join normalized tx with raw to expose date/amount/description in one payload
    stmt = (
        select(
            Transactions.id.label("id"),
            Transactions.user_id,
            Transactions.category,
            Transactions.merchant_norm,
            TransactionsRaw.date,
            TransactionsRaw.amount,
            TransactionsRaw.description,
        )
        .join(TransactionsRaw, Transactions.tx_id == TransactionsRaw.id)
        .order_by(Transactions.id.desc())
        .limit(limit)
    )
    if cursor is not None:
        stmt = stmt.where(Transactions.id < cursor)
    if category:
        stmt = stmt.where(Transactions.category == category)

    rows = db.execute(stmt).all()
    items = [
        {
            "id": r.id,
            "user_id": r.user_id,
            "category": r.category,
            "merchant": r.merchant_norm,
            "date": r.date.isoformat() if r.date else None,
            "amount": float(r.amount) if r.amount is not None else None,
            "description": r.description,
        }
        for r in rows
    ]
    next_cursor = items[-1]["id"] if items else None
    return {"items": items, "next_cursor": next_cursor}

@app.get("/v1/spend/summary")
async def spend_summary(period: str = "last_30d", db: Session = Depends(get_session)):
    # Minimal: sum by category from normalized transactions joined to raw amounts
    if period == "last_7d":
        days = 7
    elif period == "last_30d":
        days = 30
    elif period == "last_90d":
        days = 90
    else:
        days = 30
    # If no created_at, filter by raw.date
    stmt = (
        select(Transactions.category, func.coalesce(func.sum(TransactionsRaw.amount), 0))
        .join(TransactionsRaw, Transactions.tx_id == TransactionsRaw.id)
        .where(TransactionsRaw.date >= func.current_date() - days)
        .group_by(Transactions.category)
    )
    rows = db.execute(stmt).all()
    by_category = { (k or "uncategorized"): float(v or 0) for k, v in rows }
    total = float(sum(by_category.values()))
    return {"period": period, "total": total, "by_category": by_category}


@app.get("/v1/suggestions")
async def get_suggestions(db: Session = Depends(get_session)):
    items = generate_suggestions(db)
    return {"items": items}


class DebtItem(BaseModel):
    name: str
    balance: float
    apr: float
    min_payment: float
    promo_apr: float | None = None
    promo_months: int | None = None


class ExtraPayment(BaseModel):
    month: int | None = None
    monthOffset: int | None = None
    amount: float


class DebtSimRequest(BaseModel):
    debts: List[DebtItem]
    extra: float = 0
    strategy: Optional[str] = None  # "snowball" | "avalanche" | None (both)
    include_schedule: bool = False
    extra_schedule: List[ExtraPayment] | None = None
    issuer_percent: float | None = None
    issuer_floor: float | None = None


@app.post("/v1/debt/simulate")
async def debt_simulate(payload: DebtSimRequest):
    debts = [
        SimDebt(
            name=d.name,
            balance=d.balance,
            apr=d.apr,
            min_payment=d.min_payment,
            promo_apr=d.promo_apr,
            promo_months=d.promo_months,
        )
        for d in payload.debts
    ]
    extra = float(payload.extra or 0)
    include_schedule = bool(payload.include_schedule)
    extra_schedule = [e.model_dump() for e in (payload.extra_schedule or [])]
    issuer_percent = 0.01 if payload.issuer_percent is None else float(payload.issuer_percent)
    issuer_floor = 25.0 if payload.issuer_floor is None else float(payload.issuer_floor)

    # If strategy not specified, compute both
    if not payload.strategy:
        snow = simulate_debts(
            debts, extra, "snowball",
            include_schedule=include_schedule,
            extra_schedule=extra_schedule,
            issuer_percent=issuer_percent,
            issuer_floor=issuer_floor,
        )
        aval = simulate_debts(
            debts, extra, "avalanche",
            include_schedule=include_schedule,
            extra_schedule=extra_schedule,
            issuer_percent=issuer_percent,
            issuer_floor=issuer_floor,
        )
        return {
            "snowball": {
                "strategy": snow.strategy,
                "months": snow.months,
                "interest_paid": snow.interest_paid,
                "total_paid": snow.total_paid,
                "debts": [
                    {
                        "name": d.name,
                        "months": d.months,
                        "interest_paid": d.interest_paid,
                        "total_paid": d.total_paid,
                    }
                    for d in snow.debts
                ],
                **({"monthly": snow.monthly} if include_schedule else {}),
            },
            "avalanche": {
                "strategy": aval.strategy,
                "months": aval.months,
                "interest_paid": aval.interest_paid,
                "total_paid": aval.total_paid,
                "debts": [
                    {
                        "name": d.name,
                        "months": d.months,
                        "interest_paid": d.interest_paid,
                        "total_paid": d.total_paid,
                    }
                    for d in aval.debts
                ],
                **({"monthly": aval.monthly} if include_schedule else {}),
            },
        }
    # Single strategy
    strat = payload.strategy.lower().strip()
    if strat not in {"snowball", "avalanche"}:
        raise HTTPException(status_code=400, detail={"code": "invalid_strategy", "message": "Use snowball or avalanche"})
    res = simulate_debts(
        debts, extra, strat,
        include_schedule=include_schedule,
        extra_schedule=extra_schedule,
        issuer_percent=issuer_percent,
        issuer_floor=issuer_floor,
    )
    return {
        "strategy": res.strategy,
        "months": res.months,
        "interest_paid": res.interest_paid,
        "total_paid": res.total_paid,
        "debts": [
            {
                "name": d.name,
                "months": d.months,
                "interest_paid": d.interest_paid,
                "total_paid": d.total_paid,
            }
            for d in res.debts
        ],
        **({"monthly": res.monthly} if include_schedule else {}),
    }


class DebtExportRequest(BaseModel):
    debts: List[DebtItem]
    extra: float = 0
    strategy: Optional[str] = None
    include_schedule: bool = True
    extra_schedule: List[ExtraPayment] | None = None
    format: Literal['pdf', 'email']
    email: Optional[str] = None
    title: Optional[str] = None


@app.post("/v1/debt/export")
async def debt_export(payload: DebtExportRequest, db: Session = Depends(get_session)):
    def to_dict(result):
        if not result:
            return None
        return {
            "strategy": result.strategy,
            "months": result.months,
            "interest_paid": result.interest_paid,
            "total_paid": result.total_paid,
            "debts": [
                {
                    "name": d.name,
                    "months": d.months,
                    "interest_paid": d.interest_paid,
                    "total_paid": d.total_paid,
                }
                for d in (result.debts or [])
            ],
            **({"monthly": result.monthly} if getattr(result, "monthly", None) else {}),
        }
    # Build debts and simulate (both or single) with schedule
    debts = [
        SimDebt(
            name=d.name,
            balance=d.balance,
            apr=d.apr,
            min_payment=d.min_payment,
            promo_apr=d.promo_apr,
            promo_months=d.promo_months,
        )
        for d in payload.debts
    ]
    extra = float(payload.extra or 0)
    include_schedule = bool(payload.include_schedule)
    extra_schedule = [e.model_dump() for e in (payload.extra_schedule or [])]

    if not payload.strategy:
        snow = simulate_debts(
            debts, extra, "snowball",
            include_schedule=include_schedule,
            extra_schedule=extra_schedule,
        )
        aval = simulate_debts(
            debts, extra, "avalanche",
            include_schedule=include_schedule,
            extra_schedule=extra_schedule,
        )
        pdf_payload = {
            "title": payload.title or "Debt Payoff Plan",
            "snowball": to_dict(snow),
            "avalanche": to_dict(aval),
        }
    else:
        strat = payload.strategy.lower().strip()
        if strat not in {"snowball", "avalanche"}:
            raise HTTPException(status_code=400, detail={"code": "invalid_strategy", "message": "Use snowball or avalanche"})
        res = simulate_debts(
            debts, extra, strat,
            include_schedule=include_schedule,
            extra_schedule=extra_schedule,
        )
        pdf_payload = {
            "title": payload.title or "Debt Payoff Plan",
            "strategy": to_dict(res),
        }

    # If emailing, enforce gating & input before rendering the PDF
    if payload.format == 'email':
        flag = db.get(Flag, "pro_enabled")
        if not flag or not flag.bool_value:
            raise HTTPException(status_code=402, detail={"code": "pro_required", "message": "Upgrade to Pro to email exports"})
        if not payload.email or "@" not in payload.email:
            raise HTTPException(status_code=400, detail={"code": "invalid_email", "message": "Valid email required"})

    # Render PDF via pdf-service (with fallbacks)
    pdf_url_primary = os.getenv("PDF_SERVICE_URL", "http://pdf:4000/render")
    pdf_candidates = [
        pdf_url_primary,
        "http://host.docker.internal:4000/render",
        "http://localhost:4000/render",
    ]
    pdf_bytes = None
    last_err = None
    async with httpx.AsyncClient(timeout=30.0) as client:
        for url in pdf_candidates:
            try:
                pdf_resp = await client.post(url, json=pdf_payload)
                if pdf_resp.status_code == 200:
                    pdf_bytes = pdf_resp.content
                    break
                last_err = f"status {pdf_resp.status_code}"
            except Exception as e:  # Connect or other errors
                last_err = str(e)
        if pdf_bytes is None:
            raise HTTPException(status_code=502, detail={"code": "pdf_render_failed", "message": f"PDF service unreachable: {last_err}"})

    if payload.format == 'pdf':
        return Response(content=pdf_bytes, media_type='application/pdf', headers={"Content-Disposition": 'inline; filename="debt-plan.pdf"'})

    msg = EmailMessage()
    msg["Subject"] = payload.title or "Your Debt Payoff Plan"
    msg["From"] = os.getenv("MAIL_FROM", "noreply@craft_cost.local")
    msg["To"] = payload.email
    # Text body
    msg.set_content("Your debt payoff plan is attached as a PDF.\n\nThis message includes a brief summary below. View the full plan in the attachment.")

    # Build simple HTML summary
    def _row(label: str, v: float | int | str) -> str:
        return f"<tr><td style='padding:6px 10px;border:1px solid #e5e7eb'>{label}</td><td style='padding:6px 10px;border:1px solid #e5e7eb;text-align:right'>{v}</td></tr>"

    def _fmt(x):
        try:
            return f"${float(x or 0):.2f}"
        except Exception:
            return str(x)

    html_parts = [
        "<html><body style='font-family:Inter,Helvetica,Arial,sans-serif;color:#111827'>",
        f"<h2 style='margin:0 0 8px 0'>{(payload.title or 'Your Debt Payoff Plan')}</h2>",
    ]
    if pdf_payload.get("snowball") or pdf_payload.get("avalanche"):
        for key in ["snowball", "avalanche"]:
            r = pdf_payload.get(key)
            if not r:
                continue
            html_parts.append(f"<h3 style='margin:16px 0 6px 0;text-transform:capitalize'>{key}</h3>")
            html_parts.append("<table style='border-collapse:collapse;border:1px solid #e5e7eb'>")
            html_parts.append(_row("Months", r.get("months", 0)))
            html_parts.append(_row("Interest paid", _fmt(r.get("interest_paid"))))
            html_parts.append(_row("Total paid", _fmt(r.get("total_paid"))))
            html_parts.append("</table>")
    elif pdf_payload.get("strategy"):
        r = pdf_payload["strategy"]
        name = r.get("strategy", "Result").title()
        html_parts.append(f"<h3 style='margin:16px 0 6px 0'>{name}</h3>")
        html_parts.append("<table style='border-collapse:collapse;border:1px solid #e5e7eb'>")
        html_parts.append(_row("Months", r.get("months", 0)))
        html_parts.append(_row("Interest paid", _fmt(r.get("interest_paid"))))
        html_parts.append(_row("Total paid", _fmt(r.get("total_paid"))))
        html_parts.append("</table>")
    html_parts.append("<p style='margin-top:16px'>See the attached PDF for detailed tables and schedules.</p>")
    html_parts.append("</body></html>")
    msg.add_alternative("".join(html_parts), subtype='html')

    # Attachment
    msg.add_attachment(pdf_bytes, maintype='application', subtype='pdf', filename='debt-plan.pdf')

    smtp_host = os.getenv("SMTP_HOST", "mailhog")
    smtp_port = int(os.getenv("SMTP_PORT", "1025"))
    with smtplib.SMTP(smtp_host, smtp_port) as s:
        s.send_message(msg)

    return {"ok": True}

class FlagPayload(BaseModel):
    key: str
    value: bool


@app.get("/v1/flags")
async def get_flags(db: Session = Depends(get_session)):
    rows = db.execute(select(Flag)).scalars().all()
    return {"flags": {r.key: r.bool_value for r in rows}}


@app.post("/v1/flags")
async def set_flag(payload: FlagPayload, db: Session = Depends(get_session)):
    # upsert simple bool flag
    existing = db.get(Flag, payload.key)
    if existing:
        existing.bool_value = payload.value
    else:
        db.add(Flag(key=payload.key, bool_value=payload.value))
    db.commit()
    return {"ok": True}

# (DB-backed /v1/flags defined above)


# Week 3: Recategorize a transaction by id
class RecategorizePayload(BaseModel):
    category: str


ALLOWED_CATEGORIES = {
    "housing","utilities","telco","insurance","transport","grocery","dining","entertainment",
    "subscriptions","health","personal","fees","income","other",
}


@app.post("/v1/transactions/{tx_id}/recategorize")
async def recategorize_transaction(tx_id: int, payload: RecategorizePayload, db: Session = Depends(get_session)):
    cat = payload.category.strip().lower()
    if cat not in ALLOWED_CATEGORIES:
        raise HTTPException(status_code=400, detail={"code": "invalid_category", "message": "Unsupported category"})

    # Ensure exists, then update
    tx = db.get(Transactions, tx_id)
    if not tx:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Transaction not found"})
    tx.category = cat
    db.commit()

    # Return joined view consistent with list endpoint
    stmt = (
        select(
            Transactions.id.label("id"),
            Transactions.user_id,
            Transactions.category,
            Transactions.merchant_norm,
            TransactionsRaw.date,
            TransactionsRaw.amount,
            TransactionsRaw.description,
        )
        .join(TransactionsRaw, Transactions.tx_id == TransactionsRaw.id)
        .where(Transactions.id == tx_id)
        .limit(1)
    )
    row = db.execute(stmt).first()
    if not row:
        raise HTTPException(status_code=500, detail={"code": "updated_row_missing", "message": "Updated row missing"})
    return {
        "id": row.id,
        "user_id": row.user_id,
        "category": row.category,
        "merchant": row.merchant_norm,
        "date": row.date.isoformat() if row.date else None,
        "amount": float(row.amount) if row.amount is not None else None,
        "description": row.description,
    }
