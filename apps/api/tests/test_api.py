from __future__ import annotations
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from app.main import app

client = TestClient(app)

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql+psycopg://postgres:postgres@db:5432/app")


def ensure_fixture_tx() -> int:
    engine = create_engine(POSTGRES_URL, future=True)
    with engine.begin() as conn:
        # create or get user
        res = conn.execute(text("SELECT id FROM users WHERE email=:email"), {"email": "pytest@example.com"}).fetchone()
        if res:
            user_id = int(res[0])
        else:
            user_id = int(
                conn.execute(
                    text(
                        """
                        INSERT INTO users (email, auth_id, kyc_min, marketing_opt_in)
                        VALUES (:email, NULL, FALSE, FALSE)
                        RETURNING id
                        """
                    ),
                    {"email": "pytest@example.com"},
                ).fetchone()[0]
            )
        # insert raw tx
        tx_raw_id = int(
            conn.execute(
                text(
                    """
                    INSERT INTO transactions_raw (user_id, account_id, plaid_tx_id, date, amount, iso_currency, description, merchant_raw, meta_json)
                    VALUES (:user_id, NULL, NULL, :date, :amount, NULL, :description, :merchant_raw, NULL)
                    RETURNING id
                    """
                ),
                {
                    "user_id": user_id,
                    "date": "2025-01-10",
                    "amount": -12.34,
                    "description": "pytest tx",
                    "merchant_raw": "PyTest Shop",
                },
            ).fetchone()[0]
        )
        # insert normalized
        tx_id = int(
            conn.execute(
                text(
                    """
                    INSERT INTO transactions (user_id, tx_id, category, merchant_norm, normalized_desc, confidence, is_recurring)
                    VALUES (:user_id, :tx_id, NULL, :merchant_norm, :normalized_desc, NULL, FALSE)
                    RETURNING id
                    """
                ),
                {
                    "user_id": user_id,
                    "tx_id": tx_raw_id,
                    "merchant_norm": "PyTest Shop",
                    "normalized_desc": "pytest tx",
                },
            ).fetchone()[0]
        )
    return tx_id


def test_healthz_ok():
    r = client.get("/healthz")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"


def test_flags_toggle_roundtrip():
    # enable
    r = client.post("/v1/flags", json={"key": "csv_ingestion_enabled", "value": True})
    assert r.status_code == 200
    # read
    r = client.get("/v1/flags")
    assert r.status_code == 200
    flags = r.json().get("flags", {})
    assert "csv_ingestion_enabled" in flags


def test_spend_summary_shape():
    r = client.get("/v1/spend/summary?period=last_90d")
    assert r.status_code == 200
    data = r.json()
    assert "total" in data and "by_category" in data


def test_transactions_and_recategorize_flow():
    tx_id = ensure_fixture_tx()
    # recategorize to grocery
    r = client.post(f"/v1/transactions/{tx_id}/recategorize", json={"category": "grocery"})
    assert r.status_code == 200
    payload = r.json()
    assert payload.get("id") == tx_id
    assert payload.get("category") == "grocery"
    # list should include our tx id somewhere
    r = client.get("/v1/transactions?limit=20")
    assert r.status_code == 200
    items = r.json().get("items", [])
    assert any(it.get("id") == tx_id and it.get("category") == "grocery" for it in items)
