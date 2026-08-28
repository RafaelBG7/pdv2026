"""separate the master system context from customer companies

Revision ID: tenant_0007
Revises: tenant_0006
Create Date: 2026-08-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'tenant_0007'
down_revision: Union[str, Sequence[str], None] = 'tenant_0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column['name'] for column in inspector.get_columns('companies')}
    if 'is_system' not in columns:
        op.add_column('companies', sa.Column('is_system', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute(
        sa.text("UPDATE companies SET is_system = :enabled WHERE activation_key = :key")
        .bindparams(enabled=True, key='MASTER-SYSTEM-KEY')
    )


def downgrade() -> None:
    with op.batch_alter_table('companies') as batch_op:
        batch_op.drop_column('is_system')
