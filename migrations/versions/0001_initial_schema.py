"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-10 09:00:00.000000
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(open("infra/postgres/init.sql").read())


def downgrade() -> None:
    op.execute("""
        DROP TABLE IF EXISTS tool_invocations CASCADE;
        DROP TABLE IF EXISTS task_nodes CASCADE;
        DROP TABLE IF EXISTS task_graphs CASCADE;
        DROP TABLE IF EXISTS sessions CASCADE;
        DROP EXTENSION IF EXISTS "uuid-ossp";
    """)
