"""detach the SaaS master context from tenant databases

Revision ID: central_0008
Revises: central_0007
Create Date: 2026-08-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'central_0008'
down_revision: Union[str, Sequence[str], None] = 'central_0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = {column['name'] for column in inspector.get_columns('companies')}
    if {'database_path', 'is_system'} <= columns:
        connection.execute(sa.text(
            "UPDATE companies SET database_path = '' WHERE is_system = 1"
        ))


def downgrade() -> None:
    # O painel master não volta a receber um tenant no downgrade.
    pass
