"""Repair notification tables missing from legacy tenant databases.

Revision ID: tenant_0011
Revises: tenant_0010
"""

from alembic import op
import sqlalchemy as sa


revision = 'tenant_0011'
down_revision = 'tenant_0010'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    existing_tables = set(sa.inspect(connection).get_table_names())

    if 'notification_preferences' not in existing_tables:
        op.create_table(
            'notification_preferences',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('company_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('notification_type', sa.String(length=80), nullable=False),
            sa.Column('in_app_enabled', sa.Boolean(), nullable=False),
            sa.Column('email_enabled', sa.Boolean(), nullable=False),
            sa.Column('desktop_enabled', sa.Boolean(), nullable=False),
            sa.Column('minimum_severity', sa.String(length=20), nullable=False),
            sa.Column('email_recipients', sa.String(length=1000), nullable=True),
            sa.Column('quiet_hours_start', sa.String(length=5), nullable=True),
            sa.Column('quiet_hours_end', sa.String(length=5), nullable=True),
            sa.Column('daily_digest_enabled', sa.Boolean(), nullable=False),
            sa.Column('daily_digest_time', sa.String(length=5), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint(
                'company_id', 'user_id', 'notification_type',
                name='uq_notification_preference',
            ),
        )
        op.create_index(
            op.f('ix_notification_preferences_company_id'),
            'notification_preferences', ['company_id'], unique=False,
        )
        op.create_index(
            op.f('ix_notification_preferences_user_id'),
            'notification_preferences', ['user_id'], unique=False,
        )

    if 'notifications' not in existing_tables:
        op.create_table(
            'notifications',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('company_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('notification_type', sa.String(length=80), nullable=False),
            sa.Column('category', sa.String(length=40), nullable=False),
            sa.Column('severity', sa.String(length=20), nullable=False),
            sa.Column('title', sa.String(length=180), nullable=False),
            sa.Column('message', sa.String(length=1000), nullable=False),
            sa.Column('entity_type', sa.String(length=80), nullable=True),
            sa.Column('entity_id', sa.Integer(), nullable=True),
            sa.Column('action_url', sa.String(length=500), nullable=True),
            sa.Column('deduplication_key', sa.String(length=255), nullable=False),
            sa.Column('is_read', sa.Boolean(), nullable=False),
            sa.Column('read_at', sa.DateTime(), nullable=True),
            sa.Column('is_dismissed', sa.Boolean(), nullable=False),
            sa.Column('dismissed_at', sa.DateTime(), nullable=True),
            sa.Column('is_resolved', sa.Boolean(), nullable=False),
            sa.Column('resolved_at', sa.DateTime(), nullable=True),
            sa.Column('email_status', sa.String(length=20), nullable=True),
            sa.Column('email_sent_at', sa.DateTime(), nullable=True),
            sa.Column('email_error', sa.String(length=500), nullable=True),
            sa.Column('metadata_json', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('expires_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint(
                'company_id', 'deduplication_key',
                name='uq_notification_company_dedup',
            ),
        )
        for column_name in (
            'category', 'company_id', 'created_at', 'entity_id', 'entity_type',
            'expires_at', 'is_dismissed', 'is_read', 'is_resolved',
            'notification_type', 'severity', 'user_id',
        ):
            op.create_index(
                op.f(f'ix_notifications_{column_name}'),
                'notifications', [column_name], unique=False,
            )


def downgrade():
    # Esta migration repara bancos legados e não pode distinguir tabelas
    # preexistentes das criadas por ela. Preservar dados é mais seguro.
    pass
