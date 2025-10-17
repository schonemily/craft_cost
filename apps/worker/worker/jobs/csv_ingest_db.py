from __future__ import annotations
import csv
import io
import os
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any

from sqlalchemy import create_engine, text

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql+psycopg://postgres:postgres@db:5432/app")


def _ensure_dev_user(conn) -> int:
    # ensure a dev user exists; return its id
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


def ingest_csv(data: bytes) -> Dict[str, Any]:
    engine = create_engine(POSTGRES_URL, future=True)
    rows = 0
    with engine.begin() as conn:
        user_id = _ensure_dev_user(conn)
        buf = io.StringIO(data.decode("utf-8", errors="replace"))
        reader = csv.DictReader(buf)
        for rec in reader:
            try:
                dt = rec.get("date") or rec.get("Date")
                date_obj = datetime.strptime(dt.strip(), "%Y-%m-%d").date() if dt else None
                amount_str = (rec.get("amount") or rec.get("Amount") or "0").replace(",", "")
                amount = Decimal(amount_str)
                desc = (rec.get("description") or rec.get("Description") or "").strip() or None
                merchant_raw = (rec.get("merchant") or rec.get("Merchant") or rec.get("merchant_raw") or "").strip() or None

                tx_raw_id = conn.execute(text("""
                    INSERT INTO transactions_raw (user_id, account_id, plaid_tx_id, date, amount, iso_currency, description, merchant_raw, meta_json)
                    VALUES (:user_id, NULL, NULL, :date, :amount, NULL, :description, :merchant_raw, NULL)
                    RETURNING id
                """), {
                    "user_id": user_id,
                    "date": date_obj,
                    "amount": amount,
                    "description": desc,
                    "merchant_raw": merchant_raw,
                }).fetchone()[0]

                conn.execute(text("""
                    INSERT INTO transactions (user_id, tx_id, category, merchant_norm, normalized_desc, confidence, is_recurring)
                    VALUES (:user_id, :tx_id, NULL, :merchant_norm, :normalized_desc, NULL, FALSE)
                """), {
                    "user_id": user_id,
                    "tx_id": tx_raw_id,
                    "merchant_norm": merchant_raw,
                    "normalized_desc": desc,
                })
                rows += 1
            except Exception:
                # Continue on bad rows; production code should dead-letter
                continue
    return {"rows": rows}
