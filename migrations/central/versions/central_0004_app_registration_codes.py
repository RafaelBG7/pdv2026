"""Add one-time PKCE codes for desktop registration handoff."""

from alembic import op
import sqlalchemy as sa


revision = 'central_0004'
down_revision = 'central_0003'
branch_labels = None
depends_on = None


def upgrade():
    if 'app_registration_codes' in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        'app_registration_codes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('code_hash', sa.String(length=64), nullable=False),
        sa.Column('state_hash', sa.String(length=64), nullable=False),
        sa.Column('code_challenge', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('code_hash'),
    )
    op.create_index('ix_app_registration_codes_user_id', 'app_registration_codes', ['user_id'])
    op.create_index('ix_app_registration_codes_code_hash', 'app_registration_codes', ['code_hash'], unique=True)
    op.create_index('ix_app_registration_codes_expires_at', 'app_registration_codes', ['expires_at'])
    op.create_index('ix_app_registration_codes_used_at', 'app_registration_codes', ['used_at'])


def downgrade():
    op.drop_table('app_registration_codes')
