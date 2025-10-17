from __future__ import annotations
import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text

# Ensure worker package is importable: add repo_root/apps to sys.path
HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[3]
APPS_DIR = REPO_ROOT / "apps"
sys.path.insert(0, str(APPS_DIR))

# Set POSTGRES_URL for the worker module before import
POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/app")
os.environ["POSTGRES_URL"] = POSTGRES_URL

from worker.jobs.csv_ingest_db import ingest_csv  # type: ignore  # noqa: E402


def test_worker_ingest_minimal_roundtrip():
    engine = create_engine(POSTGRES_URL, future=True)

    # Minimal CSV sample
    csv_bytes = (
        "date,description,amount,merchant\n"
        "2025-01-05,Groceries,-54.32,Local Market\n"
        "2025-01-06,Internet,-60.00,ISP Co\n"
    ).encode("utf-8")

    # Call worker ingest
    res = ingest_csv(csv_bytes)
    assert isinstance(res, dict)
    assert res.get("rows", 0) >= 2

    # Verify a row exists joined across normalized and raw tables
    with engine.begin() as conn:
        out = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM transactions t
                JOIN transactions_raw r ON t.tx_id = r.id
                WHERE r.description IN ('Groceries', 'Internet')
                """
            )
        ).scalar_one()
        assert out >= 2
