from dataclasses import dataclass
from pathlib import Path
import time

from alembic import command
from alembic.config import Config as AlembicConfig
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from app.extensions import db


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_DIRECTORIES = {
    'central': PROJECT_ROOT / 'migrations' / 'central',
    'tenant': PROJECT_ROOT / 'migrations' / 'tenant',
}
BASELINE_REVISIONS = {
    'central': 'central_0001',
    'tenant': 'tenant_0001',
}
BASELINE_REQUIRED_TABLES = {
    'central': {'companies', 'users'},
    'tenant': {
        'companies', 'users', 'categories', 'products', 'cash_registers',
        'sales', 'sale_items', 'payments', 'stock_movements', 'audit_logs',
    },
}


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class MigrationResult:
    database: str
    migration_kind: str
    previous_revision: str | None
    current_revision: str | None
    status: str
    duration_seconds: float
    baseline_applied: bool = False
    error: str = ''


def migration_config(kind, connection=None):
    directory = MIGRATION_DIRECTORIES.get(kind)
    if directory is None:
        raise MigrationError(f'Tipo de migration inválido: {kind}.')
    config = AlembicConfig(str(directory / 'alembic.ini'))
    config.set_main_option('script_location', str(directory))
    if connection is not None:
        config.attributes['connection'] = connection
    return config


def migration_head(kind):
    script = ScriptDirectory.from_config(migration_config(kind))
    heads = script.get_heads()
    if len(heads) != 1:
        raise MigrationError(f'A árvore {kind} precisa possuir exatamente um head; encontrados: {heads}.')
    return heads[0]


def current_revision(connection):
    return MigrationContext.configure(connection).get_current_revision()


def database_label(engine):
    url = engine.url
    return url.database or 'database'


def existing_business_tables(engine):
    return set(inspect(engine).get_table_names()) - {'alembic_version'}


def validate_baseline_schema(engine, kind):
    tables = existing_business_tables(engine)
    missing = sorted(BASELINE_REQUIRED_TABLES[kind] - tables)
    if missing:
        raise MigrationError(
            f'O banco existente não é compatível com o baseline {kind}; tabelas ausentes: {", ".join(missing)}.'
        )


def validate_current_schema(engine, kind):
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    expected_tables = set(db.Model.metadata.tables)
    if kind == 'tenant':
        expected_tables.discard('app_registration_codes')
    missing_tables = sorted(expected_tables - tables)
    if missing_tables:
        raise MigrationError(f'Tabelas ausentes após migration: {", ".join(missing_tables)}.')
    for table_name, table in db.Model.metadata.tables.items():
        if table_name not in expected_tables:
            continue
        actual_columns = {column['name'] for column in inspector.get_columns(table_name)}
        missing_columns = sorted(set(table.columns.keys()) - actual_columns)
        if missing_columns:
            raise MigrationError(
                f'Colunas ausentes em {table_name}: {", ".join(missing_columns)}.'
            )


def database_revision(engine):
    with engine.connect() as connection:
        return current_revision(connection)


def upgrade_database(engine, kind, allow_baseline=True, logger=None):
    started_at = time.perf_counter()
    label = database_label(engine)
    previous = database_revision(engine)
    baseline_applied = False
    head = migration_head(kind)
    if logger:
        logger.info('Migration %s iniciada: banco=%s de=%s para=%s', kind, label, previous or 'sem revisão', head)
    try:
        tables = existing_business_tables(engine)
        with engine.connect() as connection:
            config = migration_config(kind, connection)
            if tables and previous is None:
                if not allow_baseline:
                    raise MigrationError(f'O banco {label} existe, mas ainda não possui revisão Alembic.')
                validate_baseline_schema(engine, kind)
                command.stamp(config, BASELINE_REVISIONS[kind])
                connection.commit()
                baseline_applied = True
            command.upgrade(config, 'head')
            connection.commit()
        validate_current_schema(engine, kind)
        current = database_revision(engine)
        if current != head:
            raise MigrationError(f'Revisão inesperada após upgrade: {current}; esperado: {head}.')
        result = MigrationResult(
            database=label, migration_kind=kind, previous_revision=previous,
            current_revision=current, status='success',
            duration_seconds=round(time.perf_counter() - started_at, 3),
            baseline_applied=baseline_applied,
        )
        if logger:
            logger.info('Migration %s concluída: banco=%s revisão=%s duração=%.3fs', kind, label, current, result.duration_seconds)
        return result
    except Exception as error:
        if logger:
            logger.error('Migration %s falhou: banco=%s de=%s para=%s erro=%s', kind, label, previous or 'sem revisão', head, error)
        raise MigrationError(f'Migration {kind} falhou no banco {label}: {error}') from error


def assert_database_at_head(engine, kind):
    current = database_revision(engine)
    head = migration_head(kind)
    if current != head:
        raise MigrationError(
            f'Banco {database_label(engine)} desatualizado: revisão atual {current or "não versionada"}, esperada {head}.'
        )
    validate_current_schema(engine, kind)
    return current
