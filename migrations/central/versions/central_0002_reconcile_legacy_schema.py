"""Reconcile databases created before Alembic was introduced."""

from alembic import op
import sqlalchemy as sa


revision = 'central_0002'
down_revision = 'central_0001'
branch_labels = None
depends_on = None


LEGACY_COLUMNS = {
    'products': [
        sa.Column('is_kit', sa.Boolean(), server_default=sa.false()),
        sa.Column('kit_component_product_id', sa.Integer()),
        sa.Column('kit_component_quantity', sa.Integer(), server_default='0'),
        sa.Column('min_stock_quantity', sa.Integer(), server_default='0'),
        sa.Column('company_id', sa.Integer()),
    ],
    'sales': [
        sa.Column('discount_amount', sa.Float(), server_default='0'),
        sa.Column('status', sa.String(20), nullable=False, server_default='completed'),
        sa.Column('cancelled_at', sa.DateTime()),
        sa.Column('cancelled_by_user_id', sa.Integer()),
        sa.Column('cancellation_reason', sa.String(500), server_default=''),
        sa.Column('company_id', sa.Integer()),
    ],
    'sale_items': [
        sa.Column('unit_cost_price', sa.Float(), server_default='0'),
        sa.Column('profit_amount', sa.Float(), server_default='0'),
    ],
    'users': [
        sa.Column('first_name', sa.String(120), server_default=''),
        sa.Column('last_name', sa.String(120), server_default=''),
        sa.Column('cpf', sa.String(20), server_default=''),
        sa.Column('email', sa.String(255), server_default=''),
        sa.Column('phone', sa.String(40), server_default=''),
        sa.Column('email_verified', sa.Boolean(), server_default=sa.true()),
        sa.Column('email_verified_at', sa.DateTime()),
        sa.Column('company_id', sa.Integer()),
        *[sa.Column(name, sa.Boolean(), server_default=sa.true()) for name in (
            'can_view_products', 'can_manage_products', 'can_manage_categories',
            'can_manage_sales', 'can_manage_cash_register', 'can_view_reports',
            'can_manage_payables', 'can_manage_settings', 'can_view_stock_movements',
            'can_manage_stock', 'can_view_audit_logs',
        )],
        sa.Column('can_cancel_sales', sa.Boolean(), server_default=sa.false()),
    ],
    'companies': [
        sa.Column('database_path', sa.String(255), server_default=''),
        sa.Column('active', sa.Boolean(), server_default=sa.true()),
        sa.Column('allow_negative_stock', sa.Boolean(), server_default=sa.false()),
        sa.Column('subscription_plan', sa.String(80), server_default='Essencial'),
        sa.Column('billing_cycle', sa.String(20), server_default='monthly'),
        sa.Column('subscription_started_at', sa.Date()),
        sa.Column('subscription_renews_at', sa.Date()),
        sa.Column('activation_key', sa.String(80), server_default=''),
        sa.Column('activation_key_updated_at', sa.DateTime()),
        *[sa.Column(name, sa.Boolean(), server_default=sa.false()) for name in (
            'card_fee_enabled', 'pix_fee_enabled', 'debit_fee_enabled', 'credit_fee_enabled',
        )],
        *[sa.Column(name, sa.Float(), server_default='0') for name in (
            'pix_fee_percent', 'debit_fee_percent', 'credit_fee_percent',
        )],
        sa.Column('backup_frequency', sa.String(20), server_default='manual'),
        sa.Column('backup_last_at', sa.DateTime()),
        sa.Column('backup_last_path', sa.String(255), server_default=''),
        sa.Column('backup_last_status', sa.String(40), server_default=''),
    ],
    'categories': [sa.Column('company_id', sa.Integer())],
    'cash_registers': [sa.Column('company_id', sa.Integer())],
}

PERFORMANCE_INDEXES = {
    'products': [('idx_products_company_active_name', ['company_id', 'active', 'name']), ('idx_products_company_barcode', ['company_id', 'barcode']), ('idx_products_company_category', ['company_id', 'category_id'])],
    'categories': [('idx_categories_company_name', ['company_id', 'name'])],
    'sales': [('idx_sales_company_created', ['company_id', 'created_at']), ('idx_sales_company_cash_created', ['company_id', 'cash_register_id', 'created_at']), ('idx_sales_company_status_created', ['company_id', 'payment_status', 'created_at'])],
    'sale_items': [('idx_sale_items_sale_product', ['sale_id', 'product_id']), ('idx_sale_items_product', ['product_id'])],
    'payments': [('idx_payments_sale_method', ['sale_id', 'method'])],
    'cash_registers': [('idx_cash_company_status_opened', ['company_id', 'status', 'opened_at'])],
    'stock_movements': [('idx_stock_company_created', ['company_id', 'created_at']), ('idx_stock_company_product_created', ['company_id', 'product_id', 'created_at']), ('idx_stock_company_type_created', ['company_id', 'movement_type', 'created_at'])],
    'audit_logs': [('idx_audit_company_created', ['company_id', 'created_at']), ('idx_audit_company_action_created', ['company_id', 'action', 'created_at']), ('idx_audit_company_entity_created', ['company_id', 'entity_type', 'created_at'])],
    'payables': [('idx_payables_company_paid_due', ['company_id', 'paid', 'due_date'])],
}


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = set(inspector.get_table_names())
    for table, columns in LEGACY_COLUMNS.items():
        if table not in tables:
            continue
        existing = {column['name'] for column in inspector.get_columns(table)}
        for column in columns:
            if column.name not in existing:
                op.add_column(table, column)
                existing.add(column.name)

    inspector = sa.inspect(connection)
    for table, indexes in PERFORMANCE_INDEXES.items():
        if table not in tables:
            continue
        existing = {index['name'] for index in inspector.get_indexes(table)}
        columns = {column['name'] for column in inspector.get_columns(table)}
        for name, index_columns in indexes:
            if name not in existing and set(index_columns) <= columns:
                op.create_index(name, table, index_columns)

    if 'sales' in tables:
        op.execute("UPDATE sales SET status = 'completed' WHERE status IS NULL OR status = ''")
    if 'users' in tables:
        op.execute('UPDATE users SET email_verified = 1 WHERE email_verified IS NULL')


def downgrade():
    raise RuntimeError('A reconciliação de schemas legados não possui downgrade destrutivo.')
