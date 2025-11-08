from __future__ import annotations
import csv
import io
import os
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any
import hashlib

from sqlalchemy import create_engine, text

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql+psycopg://postgres:postgres@db:5432/app")


def _ensure_dev_user(conn) -> int:
    # ensure a dev user exists; return its id (match current schema)
    res = conn.execute(text("""
        SELECT id FROM users WHERE email=:email
    """), {"email": "dev@example.com"}).fetchone()
    if res:
        return int(res[0])
    res = conn.execute(text("""
        INSERT INTO users (email, auth_id, kyc_min, marketing_opt_in)
        VALUES (:email, NULL, FALSE, FALSE)
        RETURNING id
    """), {"email": "dev@example.com"}).fetchone()
    return int(res[0])


def _row_hash(user_id: int, date_s: str | None, amount: Decimal, desc: str | None, merchant_raw: str | None) -> str:
    # Normalize to a deterministic key; include user_id to avoid cross-user collisions
    base = "|".join([
        str(user_id),
        (date_s or "").strip(),
        f"{amount:.2f}",
        (desc or "").strip().lower(),
        (merchant_raw or "").strip().lower(),
    ])
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _guess_category(desc: str | None, merchant: str | None) -> str | None:
    t = f"{(merchant or '').lower()} {(desc or '').lower()}".strip()
    if not t:
        return None
    # Transport first: avoid misclassifying gas station as utilities
    if any(k in t for k in ("fuel", "gas station", "rideshare", "ride share", "uber", "lyft", "metro", "bus", "train", "taxi", "transport")):
        return "transport"
    # Housing
    if any(k in t for k in ("rent", "landlord")):
        return "housing"
    # Telco
    if any(k in t for k in ("internet", "isp", "mobile", "telco", "phone")):
        return "telco"
    # Utilities (not gas station)
    if any(k in t for k in ("utilit", "electric", "water", "power", "sewer", "energy", "natural gas", "gas bill", "gas utility", "gas company", "city utilities")):
        return "utilities"
    # Insurance
    if "insurance" in t:
        return "insurance"
    # Grocery
    if any(k in t for k in ("grocery", "grocer", "market")):
        return "grocery"
    # Dining
    if any(k in t for k in ("dining", "restaurant", "sushi", "pizza", "burger", "cafe", "coffee")):
        return "dining"
    # Subscriptions / streaming
    if any(k in t for k in ("stream", "subscription", "netflix", "hulu", "disney", "spotify", "apple tv", "youtube premium")):
        return "subscriptions"
    # Health / personal
    if any(k in t for k in ("pharmacy", "doctor", "clinic")):
        return "health"
    if any(k in t for k in ("gym", "fitness")):
        return "personal"
    # Income
    if any(k in t for k in ("salary", "payroll", "employer")):
        return "income"
    # Entertainment / travel / gift fallbacks
    if any(k in t for k in ("cinema", "movie", "entertainment")):
        return "entertainment"
    if any(k in t for k in ("flight", "hotel", "travel")):
        return "other"
    return None


def _parse_date_flexible(dt: str | None):
    if not dt:
        return None
    s = dt.strip()
    fmts = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%m/%d/%y",
        "%Y/%m/%d",
        "%d-%b-%Y",  # e.g., 05-Feb-2024
    ]
    for f in fmts:
        try:
            return datetime.strptime(s, f).date()
        except Exception:
            continue
    return None


def _parse_amount_flexible(raw: str | None) -> Decimal:
    s = (raw or "0").strip().replace(",", "").replace("$", "")
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    try:
        val = Decimal(s)
    except Exception:
        val = Decimal("0")
    return -val if neg else val


def _ensure_user_with_id(conn, uid: int, email: str | None) -> int:
    # Ensure a users row exists with the given id; create if missing with provided email
    res = conn.execute(text("""SELECT id FROM users WHERE id=:id"""), {"id": int(uid)}).fetchone()
    if res:
        return int(res[0])
    res = conn.execute(text("""
        INSERT INTO users (id, email, auth_id, kyc_min, marketing_opt_in)
        VALUES (:id, :email, NULL, FALSE, FALSE)
        RETURNING id
    """), {"id": int(uid), "email": (email or f"user{uid}@local")}).fetchone()
    return int(res[0])


def _ensure_user_by_email(conn, email: str) -> int:
    res = conn.execute(text("""SELECT id FROM users WHERE email=:email"""), {"email": email}).fetchone()
    if res:
        return int(res[0])
    res = conn.execute(text("""
        INSERT INTO users (email, auth_id, kyc_min, marketing_opt_in)
        VALUES (:email, NULL, FALSE, FALSE)
        RETURNING id
    """), {"email": email}).fetchone()
    return int(res[0])


def ingest_csv(data: bytes, user_id: int | None = None, user_email: str | None = None) -> Dict[str, Any]:
    engine = create_engine(POSTGRES_URL, future=True)
    rows = 0
    with engine.begin() as conn:
        # Determine/ensure DB user id to attach rows
        if user_id is not None:
            uid = _ensure_user_with_id(conn, int(user_id), user_email)
        elif user_email:
            uid = _ensure_user_by_email(conn, user_email)
        else:
            uid = _ensure_dev_user(conn)
        buf = io.StringIO(data.decode("utf-8", errors="replace"))
        reader = csv.DictReader(buf)
        for rec in reader:
            try:
                dt = rec.get("date") or rec.get("Date") or rec.get("transaction_date") or rec.get("Posting Date")
                date_obj = _parse_date_flexible(dt)
                if not date_obj:
                    raise ValueError("invalid_date")
                amount_raw = rec.get("amount") or rec.get("Amount") or rec.get("Debit") or rec.get("Credit") or "0"
                amount = _parse_amount_flexible(amount_raw)
                # If CSV separates Debit/Credit, prefer Debit as negative, Credit as positive
                if rec.get("Debit") and not rec.get("amount") and not rec.get("Amount"):
                    amount = -_parse_amount_flexible(rec.get("Debit"))
                if rec.get("Credit") and not rec.get("amount") and not rec.get("Amount"):
                    amount = _parse_amount_flexible(rec.get("Credit"))
                desc = (rec.get("description") or rec.get("Description") or rec.get("Narration") or "").strip() or None
                merchant_raw = (rec.get("merchant") or rec.get("Merchant") or rec.get("merchant_raw") or rec.get("Payee") or "").strip() or None

                rhash = _row_hash(uid, date_obj.isoformat() if date_obj else None, amount, desc, merchant_raw)
                existing = conn.execute(text("""
                    SELECT id FROM transactions_raw
                    WHERE user_id = :user_id AND row_hash = :row_hash
                    LIMIT 1
                """), {"user_id": uid, "row_hash": rhash}).fetchone()
                if existing:
                    continue

                tx_raw_id = conn.execute(text("""
                    INSERT INTO transactions_raw (user_id, account_id, plaid_tx_id, date, amount, iso_currency, description, merchant_raw, meta_json, row_hash)
                    VALUES (:user_id, NULL, NULL, :date, :amount, NULL, :description, :merchant_raw, NULL, :row_hash)
                    RETURNING id
                """), {
                    "user_id": uid,
                    "date": date_obj,
                    "amount": amount,
                    "description": desc,
                    "merchant_raw": merchant_raw,
                    "row_hash": rhash,
                }).fetchone()[0]

                cat = _guess_category(desc, merchant_raw)
                conn.execute(text("""
                    INSERT INTO transactions (user_id, tx_id, category, merchant_norm, normalized_desc, confidence, is_recurring)
                    VALUES (:user_id, :tx_id, CAST(:category AS tx_category), :merchant_norm, :normalized_desc, NULL, FALSE)
                """), {
                    "user_id": uid,
                    "tx_id": tx_raw_id,
                    "category": cat,
                    "merchant_norm": merchant_raw,
                    "normalized_desc": desc,
                })
                rows += 1
            except Exception:
                # Continue on bad rows; production code should dead-letter
                continue
    return {"rows": rows}
