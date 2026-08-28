"""activation key management fields

Revision ID: central_0005
Revises: central_0004
Create Date: 2026-08-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'central_0005'
down_revision: Union[str, Sequence[str], None] = 'central_0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column['name'] for column in inspector.get_columns('activation_keys')}
    additions = {
        'display_name': sa.Column('display_name', sa.String(length=160), nullable=True, server_default=''),
        'payment_cycle': sa.Column('payment_cycle', sa.String(length=20), nullable=True, server_default='monthly'),
        'assigned_company_id': sa.Column('assigned_company_id', sa.Integer(), nullable=True),
        'revoked_at': sa.Column('revoked_at', sa.DateTime(), nullable=True),
        'created_by_user_id': sa.Column('created_by_user_id', sa.Integer(), nullable=True),
    }
    for name, column in additions.items():
        if name not in columns:
            op.add_column('activation_keys', column)
    existing_indexes = {index['name'] for index in inspector.get_indexes('activation_keys')}
    for name, fields in (
        ('ix_activation_keys_assigned_company_id', ['assigned_company_id']),
        ('ix_activation_keys_created_at', ['created_at']),
        ('ix_activation_keys_renews_at', ['renews_at']),
    ):
        if name not in existing_indexes:
            op.create_index(name, 'activation_keys', fields)


def downgrade() -> None:
    with op.batch_alter_table('activation_keys') as batch_op:
        batch_op.drop_index('ix_activation_keys_renews_at')
        batch_op.drop_index('ix_activation_keys_created_at')
        batch_op.drop_index('ix_activation_keys_assigned_company_id')
        batch_op.drop_column('created_by_user_id')
        batch_op.drop_column('revoked_at')
        batch_op.drop_column('assigned_company_id')
        batch_op.drop_column('payment_cycle')
        batch_op.drop_column('display_name')
