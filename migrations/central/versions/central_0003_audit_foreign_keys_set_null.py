"""Preserve audit history when companies or users are deleted."""

from alembic import op
import sqlalchemy as sa


revision = 'central_0003'
down_revision = 'central_0002'
branch_labels = None
depends_on = None


def _replace_foreign_key(column_name, referred_table, ondelete):
    connection = op.get_bind()
    if connection.dialect.name == 'sqlite':
        return

    foreign_keys = sa.inspect(connection).get_foreign_keys('audit_logs')
    foreign_key = next(
        (
            item
            for item in foreign_keys
            if item.get('constrained_columns') == [column_name]
            and item.get('referred_table') == referred_table
        ),
        None,
    )
    if foreign_key and foreign_key.get('name'):
        op.drop_constraint(foreign_key['name'], 'audit_logs', type_='foreignkey')

    op.create_foreign_key(
        f'fk_audit_logs_{column_name}',
        'audit_logs',
        referred_table,
        [column_name],
        ['id'],
        ondelete=ondelete,
    )


def upgrade():
    _replace_foreign_key('company_id', 'companies', 'SET NULL')
    _replace_foreign_key('user_id', 'users', 'SET NULL')


def downgrade():
    _replace_foreign_key('company_id', 'companies', None)
    _replace_foreign_key('user_id', 'users', None)
