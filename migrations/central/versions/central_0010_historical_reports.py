"""Add historical reports to the shared model-compatible schema."""

from alembic import op
import sqlalchemy as sa


revision = 'central_0010'
down_revision = 'central_0009'
branch_labels = None
depends_on = None


def upgrade():
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    if 'historical_report_import_batches' in existing_tables:
        return
    op.create_table(
        'historical_report_import_batches',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('file_hash', sa.String(64), nullable=False),
        sa.Column('source', sa.String(120), nullable=False),
        sa.Column('strategy', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('valid_rows', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('invalid_rows', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('inserted_rows', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_rows', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('ignored_rows', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('period_start', sa.Date(), nullable=True),
        sa.Column('period_end', sa.Date(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('idempotency_key', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.UniqueConstraint('company_id', 'idempotency_key', name='uq_historical_batch_company_request'),
    )
    op.create_index('ix_historical_batch_company_created', 'historical_report_import_batches', ['company_id', 'created_at'])
    op.create_table(
        'historical_daily_reports',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('report_date', sa.Date(), nullable=False),
        sa.Column('sales_count', sa.Integer(), nullable=False),
        sa.Column('revenue', sa.Numeric(18, 2), nullable=False),
        sa.Column('gross_profit', sa.Numeric(18, 2), nullable=True),
        sa.Column('average_ticket', sa.Numeric(18, 2), nullable=False),
        sa.Column('source', sa.String(120), nullable=False),
        sa.Column('batch_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('sales_count >= 0', name='ck_historical_report_sales_count_nonnegative'),
        sa.CheckConstraint('revenue >= 0', name='ck_historical_report_revenue_nonnegative'),
        sa.ForeignKeyConstraint(['batch_id'], ['historical_report_import_batches.id']),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.UniqueConstraint('company_id', 'report_date', name='uq_historical_report_company_date'),
    )
    op.create_index('ix_historical_report_company_date', 'historical_daily_reports', ['company_id', 'report_date'])


def downgrade():
    op.drop_index('ix_historical_report_company_date', table_name='historical_daily_reports')
    op.drop_table('historical_daily_reports')
    op.drop_index('ix_historical_batch_company_created', table_name='historical_report_import_batches')
    op.drop_table('historical_report_import_batches')
