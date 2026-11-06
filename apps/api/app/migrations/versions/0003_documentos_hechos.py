"""documentos importados y hechos extraidos

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "profile_id", sa.String(32), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("stored_name", sa.String(80), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("page_count", sa.Integer, nullable=False),
        sa.Column("ocr_pages", sa.JSON, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("error", sa.Text),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_documents_profile_id", "documents", ["profile_id"])
    op.create_table(
        "extracted_facts",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "profile_id", sa.String(32), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "document_id", sa.String(32), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("data", sa.JSON, nullable=False),
        sa.Column("quote", sa.Text, nullable=False),
        sa.Column("page", sa.Integer),
        sa.Column("dropped_fields", sa.JSON, nullable=False),
        sa.Column("from_ocr", sa.Boolean, nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_extracted_facts_profile_id", "extracted_facts", ["profile_id"])
    op.create_index("ix_extracted_facts_document_id", "extracted_facts", ["document_id"])


def downgrade() -> None:
    op.drop_table("extracted_facts")
    op.drop_table("documents")
