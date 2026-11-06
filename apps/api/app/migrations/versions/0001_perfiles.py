"""tabla de perfiles

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("nombre_completo", sa.String(200), nullable=False),
        sa.Column("titular", sa.String(200)),
        sa.Column("email", sa.String(254)),
        sa.Column("telefono", sa.String(40)),
        sa.Column("ciudad", sa.String(120)),
        sa.Column("pais", sa.String(120)),
        sa.Column("enlaces", sa.JSON, nullable=False),
        sa.Column("resumen", sa.Text),
        sa.Column("creado_en", sa.DateTime, nullable=False),
        sa.Column("actualizado_en", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("profiles")
