"""Store payable amounts as exact decimal values.

Revision ID: tenant_0004
Revises: tenant_0003
"""

from alembic import op
import sqlalchemy as sa


revision = 'tenant_0004'
down_revision = 'tenant_0003'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    connection.execute(sa.text('UPDATE payables SET amount = 0 WHERE amount IS NULL'))
    connection.execute(sa.text('UPDATE payables SET amount = ROUND(amount, 2)'))
    connection.execute(sa.text('UPDATE payables SET paid = 0 WHERE paid IS NULL'))
    with op.batch_alter_table('payables') as batch_op:
        batch_op.alter_column(
            'amount',
            existing_type=sa.Float(),
            type_=sa.Numeric(precision=12, scale=2),
            existing_nullable=True,
            nullable=False,
        )
        batch_op.alter_column(
            'paid',
            existing_type=sa.Boolean(),
            existing_nullable=True,
            nullable=False,
        )


def downgrade():
    with op.batch_alter_table('payables') as batch_op:
        batch_op.alter_column(
            'paid',
            existing_type=sa.Boolean(),
            existing_nullable=False,
            nullable=True,
        )
        batch_op.alter_column(
            'amount',
            existing_type=sa.Numeric(precision=12, scale=2),
            type_=sa.Float(),
            existing_nullable=False,
            nullable=True,
        )
