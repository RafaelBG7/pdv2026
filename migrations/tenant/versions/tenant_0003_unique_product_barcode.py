"""Guarantee one product barcode per tenant/company."""

from alembic import op
import sqlalchemy as sa


revision = 'tenant_0003'
down_revision = 'tenant_0002'
branch_labels = None
depends_on = None


CONSTRAINT_NAME = 'uq_products_company_barcode'


def upgrade():
    connection = op.get_bind()
    duplicate = connection.execute(sa.text(
        """
        SELECT company_id, barcode, COUNT(*) AS total
        FROM products
        WHERE barcode IS NOT NULL AND barcode <> ''
        GROUP BY company_id, barcode
        HAVING COUNT(*) > 1
        LIMIT 1
        """,
    )).first()
    if duplicate is not None:
        raise RuntimeError(
            'Existem códigos de barras duplicados no mesmo tenant. '
            'Corrija os produtos antes de aplicar tenant_0003.',
        )

    with op.batch_alter_table('products') as batch_op:
        batch_op.create_unique_constraint(
            CONSTRAINT_NAME,
            ['company_id', 'barcode'],
        )


def downgrade():
    with op.batch_alter_table('products') as batch_op:
        batch_op.drop_constraint(CONSTRAINT_NAME, type_='unique')
