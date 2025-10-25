import os
import time
import uuid
import json
import hmac
import hashlib
import logging
import redis
from rq import Queue
from rq.job import Job
from fastapi import FastAPI, UploadFile, File, HTTPException, status, Depends, Query, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from typing import List, Optional, Literal
import httpx
import smtplib
from email.message import EmailMessage
from .debt_simulator import Debt as SimDebt, simulate as simulate_debts
from sqlalchemy import select, func, and_, text, String
from sqlalchemy.orm import Session
from .db import get_session
from .models import Transactions, TransactionsRaw, Flag, Users, Billing
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
import random
import jwt
from .suggestions_engine import generate_suggestions

app = FastAPI(title="craft_cost API")

# CORS: configurable via env; default to localhost for dev
cors_env = os.getenv("CORS_ALLOW_ORIGINS")
if cors_env:
    allowed = [o.strip() for o in cors_env.split(",") if o.strip()]
else:
    # Dev default
    allowed = ["http://localhost:3000", "http://localhost:3001", "http://localhost:5173", "http://127.0.0.1:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth config and helpers
JWT_SECRET = os.getenv("JWT_SECRET", "dev_jwt_secret")
JWT_ALG = "HS256"
SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", "604800"))  # 7 days
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
MINT_TOKEN_SECRET = os.getenv("MINT_TOKEN_SECRET", "dev_mint_secret")
USE_LOCAL_DB = str(os.getenv("USE_LOCAL_DB", "false")).lower() in {"1", "true", "yes"}

ADMIN_EMAILS = {e.strip().lower() for e in (os.getenv("ADMIN_EMAILS", "").split(",") if os.getenv("ADMIN_EMAILS") else [])}

def _role_for(email: str, default_role: str = "user") -> str:
    try:
        return "admin" if email.strip().lower() in ADMIN_EMAILS else default_role
    except Exception:
        return default_role

try:
    from . import local_users as LU
except Exception:
    LU = None

class MintPayload(BaseModel):
    email: str

@app.post("/v1/auth/mint")
async def auth_mint(payload: MintPayload, request: Request, db: Session = Depends(get_session)):
    # Internal-only token minting to support magic-link sessions
    secret = request.headers.get("X-Internal-Secret")
    if not secret or secret != MINT_TOKEN_SECRET:
        raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "Invalid secret"})
    email = payload.email.strip().lower()
    # Prefer local users store in dev mode to avoid ORM/DB schema drift
    if USE_LOCAL_DB and LU:
        created = False
        u = LU.get_by_email(email)
        if not u:
            u = LU.add_user(email, None, role=_role_for(email, "user"))
            created = True
        uid = int(u["id"])
        token = _create_jwt(uid, _role_for(email, str(u.get("role") or "user")))
        return {"access_token": token, "token_type": "bearer", "created": created}
    # Fallback: relational DB user creation
    row = db.execute(select(Users).where(Users.email == email)).scalar_one_or_none()
    created = False
    if not row:
        # create minimal user
        row = Users(email=email, role="user")
        db.add(row)
        db.commit()
        db.refresh(row)
        created = True
        # Audit register
        try:
            db.execute(text("INSERT INTO audit_events (user_id, actor, action, payload_json) VALUES (:uid, 'user', :act, :payload)"),
                       {"uid": row.id, "act": "auth_register", "payload": json.dumps({"email": email, "source": "mint"})})
            db.commit()
        except Exception:
            pass
    token = _create_jwt(row.id, _role_for(email, getattr(row, "role", "user")))
    return {"access_token": token, "token_type": "bearer", "created": created}

def _hash_password(p: str) -> str:
    return pwd_context.hash(p)

def _verify_password(p: str, ph: str | None) -> bool:
    if not ph:
        return False
    try:
        return pwd_context.verify(p, ph)
    except Exception:
        return False

def _create_jwt(user_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=SESSION_MAX_AGE)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def _decode_jwt(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except Exception:
        return None

def _get_auth_user(authorization: str | None, db: Session) -> tuple[dict | None, str]:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None, "free"
    token = authorization.split(" ", 1)[1].strip()
    claims = _decode_jwt(token)
    if not claims:
        return None, "free"
    try:
        uid = int(claims.get("sub"))
    except Exception:
        return None, "free"
    if USE_LOCAL_DB and LU:
        u = LU.get_by_id(uid)
        if not u:
            return None, "free"
        return {"id": int(u.get("id")), "email": str(u.get("email") or ""), "role": _role_for(str(u.get("email") or ""), str(u.get("role") or "user"))}, "free"
    user = db.get(Users, uid)
    if not user:
        return None, "free"
    plan = "free"
    row = db.execute(select(Billing.plan).where(Billing.user_id == uid)).first()
    if row and row[0]:
        plan = str(row[0])
    return {"id": user.id, "email": user.email, "role": getattr(user, "role", "user")}, plan

RATE_LIMIT_RPM = int(os.getenv("RATE_LIMIT_RPM", "120"))
_redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if RATE_LIMIT_RPM <= 0:
        return await call_next(request)
    try:
        ip = request.client.host if request.client else "unknown"
        bucket = int(time.time() // 60)
        key = f"rl:{ip}:{request.url.path}:{bucket}"
        r = redis.from_url(_redis_url)
        count = r.incr(key)
        if count == 1:
            r.expire(key, 60)
        if count > RATE_LIMIT_RPM:
            return JSONResponse(status_code=429, content={"error": {"code": "rate_limited", "message": "Too many requests"}})
    except Exception:
        # Fail open on limiter errors in dev
        pass
    return await call_next(request)


@app.middleware("http")
async def request_id_and_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    start = time.time()
    response = await call_next(request)
    duration_ms = int((time.time() - start) * 1000)
    response.headers["X-Request-ID"] = request_id
    # Security headers (API)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    # Minimal JSON log with redaction
    redact = {"authorization", "cookie"}
    headers = {k: ("<redacted>" if k.lower() in redact else v) for k, v in request.headers.items()}
    logging.getLogger("api").info(json.dumps({
        "event": "http_request",
        "method": request.method,
        "path": request.url.path,
        "status": getattr(response, "status_code", None),
        "duration_ms": duration_ms,
        "request_id": request_id,
    }))
    return response

@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "craft_cost API"}

# CRA/Vite-friendly aliases
@app.get("/api/status")
async def api_status():
    return {"status": "ok", "service": "craft_cost API"}


# Auth endpoints (Phase 1: API JWT)
class RegisterPayload(BaseModel):
    email: str
    password: str


class LoginPayload(BaseModel):
    email: str
    password: str


# Signup payload must be defined before any route references it
class SignupPayload(BaseModel):
    name: str
    email: str
    password: str


@app.post("/v1/auth/register")
async def auth_register(payload: RegisterPayload, db: Session = Depends(get_session)):
    if (os.getenv("APP_ENV") or "development").lower() != "development":
        raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "Registration disabled"})
    email = payload.email.strip().lower()
    if USE_LOCAL_DB and LU:
        # Explicit local user handling
        existing = LU.get_by_email(email)
        if existing:
            if _verify_password(payload.password, str(existing.get("password_hash") or "")):
                token = _create_jwt(int(existing["id"]), _role_for(email, str(existing.get("role") or "user")))
                try:
                    db.execute(text("INSERT INTO audit_events (user_id, actor, action, payload_json) VALUES (:uid, 'user', :act, :payload)"),
                               {"uid": int(existing["id"]), "act": "auth_register_idempotent", "payload": json.dumps({"email": email, "local": True})})
                    db.commit()
                except Exception:
                    pass
                return {"access_token": token, "token_type": "bearer"}


@app.post("/api/auth/signup")
async def api_auth_signup(payload: SignupPayload, db: Session = Depends(get_session)):
    try:
        nm = (payload.name or "").strip()
        em = (payload.email or "").strip().lower()
        pw = payload.password or ""
        if len(nm) < 2:
            raise HTTPException(status_code=400, detail={"code": "invalid_name", "message": "Name must be at least 2 characters"})
        if "@" not in em or "." not in em:
            raise HTTPException(status_code=400, detail={"code": "invalid_email", "message": "Enter a valid email"})
        if len(pw) < 8:
            raise HTTPException(status_code=400, detail={"code": "weak_password", "message": "Password must be at least 8 characters"})
        result = await signup(payload, db)
        token = result.get("access_token") if isinstance(result, dict) else None
        if not token:
            raise HTTPException(status_code=500, detail={"code": "signup_failed", "message": "Failed to create account"})
        user, plan = _get_auth_user(f"Bearer {token}", db)
        return {"success": True, "token": token, "user": {**(user or {}), "plan": plan}}
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"success": False, "error": e.detail})


@app.post("/api/auth/login")
async def api_auth_login(payload: LoginPayload, db: Session = Depends(get_session)):
    try:
        em = (payload.email or "").strip().lower()
        pw = payload.password or ""
        if not em or not pw:
            raise HTTPException(status_code=400, detail={"code": "missing_fields", "message": "Email and password are required"})
        if "@" not in em or "." not in em:
            raise HTTPException(status_code=400, detail={"code": "invalid_email", "message": "Enter a valid email"})
        result = await login(payload, db)
        token = result.get("access_token") if isinstance(result, dict) else None
        if not token:
            raise HTTPException(status_code=401, detail={"code": "invalid_credentials", "message": "Invalid email or password"})
        user, plan = _get_auth_user(f"Bearer {token}", db)
        return {"success": True, "token": token, "user": {**(user or {}), "plan": plan}}
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"success": False, "error": e.detail})


@app.post("/api/login")
async def api_login(payload: LoginPayload, db: Session = Depends(get_session)):
    return await login(payload, db)


# Aliases to meet simplified API spec


@app.post("/signup")
async def signup(payload: SignupPayload, db: Session = Depends(get_session)):
    # Mirror /v1/auth/register, accept name but store it only in audit payload
    if (os.getenv("APP_ENV") or "development").lower() != "development":
        raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "Registration disabled"})
    email = payload.email.strip().lower()
    if USE_LOCAL_DB and LU:
        # Explicit local user handling
        existing = LU.get_by_email(email)
        if existing:
            if _verify_password(payload.password, str(existing.get("password_hash") or "")):
                token = _create_jwt(int(existing["id"]), _role_for(email, str(existing.get("role") or "user")))
                try:
                    db.execute(text("INSERT INTO audit_events (user_id, actor, action, payload_json) VALUES (:uid, 'user', :act, :payload)"),
                               {"uid": int(existing["id"]), "act": "auth_register_idempotent", "payload": json.dumps({"email": email, "name": payload.name, "local": True})})
                    db.commit()
                except Exception:
                    pass
                return {"access_token": token, "token_type": "bearer"}
            # Else, check relational DB for a minted user or idempotent match
            row = db.execute(select(Users).where(Users.email == email)).scalar_one_or_none()
            if row and not getattr(row, "password_hash", None):
                row.password_hash = _hash_password(payload.password)
                row.role = _role_for(email, getattr(row, "role", "user"))
                db.add(row)
                db.commit()
                db.refresh(row)
                token = _create_jwt(row.id, row.role)
                return {"access_token": token, "token_type": "bearer"}
            if row and _verify_password(payload.password, row.password_hash or ""):
                token = _create_jwt(row.id, _role_for(email, getattr(row, "role", "user")))
                return {"access_token": token, "token_type": "bearer"}
            raise HTTPException(status_code=400, detail={"code": "email_taken", "message": "Email already registered"})
        # Create new local user
        u = LU.add_user(email, _hash_password(payload.password), role=_role_for(email, "user"))
        token = _create_jwt(int(u["id"]), _role_for(email, str(u.get("role") or "user")))
        try:
            db.execute(text("INSERT INTO audit_events (user_id, actor, action, payload_json) VALUES (:uid, 'user', :act, :payload)"),
                       {"uid": int(u["id"]), "act": "auth_register", "payload": json.dumps({"email": email, "name": payload.name, "local": True})})
            db.commit()
        except Exception:
            pass
        return {"access_token": token, "token_type": "bearer"}
    row = db.execute(select(Users).where(Users.email == email)).scalar_one_or_none()
    if row:
        # Upgrade a minted user (no password yet) by setting credentials now
        if not getattr(row, "password_hash", None):
            row.password_hash = _hash_password(payload.password)
            row.role = _role_for(email, getattr(row, "role", "user"))
            db.add(row)
            db.commit()
            db.refresh(row)
            token = _create_jwt(row.id, row.role)
            try:
                db.execute(text("INSERT INTO audit_events (user_id, actor, action, payload_json) VALUES (:uid, 'user', :act, :payload)"),
                           {"uid": row.id, "act": "auth_register", "payload": json.dumps({"email": email, "name": payload.name, "upgraded": True})})
                db.commit()
            except Exception:
                pass
            return {"access_token": token, "token_type": "bearer"}
        # If user exists with password, allow idempotent sign-up when password matches
        if _verify_password(payload.password, row.password_hash or ""):
            token = _create_jwt(row.id, _role_for(email, getattr(row, "role", "user")))
            try:
                db.execute(text("INSERT INTO audit_events (user_id, actor, action, payload_json) VALUES (:uid, 'user', :act, :payload)"),
                           {"uid": row.id, "act": "auth_register_idempotent", "payload": json.dumps({"email": email, "name": payload.name})})
                db.commit()
            except Exception:
                pass
            return {"access_token": token, "token_type": "bearer"}
        raise HTTPException(status_code=400, detail={"code": "email_taken", "message": "Email already registered"})
    u = Users(email=email, password_hash=_hash_password(payload.password), role=_role_for(email, "user"))
    db.add(u)
    db.commit()
    db.refresh(u)
    token = _create_jwt(u.id, u.role)
    # Audit register with name (best-effort)
    try:
        db.execute(text("INSERT INTO audit_events (user_id, actor, action, payload_json) VALUES (:uid, 'user', :act, :payload)"),
                   {"uid": u.id, "act": "auth_register", "payload": json.dumps({"email": email, "name": payload.name})})
        db.commit()
    except Exception:
        pass
    return {"access_token": token, "token_type": "bearer"}


@app.post("/api/signup")
async def api_signup(payload: SignupPayload, db: Session = Depends(get_session)):
    return await signup(payload, db)


@app.post("/login")
async def login(payload: LoginPayload, db: Session = Depends(get_session)):
    # Mirror /v1/auth/login
    email = payload.email.strip().lower()
    if USE_LOCAL_DB and LU:
        u = LU.get_by_email(email)
        if not u or not _verify_password(payload.password, str(u.get("password_hash") or "")):
            try:
                if u:
                    db.execute(text("INSERT INTO audit_events (user_id, actor, action, payload_json) VALUES (:uid, 'system', :act, :payload)"),
                               {"uid": int(u["id"]), "act": "auth_login_failed", "payload": json.dumps({"email": email, "alias": True, "local": True})})
                    db.commit()
            except Exception:
                pass
            raise HTTPException(status_code=401, detail={"code": "invalid_credentials", "message": "Invalid email or password"})
        token = _create_jwt(int(u["id"]), _role_for(email, str(u.get("role") or "user")))
        try:
            db.execute(text("INSERT INTO audit_events (user_id, actor, action, payload_json) VALUES (:uid, 'user', :act, :payload)"),
                       {"uid": int(u["id"]), "act": "auth_login_success", "payload": json.dumps({"email": email, "alias": True, "local": True})})
            db.commit()
        except Exception:
            pass
        return {"access_token": token, "token_type": "bearer"}
    row = db.execute(select(Users).where(Users.email == email)).scalar_one_or_none()
    if not row or not _verify_password(payload.password, row.password_hash):
        # Best-effort audit
        try:
            if row:
                db.execute(text("INSERT INTO audit_events (user_id, actor, action, payload_json) VALUES (:uid, 'system', :act, :payload)"),
                           {"uid": row.id, "act": "auth_login_failed", "payload": json.dumps({"email": email, "alias": True})})
                db.commit()
        except Exception:
            pass
        raise HTTPException(status_code=401, detail={"code": "invalid_credentials", "message": "Invalid email or password"})
    token = _create_jwt(row.id, _role_for(email, getattr(row, "role", "user")))
    try:
        db.execute(text("INSERT INTO audit_events (user_id, actor, action, payload_json) VALUES (:uid, 'user', :act, :payload)"),
                   {"uid": row.id, "act": "auth_login_success", "payload": json.dumps({"email": email, "alias": True})})
        db.commit()
    except Exception:
        pass
    return {"access_token": token, "token_type": "bearer"}


@app.post("/v1/auth/login")
async def auth_login(payload: LoginPayload, db: Session = Depends(get_session)):
    email = payload.email.strip().lower()
    if USE_LOCAL_DB and LU:
        u = LU.get_by_email(email)
        if not u or not _verify_password(payload.password, str(u.get("password_hash") or "")):
            try:
                if u:
                    db.execute(text("INSERT INTO audit_events (user_id, actor, action, payload_json) VALUES (:uid, 'system', :act, :payload)"),
                               {"uid": int(u["id"]), "act": "auth_login_failed", "payload": json.dumps({"email": email, "local": True})})
                    db.commit()
            except Exception:
                pass
            raise HTTPException(status_code=401, detail={"code": "invalid_credentials", "message": "Invalid email or password"})
        token = _create_jwt(int(u["id"]), _role_for(email, str(u.get("role") or "user")))
        try:
            db.execute(text("INSERT INTO audit_events (user_id, actor, action, payload_json) VALUES (:uid, 'user', :act, :payload)"),
                       {"uid": int(u["id"]), "act": "auth_login_success", "payload": json.dumps({"email": email, "local": True})})
            db.commit()
        except Exception:
            pass
        return {"access_token": token, "token_type": "bearer"}
    row = db.execute(select(Users).where(Users.email == email)).scalar_one_or_none()
    if not row or not _verify_password(payload.password, row.password_hash):
        # Audit (failed) if user exists
        try:
            if row:
                db.execute(text("INSERT INTO audit_events (user_id, actor, action, payload_json) VALUES (:uid, 'system', :act, :payload)"),
                           {"uid": row.id, "act": "auth_login_failed", "payload": json.dumps({"email": email})})
                db.commit()
        except Exception:
            pass
        raise HTTPException(status_code=401, detail={"code": "invalid_credentials", "message": "Invalid email or password"})
    token = _create_jwt(row.id, _role_for(email, getattr(row, "role", "user")))
    # Audit (success)
    try:
        db.execute(text("INSERT INTO audit_events (user_id, actor, action, payload_json) VALUES (:uid, 'user', :act, :payload)"),
                   {"uid": row.id, "act": "auth_login_success", "payload": json.dumps({"email": email})})
        db.commit()
    except Exception:
        pass
    return {"access_token": token, "token_type": "bearer"}


@app.get("/v1/auth/me")
async def auth_me(authorization: str | None = Header(default=None), db: Session = Depends(get_session)):
    user, plan = _get_auth_user(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Login required"})
    return {"user": {**user, "plan": plan}}

def _queue() -> Queue:
    return Queue("default", connection=redis.from_url(_redis_url))


# Week 2: enqueue CSV ingestion job (no DB writes yet)
@app.post("/v1/transactions/csv")
async def upload_csv(
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_session),
):
    data = await file.read()
    # Require auth; determine owner for ingestion
    user, _plan = _get_auth_user(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Login required"})
    uid = int(user["id"])
    q = _queue()
    job = q.enqueue_call(
        func="worker.jobs.csv_ingest_db.ingest_csv",
        args=(data,),
        kwargs={"user_id": uid, "user_email": user["email"]},
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
    period: str | None = Query(None, description="Optional: last_7d | last_30d | last_90d | all_time"),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_session),
):
    # Require auth and owner filter (BOLA)
    user, _plan = _get_auth_user(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Login required"})
    # Join normalized tx with raw to expose date/amount/description in one payload
    stmt = (
        select(
            Transactions.id.label("id"),
            Transactions.user_id,
            func.cast(Transactions.category, String).label("category"),
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
    if period in {"last_7d", "last_30d", "last_90d"}:
        days = 7 if period == "last_7d" else (30 if period == "last_30d" else 90)
        stmt = stmt.where(TransactionsRaw.date >= func.current_date() - days)
    stmt = stmt.where(Transactions.user_id == user["id"])

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
async def spend_summary(period: str = "last_30d", authorization: str | None = Header(default=None), db: Session = Depends(get_session)):
    # Minimal: sum by category from normalized transactions joined to raw amounts
    if period == "last_7d":
        days = 7
    elif period == "last_30d":
        days = 30
    elif period == "last_90d":
        days = 90
    elif period == "all_time":
        days = None
    else:
        days = 30
    # If no created_at, filter by raw.date
    stmt = (
        select(Transactions.category, func.coalesce(func.sum(TransactionsRaw.amount), 0))
        .join(TransactionsRaw, Transactions.tx_id == TransactionsRaw.id)
    )
    if days is not None:
        stmt = stmt.where(TransactionsRaw.date >= func.current_date() - days)
    # Owner scoping
    user, _plan = _get_auth_user(authorization, db)
    if user:
        stmt = stmt.where(Transactions.user_id == user["id"])
    stmt = stmt.group_by(Transactions.category)
    rows = db.execute(stmt).all()
    by_category = { (k or "uncategorized"): float(v or 0) for k, v in rows }
    total = float(sum(by_category.values()))
    return {"period": period, "total": total, "by_category": by_category}


@app.post("/v1/transactions/seed")
async def seed_transactions(count: int = 50, authorization: str | None = Header(default=None), db: Session = Depends(get_session)):
    # Dev-only convenience to populate demo data
    if (os.getenv("APP_ENV") or "development").lower() != "development":
        raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "Seeding disabled"})
    user, _plan = _get_auth_user(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Login required"})
    uid = int(user["id"])  # seed for the current user

    n = max(1, min(int(count or 0), 200))
    merchants = [
        ("SuperMart", "grocery"),
        ("City Utilities", "utilities"),
        ("Acme Telco", "telco"),
        ("QuickBite", "dining"),
        ("Prime Video", "subscriptions"),
        ("Gym+", "personal"),
        ("RideNow", "transport"),
        ("Landlord LLC", "housing"),
        ("PharmaCare", "health"),
        ("Cinema Plaza", "entertainment"),
    ]
    seeded = 0
    total_amount = 0.0
    for i in range(n):
        merchant, default_cat = random.choice(merchants)
        # 85% expenses (negative), 15% income (positive)
        if random.random() < 0.15:
            cat = "income"
            amt = round(random.uniform(1500, 3500), 2)
            desc = "Monthly salary"
        else:
            cat = default_cat
            amt = round(-1 * random.uniform(5, 250), 2)
            desc = f"{merchant} purchase"
        d = (datetime.now().date() - timedelta(days=random.randint(0, 90)))

        # Insert into raw table (minimal columns for wide DB compatibility)
        try:
            tx_raw_id_row = db.execute(text(
                """
                INSERT INTO transactions_raw (user_id, date, amount, description, merchant_raw)
                VALUES (:user_id, :date, :amount, :description, :merchant_raw)
                RETURNING id
                """
            ), {
                "user_id": uid,
                "date": d,
                "amount": amt,
                "description": desc,
                "merchant_raw": merchant,
            }).fetchone()
            tx_raw_id = int(tx_raw_id_row[0]) if tx_raw_id_row else None
            if not tx_raw_id:
                continue
            # Insert normalized transaction; handle absence of tx_category enum gracefully
            has_enum = False
            try:
                chk = db.execute(text("SELECT 1 FROM pg_type WHERE typname = 'tx_category'"))
                has_enum = bool(chk.first())
            except Exception:
                has_enum = False
            if has_enum:
                db.execute(text(
                    """
                    INSERT INTO transactions (user_id, tx_id, category, merchant_norm)
                    VALUES (:user_id, :tx_id, CAST(:category AS tx_category), :merchant_norm)
                    """
                ), {
                    "user_id": uid,
                    "tx_id": tx_raw_id,
                    "category": cat,
                    "merchant_norm": merchant,
                })
            else:
                db.execute(text(
                    """
                    INSERT INTO transactions (user_id, tx_id, category, merchant_norm)
                    VALUES (:user_id, :tx_id, :category, :merchant_norm)
                    """
                ), {
                    "user_id": uid,
                    "tx_id": tx_raw_id,
                    "category": cat,
                    "merchant_norm": merchant,
                })
            seeded += 1
            total_amount += amt
        except Exception:
            # skip on error; continue best-effort in dev
            continue
    try:
        db.commit()
    except Exception:
        pass
    return {"seeded": seeded, "user_id": uid, "total_amount": round(total_amount, 2)}


@app.get("/v1/suggestions")
async def get_suggestions(authorization: str | None = Header(default=None), db: Session = Depends(get_session)):
    user, _plan = _get_auth_user(authorization, db)
    items = generate_suggestions(db, user_id=(user["id"] if user else None))
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
    extra_schedule: List[dict] | None = None
    format: Literal['pdf', 'email']
    email: Optional[str] = None
    title: Optional[str] = None


@app.post("/v1/debt/export")
async def debt_export(payload: DebtExportRequest, request: Request, db: Session = Depends(get_session)):
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
    extra_schedule = [e for e in (payload.extra_schedule or [])]

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

    pdf_url = os.getenv("PDF_SERVICE_URL", "http://pdf:4000/render")
    async with httpx.AsyncClient(timeout=30.0) as client:
        pdf_resp = await client.post(pdf_url, json=pdf_payload)
        if pdf_resp.status_code != 200:
            raise HTTPException(status_code=502, detail={"code": "pdf_render_failed", "message": f"PDF service error {pdf_resp.status_code}"})
        pdf_bytes = pdf_resp.content

    if payload.format == 'pdf':
        return Response(content=pdf_bytes, media_type='application/pdf', headers={"Content-Disposition": 'inline; filename="debt-plan.pdf"'})

    # Entitlements: allow if user has plan 'plus' OR feature flag pro_enabled is on
    auth_header = request.headers.get("authorization")
    _user, plan = _get_auth_user(auth_header, db)
    flag = db.get(Flag, "pro_enabled")
    allowed = (plan == "plus") or (flag and flag.bool_value)
    if not allowed:
        raise HTTPException(status_code=402, detail={"code": "pro_required", "message": "Upgrade to Pro to email exports"})
    if not payload.email or "@" not in payload.email:
        raise HTTPException(status_code=400, detail={"code": "invalid_email", "message": "Valid email required"})

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
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    use_ssl = os.getenv("SMTP_USE_SSL", "false").lower() == "true"
    use_tls = os.getenv("SMTP_USE_TLS", "false").lower() == "true"

    if use_ssl:
        with smtplib.SMTP_SSL(smtp_host, smtp_port) as s:
            if smtp_user and smtp_pass:
                s.login(smtp_user, smtp_pass)
            s.send_message(msg)
    else:
        with smtplib.SMTP(smtp_host, smtp_port) as s:
            if use_tls:
                s.starttls()
            if smtp_user and smtp_pass:
                s.login(smtp_user, smtp_pass)
            s.send_message(msg)

    # Audit export email sent (if we have a user)
    try:
        if _user:
            db.execute(text("INSERT INTO audit_events (user_id, actor, action, payload_json) VALUES (:uid, 'user', :act, :payload)"),
                       {"uid": _user["id"], "act": "export_email_sent", "payload": json.dumps({"email": payload.email, "title": payload.title})})
            db.commit()
    except Exception:
        pass

    return {"ok": True}

class FlagPayload(BaseModel):
    key: str
    value: bool


@app.get("/v1/flags")
async def get_flags(db: Session = Depends(get_session)):
    rows = db.execute(select(Flag)).scalars().all()
    return {"flags": {r.key: r.bool_value for r in rows}}


@app.post("/v1/flags")
async def set_flag(payload: FlagPayload, authorization: str | None = Header(default=None), db: Session = Depends(get_session)):
    # upsert simple bool flag
    user, _plan = _get_auth_user(authorization, db)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "Admin required"})
    existing = db.get(Flag, payload.key)
    if existing:
        existing.bool_value = payload.value
    else:
        db.add(Flag(key=payload.key, bool_value=payload.value))
    db.commit()
    # Audit flag change (best-effort)
    try:
        user, _plan = _get_auth_user(authorization, db)
        if user:
            db.execute(text("INSERT INTO audit_events (user_id, actor, action, payload_json) VALUES (:uid, 'admin', :act, :payload)"),
                       {"uid": user["id"], "act": "flag_changed", "payload": json.dumps({"key": payload.key, "value": payload.value})})
            db.commit()
    except Exception:
        pass
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
async def recategorize_transaction(tx_id: int, payload: RecategorizePayload, authorization: str | None = Header(default=None), db: Session = Depends(get_session)):
    cat = payload.category.strip().lower()
    if cat not in ALLOWED_CATEGORIES:
        raise HTTPException(status_code=400, detail={"code": "invalid_category", "message": "Unsupported category"})

    # Ensure exists, then update (owner or admin only)
    tx = db.get(Transactions, tx_id)
    if not tx:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Transaction not found"})
    user, _plan = _get_auth_user(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Login required"})
    if (user.get("role") != "admin") and (getattr(tx, "user_id", None) != user.get("id")):
        raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "Not your transaction"})
    # Explicitly cast to Postgres enum to avoid type mismatch on update
    db.execute(text("UPDATE transactions SET category = CAST(:cat AS tx_category) WHERE id = :id"), {"cat": cat, "id": tx_id})
    db.commit()

    # Return joined view consistent with list endpoint
    stmt = (
        select(
            Transactions.id.label("id"),
            Transactions.user_id,
            func.cast(Transactions.category, String).label("category"),
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


# Webhook scaffolds (Stripe/Plaid)
@app.post("/v1/webhooks/stripe")
async def webhook_stripe(request: Request):
    secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    payload = await request.body()
    sig = request.headers.get("Stripe-Signature")
    if secret and sig:
        try:
            mac = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
            if mac not in sig:
                return JSONResponse(status_code=400, content={"error": {"code": "invalid_signature", "message": "Signature mismatch"}})
        except Exception:
            return JSONResponse(status_code=400, content={"error": {"code": "invalid_request", "message": "Unable to verify"}})
    # Accept in dev even without secret
    return {"ok": True}


@app.post("/v1/webhooks/plaid")
async def webhook_plaid(request: Request):
    secret = os.getenv("PLAID_WEBHOOK_SECRET")
    payload = await request.body()
    sig = request.headers.get("Plaid-Verification") or request.headers.get("Plaid-Webhook-Signature")
    if secret and sig:
        try:
            mac = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
            if mac not in sig:
                return JSONResponse(status_code=400, content={"error": {"code": "invalid_signature", "message": "Signature mismatch"}})
        except Exception:
            return JSONResponse(status_code=400, content={"error": {"code": "invalid_request", "message": "Unable to verify"}})
    return {"ok": True}


# Retention job trigger (dev/admin)
@app.post("/v1/admin/retention/transactions_raw")
async def trigger_retention(days: int = 90, dry_run: bool = True, authorization: str | None = Header(default=None), db: Session = Depends(get_session)):
    # Require admin
    user, _plan = _get_auth_user(authorization, db)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "Admin required"})
    q = _queue()
    job = q.enqueue_call(
        func="worker.jobs.retention.enforce_transactions_raw_retention",
        args=(days, dry_run),
        timeout=120,
    )
    try:
        db.execute(text("INSERT INTO audit_events (user_id, actor, action, payload_json) VALUES (:uid, 'admin', :act, :payload)"),
                   {"uid": user["id"], "act": "admin_action", "payload": json.dumps({"action": "retention_transactions_raw", "days": days, "dry_run": dry_run})})
        db.commit()
    except Exception:
        pass
    return {"job_id": job.id}


class AdminPlanPayload(BaseModel):
    plan: Literal["free", "plus"]


@app.post("/v1/admin/users/{user_id}/plan")
async def set_user_plan(user_id: int, payload: AdminPlanPayload, authorization: str | None = Header(default=None), db: Session = Depends(get_session)):
    user, _ = _get_auth_user(authorization, db)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "Admin required"})
    # Upsert billing plan
    row = db.execute(select(Billing).where(Billing.user_id == user_id)).scalar_one_or_none()
    if row:
        db.execute(text("UPDATE billing SET plan = CAST(:plan AS plan) WHERE user_id = :uid"), {"plan": payload.plan, "uid": user_id})
    else:
        db.execute(text("INSERT INTO billing (user_id, plan) VALUES (:uid, CAST(:plan AS plan))"), {"uid": user_id, "plan": payload.plan})
    db.commit()
    try:
        db.execute(text("INSERT INTO audit_events (user_id, actor, action, payload_json) VALUES (:uid, 'admin', :act, :payload)"),
                   {"uid": user["id"], "act": "admin_action", "payload": json.dumps({"action": "set_plan", "target_user_id": user_id, "plan": payload.plan})})
        db.commit()
    except Exception:
        pass
    return {"ok": True}
