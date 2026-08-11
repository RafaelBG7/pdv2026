#!/usr/bin/env python3
"""Versioned schema operations for the central and tenant databases."""

import argparse
import sys
from pathlib import Path

from sqlalchemy import MetaData, Table, create_engine, inspect, select, text
from sqlalchemy.engine import make_url

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.migration_service import (  # noqa: E402
    assert_database_at_head, database_revision, migration_head, upgrade_database,
)
from config import Config  # noqa: E402


def safe_database_name(value):
    safe = ''.join(char for char in value if char.isalnum() or char == '_')
    if safe != value or not safe:
        raise ValueError(f'Nome de banco inválido: {value!r}.')
    return safe


def ensure_database(database_name):
    database_name = safe_database_name(database_name)
    engine = create_engine(Config.MYSQL_SERVER_DATABASE_URL)
    if engine.url.drivername.startswith('mysql'):
        with engine.begin() as connection:
            connection.execute(text(f'CREATE DATABASE IF NOT EXISTS `{database_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'))
    engine.dispose()


def central_engine():
    url = make_url(Config.SQLALCHEMY_DATABASE_URI)
    if url.drivername.startswith('mysql') and url.database:
        ensure_database(url.database)
    return create_engine(url)


def tenant_url(database_name):
    template = Config.MYSQL_TENANT_DATABASE_URL_TEMPLATE
    if template:
        return make_url(template.format(database=safe_database_name(database_name)))
    return make_url(Config.SQLALCHEMY_DATABASE_URI).set(database=safe_database_name(database_name))


def tenant_names(engine):
    metadata = MetaData()
    companies = Table('companies', metadata, autoload_with=engine)
    with engine.connect() as connection:
        return [row.database_path for row in connection.execute(select(companies.c.database_path).where(companies.c.database_path != '')) if row.database_path]


def status(engine, kind):
    label = engine.url.database or 'database'
    head = migration_head(kind)
    try:
        current = database_revision(engine)
        assert_database_at_head(engine, kind)
        state = 'atualizado'
    except Exception as error:
        current = database_revision(engine) if inspect(engine).has_table('alembic_version') else None
        state = f'pendente/inválido ({error})'
    print(f'{kind}:{label}: atual={current or "sem revisão"} head={head} estado={state}')


def upgrade_all(continue_on_error=False):
    central = central_engine()
    failures = []
    try:
        result = upgrade_database(central, 'central')
        print(f'central:{result.database}: {result.previous_revision or "sem revisão"} -> {result.current_revision} ({result.status})')
        for name in tenant_names(central):
            tenant = None
            try:
                ensure_database(name)
                tenant = create_engine(tenant_url(name))
                result = upgrade_database(tenant, 'tenant')
                print(f'tenant:{name}: {result.previous_revision or "sem revisão"} -> {result.current_revision} ({result.status})')
            except Exception as error:
                failures.append((name, str(error)))
                print(f'tenant:{name}: FALHA: {error}', file=sys.stderr)
                if not continue_on_error:
                    break
            finally:
                if tenant is not None:
                    tenant.dispose()
    finally:
        central.dispose()
    if failures:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('central-current', 'central-upgrade', 'tenants-status', 'tenants-upgrade', 'upgrade-all'))
    parser.add_argument('--continue-on-error', action='store_true')
    args = parser.parse_args()
    central = central_engine()
    try:
        if args.command == 'central-current':
            status(central, 'central')
        elif args.command == 'central-upgrade':
            result = upgrade_database(central, 'central')
            print(f'central:{result.database}: {result.previous_revision or "sem revisão"} -> {result.current_revision} ({result.status})')
        elif args.command == 'upgrade-all':
            central.dispose()
            upgrade_all(args.continue_on_error)
            return
        else:
            for name in tenant_names(central):
                ensure_database(name)
                engine = create_engine(tenant_url(name))
                try:
                    if args.command == 'tenants-status':
                        status(engine, 'tenant')
                    else:
                        result = upgrade_database(engine, 'tenant')
                        print(f'tenant:{name}: {result.previous_revision or "sem revisão"} -> {result.current_revision} ({result.status})')
                finally:
                    engine.dispose()
    finally:
        central.dispose()


if __name__ == '__main__':
    main()
