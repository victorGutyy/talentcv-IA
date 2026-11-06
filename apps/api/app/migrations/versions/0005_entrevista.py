"""preguntas omitidas del cuestionario

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_skips",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "profile_id", sa.String(32), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("question_id", sa.String(80), nullable=False),
        sa.Column("answered", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("profile_id", "question_id", name="uq_skip_profile_question"),
    )
    op.create_index("ix_interview_skips_profile_id", "interview_skips", ["profile_id"])


def downgrade() -> None:
    op.drop_table("interview_skips")
