import os
import time
import uuid
import json
import hmac
import hashlib
import logging
import redis
import csv
import io
import re
from rq import Queue
from rq.job import Job
from fastapi import FastAPI, UploadFile, File, HTTPException, status, Depends, Query, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from typing import List, Optional, Literal
import stripe
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
from datetime import datetime
from openpyxl import load_workbook
from PyPDF2 import PdfReader

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

# Stripe configuration
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

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

def _redis() -> redis.Redis:
    return redis.from_url(_redis_url)


# Stripe helper: per-user customer caching
def _stripe_customer_for(uid: int, email: str) -> str:
    r = _redis()
    key = f"stripe:cust:{uid}"
    existing = r.get(key)
    if existing:
        try:
            return existing.decode("utf-8") if isinstance(existing, (bytes, bytearray)) else str(existing)
        except Exception:
            return str(existing)
    cust = stripe.Customer.create(email=email)
    r.set(key, cust.id)
    return cust.id


class FinConnSavePayload(BaseModel):
    session_id: Optional[str] = None
    account_ids: Optional[List[str]] = None


@app.post("/v1/finconn/session")
async def finconn_create_session(authorization: str | None = Header(default=None), db: Session = Depends(get_session)):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail={"code": "stripe_not_configured", "message": "STRIPE_SECRET_KEY missing"})
    user, _plan = _get_auth_user(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Login required"})
    uid = int(user["id"])
    email = str(user.get("email") or "")
    customer_id = _stripe_customer_for(uid, email)
    try:
        session = stripe.financial_connections.Session.create(
            account_holder={"type": "customer", "customer": customer_id},
            permissions=["balances", "ownership", "transactions"],
            filters={"countries": ["US"]},
            prefetched_data={"balances": True},
        )
        return {"id": session.id, "client_secret": session.client_secret}
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "fc_session_failed", "message": str(e)})


@app.post("/v1/finconn/accounts")
async def finconn_save_accounts(payload: FinConnSavePayload, authorization: str | None = Header(default=None), db: Session = Depends(get_session)):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail={"code": "stripe_not_configured", "message": "STRIPE_SECRET_KEY missing"})
    user, _plan = _get_auth_user(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Login required"})
    uid = int(user["id"]) 
    r = _redis()
    items = []
    ids: List[str] = list(payload.account_ids or [])
    # If session_id provided, resolve to account ids server-side
    if payload.session_id:
        try:
            sess = stripe.financial_connections.Session.retrieve(payload.session_id)
            sess_accounts = []
            # Handle both list and {data:[...]}
            try:
                sess_accounts = [getattr(a, "id", None) or (a.get("id") if isinstance(a, dict) else None) for a in (getattr(sess, "accounts", []) or [])]
            except Exception:
                data = getattr(getattr(sess, "accounts", {}), "data", []) or []
                sess_accounts = [getattr(a, "id", None) or (a.get("id") if isinstance(a, dict) else None) for a in data]
            ids.extend([x for x in sess_accounts if x])
        except Exception:
            pass
    # de-dup ids
    seen = set()
    uniq_ids = []
    for x in ids:
        if x and x not in seen:
            seen.add(x)
            uniq_ids.append(x)
    for acc_id in uniq_ids:
        try:
            acc = stripe.financial_connections.Account.retrieve(acc_id)
            info = {
                "id": acc.id,
                "display_name": getattr(acc, "display_name", None),
                "institution_name": getattr(acc, "institution_name", None),
                "last4": getattr(acc, "last4", None),
                "category": getattr(acc, "category", None),
                "subcategory": getattr(acc, "subcategory", None),
            }
            items.append(info)
            # map acc->user for webhook cleanup
            r.set(f"fc:acct:{acc.id}", str(uid))
        except Exception:
            continue
    key = f"fc:accounts:{uid}"
    r.set(key, json.dumps(items))
    return {"items": items}


@app.get("/v1/finconn/accounts")
async def finconn_list_accounts(authorization: str | None = Header(default=None), db: Session = Depends(get_session)):
    user, _plan = _get_auth_user(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Login required"})
    uid = int(user["id"]) 
    r = _redis()
    raw = r.get(f"fc:accounts:{uid}")
    arr = json.loads(raw) if raw else []
    return {"items": arr}


@app.post("/v1/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("Stripe-Signature")
    if not STRIPE_WEBHOOK_SECRET:
        # Accept silently in dev when not configured
        return {"received": True, "unchecked": True}
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except Exception:
        raise HTTPException(status_code=400, detail={"code": "bad_signature", "message": "Invalid webhook signature"})

    et = event.get("type") or getattr(event, "type", None)
    obj = event.get("data", {}).get("object") if isinstance(event, dict) else getattr(event, "data", {}).get("object")
    try:
        if et == "financial_connections.account.disconnected" and obj:
            acc_id = obj.get("id")
            r = _redis()
            uid_raw = r.get(f"fc:acct:{acc_id}")
            if uid_raw:
                try:
                    uid = int(uid_raw.decode("utf-8")) if isinstance(uid_raw, (bytes, bytearray)) else int(uid_raw)
                    k = f"fc:accounts:{uid}"
                    raw = r.get(k)
                    arr = json.loads(raw) if raw else []
                    arr = [x for x in arr if str(x.get("id")) != acc_id]
                    r.set(k, json.dumps(arr))
                except Exception:
                    pass
            r.delete(f"fc:acct:{acc_id}")
    except Exception:
        # best-effort; never fail webhook processing in dev
        pass
    return {"received": True}


def _stripe_ensure_price(period: str) -> str:
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail={"code": "stripe_not_configured", "message": "STRIPE_SECRET_KEY missing"})
    r = _redis()
    price_key = f"stripe:price:{period}"
    existing = r.get(price_key)
    if existing:
        try:
            return existing.decode("utf-8") if isinstance(existing, (bytes, bytearray)) else str(existing)
        except Exception:
            return str(existing)
    # Ensure product
    pkey = "stripe:product:plus"
    prod_id_raw = r.get(pkey)
    if prod_id_raw:
        try:
            product_id = prod_id_raw.decode("utf-8") if isinstance(prod_id_raw, (bytes, bytearray)) else str(prod_id_raw)
        except Exception:
            product_id = str(prod_id_raw)
    else:
        product = stripe.Product.create(name="Plus Plan", description="Plus subscription plan")
        product_id = product.id
        r.set(pkey, product_id)
    interval = "month" if period == "monthly" else "year"
    price = stripe.Price.create(product=product_id, unit_amount=100, currency="usd", recurring={"interval": interval})
    r.set(price_key, price.id)
    return price.id


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


# ---- Statement detection/parsing (CSV/XLSX, basic PDF guidance) ----

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(15 * 1024 * 1024)))  # 15MB

_DATE_TOKENS = [
    "posting date", "post date", "transaction date", "date"
]
_DESC_TOKENS = [
    "description", "transaction description", "memo", "payee", "name"
]
_AMOUNT_TOKENS = [
    "amount", "charge", "payment", "deposit"
]
_DEBIT_TOKENS = [
    "debit", "withdrawal", "outflow"
]
_CREDIT_TOKENS = [
    "credit", "payment", "deposit", "inflow"
]
_BALANCE_TOKENS = [
    "balance", "running balance"
]

def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s

def _best_match(headers: list[str], candidates: list[str]) -> str | None:
    hs = [_norm(h) for h in headers]
    for cand in candidates:
        if cand in hs:
            return headers[hs.index(cand)]
    # fuzzy contains
    for i, h in enumerate(hs):
        for cand in candidates:
            if cand in h:
                return headers[i]
    return None

def _classify_headers(headers: list[str]) -> dict:
    h_date = _best_match(headers, _DATE_TOKENS)
    h_desc = _best_match(headers, _DESC_TOKENS)
    h_amount = _best_match(headers, _AMOUNT_TOKENS)
    h_debit = _best_match(headers, _DEBIT_TOKENS)
    h_credit = _best_match(headers, _CREDIT_TOKENS)
    h_balance = _best_match(headers, _BALANCE_TOKENS)
    shape = "unknown"
    if h_debit and h_credit:
        shape = "split_debit_credit"
    elif h_amount:
        shape = "single_amount"
    mapping = {
        "date": h_date,
        "description": h_desc,
        "amount": h_amount,
        "debit": h_debit,
        "credit": h_credit,
        "balance": h_balance,
    }
    detected = shape != "unknown" and (h_date or h_desc) is not None
    return {"shape": shape, "mapping": mapping, "detected": bool(detected)}

def _csv_headers(data: bytes) -> list[str]:
    # Try utf-8 first, fallback latin-1
    for enc in ("utf-8", "latin-1"):
        try:
            text = data.decode(enc, errors="strict")
            break
        except Exception:
            text = data.decode(enc, errors="ignore")
            break
    sample = "\n".join(text.splitlines()[:3])
    reader = csv.reader(io.StringIO(sample))
    try:
        header = next(reader)
        return [str(h or "").strip() for h in header]
    except Exception:
        # fallback: first line split by comma
        first = sample.splitlines()[0] if sample else ""
        return [h.strip() for h in first.split(",") if h.strip()]

def _xlsx_headers(data: bytes) -> list[str]:
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    ws = wb.worksheets[0]
    row1 = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
    headers = [str(x) if x is not None else "" for x in row1]
    return headers

def _xlsx_to_csv_bytes(data: bytes) -> bytes:
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    ws = wb.worksheets[0]
    sio = io.StringIO()
    writer = csv.writer(sio)
    for row in ws.iter_rows(values_only=True):
        vals = ["" if v is None else (str(v) if not isinstance(v, (int, float)) else v) for v in row]
        writer.writerow(vals)
    return sio.getvalue().encode("utf-8")

def _parse_amount(val) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        try:
            return float(val)
        except Exception:
            return None
    s = str(val).strip()
    if not s:
        return None
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    s = s.replace(",", "").replace("$", "").replace("€", "").replace("£", "")
    if s.lower().endswith(" cr"):
        s = s[:-3].strip()
    if s.lower().endswith(" dr"):
        s = s[:-3].strip()
        neg = True
    try:
        v = float(s)
        return -v if neg else v
    except Exception:
        # try to extract digits
        m = re.search(r"-?\d+(?:\.\d+)?", s)
        if not m:
            return None
        v = float(m.group(0))
        return -v if neg or s.strip().startswith("-") else v

def _parse_date(val) -> str | None:
    if not val:
        return None
    if isinstance(val, datetime):
        return val.date().isoformat()
    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d", "%d-%b-%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except Exception:
            continue
    # leave as-is if looks like ISO
    if re.match(r"\d{4}-\d{2}-\d{2}", s):
        return s[:10]
    return None

def _normalize_csv(csv_bytes: bytes) -> bytes:
    # Decode using tolerant approach
    text: str
    try:
        text = csv_bytes.decode("utf-8")
    except Exception:
        text = csv_bytes.decode("latin-1", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=422, detail={"code": "bad_csv", "message": "Missing header row"})
    headers = [h for h in reader.fieldnames if h is not None]
    cls = _classify_headers(headers)
    if not cls.get("detected"):
        raise HTTPException(status_code=422, detail={"code": "unsupported_format", "message": "Could not recognize columns"})
    m = cls["mapping"]
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["date", "amount", "description"])  # normalized minimal schema
    for row in reader:
        raw_date = row.get(m.get("date")) if m.get("date") else (row.get("Date") or row.get("date"))
        raw_desc = row.get(m.get("description")) if m.get("description") else (row.get("Description") or row.get("description"))
        amt: float | None = None
        if cls["shape"] == "single_amount":
            amt = _parse_amount(row.get(m.get("amount"))) if m.get("amount") else None
        elif cls["shape"] == "split_debit_credit":
            d = _parse_amount(row.get(m.get("debit"))) if m.get("debit") else None
            c = _parse_amount(row.get(m.get("credit"))) if m.get("credit") else None
            if d is not None or c is not None:
                d = d or 0.0
                c = c or 0.0
                amt = (c - d)
        date_iso = _parse_date(raw_date)
        desc = (raw_desc or "").strip()
        if date_iso is None and amt is None and not desc:
            continue  # skip empty row
        # Default any missing
        if date_iso is None:
            # skip if hopeless
            continue
        if amt is None:
            amt = 0.0
        w.writerow([date_iso, f"{amt:.2f}", desc])
    return out.getvalue().encode("utf-8")

@app.post("/v1/statements/detect")
async def detect_statement(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail={"code": "file_too_large", "message": "File exceeds size limit"})
    name = (file.filename or "").lower()
    ctype = (file.content_type or "").lower()

    try:
        if name.endswith(".csv") or "csv" in ctype:
            headers = _csv_headers(data[:64*1024])
            result = _classify_headers(headers)
            return {"kind": "csv", "headers": headers, **result,
                    "recommended_action": "parse" if result["detected"] else "manual_map"}
        if name.endswith(".xlsx") or "spreadsheetml" in ctype:
            headers = _xlsx_headers(data)
            result = _classify_headers(headers)
            return {"kind": "xlsx", "headers": headers, **result,
                    "recommended_action": "parse" if result["detected"] else "manual_map"}
        if name.endswith(".pdf") or ctype == "application/pdf":
            # basic guidance only
            try:
                reader = PdfReader(io.BytesIO(data))
                text = reader.pages[0].extract_text() if reader.pages else ""
                has_table = bool(re.search(r"Date\s+.*Amount|Debit|Credit", text or "", flags=re.I))
            except Exception:
                has_table = False
            return {"kind": "pdf", "detected": has_table, "recommended_action": "convert_to_csv"}
        return {"kind": "unknown", "detected": False, "recommended_action": "convert_to_csv"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "detect_failed", "message": str(e)})


@app.post("/v1/statements/ingest")
async def ingest_statement(
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_session),
):
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail={"code": "file_too_large", "message": "File exceeds size limit"})
    user, _plan = _get_auth_user(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Login required"})

    name = (file.filename or "").lower()
    ctype = (file.content_type or "").lower()
    csv_bytes: bytes
    try:
        if name.endswith(".csv") or "csv" in ctype:
            csv_bytes = data
        elif name.endswith(".xlsx") or "spreadsheetml" in ctype:
            csv_bytes = _xlsx_to_csv_bytes(data)
        else:
            raise HTTPException(status_code=415, detail={"code": "unsupported_type", "message": "Please upload CSV or XLSX"})
        # Normalize columns to minimal schema
        csv_bytes = _normalize_csv(csv_bytes)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "convert_failed", "message": str(e)})

    q = _queue()
    job = q.enqueue_call(
        func="worker.jobs.csv_ingest_db.ingest_csv",
        args=(csv_bytes,),
        kwargs={"user_id": int(user["id"]), "user_email": user["email"]},
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
        .order_by(TransactionsRaw.date.desc(), Transactions.id.desc())
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

@app.delete("/v1/transactions")
async def delete_all_transactions(authorization: str | None = Header(default=None), db: Session = Depends(get_session)):
    user, _plan = _get_auth_user(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Login required"})
    # Count first for response
    cnt_row = db.execute(text("SELECT COUNT(*) FROM transactions_raw WHERE user_id=:uid"), {"uid": user["id"]}).first()
    count = int(cnt_row[0]) if cnt_row else 0
    # Delete normalized first (in case FK cascade is not present)
    db.execute(text("""
        DELETE FROM transactions
        WHERE user_id=:uid AND tx_id IN (SELECT id FROM transactions_raw WHERE user_id=:uid)
    """), {"uid": user["id"]})
    # Then delete raw rows
    db.execute(text("DELETE FROM transactions_raw WHERE user_id=:uid"), {"uid": user["id"]})
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail={"code": "delete_failed", "message": "Could not clear transactions"})
    return {"ok": True, "deleted": count}

@app.post("/v1/transactions/backfill")
async def backfill_transactions(authorization: str | None = Header(default=None), db: Session = Depends(get_session)):
    user, _plan = _get_auth_user(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Login required"})
    # Insert missing normalized rows for this user; leave category as NULL to avoid enum cast issues
    try:
        db.execute(text(
            """
            INSERT INTO transactions (user_id, tx_id, category, merchant_norm, normalized_desc, confidence, is_recurring)
            SELECT tr.user_id, tr.id, NULL, tr.merchant_raw, tr.description, NULL, FALSE
            FROM transactions_raw tr
            LEFT JOIN transactions t ON t.tx_id = tr.id
            WHERE tr.user_id = :uid AND t.id IS NULL
            """
        ), {"uid": user["id"]})
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail={"code": "backfill_failed", "message": str(e)})
    return {"ok": True}

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


class ManualSubPayload(BaseModel):
    title: str
    amount: Optional[float] = None
    cadence: Optional[str] = "monthly"


@app.get("/v1/subscriptions")
async def list_subscriptions(authorization: str | None = Header(default=None), db: Session = Depends(get_session)):
    user, _plan = _get_auth_user(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Login required"})
    uid = int(user["id"])
    sugs = generate_suggestions(db, user_id=uid)
    derived = [s for s in sugs if ("subscriptions" in (s.get("tags") or []) or str(s.get("id") or "").startswith("sub:") or str(s.get("id") or "").startswith("streaming:"))]
    r = _redis()
    manual_raw = r.get(f"subs:{uid}")
    manual = json.loads(manual_raw) if manual_raw else []
    return {"items": manual + derived}


@app.post("/v1/subscriptions/manual")
async def add_manual_subscription(payload: ManualSubPayload, authorization: str | None = Header(default=None), db: Session = Depends(get_session)):
    user, _ = _get_auth_user(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Login required"})
    uid = int(user["id"])
    r = _redis()
    key = f"subs:{uid}"
    raw = r.get(key)
    arr = json.loads(raw) if raw else []
    item = {
        "id": f"manual:{uuid.uuid4().hex}",
        "title": payload.title,
        "summary": f"${payload.amount}/{payload.cadence}" if payload.amount else payload.cadence,
        "estimated_monthly_saving": 0,
        "tags": ["subscriptions", "manual"],
        "evidence": [],
        "created_at": datetime.utcnow().isoformat(),
    }
    arr.insert(0, item)
    r.set(key, json.dumps(arr))
    return {"ok": True, "item": item}


@app.delete("/v1/subscriptions/manual/{item_id}")
async def delete_manual_subscription(item_id: str, authorization: str | None = Header(default=None), db: Session = Depends(get_session)):
    user, _ = _get_auth_user(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Login required"})
    uid = int(user["id"])
    if not item_id or not item_id.startswith("manual:"):
        raise HTTPException(status_code=400, detail={"code": "bad_request", "message": "Invalid manual subscription id"})
    r = _redis()
    key = f"subs:{uid}"
    raw = r.get(key)
    arr = json.loads(raw) if raw else []
    new_arr = [x for x in arr if str(x.get("id")) != item_id]
    if len(new_arr) == len(arr):
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Item not found"})
    r.set(key, json.dumps(new_arr))
    return {"ok": True, "deleted": True, "id": item_id}


class NegotiationPayload(BaseModel):
    merchant: str
    account: Optional[str] = None


@app.get("/v1/negotiations")
async def list_negotiations(authorization: str | None = Header(default=None), db: Session = Depends(get_session)):
    user, _ = _get_auth_user(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Login required"})
    uid = int(user["id"])
    r = _redis()
    raw = r.get(f"neg:{uid}")
    arr = json.loads(raw) if raw else []
    return {"items": arr}


@app.post("/v1/negotiations")
async def create_negotiation(payload: NegotiationPayload, authorization: str | None = Header(default=None), db: Session = Depends(get_session)):
    user, _ = _get_auth_user(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Login required"})
    uid = int(user["id"])
    r = _redis()
    key = f"neg:{uid}"
    raw = r.get(key)
    arr = json.loads(raw) if raw else []
    item = {
        "id": f"n:{uuid.uuid4().hex}",
        "merchant": payload.merchant,
        "account": payload.account,
        "status": "draft",
        "created_at": datetime.utcnow().isoformat(),
    }
    arr.insert(0, item)
    r.set(key, json.dumps(arr))
    return {"ok": True, "item": item}


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


# Billing: upgrade current authenticated user to plus
class BillingUpgradePayload(BaseModel):
    plan: Literal["plus"] = "plus"


@app.post("/v1/billing/upgrade")
async def billing_upgrade(payload: BillingUpgradePayload, authorization: str | None = Header(default=None), db: Session = Depends(get_session)):
    user, _plan = _get_auth_user(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Login required"})
    uid = int(user["id"])
    row = db.execute(select(Billing).where(Billing.user_id == uid)).scalar_one_or_none()
    if row:
        db.execute(text("UPDATE billing SET plan = CAST(:plan AS plan) WHERE user_id = :uid"), {"plan": payload.plan, "uid": uid})
    else:
        db.execute(text("INSERT INTO billing (user_id, plan) VALUES (:uid, CAST(:plan AS plan))"), {"uid": uid, "plan": payload.plan})
    db.commit()
    return {"ok": True, "plan": payload.plan}


@app.get("/v1/billing/status")
async def billing_status(authorization: str | None = Header(default=None), db: Session = Depends(get_session)):
    user, plan = _get_auth_user(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Login required"})
    return {"plan": plan}


class StripeCheckoutPayload(BaseModel):
    period: Literal["monthly", "annual"] = "monthly"


@app.post("/v1/billing/stripe/checkout")
async def stripe_checkout(payload: StripeCheckoutPayload, authorization: str | None = Header(default=None), db: Session = Depends(get_session)):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail={"code": "stripe_not_configured", "message": "STRIPE_SECRET_KEY missing"})
    user, _plan = _get_auth_user(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Login required"})
    uid = int(user["id"])
    price_monthly = os.getenv("STRIPE_PRICE_ID_MONTHLY")
    price_annual = os.getenv("STRIPE_PRICE_ID_ANNUAL")
    price_id = price_monthly if payload.period == "monthly" else price_annual
    if not price_id:
        # Auto-create $1.00 price and cache in Redis
        price_id = _stripe_ensure_price(payload.period)
    web_base = os.getenv("WEB_BASE_URL", "http://localhost:3001")
    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{web_base}/dashboard?checkout=success&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{web_base}/?checkout=canceled",
            client_reference_id=str(uid),
            customer_email=(user.get("email") or None),
            metadata={"user_id": str(uid), "period": payload.period},
            allow_promotion_codes=True,
        )
        return {"id": session.get("id"), "url": session.get("url")}
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "stripe_error", "message": str(e)})


@app.post("/v1/billing/stripe/portal")
async def stripe_portal(authorization: str | None = Header(default=None), db: Session = Depends(get_session)):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail={"code": "stripe_not_configured", "message": "STRIPE_SECRET_KEY missing"})
    user, _plan = _get_auth_user(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Login required"})
    uid = int(user["id"])
    r = _redis()
    cust_raw = r.get(f"stripe:customer:{uid}")
    customer_id = (
        cust_raw.decode("utf-8") if isinstance(cust_raw, (bytes, bytearray)) else (str(cust_raw) if cust_raw else None)
    )
    try:
        if not customer_id and user.get("email"):
            res = stripe.Customer.list(email=user["email"], limit=1)
            if res and getattr(res, "data", None):
                customer_id = res.data[0].id
                r.set(f"stripe:customer:{uid}", customer_id)
        if not customer_id:
            c = stripe.Customer.create(email=user.get("email") or None, metadata={"user_id": str(uid)})
            customer_id = c.id
            r.set(f"stripe:customer:{uid}", customer_id)
        web_base = os.getenv("WEB_BASE_URL", "http://localhost:3001")
        ps = stripe.billing_portal.Session.create(customer=customer_id, return_url=f"{web_base}/dashboard")
        return {"url": ps.get("url") or getattr(ps, "url", None)}
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "stripe_error", "message": str(e)})


# Paddle webhook (dev-friendly placeholder). In production, verify using Paddle's signature scheme.
@app.post("/v1/billing/webhook/paddle")
async def paddle_webhook(request: Request, db: Session = Depends(get_session)):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": {"code": "invalid_json", "message": "Invalid payload"}})
    secret = os.getenv("PADDLE_WEBHOOK_SECRET")
    if secret:
        supplied = request.headers.get("X-Webhook-Secret") or request.headers.get("X-Paddle-Webhook-Secret")
        if not supplied or supplied != secret:
            return JSONResponse(status_code=401, content={"error": {"code": "unauthorized", "message": "Invalid webhook secret"}})
    event_type = str(body.get("event_type") or body.get("eventName") or "").lower()
    email = None
    # Try Paddle v2 structure
    try:
        email = (
            body.get("data", {}).get("customer", {}).get("email")
            or body.get("data", {}).get("user", {}).get("email")
        )
    except Exception:
        email = None
    if event_type in {"transaction.completed", "subscription.activated"} and email:
        row = db.execute(select(Users).where(Users.email == email)).scalar_one_or_none()
        if row:
            uid = int(row.id)
            exists = db.execute(select(Billing).where(Billing.user_id == uid)).scalar_one_or_none()
            if exists:
                db.execute(text("UPDATE billing SET plan = CAST('plus' AS plan) WHERE user_id = :uid"), {"uid": uid})
            else:
                db.execute(text("INSERT INTO billing (user_id, plan) VALUES (:uid, CAST('plus' AS plan))"), {"uid": uid})
            db.commit()
            try:
                db.execute(text("INSERT INTO audit_events (user_id, actor, action, payload_json) VALUES (:uid, 'system', :act, :payload)"),
                           {"uid": uid, "act": "paddle_webhook", "payload": json.dumps({"event": event_type})})
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


@app.post("/v1/webhooks/stripe")
async def webhook_stripe(request: Request, db: Session = Depends(get_session)):
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")
    secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    event = None
    if secret:
        try:
            event = stripe.Webhook.construct_event(payload=payload, sig_header=sig_header, secret=secret)
        except Exception as e:
            return JSONResponse(status_code=400, content={"error": {"code": "invalid_signature", "message": str(e)}})
    else:
        # Dev: parse without verification
        try:
            event = json.loads(payload)
        except Exception:
            return JSONResponse(status_code=400, content={"error": {"code": "invalid_json", "message": "Invalid payload"}})

    et = (event.get("type") if isinstance(event, dict) else getattr(event, "type", "")) or ""
    data = (event.get("data", {}).get("object") if isinstance(event, dict) else getattr(event, "data", {}).get("object")) or {}
    if et == "checkout.session.completed":
        uid = (
            (data.get("metadata", {}) or {}).get("user_id")
            or data.get("client_reference_id")
        )
        email = (data.get("customer_details") or {}).get("email")
        customer_id = data.get("customer")
        try:
            if uid:
                uid = int(uid)
                exists = db.execute(select(Billing).where(Billing.user_id == uid)).scalar_one_or_none()
                if exists:
                    db.execute(text("UPDATE billing SET plan = CAST('plus' AS plan) WHERE user_id = :uid"), {"uid": uid})
                else:
                    db.execute(text("INSERT INTO billing (user_id, plan) VALUES (:uid, CAST('plus' AS plan))"), {"uid": uid})
                db.commit()
                # Cache Stripe customer mapping
                try:
                    if customer_id:
                        r = _redis()
                        r.set(f"stripe:customer:{uid}", str(customer_id))
                except Exception:
                    pass
            elif email:
                row = db.execute(select(Users).where(Users.email == email)).scalar_one_or_none()
                if row:
                    uid2 = int(row.id)
                    exists = db.execute(select(Billing).where(Billing.user_id == uid2)).scalar_one_or_none()
                    if exists:
                        db.execute(text("UPDATE billing SET plan = CAST('plus' AS plan) WHERE user_id = :uid"), {"uid": uid2})
                    else:
                        db.execute(text("INSERT INTO billing (user_id, plan) VALUES (:uid, CAST('plus' AS plan))"), {"uid": uid2})
                    db.commit()
                    # Cache Stripe customer mapping
                    try:
                        if customer_id:
                            r = _redis()
                            r.set(f"stripe:customer:{uid2}", str(customer_id))
                    except Exception:
                        pass
        except Exception:
            pass
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
