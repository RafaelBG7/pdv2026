"""Store monetary values and fee percentages as exact decimals.

Revision ID: central_0009
Revises: central_0008
"""

from alembic import op
from decimal import Decimal, ROUND_HALF_UP
import sqlalchemy as sa


revision = 'central_0009'
down_revision = 'central_0008'
branch_labels = None
depends_on = None


FLOAT_MONEY_COLUMNS = {
    'cash_registers': ('opening_amount', 'closing_amount'),
    'payments': ('amount',),
    'products': ('cost_price', 'sale_price'),
    'sales': ('total_amount', 'discount_amount', 'final_amount'),
    'sale_items': ('unit_price', 'unit_cost_price', 'total_price', 'profit_amount'),
}
DECIMAL_MONEY_COLUMNS = {
    'payables': ('amount',),
    'stock_movements': ('unit_cost', 'total_cost'),
}
PERCENT_COLUMNS = {
    'companies': ('pix_fee_percent', 'debit_fee_percent', 'credit_fee_percent'),
}


def _normalize_and_convert(table_name, columns, precision, scale, existing_type):
    connection = op.get_bind()
    quantum = Decimal('1').scaleb(-scale)
    for column_name in columns:
        rows = connection.execute(sa.text(
            f'SELECT id, {column_name} FROM {table_name}'
        )).all()
        for row_id, raw_value in rows:
            source_value = Decimal(str(raw_value or 0))
            if not source_value.is_finite():
                raise RuntimeError(
                    f'Valor financeiro inválido em {table_name}.{column_name}, id={row_id}'
                )
            normalized = source_value.quantize(quantum, rounding=ROUND_HALF_UP)
            connection.execute(
                sa.text(f'UPDATE {table_name} SET {column_name} = :value WHERE id = :id'),
                {'value': str(normalized), 'id': row_id},
            )
    with op.batch_alter_table(table_name) as batch_op:
        for column_name in columns:
            batch_op.alter_column(
                column_name,
                existing_type=existing_type,
                type_=sa.Numeric(precision=precision, scale=scale),
                existing_nullable=True,
                nullable=False,
                server_default='0',
            )


def upgrade():
    # 18,2 deliberately leaves headroom for known legacy imports whose values
    # exceeded the application's current per-transaction validation ceiling.
    for table_name, columns in FLOAT_MONEY_COLUMNS.items():
        _normalize_and_convert(table_name, columns, 18, 2, sa.Float())
    for table_name, columns in DECIMAL_MONEY_COLUMNS.items():
        _normalize_and_convert(table_name, columns, 18, 2, sa.Numeric(12, 2))
    for table_name, columns in PERCENT_COLUMNS.items():
        _normalize_and_convert(table_name, columns, 8, 4, sa.Float())


def downgrade():
    raise RuntimeError('Downgrade bloqueado: converter DECIMAL financeiro para FLOAT perde precisão.')
