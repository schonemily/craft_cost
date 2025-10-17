from __future__ import annotations
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import BigInteger, String, Text, Date, Numeric, DateTime, Boolean, func, ForeignKey


class Base(DeclarativeBase):
    pass


class TransactionsRaw(Base):
    __tablename__ = "transactions_raw"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    date: Mapped[Date] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    merchant_raw: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Transactions(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tx_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("transactions_raw.id", ondelete="CASCADE"), nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    merchant_norm: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Flag(Base):
    __tablename__ = "flags"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    bool_value: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
