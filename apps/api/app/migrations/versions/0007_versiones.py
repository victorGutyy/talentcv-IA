"""historial de versiones del curriculum

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cv_versions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "profile_id", sa.String(32), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("numero", sa.Integer, nullable=False),
        sa.Column("etiqueta", sa.String(80)),
        sa.Column("origen", sa.String(12), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("cv", sa.JSON, nullable=False),
        sa.Column("exportaciones", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("profile_id", "content_hash", name="uq_version_contenido"),
        sa.UniqueConstraint("profile_id", "numero", name="uq_version_numero"),
    )
    op.create_index("ix_cv_versions_profile_id", "cv_versions", ["profile_id"])


def downgrade() -> None:
    op.drop_table("cv_versions")
