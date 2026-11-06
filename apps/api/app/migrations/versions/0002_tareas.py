"""tabla de tareas en segundo plano

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("kind", sa.String(60), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("progress", sa.Float, nullable=False),
        sa.Column("message", sa.String(300), nullable=False),
        sa.Column("params", sa.JSON, nullable=False),
        sa.Column("result", sa.JSON),
        sa.Column("error", sa.Text),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("started_at", sa.DateTime),
        sa.Column("finished_at", sa.DateTime),
    )


def downgrade() -> None:
    op.drop_table("jobs")
