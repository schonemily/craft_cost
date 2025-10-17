from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20250922_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enums (let SQLAlchemy create once during table creation)
    consent_type = sa.Enum("plaid", "billing", "analytics", "marketing", name="consent_type")
    tx_category = sa.Enum(
        "housing","utilities","telco","insurance","transport","grocery","dining","entertainment","subscriptions","health","personal","fees","income","other",
        name="tx_category",
    )
    cadence = sa.Enum("weekly", "monthly", "yearly", name="cadence")
    goal_type = sa.Enum("savings", "debt_payoff", name="goal_type")
    suggestion_type = sa.Enum("cancel", "renegotiate", "switch", "cap", "nudge", name="suggestion_type")
    difficulty = sa.Enum("low", "med", "high", name="difficulty")
    risk = sa.Enum("low", "med", "high", name="risk")
    export_type = sa.Enum("pdf", "email", name="export_type")
    plan = sa.Enum("free", "plus", name="plan")
    actor = sa.Enum("system", "user", "admin", name="actor")

    # Tables
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("auth_id", sa.String(length=255), nullable=True),
        sa.Column("kyc_min", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("marketing_opt_in", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    op.create_table(
        "consents",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", consent_type, nullable=False),
        sa.Column("scope", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("user_id", "type", name="uq_consents_user_type"),
    )

    op.create_table(
        "accounts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plaid_item_id", sa.String(length=255), nullable=True),
        sa.Column("plaid_account_id", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("type", sa.String(length=64), nullable=True),
        sa.Column("institution", sa.String(length=255), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("plaid_item_id", "plaid_account_id", name="uq_accounts_plaid"),
    )

    op.create_table(
        "transactions_raw",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.BigInteger(), sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("plaid_tx_id", sa.String(length=255), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("iso_currency", sa.String(length=3), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("merchant_raw", sa.String(length=255), nullable=True),
        sa.Column("meta_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("plaid_tx_id", name="uq_transactions_raw_plaid_tx_id"),
        sa.Index("ix_transactions_raw_user_date", "user_id", "date"),
    )

    op.create_table(
        "transactions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tx_id", sa.BigInteger(), sa.ForeignKey("transactions_raw.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", tx_category, nullable=True),
        sa.Column("merchant_norm", sa.String(length=255), nullable=True),
        sa.Column("normalized_desc", sa.String(length=255), nullable=True),
        sa.Column("confidence", sa.Numeric(3, 2), nullable=True),
        sa.Column("is_recurring", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Index("ix_transactions_user_date", "user_id", "tx_id"),
        sa.Index("ix_transactions_user_category", "user_id", "category"),
    )

    op.create_table(
        "recurring",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("merchant_norm", sa.String(length=255), nullable=False),
        sa.Column("amount_est", sa.Numeric(12, 2), nullable=False),
        sa.Column("cadence", cadence, nullable=False),
        sa.Column("next_date", sa.Date(), nullable=True),
        sa.Index("ix_recurring_user_merchant", "user_id", "merchant_norm"),
    )

    op.create_table(
        "debts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("apr", sa.Numeric(5, 3), nullable=False),
        sa.Column("balance", sa.Numeric(12, 2), nullable=False),
        sa.Column("min_payment", sa.Numeric(12, 2), nullable=False),
        sa.Column("promo_apr", sa.Numeric(5, 3), nullable=True),
        sa.Column("promo_end", sa.Date(), nullable=True),
        sa.Column("provider", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    op.create_table(
        "goals",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", goal_type, nullable=False),
        sa.Column("target_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("monthly_extra", sa.Numeric(12, 2), nullable=True),
        sa.Column("constraints", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    op.create_table(
        "suggestions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("type", suggestion_type, nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("est_monthly_saving", sa.Integer(), nullable=True),
        sa.Column("difficulty", difficulty, nullable=True),
        sa.Column("risk", risk, nullable=True),
        sa.Column("confidence", sa.Numeric(3, 2), nullable=True),
        sa.Column("accepted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    op.create_table(
        "exports",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", export_type, nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("signed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    op.create_table(
        "billing",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
        sa.Column("plan", plan, nullable=False, server_default=sa.text("'free'")),
        sa.Column("renews_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor", actor, nullable=False),
        sa.Column("action", sa.String(length=255), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Index("ix_audit_user_ts", "user_id", "ts"),
    )

    op.create_table(
        "idempotency",
        sa.Column("key", sa.String(length=255), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("path", sa.String(length=255), nullable=False),
        sa.Column("body_hash", sa.String(length=64), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("response_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("idempotency")
    op.drop_index("ix_audit_user_ts", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("billing")
    op.drop_table("exports")
    op.drop_table("suggestions")
    op.drop_table("goals")
    op.drop_table("debts")
    op.drop_index("ix_recurring_user_merchant", table_name="recurring")
    op.drop_table("recurring")
    op.drop_index("ix_transactions_user_category", table_name="transactions")
    op.drop_index("ix_transactions_user_date", table_name="transactions")
    op.drop_table("transactions")
    op.drop_index("ix_transactions_raw_user_date", table_name="transactions_raw")
    op.drop_table("transactions_raw")
    op.drop_table("accounts")
    op.drop_table("consents")
    op.drop_table("users")

    for enum_name in [
        "actor",
        "plan",
        "export_type",
        "risk",
        "difficulty",
        "suggestion_type",
        "goal_type",
        "cadence",
        "tx_category",
        "consent_type",
    ]:
        try:
            sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
        except Exception:
            pass
