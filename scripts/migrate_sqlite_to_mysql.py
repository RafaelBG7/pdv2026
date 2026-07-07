import argparse
import sqlite3
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import create_app
from app.extensions import db
from app.tenant import create_mysql_database_if_needed, mysql_database_name, mysql_tenant_url


SQLITE_CENTRAL = ROOT / 'database' / 'adega_jf.db'


TENANT_TABLES = (
    'categories',
    'products',
    'cash_registers',
    'sales',
    'sale_items',
    'payments',
    'payables',
)


def sqlite_rows(path, table_name):
    if not path.exists():
        return []

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        tables = {
            row['name']
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        if table_name not in tables:
            return []
        return [dict(row) for row in connection.execute(f'SELECT * FROM {table_name}')]
    finally:
        connection.close()


def target_columns(engine, table_name):
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return [], set()

    columns = inspector.get_columns(table_name)
    names = [column['name'] for column in columns]
    date_columns = {
        column['name']
        for column in columns
        if 'DATE' in str(column['type']).upper() or 'TIME' in str(column['type']).upper()
    }
    return names, date_columns


def clean_row(row, columns, date_columns):
    cleaned = {}
    for column in columns:
        value = row.get(column)
        if column in date_columns and value == '':
            value = None
        cleaned[column] = value
    return cleaned


def reset_tables(engine, table_names):
    with engine.begin() as connection:
        connection.execute(text('SET FOREIGN_KEY_CHECKS = 0'))
        for table_name in reversed(table_names):
            connection.execute(text(f'DELETE FROM `{table_name}`'))
            try:
                connection.execute(text(f'ALTER TABLE `{table_name}` AUTO_INCREMENT = 1'))
            except Exception:
                pass
        connection.execute(text('SET FOREIGN_KEY_CHECKS = 1'))


def insert_rows(engine, table_name, rows):
    columns, date_columns = target_columns(engine, table_name)
    if not columns or not rows:
        return 0

    filtered_rows = [clean_row(row, columns, date_columns) for row in rows]
    column_sql = ', '.join(f'`{column}`' for column in columns)
    value_sql = ', '.join(f':{column}' for column in columns)

    with engine.begin() as connection:
        connection.execute(text('SET FOREIGN_KEY_CHECKS = 0'))
        connection.execute(
            text(f'INSERT INTO `{table_name}` ({column_sql}) VALUES ({value_sql})'),
            filtered_rows,
        )
        connection.execute(text('SET FOREIGN_KEY_CHECKS = 1'))
    return len(filtered_rows)


def migrate_central(app, company_database_names):
    central_engine = db.engine
    table_names = inspect(central_engine).get_table_names()
    reset_tables(central_engine, table_names)

    totals = {}
    for table_name in table_names:
        rows = sqlite_rows(SQLITE_CENTRAL, table_name)
        if table_name == 'companies':
            for row in rows:
                row['database_path'] = company_database_names.get(row['id'], row.get('database_path') or '')
        totals[table_name] = insert_rows(central_engine, table_name, rows)

    return totals


def migrate_tenant(app, company_id, tenant_database_name, sqlite_path):
    create_mysql_database_if_needed(tenant_database_name)
    engine = create_engine(mysql_tenant_url(tenant_database_name))
    db.Model.metadata.create_all(bind=engine)

    table_names = [table for table in TENANT_TABLES if table in inspect(engine).get_table_names()]
    reset_tables(engine, table_names)

    totals = {}
    for table_name in table_names:
        rows = sqlite_rows(sqlite_path, table_name)
        totals[table_name] = insert_rows(engine, table_name, rows)

    engine.dispose()
    return totals


def main():
    parser = argparse.ArgumentParser(description='Migra dados SQLite do Girofy para MySQL.')
    parser.add_argument('--yes', action='store_true', help='Confirma que o destino MySQL pode ser limpo antes da cópia.')
    args = parser.parse_args()

    if not args.yes:
        raise SystemExit('Use --yes para confirmar a limpeza do destino MySQL antes da migração.')
    if not SQLITE_CENTRAL.exists():
        raise SystemExit(f'Banco SQLite central não encontrado: {SQLITE_CENTRAL}')

    app = create_app()
    with app.app_context():
        from app.models import Company

        companies = sqlite_rows(SQLITE_CENTRAL, 'companies')
        company_database_names = {}
        company_sqlite_paths = {}
        for company_row in companies:
            company = Company(id=company_row['id'], name=company_row['name'])
            database_name = mysql_database_name(company)
            company_database_names[company_row['id']] = database_name
            company_sqlite_paths[company_row['id']] = Path(company_row.get('database_path') or '')

        print('Migrando banco central...')
        central_totals = migrate_central(app, company_database_names)
        print(f'Central: {central_totals}')

        for company_row in companies:
            company_id = company_row['id']
            database_name = company_database_names[company_id]
            sqlite_path = company_sqlite_paths[company_id]
            print(f'Migrando adega {company_id} -> {database_name}...')
            tenant_totals = migrate_tenant(app, company_id, database_name, sqlite_path)
            print(f'Adega {company_id}: {tenant_totals}')

    print('Migração concluída.')


if __name__ == '__main__':
    main()
