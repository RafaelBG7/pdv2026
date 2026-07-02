from datetime import date, timedelta

from flask import Flask, redirect, render_template, request, session, url_for
from flask_login import current_user
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

from app.extensions import db, login_manager
from app.error_logging import log_http_error, setup_error_logging
from config import Config


def ensure_mysql_database_exists(database_uri):
    url = make_url(database_uri)
    if not url.drivername.startswith('mysql'):
        return

    database_name = url.database
    if not database_name:
        return

    admin_url = url.set(database='mysql')
    admin_engine = create_engine(admin_url)
    safe_name = ''.join(char for char in database_name if char.isalnum() or char == '_')
    if safe_name != database_name:
        raise ValueError('Nome do banco central inválido.')

    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE DATABASE IF NOT EXISTS `{database_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'))
    admin_engine.dispose()


def ensure_product_kit_columns():
    inspector = inspect(db.engine)
    if 'products' not in inspector.get_table_names():
        return

    columns = {column['name'] for column in inspector.get_columns('products')}
    migrations = {
        'is_kit': 'ALTER TABLE products ADD COLUMN is_kit BOOLEAN DEFAULT 0',
        'kit_component_product_id': 'ALTER TABLE products ADD COLUMN kit_component_product_id INTEGER',
        'kit_component_quantity': 'ALTER TABLE products ADD COLUMN kit_component_quantity INTEGER DEFAULT 0',
    }

    for column, statement in migrations.items():
        if column not in columns:
            db.session.execute(text(statement))

    db.session.commit()


def ensure_product_stock_columns():
    inspector = inspect(db.engine)
    if 'products' not in inspector.get_table_names():
        return

    columns = {column['name'] for column in inspector.get_columns('products')}
    migrations = {
        'min_stock_quantity': 'ALTER TABLE products ADD COLUMN min_stock_quantity INTEGER DEFAULT 0',
    }

    for column, statement in migrations.items():
        if column not in columns:
            db.session.execute(text(statement))

    db.session.commit()


def ensure_sale_discount_columns():
    inspector = inspect(db.engine)
    if 'sales' not in inspector.get_table_names():
        return

    columns = {column['name'] for column in inspector.get_columns('sales')}
    migrations = {
        'discount_amount': 'ALTER TABLE sales ADD COLUMN discount_amount FLOAT DEFAULT 0.0',
    }

    for column, statement in migrations.items():
        if column not in columns:
            db.session.execute(text(statement))

    db.session.commit()


def ensure_sale_item_profit_columns():
    inspector = inspect(db.engine)
    if 'sale_items' not in inspector.get_table_names():
        return

    columns = {column['name'] for column in inspector.get_columns('sale_items')}
    migrations = {
        'unit_cost_price': 'ALTER TABLE sale_items ADD COLUMN unit_cost_price FLOAT DEFAULT 0.0',
        'profit_amount': 'ALTER TABLE sale_items ADD COLUMN profit_amount FLOAT DEFAULT 0.0',
    }

    for column, statement in migrations.items():
        if column not in columns:
            db.session.execute(text(statement))

    db.session.commit()


def ensure_user_profile_columns():
    inspector = inspect(db.engine)
    if 'users' not in inspector.get_table_names():
        return

    columns = {column['name'] for column in inspector.get_columns('users')}
    migrations = {
        'first_name': 'ALTER TABLE users ADD COLUMN first_name VARCHAR(120) DEFAULT ""',
        'last_name': 'ALTER TABLE users ADD COLUMN last_name VARCHAR(120) DEFAULT ""',
        'email': 'ALTER TABLE users ADD COLUMN email VARCHAR(255) DEFAULT ""',
        'phone': 'ALTER TABLE users ADD COLUMN phone VARCHAR(40) DEFAULT ""',
    }

    for column, statement in migrations.items():
        if column not in columns:
            db.session.execute(text(statement))

    db.session.commit()


def ensure_user_permission_columns():
    inspector = inspect(db.engine)
    if 'users' not in inspector.get_table_names():
        return

    columns = {column['name'] for column in inspector.get_columns('users')}
    migrations = {
        'can_view_products': 'ALTER TABLE users ADD COLUMN can_view_products BOOLEAN DEFAULT 1',
        'can_manage_products': 'ALTER TABLE users ADD COLUMN can_manage_products BOOLEAN DEFAULT 1',
        'can_manage_categories': 'ALTER TABLE users ADD COLUMN can_manage_categories BOOLEAN DEFAULT 1',
        'can_manage_sales': 'ALTER TABLE users ADD COLUMN can_manage_sales BOOLEAN DEFAULT 1',
        'can_manage_cash_register': 'ALTER TABLE users ADD COLUMN can_manage_cash_register BOOLEAN DEFAULT 1',
        'can_view_reports': 'ALTER TABLE users ADD COLUMN can_view_reports BOOLEAN DEFAULT 1',
        'can_manage_payables': 'ALTER TABLE users ADD COLUMN can_manage_payables BOOLEAN DEFAULT 1',
        'can_manage_settings': 'ALTER TABLE users ADD COLUMN can_manage_settings BOOLEAN DEFAULT 1',
    }

    for column, statement in migrations.items():
        if column not in columns:
            db.session.execute(text(statement))

    db.session.commit()


def ensure_company_columns():
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()

    company_columns = {
        'users': 'ALTER TABLE users ADD COLUMN company_id INTEGER',
        'companies': 'ALTER TABLE companies ADD COLUMN database_path VARCHAR(255) DEFAULT ""',
        'companies_active': 'ALTER TABLE companies ADD COLUMN active BOOLEAN DEFAULT 1',
        'categories': 'ALTER TABLE categories ADD COLUMN company_id INTEGER',
        'products': 'ALTER TABLE products ADD COLUMN company_id INTEGER',
        'cash_registers': 'ALTER TABLE cash_registers ADD COLUMN company_id INTEGER',
        'sales': 'ALTER TABLE sales ADD COLUMN company_id INTEGER',
    }

    for table_name, statement in company_columns.items():
        actual_table = 'companies' if table_name == 'companies_active' else table_name
        if actual_table not in tables:
            continue
        columns = {column['name'] for column in inspector.get_columns(actual_table)}
        if table_name != 'companies' and table_name != 'companies_active' and 'company_id' not in columns:
            try:
                db.session.execute(text(statement))
            except OperationalError:
                db.session.rollback()
        if table_name == 'companies':
            columns = {column['name'] for column in inspect(db.engine).get_columns(actual_table)}
            if 'database_path' not in columns:
                try:
                    db.session.execute(text(statement))
                except OperationalError:
                    db.session.rollback()
        if table_name == 'companies_active' and 'active' not in columns:
            try:
                db.session.execute(text(statement))
            except OperationalError:
                db.session.rollback()

    db.session.commit()


def ensure_company_subscription_columns():
    inspector = inspect(db.engine)
    if 'companies' not in inspector.get_table_names():
        return

    columns = {column['name'] for column in inspector.get_columns('companies')}
    migrations = {
        'subscription_plan': 'ALTER TABLE companies ADD COLUMN subscription_plan VARCHAR(80) DEFAULT "Essencial"',
        'billing_cycle': 'ALTER TABLE companies ADD COLUMN billing_cycle VARCHAR(20) DEFAULT "monthly"',
        'subscription_started_at': 'ALTER TABLE companies ADD COLUMN subscription_started_at DATE',
        'subscription_renews_at': 'ALTER TABLE companies ADD COLUMN subscription_renews_at DATE',
        'activation_key': 'ALTER TABLE companies ADD COLUMN activation_key VARCHAR(80) DEFAULT ""',
        'activation_key_updated_at': 'ALTER TABLE companies ADD COLUMN activation_key_updated_at DATETIME',
    }

    for column, statement in migrations.items():
        if column not in columns:
            try:
                db.session.execute(text(statement))
            except OperationalError:
                db.session.rollback()

    today = date.today()
    renewal = today + timedelta(days=30)
    db.session.execute(text(
        'UPDATE companies SET subscription_plan = "Essencial" '
        'WHERE subscription_plan IS NULL OR subscription_plan = ""'
    ))
    db.session.execute(text(
        'UPDATE companies SET billing_cycle = "monthly" '
        'WHERE billing_cycle IS NULL OR billing_cycle = ""'
    ))
    db.session.execute(
        text('UPDATE companies SET subscription_started_at = :today WHERE subscription_started_at IS NULL'),
        {'today': today.isoformat()},
    )
    db.session.execute(
        text('UPDATE companies SET subscription_renews_at = :renewal WHERE subscription_renews_at IS NULL'),
        {'renewal': renewal.isoformat()},
    )
    db.session.commit()


def ensure_company_card_fee_columns():
    inspector = inspect(db.engine)
    if 'companies' not in inspector.get_table_names():
        return

    columns = {column['name'] for column in inspector.get_columns('companies')}
    migrations = {
        'card_fee_enabled': 'ALTER TABLE companies ADD COLUMN card_fee_enabled BOOLEAN DEFAULT 0',
        'pix_fee_enabled': 'ALTER TABLE companies ADD COLUMN pix_fee_enabled BOOLEAN DEFAULT 0',
        'debit_fee_enabled': 'ALTER TABLE companies ADD COLUMN debit_fee_enabled BOOLEAN DEFAULT 0',
        'credit_fee_enabled': 'ALTER TABLE companies ADD COLUMN credit_fee_enabled BOOLEAN DEFAULT 0',
        'pix_fee_percent': 'ALTER TABLE companies ADD COLUMN pix_fee_percent FLOAT DEFAULT 0.0',
        'debit_fee_percent': 'ALTER TABLE companies ADD COLUMN debit_fee_percent FLOAT DEFAULT 0.0',
        'credit_fee_percent': 'ALTER TABLE companies ADD COLUMN credit_fee_percent FLOAT DEFAULT 0.0',
    }

    for column, statement in migrations.items():
        if column not in columns:
            try:
                db.session.execute(text(statement))
            except OperationalError:
                db.session.rollback()

    db.session.commit()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    setup_error_logging(app)
    ensure_mysql_database_exists(app.config['SQLALCHEMY_DATABASE_URI'])

    db.init_app(app)
    login_manager.init_app(app)

    with app.app_context():
        from app.models import Company, User
        from app.routes import auth_bp, catalog_bp, main_bp
        from app.tenant import tenant_database_identifier, tenant_engine

        app.register_blueprint(auth_bp)
        app.register_blueprint(catalog_bp)
        app.register_blueprint(main_bp)

        db.create_all()
        ensure_product_kit_columns()
        ensure_product_stock_columns()
        ensure_sale_discount_columns()
        ensure_sale_item_profit_columns()
        ensure_user_profile_columns()
        ensure_user_permission_columns()
        ensure_company_columns()
        ensure_company_subscription_columns()
        ensure_company_card_fee_columns()

        if not User.query.filter_by(username='master').first():
            company = Company(name='Painel Master')
            db.session.add(company)
            db.session.flush()
            tenant_database_identifier(company)
            tenant_engine(company)
            master = User(username='master', role='master', is_active=True)
            master.company_id = company.id
            master.set_password('master123')
            db.session.add(master)
            db.session.commit()
        else:
            users_without_company = User.query.filter(User.company_id.is_(None)).all()
            if users_without_company:
                company = Company.query.order_by(Company.id.asc()).first()
                if not company:
                    company = Company(name='Adega JF')
                    db.session.add(company)
                    db.session.flush()
                tenant_database_identifier(company)
                for user in users_without_company:
                    user.company_id = company.id
                for table_name in ('categories', 'products', 'cash_registers', 'sales'):
                    if table_name in inspect(db.engine).get_table_names():
                        db.session.execute(text(f'UPDATE {table_name} SET company_id = :company_id WHERE company_id IS NULL'), {'company_id': company.id})
                db.session.commit()

            for company in Company.query.all():
                tenant_database_identifier(company)
                tenant_engine(company)

    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return db.session.get(User, int(user_id))

    @app.before_request
    def block_expired_subscription():
        if not current_user.is_authenticated:
            return None
        if current_user.role == 'master':
            return None
        if not request.endpoint:
            return None
        allowed_endpoints = {
            'auth.subscription_activation',
            'auth.subscriptions',
            'auth.logout',
            'static',
        }
        if request.endpoint in allowed_endpoints:
            return None

        company = current_user.company
        if not company or not company.active or not company.subscription_renews_at or company.subscription_renews_at < date.today():
            return redirect(url_for('auth.subscription_activation'))
        return None

    @app.errorhandler(404)
    def not_found_error(error):
        log_http_error(app, error)
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        log_http_error(app, error)
        return render_template('errors/500.html'), 500

    @app.context_processor
    def inject_user():
        notifications = []
        master_company = None

        if current_user.is_authenticated:
            from app.models import Payable, Product
            from app.tenant import current_tenant_company, tenant_session

            low_stock_products = []
            dismissed_notifications = set(session.get('dismissed_low_stock_notifications', []))
            master_company = current_tenant_company() if current_user.role == 'master' else None
            tenant_db = tenant_session()
            products = tenant_db.query(Product).filter(
                Product.company_id == current_tenant_company().id,
                Product.active.is_(True),
            ).order_by(Product.name.asc()).all() if tenant_db and current_tenant_company() else []
            for product in products:
                stock_quantity = product.effective_stock_quantity or 0
                min_stock_quantity = product.min_stock_quantity or 0
                notification_key = f'product-low-stock:{product.id}:{stock_quantity}:{min_stock_quantity}'
                if min_stock_quantity > 0 and stock_quantity <= min_stock_quantity and notification_key not in dismissed_notifications:
                    low_stock_products.append((stock_quantity, min_stock_quantity, notification_key, product))

            low_stock_products.sort(key=lambda item: (item[0], item[3].name.lower()))
            for stock_quantity, min_stock_quantity, notification_key, product in low_stock_products[:10]:
                if stock_quantity <= 0:
                    message = f'{product.name} está sem estoque. Mínimo: {min_stock_quantity} un.'
                else:
                    message = f'{product.name} está com {stock_quantity} un. Mínimo: {min_stock_quantity} un.'

                notifications.append({
                    'title': 'Estoque baixo',
                    'message': message,
                    'url': url_for('catalog.dismiss_low_stock_notification', product_id=product.id),
                    'key': notification_key,
                })

            today = date.today()
            alert_limit = today + timedelta(days=3)
            payables = tenant_db.query(Payable).filter(
                Payable.company_id == current_tenant_company().id,
                Payable.paid.is_(False),
                Payable.due_date <= alert_limit,
            ).order_by(Payable.due_date.asc(), Payable.description.asc()).all() if tenant_db and current_tenant_company() else []

            for payable in payables[:10]:
                amount = f'R$ {(payable.amount or 0):.2f}'.replace('.', ',')
                if payable.due_date < today:
                    days = (today - payable.due_date).days
                    title = 'Conta vencida'
                    message = f'{payable.description} venceu há {days} dia{"s" if days != 1 else ""}. Valor: {amount}.'
                elif payable.due_date == today:
                    title = 'Conta vence hoje'
                    message = f'{payable.description} vence hoje. Valor: {amount}.'
                else:
                    days = (payable.due_date - today).days
                    title = 'Conta próxima do vencimento'
                    message = f'{payable.description} vence em {days} dia{"s" if days != 1 else ""}. Valor: {amount}.'

                notifications.append({
                    'title': title,
                    'message': message,
                    'url': url_for('main.payables'),
                    'key': f'payable:{payable.id}:{payable.due_date}',
                })

        return {
            'current_user': current_user,
            'app_notifications': notifications,
            'master_company': master_company,
            'master_company_active': bool(current_user.is_authenticated and current_user.role == 'master' and master_company and master_company.id != current_user.company_id),
        }

    from app.tenant import close_tenant_session
    app.teardown_request(close_tenant_session)

    return app
