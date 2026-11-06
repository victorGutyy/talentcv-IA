"""borradores de redaccion

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "drafts",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "profile_id", sa.String(32), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("section", sa.String(10), nullable=False),
        sa.Column(
            "target_fact_id",
            sa.String(32),
            sa.ForeignKey("extracted_facts.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("source_ids", sa.JSON, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("origin", sa.String(10), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("audit_ok", sa.Boolean, nullable=False),
        sa.Column("audit_issues", sa.JSON, nullable=False),
        sa.Column("audit_warnings", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_drafts_profile_id", "drafts", ["profile_id"])
    op.create_index("ix_drafts_target_fact_id", "drafts", ["target_fact_id"])


def downgrade() -> None:
    op.drop_table("drafts")
