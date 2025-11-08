from __future__ import annotations
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import BigInteger, String, Text, Date, Numeric, DateTime, Boolean, func, ForeignKey
from sqlalchemy.dialects import postgresql


class Base(DeclarativeBase):
    pass


# Mirror DB enum values for tx_category so SQLAlchemy can serialize/deserialize correctly
TX_CATEGORY = postgresql.ENUM(
    "housing","utilities","telco","insurance","transport","grocery","dining","entertainment",
    "subscriptions","health","personal","fees","income","other",
    name="tx_category", create_type=False
)

ROLE = postgresql.ENUM(
    "user","admin",
    name="role", create_type=False
)

PLAN = postgresql.ENUM(
    "free","plus",
    name="plan", create_type=False
)


class TransactionsRaw(Base):
    __tablename__ = "transactions_raw"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    date: Mapped[Date] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    merchant_raw: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # For duplicate detection in merge mode
    row_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Transactions(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tx_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("transactions_raw.id", ondelete="CASCADE"), nullable=False)
    category: Mapped[str | None] = mapped_column(TX_CATEGORY, nullable=True)
    merchant_norm: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Import mode support: only active rows are considered for analytics
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=func.true())


class Flag(Base):
    __tablename__ = "flags"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    bool_value: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Users(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(ROLE, nullable=False, default="user")
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Billing(Base):
    __tablename__ = "billing"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    plan: Mapped[str] = mapped_column(PLAN, nullable=False)
