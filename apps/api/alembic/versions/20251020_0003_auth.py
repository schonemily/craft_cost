from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20251020_0003"
down_revision = "20251014_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create role enum if not exists; add columns password_hash and role to users
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'role') THEN
            CREATE TYPE role AS ENUM ('user','admin');
          END IF;
        END$$;
        """
    )
    # password_hash column (idempotent)
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
              SELECT 1 FROM information_schema.columns
              WHERE table_name='users' AND column_name='password_hash'
          ) THEN
            ALTER TABLE users ADD COLUMN password_hash VARCHAR(255);
          END IF;
        END$$;
        """
    )
    # role column with default 'user' (idempotent)
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
              SELECT 1 FROM information_schema.columns
              WHERE table_name='users' AND column_name='role'
          ) THEN
            ALTER TABLE users ADD COLUMN role role NOT NULL DEFAULT 'user';
          END IF;
        END$$;
        """
    )


def downgrade() -> None:
    # Drop columns if exist
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
              SELECT 1 FROM information_schema.columns
              WHERE table_name='users' AND column_name='role'
          ) THEN
            ALTER TABLE users DROP COLUMN role;
          END IF;
        END$$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
              SELECT 1 FROM information_schema.columns
              WHERE table_name='users' AND column_name='password_hash'
          ) THEN
            ALTER TABLE users DROP COLUMN password_hash;
          END IF;
        END$$;
        """
    )
    # Drop enum if unused
    try:
        sa.Enum(name="role").drop(op.get_bind(), checkfirst=True)
    except Exception:
        pass
