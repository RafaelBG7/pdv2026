#!/usr/bin/env python3
"""Fail-closed validation for SkyGest production/homologation configuration."""

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse


PROTECTED_SECRET_FIELDS = (
    'SECRET_KEY',
    'API_TOKEN_SECRET',
    'MASTER_DEFAULT_PASSWORD',
    'MYSQL_PASSWORD',
    'MYSQL_ROOT_PASSWORD',
)


def parse_env(path):
    values = {}
    for raw_line in Path(path).read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def validate_secret_strength(values, errors):
    for field in PROTECTED_SECRET_FIELDS:
        value = values.get(field, '')
        if len(value) < 16 or any(marker in value.lower() for marker in ('troque', 'defina', 'gere-', 'master123')):
            errors.append(f'{field} ausente, curto ou com valor de exemplo')


def validate_homologation(values, production_values=None, validate_secrets=True):
    errors = []
    expected = {
        'APP_ENV': 'homologation',
        'PUBLIC_BASE_URL': 'https://hml.skygest.com.br',
        'MYSQL_HOST': 'mysql',
        'MYSQL_DATABASE': 'skygest_hml_central',
        'MYSQL_TENANT_DATABASE_PREFIX': 'skygest_hml_tenant',
        'RATELIMIT_STORAGE_URI': 'redis://redis:6379/0',
        'RATELIMIT_IN_MEMORY_FALLBACK_ENABLED': '0',
        'SCHEMA_MANAGEMENT_MODE': 'verify',
        'SESSION_COOKIE_SECURE': '1',
        'API_ALLOW_INSECURE_AUTH': '0',
        'MAIL_SUPPRESS_SEND': '1',
        'SUBSCRIPTION_COMMERCIAL_ENABLED': '0',
        'HML_BACKUP_HOST_DIR': '/opt/girofy/hml/backups',
    }
    for field, expected_value in expected.items():
        if values.get(field) != expected_value:
            errors.append(f'{field} deve ser {expected_value!r} em homologação')

    if validate_secrets:
        validate_secret_strength(values, errors)

    for url_field in ('DATABASE_URL', 'MYSQL_SERVER_DATABASE_URL'):
        url_value = values.get(url_field)
        if not url_value:
            continue
        parsed = urlparse(url_value.replace('mysql+pymysql://', 'mysql://', 1))
        if parsed.hostname != 'mysql':
            errors.append(f'{url_field} deve apontar para o service mysql da stack HML')
        if url_field == 'DATABASE_URL' and parsed.path.strip('/') != 'skygest_hml_central':
            errors.append('DATABASE_URL não aponta para skygest_hml_central')

    if production_values:
        for field in PROTECTED_SECRET_FIELDS:
            if values.get(field) and values.get(field) == production_values.get(field):
                errors.append(f'{field} está compartilhado com produção')
        production_backup = production_values.get('GIROFY_BACKUP_HOST_DIR', '/opt/girofy/backups')
        if values.get('HML_BACKUP_HOST_DIR') == production_backup:
            errors.append('diretório de backup está compartilhado com produção')

    return errors


def validate_production(values, validate_secrets=True):
    errors = []
    if values.get('APP_ENV') != 'production':
        errors.append("APP_ENV deve ser 'production' em produção")
    if values.get('PUBLIC_BASE_URL') not in {'https://skygest.com.br', 'https://www.skygest.com.br'}:
        errors.append('PUBLIC_BASE_URL de produção deve usar o domínio skygest.com.br')
    if values.get('MYSQL_DATABASE', 'adega_central') == 'skygest_hml_central':
        errors.append('produção não pode usar o banco central de homologação')
    if values.get('RATELIMIT_IN_MEMORY_FALLBACK_ENABLED') not in {'0', 'false', 'False'}:
        errors.append('fallback em memória deve permanecer desativado em produção')
    if validate_secrets:
        validate_secret_strength(values, errors)
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--environment', required=True, choices=('production', 'homologation'))
    parser.add_argument('--env-file', required=True)
    parser.add_argument('--production-env-file')
    parser.add_argument('--allow-example-secrets', action='store_true')
    args = parser.parse_args()

    values = parse_env(args.env_file)
    if args.environment == 'homologation':
        production_values = parse_env(args.production_env_file) if args.production_env_file else None
        errors = validate_homologation(values, production_values, not args.allow_example_secrets)
    else:
        errors = validate_production(values, not args.allow_example_secrets)

    if errors:
        print(f'Configuração de {args.environment} recusada:', file=sys.stderr)
        for error in errors:
            print(f'- {error}', file=sys.stderr)
        raise SystemExit(1)
    print(f'Configuração de {args.environment} validada sem expor segredos.')


if __name__ == '__main__':
    main()
