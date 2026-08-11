from flask_login import LoginManager
from flask_limiter import Limiter
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from app.security.rate_limit import default_rate_limit_key


db = SQLAlchemy()
login_manager = LoginManager()
limiter = Limiter(key_func=default_rate_limit_key)
migrate = Migrate(compare_type=True, render_as_batch=False)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Faça login para acessar esta página.'
login_manager.login_message_category = 'warning'
