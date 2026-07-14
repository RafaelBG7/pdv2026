from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError


PERFORMANCE_INDEXES = {
    'products': (
        ('idx_products_company_active_name', ('company_id', 'active', 'name')),
        ('idx_products_company_barcode', ('company_id', 'barcode')),
        ('idx_products_company_category', ('company_id', 'category_id')),
    ),
    'categories': (
        ('idx_categories_company_name', ('company_id', 'name')),
    ),
    'sales': (
        ('idx_sales_company_created', ('company_id', 'created_at')),
        ('idx_sales_company_cash_created', ('company_id', 'cash_register_id', 'created_at')),
        ('idx_sales_company_status_created', ('company_id', 'payment_status', 'created_at')),
    ),
    'sale_items': (
        ('idx_sale_items_sale_product', ('sale_id', 'product_id')),
        ('idx_sale_items_product', ('product_id',)),
    ),
    'payments': (
        ('idx_payments_sale_method', ('sale_id', 'method')),
    ),
    'cash_registers': (
        ('idx_cash_company_status_opened', ('company_id', 'status', 'opened_at')),
    ),
    'stock_movements': (
        ('idx_stock_company_created', ('company_id', 'created_at')),
        ('idx_stock_company_product_created', ('company_id', 'product_id', 'created_at')),
        ('idx_stock_company_type_created', ('company_id', 'movement_type', 'created_at')),
    ),
    'audit_logs': (
        ('idx_audit_company_created', ('company_id', 'created_at')),
        ('idx_audit_company_action_created', ('company_id', 'action', 'created_at')),
        ('idx_audit_company_entity_created', ('company_id', 'entity_type', 'created_at')),
    ),
    'payables': (
        ('idx_payables_company_paid_due', ('company_id', 'paid', 'due_date')),
    ),
}


def quote_identifier(value):
    return f'`{value.replace("`", "``")}`'


def existing_index_names(inspector, table_name):
    return {index['name'] for index in inspector.get_indexes(table_name)}


def ensure_performance_indexes(engine, logger=None):
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    for table_name, indexes in PERFORMANCE_INDEXES.items():
        if table_name not in existing_tables:
            continue

        table_indexes = existing_index_names(inspector, table_name)
        for index_name, columns in indexes:
            if index_name in table_indexes:
                continue

            quoted_columns = ', '.join(quote_identifier(column) for column in columns)
            statement = f'CREATE INDEX {quote_identifier(index_name)} ON {quote_identifier(table_name)} ({quoted_columns})'
            try:
                with engine.begin() as connection:
                    connection.execute(text(statement))
                table_indexes.add(index_name)
            except SQLAlchemyError as error:
                if logger:
                    logger.warning('Não foi possível criar índice %s: %s', index_name, error)
