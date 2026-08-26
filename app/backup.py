from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from flask import current_app
from sqlalchemy import inspect, text

from app.extensions import db
from app.tenant import tenant_engine


BACKUP_FREQUENCIES = {
    'manual': 'Somente manual',
    'daily': 'Diário',
    'weekly': 'Semanal',
    'monthly': 'Mensal',
}


def backup_frequency_label(value):
    return BACKUP_FREQUENCIES.get(value or 'manual', BACKUP_FREQUENCIES['manual'])


def backup_due(company):
    if not company or (company.backup_frequency or 'manual') == 'manual':
        return False
    if not company.backup_last_at:
        return True

    now = datetime.now(timezone.utc)
    last_at = company.backup_last_at
    if last_at.tzinfo is None:
        last_at = last_at.replace(tzinfo=timezone.utc)

    intervals = {
        'daily': timedelta(days=1),
        'weekly': timedelta(days=7),
        'monthly': timedelta(days=30),
    }
    return now - last_at >= intervals.get(company.backup_frequency, timedelta.max)


def sql_value(value):
    if value is None:
        return 'NULL'
    if isinstance(value, bool):
        return '1' if value else '0'
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, datetime):
        return "'" + value.isoformat(sep=' ') + "'"
    if isinstance(value, date):
        return "'" + value.isoformat() + "'"
    if isinstance(value, bytes):
        return "X'" + value.hex() + "'"

    text_value = str(value).replace('\\', '\\\\').replace("'", "''")
    return f"'{text_value}'"


def create_statement(connection, table_name):
    dialect = connection.engine.dialect.name
    if dialect == 'mysql':
        row = connection.execute(text(f'SHOW CREATE TABLE `{table_name}`')).first()
        return row[1] if row and len(row) > 1 else ''
    if dialect == 'sqlite':
        row = connection.execute(
            text('SELECT sql FROM sqlite_master WHERE type = "table" AND name = :table_name'),
            {'table_name': table_name},
        ).first()
        return row[0] if row else ''
    return ''


def build_database_dump(engine, database_name):
    inspector = inspect(engine)
    table_names = [
        table_name
        for table_name in inspector.get_table_names()
        if not table_name.startswith('sqlite_')
    ]
    generated_at = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    lines = [
        f'-- Backup SkyGest',
        f'-- Banco: {database_name}',
        f'-- Gerado em: {generated_at}',
        'SET FOREIGN_KEY_CHECKS=0;',
        '',
    ]

    with engine.connect() as connection:
        for table_name in table_names:
            columns = [column['name'] for column in inspector.get_columns(table_name)]
            lines.append(f'-- Tabela: {table_name}')
            lines.append(f'DROP TABLE IF EXISTS `{table_name}`;')
            statement = create_statement(connection, table_name)
            if statement:
                lines.append(f'{statement};')

            rows = connection.execute(text(f'SELECT * FROM `{table_name}`')).mappings().all()
            if rows:
                column_sql = ', '.join(f'`{column}`' for column in columns)
                for row in rows:
                    values = ', '.join(sql_value(row[column]) for column in columns)
                    lines.append(f'INSERT INTO `{table_name}` ({column_sql}) VALUES ({values});')
            lines.append('')

    lines.append('SET FOREIGN_KEY_CHECKS=1;')
    lines.append('')
    return '\n'.join(lines)


def create_company_backup(company, reason='manual'):
    engine = tenant_engine(company)
    database_name = company.database_path or f'company_{company.id}'
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    safe_database_name = ''.join(char if char.isalnum() or char in ('_', '-') else '_' for char in database_name)
    backup_dir = Path(current_app.config.get('BACKUP_DIR') or (Path(current_app.root_path).parent / 'backups'))
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f'{safe_database_name}_{timestamp}_{reason}.sql'

    try:
        backup_path.write_text(build_database_dump(engine, database_name), encoding='utf-8')
        company.backup_last_at = datetime.now(timezone.utc)
        company.backup_last_path = str(backup_path)
        company.backup_last_status = 'success'
        db.session.commit()
        return backup_path
    except Exception:
        company.backup_last_at = datetime.now(timezone.utc)
        company.backup_last_status = 'error'
        db.session.commit()
        raise
