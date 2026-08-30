#!/usr/bin/env python3
"""Remove, com guardrails, o schema legado criado para o Painel Master."""

import argparse
import re
import sys
from pathlib import Path

from sqlalchemy import MetaData, Table, create_engine, inspect, select, text
from sqlalchemy.engine import make_url

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import Config


def safe_identifier(value):
    safe = ''.join(char for char in str(value or '') if char.isalnum() or char == '_')
    if not safe or safe != value:
        raise RuntimeError(f'Identificador de banco recusado: {value!r}.')
    return safe


def slugify(value):
    slug = re.sub(r'[^a-zA-Z0-9]+', '_', value or '').strip('_').lower()
    return slug or 'adega'


def expected_database_name(company_id, company_name):
    prefix = safe_identifier(Config.MYSQL_TENANT_DATABASE_PREFIX or 'adega')
    return safe_identifier(f'{prefix}_{company_id}_{slugify(company_name)}')


def validate_legacy_database(admin_url, database_name, system_company_id):
    engine = create_engine(make_url(admin_url).set(database=database_name))
    try:
        tables = set(inspect(engine).get_table_names())
        if 'companies' not in tables:
            return
        metadata = MetaData()
        companies = Table('companies', metadata, autoload_with=engine)
        with engine.connect() as connection:
            rows = connection.execute(select(companies)).mappings().all()
        for row in rows:
            is_master = (
                row.get('id') == system_company_id
                and (
                    row.get('activation_key') == 'MASTER-SYSTEM-KEY'
                    or bool(row.get('is_system'))
                )
            )
            if not is_master:
                raise RuntimeError(
                    f'O banco {database_name} contém referência de adega real; exclusão recusada.'
                )
    finally:
        engine.dispose()


def cleanup(apply=False):
    central_url = make_url(Config.SQLALCHEMY_DATABASE_URI)
    admin_url = make_url(Config.MYSQL_SERVER_DATABASE_URL)
    if not central_url.drivername.startswith('mysql') or not admin_url.drivername.startswith('mysql'):
        raise RuntimeError('A limpeza do tenant master só pode ser executada no MySQL.')

    central = create_engine(central_url)
    admin = create_engine(admin_url)
    try:
        metadata = MetaData()
        companies = Table('companies', metadata, autoload_with=central)
        with central.connect() as connection:
            statement = select(companies).where(
                (companies.c.is_system.is_(True))
                | (companies.c.activation_key == 'MASTER-SYSTEM-KEY')
            ).order_by(companies.c.id)
            system_rows = connection.execute(statement).mappings().all()

        if not system_rows:
            print('Nenhum contexto master legado encontrado.')
            return

        for row in system_rows:
            expected = expected_database_name(row['id'], row['name'])
            stored = row.get('database_path') or ''
            if stored not in ('', expected):
                raise RuntimeError(
                    f'O database_path do contexto master não corresponde ao alvo seguro esperado: {stored!r}.'
                )

            with central.connect() as connection:
                shared = connection.execute(
                    select(companies.c.id).where(
                        companies.c.id != row['id'],
                        companies.c.database_path == expected,
                    )
                ).first()
            if shared:
                raise RuntimeError(f'O banco {expected} está vinculado a outra adega; exclusão recusada.')

            with admin.connect() as connection:
                exists = connection.execute(text(
                    'SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name = :name'
                ), {'name': expected}).scalar_one()

            action = 'REMOVER' if apply else 'VALIDAR'
            print(f'{action}: contexto master id={row["id"]} banco={expected} existente={bool(exists)}')
            if not apply:
                continue

            if exists:
                validate_legacy_database(admin_url, expected, row['id'])
                with admin.begin() as connection:
                    connection.execute(text(f'DROP DATABASE `{expected}`'))

            with central.begin() as connection:
                connection.execute(
                    companies.update().where(companies.c.id == row['id']).values(database_path='')
                )
            print(f'Contexto master id={row["id"]} desvinculado de bancos de adega.')
    finally:
        admin.dispose()
        central.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Efetiva a exclusão após as validações.')
    args = parser.parse_args()
    cleanup(apply=args.apply)


if __name__ == '__main__':
    main()
