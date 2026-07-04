import re

from flask import current_app, g, session
from flask_login import current_user
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.extensions import db


_engines = {}


def slugify(value):
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', value or '').strip('-').lower()
    return slug or 'adega'


def mysql_database_name(company):
    prefix = current_app.config.get('MYSQL_TENANT_DATABASE_PREFIX') or 'adega'
    slug = slugify(company.name).replace('-', '_')
    return f'{prefix}_{company.id}_{slug}'


def tenant_database_identifier(company):
    if not company.database_path or company.database_path.endswith('.db'):
        company.database_path = mysql_database_name(company)
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


def drop_mysql_database(database_name):
    if current_app.config.get('TESTING'):
        return

    safe_name = ''.join(char for char in database_name if char.isalnum() or char == '_')
    if safe_name != database_name:
        raise ValueError('Nome do banco da adega inválido.')

    admin_url = current_app.config.get('MYSQL_SERVER_DATABASE_URL')
    admin_engine = create_engine(admin_url)
    with admin_engine.begin() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS `{database_name}`'))
    admin_engine.dispose()
    _engines.pop(f'mysql:{database_name}', None)


def sync_tenant_reference_data(company, engine):
    from app.models import User

    users = User.query.filter_by(company_id=company.id).all()
    inspector = inspect(engine)
    if 'companies' in inspector.get_table_names():
        columns = {column['name'] for column in inspector.get_columns('companies')}
        migrations = {
            'backup_frequency': 'ALTER TABLE companies ADD COLUMN backup_frequency VARCHAR(20) DEFAULT "manual"',
            'backup_last_at': 'ALTER TABLE companies ADD COLUMN backup_last_at DATETIME',
            'backup_last_path': 'ALTER TABLE companies ADD COLUMN backup_last_path VARCHAR(255) DEFAULT ""',
            'backup_last_status': 'ALTER TABLE companies ADD COLUMN backup_last_status VARCHAR(40) DEFAULT ""',
        }
        with engine.begin() as connection:
            for column, statement in migrations.items():
                if column not in columns:
                    connection.execute(text(statement))

    if 'users' in inspector.get_table_names():
        columns = {column['name'] for column in inspector.get_columns('users')}
        migrations = {
            'cpf': 'ALTER TABLE users ADD COLUMN cpf VARCHAR(20) DEFAULT ""',
        }
        with engine.begin() as connection:
            for column, statement in migrations.items():
                if column not in columns:
                    connection.execute(text(statement))

    with engine.begin() as connection:
        connection.execute(
            text(
                '''
                INSERT INTO companies (
                    id, name, database_path, active, subscription_plan, billing_cycle,
                    subscription_started_at, subscription_renews_at, activation_key,
                    activation_key_updated_at, card_fee_enabled, pix_fee_enabled,
                    debit_fee_enabled, credit_fee_enabled, pix_fee_percent,
                    debit_fee_percent, credit_fee_percent, backup_frequency,
                    backup_last_at, backup_last_path, backup_last_status, created_at
                )
                VALUES (
                    :id, :name, :database_path, :active, :subscription_plan, :billing_cycle,
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
                        can_manage_sales, can_manage_cash_register, can_view_reports,
                        can_manage_payables, can_manage_settings, created_at
                    )
                    VALUES (
                        :id, :username, :first_name, :last_name, :cpf, :email, :phone,
                        :password_hash, :role, :company_id, :is_active,
                        :can_view_products, :can_manage_products, :can_manage_categories,
                        :can_manage_sales, :can_manage_cash_register, :can_view_reports,
                        :can_manage_payables, :can_manage_settings, :created_at
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
                        can_manage_cash_register = VALUES(can_manage_cash_register),
                        can_view_reports = VALUES(can_view_reports),
                        can_manage_payables = VALUES(can_manage_payables),
                        can_manage_settings = VALUES(can_manage_settings)
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
                    'can_manage_cash_register': user.can_manage_cash_register,
                    'can_view_reports': user.can_view_reports,
                    'can_manage_payables': user.can_manage_payables,
                    'can_manage_settings': user.can_manage_settings,
                    'created_at': user.created_at,
                },
            )


def tenant_engine(company):
    identifier = tenant_database_identifier(company)
    if current_app.config.get('TESTING'):
        return db.engine

    cache_key = f'mysql:{identifier}'
    if cache_key not in _engines:
        create_mysql_database_if_needed(identifier)
        engine = create_engine(mysql_tenant_url(identifier))
        db.Model.metadata.create_all(bind=engine)
        _engines[cache_key] = engine
    sync_tenant_reference_data(company, _engines[cache_key])
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
