from datetime import date, datetime, timedelta, timezone

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from flask_login import current_user
from sqlalchemy import create_engine, inspect, or_, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import joinedload
from werkzeug.middleware.proxy_fix import ProxyFix

from app.extensions import db, limiter, login_manager, migrate
from app.money import format_brl
from app.error_logging import log_http_error, setup_error_logging
from app.security.csrf import init_csrf
from app.security.rate_limit import init_rate_limit_errors
from config import Config
from app.time_utils import business_today


def ensure_mysql_database_exists(database_uri):
    url = make_url(database_uri)
    if not url.drivername.startswith('mysql'):
        return

    database_name = url.database
    if not database_name:
        return

    admin_url = make_url(Config.MYSQL_SERVER_DATABASE_URL)
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


def ensure_sale_cancellation_columns():
    inspector = inspect(db.engine)
    if 'sales' not in inspector.get_table_names():
        return

    columns = {column['name'] for column in inspector.get_columns('sales')}
    migrations = {
        'status': "ALTER TABLE sales ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'completed'",
        'cancelled_at': 'ALTER TABLE sales ADD COLUMN cancelled_at DATETIME',
        'cancelled_by_user_id': 'ALTER TABLE sales ADD COLUMN cancelled_by_user_id INTEGER',
        'cancellation_reason': "ALTER TABLE sales ADD COLUMN cancellation_reason VARCHAR(500) DEFAULT ''",
    }
    for column, statement in migrations.items():
        if column not in columns:
            db.session.execute(text(statement))

    db.session.execute(text(
        "UPDATE sales SET status = 'completed' WHERE status IS NULL OR status = ''"
    ))
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
        'cpf': 'ALTER TABLE users ADD COLUMN cpf VARCHAR(20) DEFAULT ""',
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
        'can_cancel_sales': 'ALTER TABLE users ADD COLUMN can_cancel_sales BOOLEAN DEFAULT 0',
        'can_manage_cash_register': 'ALTER TABLE users ADD COLUMN can_manage_cash_register BOOLEAN DEFAULT 1',
        'can_view_reports': 'ALTER TABLE users ADD COLUMN can_view_reports BOOLEAN DEFAULT 1',
        'can_manage_payables': 'ALTER TABLE users ADD COLUMN can_manage_payables BOOLEAN DEFAULT 1',
        'can_manage_settings': 'ALTER TABLE users ADD COLUMN can_manage_settings BOOLEAN DEFAULT 1',
        'can_view_stock_movements': 'ALTER TABLE users ADD COLUMN can_view_stock_movements BOOLEAN DEFAULT 1',
        'can_manage_stock': 'ALTER TABLE users ADD COLUMN can_manage_stock BOOLEAN DEFAULT 1',
        'can_view_audit_logs': 'ALTER TABLE users ADD COLUMN can_view_audit_logs BOOLEAN DEFAULT 1',
    }

    for column, statement in migrations.items():
        if column not in columns:
            db.session.execute(text(statement))

    db.session.commit()


def ensure_user_email_security_columns():
    inspector = inspect(db.engine)
    if 'users' not in inspector.get_table_names():
        return

    columns = {column['name'] for column in inspector.get_columns('users')}
    migrations = {
        'email_verified': 'ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT 1',
        'email_verified_at': 'ALTER TABLE users ADD COLUMN email_verified_at DATETIME',
    }

    for column, statement in migrations.items():
        if column not in columns:
            db.session.execute(text(statement))

    db.session.execute(text('UPDATE users SET email_verified = 1 WHERE email_verified IS NULL'))
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
        text(
            'UPDATE companies SET subscription_started_at = :today '
            'WHERE subscription_started_at IS NULL AND activation_key IS NOT NULL AND activation_key != ""'
        ),
        {'today': today.isoformat()},
    )
    db.session.execute(
        text(
            'UPDATE companies SET subscription_renews_at = :renewal '
            'WHERE subscription_renews_at IS NULL AND activation_key IS NOT NULL AND activation_key != ""'
        ),
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


def ensure_company_operation_columns():
    inspector = inspect(db.engine)
    if 'companies' not in inspector.get_table_names():
        return

    columns = {column['name'] for column in inspector.get_columns('companies')}
    if 'allow_negative_stock' not in columns:
        try:
            db.session.execute(text(
                'ALTER TABLE companies ADD COLUMN allow_negative_stock BOOLEAN DEFAULT 0'
            ))
            db.session.execute(text(
                'UPDATE companies SET allow_negative_stock = 1 '
                'WHERE LOWER(REPLACE(name, " ", "")) = "adegajf"'
            ))
        except OperationalError:
            db.session.rollback()
    db.session.commit()


def ensure_company_backup_columns():
    inspector = inspect(db.engine)
    if 'companies' not in inspector.get_table_names():
        return

    columns = {column['name'] for column in inspector.get_columns('companies')}
    migrations = {
        'backup_frequency': 'ALTER TABLE companies ADD COLUMN backup_frequency VARCHAR(20) DEFAULT "manual"',
        'backup_last_at': 'ALTER TABLE companies ADD COLUMN backup_last_at DATETIME',
        'backup_last_path': 'ALTER TABLE companies ADD COLUMN backup_last_path VARCHAR(255) DEFAULT ""',
        'backup_last_status': 'ALTER TABLE companies ADD COLUMN backup_last_status VARCHAR(40) DEFAULT ""',
    }

    for column, statement in migrations.items():
        if column not in columns:
            try:
                db.session.execute(text(statement))
            except OperationalError:
                db.session.rollback()

    db.session.execute(text(
        'UPDATE companies SET backup_frequency = "manual" '
        'WHERE backup_frequency IS NULL OR backup_frequency = ""'
    ))
    db.session.commit()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    if app.config.get('TRUST_PROXY_HEADERS', False):
        trusted_proxy_count = max(1, int(app.config.get('TRUSTED_PROXY_COUNT', 1)))
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=trusted_proxy_count,
            x_proto=trusted_proxy_count,
            x_host=trusted_proxy_count,
            x_port=trusted_proxy_count,
        )
    environment = (app.config.get('ENVIRONMENT') or app.config.get('APP_ENV') or '').lower()
    if environment == 'production':
        if app.config.get('SECRET_KEY') == 'adega-jf-secret-key':
            raise RuntimeError('Defina SECRET_KEY seguro antes de rodar em produção.')
        if app.config.get('MASTER_DEFAULT_PASSWORD') == 'master123':
            raise RuntimeError('Defina MASTER_DEFAULT_PASSWORD seguro antes de rodar em produção.')
        if app.config.get('RATELIMIT_ENABLED', True) and str(
            app.config.get('RATELIMIT_STORAGE_URI', 'memory://')
        ).startswith('memory://'):
            raise RuntimeError('Configure RATELIMIT_STORAGE_URI com Redis antes de rodar em produção.')
        if app.config.get('RATELIMIT_IN_MEMORY_FALLBACK_ENABLED', False):
            raise RuntimeError('Desative RATELIMIT_IN_MEMORY_FALLBACK_ENABLED em produção.')
    setup_error_logging(app)
    ensure_mysql_database_exists(app.config['SQLALCHEMY_DATABASE_URI'])

    db.init_app(app)
    migrate.init_app(app, db, directory=str(Config.BASE_DIR / 'migrations' / 'central'))
    login_manager.init_app(app)
    limiter.init_app(app)
    init_rate_limit_errors(app)
    init_csrf(app)

    with app.app_context():
        from app.models import Company, User
        from app.routes import auth_bp, catalog_bp, main_bp
        from app.routes.api import api_v1_bp
        from app.tenant import tenant_database_identifier, tenant_engine

        app.register_blueprint(auth_bp)
        app.register_blueprint(catalog_bp)
        app.register_blueprint(api_v1_bp)
        app.register_blueprint(main_bp)

        schema_mode = 'test_create_all' if app.config.get('TESTING') else app.config.get('SCHEMA_MANAGEMENT_MODE', 'verify')
        if schema_mode == 'test_create_all':
            db.create_all()
        elif schema_mode == 'upgrade':
            from app.services.migration_service import upgrade_database
            upgrade_database(db.engine, 'central', logger=app.logger)
        elif schema_mode == 'verify':
            from app.services.migration_service import assert_database_at_head
            assert_database_at_head(db.engine, 'central')
        elif schema_mode != 'off':
            raise RuntimeError(f'SCHEMA_MANAGEMENT_MODE inválido: {schema_mode}.')

        if not User.query.filter_by(username=app.config.get('MASTER_DEFAULT_USERNAME', 'master')).first():
            company = Company.query.filter_by(name='Painel Master').order_by(Company.id.asc()).first()
            if not company:
                company = Company(name='Painel Master')
                db.session.add(company)
                db.session.flush()
            company.activation_key = 'MASTER-SYSTEM-KEY'
            company.activation_key_updated_at = datetime.now(timezone.utc)
            tenant_database_identifier(company)
            tenant_engine(company)
            master = User(username=app.config.get('MASTER_DEFAULT_USERNAME', 'master'), role='master', is_active=True)
            master.company_id = company.id
            master.set_password(app.config.get('MASTER_DEFAULT_PASSWORD', 'master123'))
            db.session.add(master)
            db.session.commit()
        else:
            users_without_company = User.query.filter(User.company_id.is_(None)).all()
            if users_without_company:
                company = Company.query.order_by(Company.id.asc()).first()
                if not company:
                    company = Company(name='Girofy')
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

    @app.get('/favicon.ico')
    def favicon():
        response = app.send_static_file('favicon-v2.png')
        response.cache_control.no_cache = True
        return response

    @app.before_request
    def mark_session_permanent():
        session.permanent = True
        return None

    @app.before_request
    def reject_cross_origin_posts():
        if request.method not in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            return None
        origin = request.headers.get('Origin')
        if origin and origin.rstrip('/') != request.host_url.rstrip('/'):
            abort(403)
        return None

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
        if not company or not company.subscription_valid:
            flash('Este recurso é apenas para assinantes.', 'warning')
            if company and (company.activation_key or '').strip():
                return redirect(url_for('auth.subscription_activation'))
            return redirect(url_for('auth.subscriptions'))
        return None

    @app.before_request
    def run_scheduled_backup():
        if not current_user.is_authenticated or not request.endpoint or request.endpoint == 'static':
            return None
        if current_user.role not in ('admin', 'master'):
            return None

        from app.backup import backup_due, create_company_backup
        from app.tenant import current_tenant_company

        company = current_tenant_company()
        if not backup_due(company):
            return None

        try:
            create_company_backup(company, reason='scheduled')
        except Exception as error:
            app.logger.error('Falha ao gerar backup agendado: %s', error, exc_info=True)
        return None

    @app.errorhandler(404)
    def not_found_error(error):
        log_http_error(app, error)
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        # Unhandled exceptions were already recorded by app.log_exception.
        if not getattr(error, 'original_exception', None):
            log_http_error(app, error)
        return render_template('errors/500.html', request_id=getattr(g, 'request_id', None)), 500

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        response.headers.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        response.headers.setdefault('Cross-Origin-Resource-Policy', 'same-origin')
        if app.config.get('SESSION_COOKIE_SECURE'):
            response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
        response.headers.setdefault('Content-Security-Policy', (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "font-src 'self' data: https://cdn.jsdelivr.net; "
            "connect-src 'self'; "
            "frame-ancestors 'self'; "
            "base-uri 'self'; "
            "form-action 'self'"
        ))
        return response

    @app.context_processor
    def inject_user():
        notifications = []
        master_company = None
        permission_authorizer_users = []
        subscription_locked = False
        from app.permissions import has_permission_view_override, needs_permission_override
        from app.services.alert_service import alert_settings_for_company, claim_email_alert_check, enqueue_configured_email_alert

        def can_view_permission(permission):
            if not current_user.is_authenticated:
                return False
            if subscription_locked and current_user.role != 'master':
                return False
            return current_user.has_permission(permission) or has_permission_view_override(permission)

        def absolute_url(path):
            base_url = (app.config.get('PUBLIC_BASE_URL') or request.host_url.rstrip('/')).rstrip('/')
            return f'{base_url}{path}'

        def mask_secret(value, visible=4):
            text_value = str(value or '')
            if not text_value:
                return 'Não gerada'
            compact = text_value.replace('-', '')
            if len(compact) <= visible:
                return '••••'
            return f'•••• {compact[-visible:]}'

        if current_user.is_authenticated:
            from app.models import Payable, Product, User
            from app.tenant import current_tenant_company, tenant_session

            company = current_tenant_company()
            subscription_locked = bool(current_user.role != 'master' and (not company or not company.subscription_valid))

            permission_authorizer_users = [
                user for user in User.query.filter(
                    User.is_active.is_(True),
                    User.role.in_(('admin', 'manager', 'master')),
                ).order_by(User.username.asc()).all()
                if user.role == 'master' or user.company_id == current_user.company_id
            ]

            if subscription_locked:
                return {
                    'current_user': current_user,
                    'app_notifications': notifications,
                    'master_company': master_company,
                    'master_company_active': False,
                    'permission_authorizer_users': permission_authorizer_users,
                    'subscription_locked': subscription_locked,
                    'can_view_permission': can_view_permission,
                    'needs_permission_override': needs_permission_override,
                    'mask_secret': mask_secret,
                    'password_min_length': int(app.config.get('PASSWORD_MIN_LENGTH') or (3 if app.config.get('TESTING') else 8)),
                }

            low_stock_products = []
            dismissed_notifications = set(session.get('dismissed_low_stock_notifications', []))
            master_company = current_tenant_company() if current_user.role == 'master' else None
            tenant_db = tenant_session()
            products = tenant_db.query(Product).options(joinedload(Product.kit_component)).filter(
                Product.company_id == company.id,
                Product.active.is_(True),
                Product.min_stock_quantity > 0,
                or_(
                    Product.is_kit.is_(True),
                    Product.stock_quantity <= Product.min_stock_quantity,
                ),
            ).order_by(Product.name.asc()).all() if tenant_db and company else []
            should_check_email_alerts = bool(
                company and (
                    app.config.get('TESTING')
                    or claim_email_alert_check(company.id)
                )
            )
            email_alert_settings = alert_settings_for_company(company) if should_check_email_alerts else None
            for product in products:
                stock_quantity = product.effective_stock_quantity or 0
                min_stock_quantity = product.min_stock_quantity or 0
                alert_type = 'product_out_of_stock' if stock_quantity <= 0 else 'product_low_stock'
                notification_key = f'{alert_type}:{product.id}:{stock_quantity}:{min_stock_quantity}'
                if min_stock_quantity > 0 and stock_quantity <= min_stock_quantity and notification_key not in dismissed_notifications:
                    low_stock_products.append((stock_quantity, min_stock_quantity, notification_key, product))

            low_stock_products.sort(key=lambda item: (item[0], item[3].name.lower()))
            for stock_quantity, min_stock_quantity, notification_key, product in low_stock_products[:10]:
                if stock_quantity <= 0:
                    title = 'Produto esgotado'
                    message = f'{product.name} está sem estoque. Mínimo: {min_stock_quantity} un.'
                else:
                    title = 'Estoque baixo'
                    message = f'{product.name} está com {stock_quantity} un. Mínimo: {min_stock_quantity} un.'

                alert_type = 'product_out_of_stock' if stock_quantity <= 0 else 'product_low_stock'
                product_url = url_for('catalog.products')
                if should_check_email_alerts:
                    enqueue_configured_email_alert(
                        company,
                        alert_type,
                        notification_key,
                        title,
                        message,
                        absolute_url(product_url),
                        settings=email_alert_settings,
                    )
                notifications.append({
                    'title': title,
                    'message': message,
                    'url': url_for('catalog.dismiss_low_stock_notification', product_id=product.id),
                    'method': 'post',
                    'key': notification_key,
                })

            today = business_today()
            alert_limit = today + timedelta(days=3)
            payables = tenant_db.query(Payable).filter(
                Payable.company_id == company.id,
                Payable.paid.is_(False),
                Payable.due_date <= alert_limit,
            ).order_by(Payable.due_date.asc(), Payable.description.asc()).all() if tenant_db and company else []

            for payable in payables[:10]:
                amount = format_brl(payable.amount or 0)
                if payable.due_date < today:
                    days = (today - payable.due_date).days
                    title = 'Conta vencida'
                    alert_type = 'payable_overdue'
                    message = f'{payable.description} venceu há {days} dia{"s" if days != 1 else ""}. Valor: {amount}.'
                elif payable.due_date == today:
                    title = 'Conta vence hoje'
                    alert_type = 'payable_due_today'
                    message = f'{payable.description} vence hoje. Valor: {amount}.'
                else:
                    days = (payable.due_date - today).days
                    title = 'Conta próxima do vencimento'
                    alert_type = ''
                    message = f'{payable.description} vence em {days} dia{"s" if days != 1 else ""}. Valor: {amount}.'

                if alert_type and should_check_email_alerts:
                    alert_key = f'{alert_type}:{payable.id}:{payable.due_date}'
                    enqueue_configured_email_alert(
                        company,
                        alert_type,
                        alert_key,
                        title,
                        message,
                        absolute_url(url_for('main.payables')),
                        settings=email_alert_settings,
                    )

                if can_view_permission('can_manage_payables'):
                    notifications.append({
                        'title': title,
                        'message': message,
                        'url': url_for('main.payables'),
                        'key': f'payable:{payable.id}:{payable.due_date}',
                    })

            if company and company.subscription_renews_at:
                days_left = (company.subscription_renews_at - today).days
                if 0 <= days_left <= 3:
                    title = 'Assinatura perto do vencimento'
                    message = f'A assinatura da adega {company.name} vence em {days_left} dia{"s" if days_left != 1 else ""}.'
                    if should_check_email_alerts:
                        enqueue_configured_email_alert(
                            company,
                            'subscription_expiring',
                            f'subscription_expiring:{company.id}:{company.subscription_renews_at}:{days_left}',
                            title,
                            message,
                            absolute_url(url_for('auth.subscriptions')),
                            settings=email_alert_settings,
                        )
                    if can_view_permission('can_view_finance'):
                        notifications.append({
                            'title': title,
                            'message': message,
                            'url': url_for('auth.subscriptions'),
                            'key': f'subscription:{company.id}:{company.subscription_renews_at}:{days_left}',
                        })

        return {
            'current_user': current_user,
            'app_notifications': notifications,
            'master_company': master_company,
            'master_company_active': bool(current_user.is_authenticated and current_user.role == 'master' and master_company and master_company.id != current_user.company_id),
            'permission_authorizer_users': permission_authorizer_users,
            'subscription_locked': subscription_locked,
            'can_view_permission': can_view_permission,
            'needs_permission_override': needs_permission_override,
            'mask_secret': mask_secret,
            'password_min_length': int(app.config.get('PASSWORD_MIN_LENGTH') or (3 if app.config.get('TESTING') else 8)),
        }

    from app.tenant import close_tenant_session
    app.teardown_request(close_tenant_session)

    return app
