from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250930_0002"
down_revision = "20250922_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "flags",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("bool_value", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("flags")
