from flask import Flask, render_template, session, url_for
from flask_login import current_user
from sqlalchemy import inspect, text

from app.extensions import db, login_manager
from config import Config


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


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)

    with app.app_context():
        from app.models import User
        from app.routes import auth_bp, catalog_bp, main_bp

        app.register_blueprint(auth_bp)
        app.register_blueprint(catalog_bp)
        app.register_blueprint(main_bp)

        db.create_all()
        ensure_product_kit_columns()
        ensure_product_stock_columns()
        ensure_sale_discount_columns()
        ensure_sale_item_profit_columns()
        ensure_user_profile_columns()

        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', role='admin', is_active=True)
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()

    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return db.session.get(User, int(user_id))

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.context_processor
    def inject_user():
        notifications = []

        if current_user.is_authenticated:
            from app.models import Product

            low_stock_products = []
            dismissed_notifications = set(session.get('dismissed_low_stock_notifications', []))
            products = Product.query.filter_by(active=True).order_by(Product.name.asc()).all()
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

        return {'current_user': current_user, 'app_notifications': notifications}

    return app
