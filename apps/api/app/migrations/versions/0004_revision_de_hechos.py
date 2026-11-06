"""datos aprobados independientes del documento y datos manuales

- extracted_facts.document_id pasa a ser opcional (ON DELETE SET NULL)
- nuevas columnas: origin ('documento' | 'manual') y original_data (valor antes de editar)
SQLite no permite cambiar la nulabilidad ni las claves foraneas, asi que se reconstruye la tabla
conservando los datos.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

COMUNES = "id, profile_id, document_id, category, data, quote, page, dropped_fields, from_ocr, status, created_at, updated_at"


def _crear(nombre: str, document_nullable: bool, con_nuevas: bool) -> None:
    columnas = [
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "profile_id", sa.String(32), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "document_id",
            sa.String(32),
            sa.ForeignKey("documents.id", ondelete="SET NULL" if document_nullable else "CASCADE"),
            nullable=document_nullable,
        ),
    ]
    if con_nuevas:
        columnas.append(sa.Column("origin", sa.String(10), nullable=False))
    columnas += [
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("data", sa.JSON, nullable=False),
    ]
    if con_nuevas:
        columnas.append(sa.Column("original_data", sa.JSON))
    columnas += [
        sa.Column("quote", sa.Text, nullable=False),
        sa.Column("page", sa.Integer),
        sa.Column("dropped_fields", sa.JSON, nullable=False),
        sa.Column("from_ocr", sa.Boolean, nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    ]
    op.create_table(nombre, *columnas)


def _reconstruir(hacia_nueva: bool) -> None:
    op.drop_index("ix_extracted_facts_profile_id", table_name="extracted_facts")
    op.drop_index("ix_extracted_facts_document_id", table_name="extracted_facts")
    op.rename_table("extracted_facts", "extracted_facts_old")
    _crear("extracted_facts", document_nullable=hacia_nueva, con_nuevas=hacia_nueva)
    if hacia_nueva:
        op.execute(
            "INSERT INTO extracted_facts (id, profile_id, document_id, origin, category, data, original_data, "
            "quote, page, dropped_fields, from_ocr, status, created_at, updated_at) "
            "SELECT id, profile_id, document_id, 'documento', category, data, NULL, quote, page, "
            "dropped_fields, from_ocr, status, created_at, updated_at FROM extracted_facts_old"
        )
    else:  # al volver atras se pierden los datos sin documento (manuales o huerfanos)
        op.execute(
            f"INSERT INTO extracted_facts ({COMUNES}) SELECT {COMUNES} FROM extracted_facts_old "
            f"WHERE document_id IS NOT NULL"
        )
    op.drop_table("extracted_facts_old")
    op.create_index("ix_extracted_facts_profile_id", "extracted_facts", ["profile_id"])
    op.create_index("ix_extracted_facts_document_id", "extracted_facts", ["document_id"])


def upgrade() -> None:
    _reconstruir(hacia_nueva=True)


def downgrade() -> None:
    _reconstruir(hacia_nueva=False)
