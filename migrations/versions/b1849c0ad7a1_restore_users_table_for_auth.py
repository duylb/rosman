"""restore_users_table_for_auth

Revision ID: b1849c0ad7a1
Revises: 73e93d947cef
Create Date: 2026-03-11 17:22:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "b1849c0ad7a1"
down_revision = "73e93d947cef"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            expires_at TIMESTAMP NULL,
            is_owner BOOLEAN NOT NULL DEFAULT FALSE,
            role TEXT NOT NULL DEFAULT 'owner',
            enable_people_ops BOOLEAN NOT NULL DEFAULT TRUE,
            enable_business_ops BOOLEAN NOT NULL DEFAULT TRUE,
            org_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_org_id ON users (org_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS users CASCADE;")
