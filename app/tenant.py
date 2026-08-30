import re
import time
from threading import Lock

from flask import current_app, g, has_request_context, session
from flask_login import current_user
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.extensions import db
from app.services.migration_service import assert_database_at_head, upgrade_database


_engines = {}
_reference_sync_times = {}
_reference_sync_locks = {}
_reference_sync_locks_guard = Lock()
CONCURRENT_DDL_ERROR_CODE = 1684
TENANT_SCHEMA_RETRIES = 4
TENANT_REFERENCE_SYNC_SECONDS = 300


def slugify(value):
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', value or '').strip('-').lower()
    return slug or 'adega'


def mysql_database_name(company):
    prefix = current_app.config.get('MYSQL_TENANT_DATABASE_PREFIX') or 'adega'
    slug = slugify(company.name).replace('-', '_')
    return f'{prefix}_{company.id}_{slug}'


def tenant_database_identifier(company, *, persist=True):
    if getattr(company, 'is_system', False):
        if company.database_path:
            company.database_path = ''
            if persist:
                db.session.commit()
        return ''
    if not company.database_path or company.database_path.endswith('.db'):
        company.database_path = mysql_database_name(company)
        if persist:
            db.session.commit()
    return company.database_path


def mysql_tenant_url(database_name):
    template = current_app.config.get('MYSQL_TENANT_DATABASE_URL_TEMPLATE') or ''
    if template:
        return template.format(database=database_name)

    central_url = make_url(current_app.config['SQLALCHEMY_DATABASE_URI'])
    return central_url.set(database=database_name)


def create_mysql_database_if_needed(database_name):
    server_url = current_app.config.get('MYSQL_SERVER_DATABASE_URL') or ''
    if server_url:
        admin_url = server_url
    else:
        central_url = make_url(current_app.config['SQLALCHEMY_DATABASE_URI'])
        admin_url = central_url.set(database='mysql')

    admin_engine = create_engine(admin_url)
    safe_name = ''.join(char for char in database_name if char.isalnum() or char == '_')
    if safe_name != database_name:
        raise ValueError('Nome do banco da adega inválido.')

    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE DATABASE IF NOT EXISTS `{database_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'))
    admin_engine.dispose()


def is_concurrent_ddl_error(error):
    original = getattr(error, 'orig', error)
    args = getattr(original, 'args', ())
    if args and args[0] == CONCURRENT_DDL_ERROR_CODE:
        return True
    return 'concurrent DDL statement' in str(error)


def run_with_concurrent_ddl_retry(operation, label):
    for attempt in range(TENANT_SCHEMA_RETRIES):
        try:
            return operation()
        except OperationalError as error:
            if not is_concurrent_ddl_error(error) or attempt == TENANT_SCHEMA_RETRIES - 1:
                raise
            wait_seconds = 0.35 * (attempt + 1)
            current_app.logger.warning(
                'DDL concorrente ao preparar tenant %s. Tentando novamente em %.2fs.',
                label,
                wait_seconds,
            )
            time.sleep(wait_seconds)
    return None


def drop_mysql_database(database_name):
    if current_app.config.get('TESTING'):
        return

    safe_name = ''.join(char for char in database_name if char.isalnum() or char == '_')
    if safe_name != database_name:
        raise ValueError('Nome do banco da adega inválido.')

    engine_key = f'mysql:{database_name}'
    existing_engine = _engines.pop(engine_key, None)
    _reference_sync_times.pop(engine_key, None)
    _reference_sync_locks.pop(engine_key, None)
    if existing_engine:
        existing_engine.dispose()

    admin_url = current_app.config.get('MYSQL_SERVER_DATABASE_URL')
    if not admin_url:
        central_url = make_url(current_app.config['SQLALCHEMY_DATABASE_URI'])
        admin_url = central_url.set(database='mysql')
    admin_engine = create_engine(admin_url)
    with admin_engine.begin() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS `{database_name}`'))
    admin_engine.dispose()


def sync_tenant_reference_data(company, engine):
    from app.models import User

    users = User.query.filter_by(company_id=company.id).all()
    inspector = inspect(engine)

    with engine.begin() as connection:
        connection.execute(
            text(
                '''
                INSERT INTO companies (
                    id, name, database_path, active, allow_negative_stock, subscription_plan, billing_cycle,
                    subscription_started_at, subscription_renews_at, activation_key,
                    activation_key_updated_at, card_fee_enabled, pix_fee_enabled,
                    debit_fee_enabled, credit_fee_enabled, pix_fee_percent,
                    debit_fee_percent, credit_fee_percent, backup_frequency,
                    backup_last_at, backup_last_path, backup_last_status, created_at
                )
                VALUES (
                    :id, :name, :database_path, :active, :allow_negative_stock, :subscription_plan, :billing_cycle,
                    :subscription_started_at, :subscription_renews_at, :activation_key,
                    :activation_key_updated_at, :card_fee_enabled, :pix_fee_enabled,
                    :debit_fee_enabled, :credit_fee_enabled, :pix_fee_percent,
                    :debit_fee_percent, :credit_fee_percent, :backup_frequency,
                    :backup_last_at, :backup_last_path, :backup_last_status, :created_at
                )
                ON DUPLICATE KEY UPDATE
                    name = VALUES(name),
                    database_path = VALUES(database_path),
                    active = VALUES(active),
                    allow_negative_stock = VALUES(allow_negative_stock),
                    subscription_plan = VALUES(subscription_plan),
                    billing_cycle = VALUES(billing_cycle),
                    subscription_started_at = VALUES(subscription_started_at),
                    subscription_renews_at = VALUES(subscription_renews_at),
                    activation_key = VALUES(activation_key),
                    activation_key_updated_at = VALUES(activation_key_updated_at),
                    card_fee_enabled = VALUES(card_fee_enabled),
                    pix_fee_enabled = VALUES(pix_fee_enabled),
                    debit_fee_enabled = VALUES(debit_fee_enabled),
                    credit_fee_enabled = VALUES(credit_fee_enabled),
                    pix_fee_percent = VALUES(pix_fee_percent),
                    debit_fee_percent = VALUES(debit_fee_percent),
                    credit_fee_percent = VALUES(credit_fee_percent),
                    backup_frequency = VALUES(backup_frequency),
                    backup_last_at = VALUES(backup_last_at),
                    backup_last_path = VALUES(backup_last_path),
                    backup_last_status = VALUES(backup_last_status)
                '''
            ),
            {
                'id': company.id,
                'name': company.name,
                'database_path': company.database_path,
                'active': company.active,
                'allow_negative_stock': company.allow_negative_stock,
                'subscription_plan': company.subscription_plan,
                'billing_cycle': company.billing_cycle,
                'subscription_started_at': company.subscription_started_at,
                'subscription_renews_at': company.subscription_renews_at,
                'activation_key': company.activation_key,
                'activation_key_updated_at': company.activation_key_updated_at,
                'card_fee_enabled': company.card_fee_enabled,
                'pix_fee_enabled': company.pix_fee_enabled,
                'debit_fee_enabled': company.debit_fee_enabled,
                'credit_fee_enabled': company.credit_fee_enabled,
                'pix_fee_percent': company.pix_fee_percent,
                'debit_fee_percent': company.debit_fee_percent,
                'credit_fee_percent': company.credit_fee_percent,
                'backup_frequency': company.backup_frequency,
                'backup_last_at': company.backup_last_at,
                'backup_last_path': company.backup_last_path,
                'backup_last_status': company.backup_last_status,
                'created_at': company.created_at,
            },
        )

        for user in users:
            connection.execute(
                text(
                    '''
                    INSERT INTO users (
                        id, username, first_name, last_name, cpf, email, phone,
                        password_hash, role, company_id, is_active,
                        can_view_products, can_manage_products, can_manage_categories,
                        can_manage_sales, can_cancel_sales, can_manage_cash_register, can_view_reports,
                        can_manage_payables, can_manage_settings,
                        can_view_stock_movements, can_manage_stock, can_view_audit_logs,
                        created_at
                    )
                    VALUES (
                        :id, :username, :first_name, :last_name, :cpf, :email, :phone,
                        :password_hash, :role, :company_id, :is_active,
                        :can_view_products, :can_manage_products, :can_manage_categories,
                        :can_manage_sales, :can_cancel_sales, :can_manage_cash_register, :can_view_reports,
                        :can_manage_payables, :can_manage_settings,
                        :can_view_stock_movements, :can_manage_stock, :can_view_audit_logs,
                        :created_at
                    )
                    ON DUPLICATE KEY UPDATE
                        username = VALUES(username),
                        first_name = VALUES(first_name),
                        last_name = VALUES(last_name),
                        cpf = VALUES(cpf),
                        email = VALUES(email),
                        phone = VALUES(phone),
                        password_hash = VALUES(password_hash),
                        role = VALUES(role),
                        company_id = VALUES(company_id),
                        is_active = VALUES(is_active),
                        can_view_products = VALUES(can_view_products),
                        can_manage_products = VALUES(can_manage_products),
                        can_manage_categories = VALUES(can_manage_categories),
                        can_manage_sales = VALUES(can_manage_sales),
                        can_cancel_sales = VALUES(can_cancel_sales),
                        can_manage_cash_register = VALUES(can_manage_cash_register),
                        can_view_reports = VALUES(can_view_reports),
                        can_manage_payables = VALUES(can_manage_payables),
                        can_manage_settings = VALUES(can_manage_settings),
                        can_view_stock_movements = VALUES(can_view_stock_movements),
                        can_manage_stock = VALUES(can_manage_stock),
                        can_view_audit_logs = VALUES(can_view_audit_logs)
                    '''
                ),
                {
                    'id': user.id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'cpf': user.cpf,
                    'email': user.email,
                    'phone': user.phone,
                    'password_hash': user.password_hash,
                    'role': user.role,
                    'company_id': user.company_id,
                    'is_active': user.is_active,
                    'can_view_products': user.can_view_products,
                    'can_manage_products': user.can_manage_products,
                    'can_manage_categories': user.can_manage_categories,
                    'can_manage_sales': user.can_manage_sales,
                    'can_cancel_sales': user.can_cancel_sales,
                    'can_manage_cash_register': user.can_manage_cash_register,
                    'can_view_reports': user.can_view_reports,
                    'can_manage_payables': user.can_manage_payables,
                    'can_manage_settings': user.can_manage_settings,
                    'can_view_stock_movements': user.can_view_stock_movements,
                    'can_manage_stock': user.can_manage_stock,
                    'can_view_audit_logs': user.can_view_audit_logs,
                    'created_at': user.created_at,
                },
            )


def tenant_reference_sync_lock(cache_key):
    with _reference_sync_locks_guard:
        return _reference_sync_locks.setdefault(cache_key, Lock())


def current_user_missing_from_tenant(company, engine):
    if not has_request_context() or not current_user.is_authenticated:
        return False
    if current_user.company_id != company.id:
        return False

    with engine.connect() as connection:
        user_id = connection.execute(
            text('SELECT id FROM users WHERE id = :user_id LIMIT 1'),
            {'user_id': current_user.id},
        ).scalar()
    return user_id is None


def ensure_tenant_reference_data(company, engine, cache_key):
    last_sync = _reference_sync_times.get(cache_key, 0)
    sync_due = (time.monotonic() - last_sync) >= TENANT_REFERENCE_SYNC_SECONDS
    if not sync_due and not current_user_missing_from_tenant(company, engine):
        return

    with tenant_reference_sync_lock(cache_key):
        last_sync = _reference_sync_times.get(cache_key, 0)
        sync_due = (time.monotonic() - last_sync) >= TENANT_REFERENCE_SYNC_SECONDS
        if not sync_due and not current_user_missing_from_tenant(company, engine):
            return

        run_with_concurrent_ddl_retry(
            lambda: sync_tenant_reference_data(company, engine),
            company.database_path,
        )
        _reference_sync_times[cache_key] = time.monotonic()


def tenant_engine(company, *, persist_identifier=True):
    if getattr(company, 'is_system', False):
        raise RuntimeError('O contexto master do SkyGest não possui banco de adega.')
    identifier = tenant_database_identifier(company, persist=persist_identifier)
    if current_app.config.get('TESTING'):
        return db.engine

    cache_key = f'mysql:{identifier}'
    if cache_key not in _engines:
        create_mysql_database_if_needed(identifier)
        engine = create_engine(mysql_tenant_url(identifier))
        schema_mode = current_app.config.get('SCHEMA_MANAGEMENT_MODE', 'verify')
        if schema_mode == 'upgrade' or not inspect(engine).get_table_names():
            upgrade_database(engine, 'tenant', logger=current_app.logger)
        elif schema_mode == 'verify':
            assert_database_at_head(engine, 'tenant')
        elif schema_mode != 'off':
            raise RuntimeError(f'SCHEMA_MANAGEMENT_MODE inválido: {schema_mode}.')
        _engines[cache_key] = engine
    ensure_tenant_reference_data(company, _engines[cache_key], cache_key)
    return _engines[cache_key]


def current_tenant_company():
    if not current_user.is_authenticated:
        return None

    if current_user.role == 'master':
        company_id = session.get('master_company_id')
        if company_id:
            from app.models import Company
            return db.session.get(Company, int(company_id))

    return current_user.company


def tenant_session():
    company = current_tenant_company()
    if not company:
        return None

    if getattr(company, 'is_system', False):
        # Mantém os testes legados sobre SQLite; ambientes reais nunca abrem
        # sessão de tenant para o painel administrativo SaaS.
        return db.session if current_app.config.get('TESTING') else None

    if current_app.config.get('TESTING'):
        return db.session

    if 'tenant_session' not in g:
        Session = sessionmaker(bind=tenant_engine(company))
        g.tenant_session = Session()

    return g.tenant_session


def close_tenant_session(error=None):
    session = g.pop('tenant_session', None)
    if session is not None:
        if error:
            session.rollback()
        session.close()
