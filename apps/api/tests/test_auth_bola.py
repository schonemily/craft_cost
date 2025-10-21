from __future__ import annotations
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from app.main import app

client = TestClient(app)

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql+psycopg://postgres:postgres@db:5432/app")
MINT_TOKEN_SECRET = os.getenv("MINT_TOKEN_SECRET", "dev_mint_secret")


def create_user(email: str) -> int:
    engine = create_engine(POSTGRES_URL, future=True)
    with engine.begin() as conn:
        row = conn.execute(text("SELECT id FROM users WHERE email=:e"), {"e": email}).fetchone()
        if row:
            return int(row[0])
        uid = conn.execute(text("INSERT INTO users (email, role) VALUES (:e, 'user') RETURNING id"), {"e": email}).fetchone()[0]
        return int(uid)


def mint_token(email: str) -> str:
    r = client.post("/v1/auth/mint", headers={"X-Internal-Secret": MINT_TOKEN_SECRET}, json={"email": email})
    assert r.status_code == 200
    return r.json()["access_token"]


def ensure_tx_for_owner(owner_id: int) -> int:
    engine = create_engine(POSTGRES_URL, future=True)
    with engine.begin() as conn:
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
                    "user_id": owner_id,
                    "date": "2025-01-10",
                    "amount": -5.00,
                    "description": "bola test tx",
                    "merchant_raw": "BOLA Shop",
                },
            ).fetchone()[0]
        )
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
                    "user_id": owner_id,
                    "tx_id": tx_raw_id,
                    "merchant_norm": "BOLA Shop",
                    "normalized_desc": "bola test tx",
                },
            ).fetchone()[0]
        )
        return tx_id


def test_recategorize_denied_for_non_owner():
    u1_email = "bola1@example.com"
    u2_email = "bola2@example.com"
    u1_id = create_user(u1_email)
    u2_id = create_user(u2_email)
    tx_id = ensure_tx_for_owner(u2_id)

    token1 = mint_token(u1_email)
    r = client.post(f"/v1/transactions/{tx_id}/recategorize", json={"category": "grocery"}, headers={"Authorization": f"Bearer {token1}"})
    assert r.status_code == 403

    token2 = mint_token(u2_email)
    r2 = client.post(f"/v1/transactions/{tx_id}/recategorize", json={"category": "grocery"}, headers={"Authorization": f"Bearer {token2}"})
    assert r2.status_code == 200
