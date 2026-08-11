import os
import sys
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote_plus


def runtime_base_dir():
    if os.environ.get('APP_BASE_DIR'):
        return Path(os.environ['APP_BASE_DIR']).expanduser().resolve()

    if getattr(sys, 'frozen', False):
        executable_path = Path(sys.executable).resolve()
        candidates = [Path.cwd(), executable_path.parent, *executable_path.parents]
        for candidate in candidates:
            if (candidate / '.env').exists():
                return candidate
        return executable_path.parent

    return Path(__file__).resolve().parent


BASE_DIR = runtime_base_dir()


def load_env_file(path):
    if not path.exists():
        return

    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


load_env_file(BASE_DIR / '.env')


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def mysql_database_url(database=None):
    user = os.environ.get('MYSQL_USER', 'root')
    password = os.environ.get('MYSQL_PASSWORD', '')
    host = os.environ.get('MYSQL_HOST', '127.0.0.1')
    port = os.environ.get('MYSQL_PORT', '3306')
    db_name = database or os.environ.get('MYSQL_DATABASE', 'adega_central')
    auth = quote_plus(user)
    if password:
        auth = f'{auth}:{quote_plus(password)}'
    return f'mysql+pymysql://{auth}@{host}:{port}/{db_name}?charset=utf8mb4'


class Config:
    BASE_DIR = BASE_DIR
    LOG_DIR = BASE_DIR / 'logs'
    LOG_DIR.mkdir(exist_ok=True)
    BACKUP_DIR = BASE_DIR / 'backups'
    BACKUP_DIR.mkdir(exist_ok=True)

    ENVIRONMENT = os.environ.get('APP_ENV', os.environ.get('FLASK_ENV', 'development')).lower()
    TESTING = env_bool('TESTING', False)
    DEBUG = env_bool('FLASK_DEBUG', ENVIRONMENT == 'development')
    SECRET_KEY = os.environ.get('SECRET_KEY', 'adega-jf-secret-key')
    API_TOKEN_SECRET = os.environ.get('API_TOKEN_SECRET', SECRET_KEY)
    API_ACCESS_TOKEN_MINUTES = int(os.environ.get('API_ACCESS_TOKEN_MINUTES', '15'))
    API_REFRESH_TOKEN_DAYS = int(os.environ.get('API_REFRESH_TOKEN_DAYS', '30'))
    API_LOGIN_ATTEMPT_LIMIT = int(os.environ.get('API_LOGIN_ATTEMPT_LIMIT', '5'))
    API_LOGIN_BLOCK_SECONDS = int(os.environ.get('API_LOGIN_BLOCK_SECONDS', str(15 * 60)))
    API_ALLOW_INSECURE_AUTH = env_bool(
        'API_ALLOW_INSECURE_AUTH',
        TESTING or ENVIRONMENT == 'development',
    )
    TRUST_PROXY_HEADERS = env_bool('TRUST_PROXY_HEADERS', False)
    TRUSTED_PROXY_COUNT = int(os.environ.get('TRUSTED_PROXY_COUNT', '1'))
    RATELIMIT_ENABLED = env_bool('RATELIMIT_ENABLED', True)
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')
    RATELIMIT_HEADERS_ENABLED = True
    RATELIMIT_SWALLOW_ERRORS = False
    RATELIMIT_IN_MEMORY_FALLBACK_ENABLED = env_bool(
        'RATELIMIT_IN_MEMORY_FALLBACK_ENABLED',
        ENVIRONMENT != 'production',
    )
    RATELIMIT_KEY_PREFIX = os.environ.get('RATELIMIT_KEY_PREFIX', 'girofy')
    RATELIMIT_LOGIN = os.environ.get('RATELIMIT_LOGIN', '5 per minute;20 per hour')
    RATELIMIT_PASSWORD_RESET = os.environ.get('RATELIMIT_PASSWORD_RESET', '3 per 15 minutes')
    RATELIMIT_EMAIL_RESEND = os.environ.get('RATELIMIT_EMAIL_RESEND', '3 per 15 minutes')
    RATELIMIT_REGISTRATION = os.environ.get('RATELIMIT_REGISTRATION', '3 per hour')
    RATELIMIT_ACTIVATION = os.environ.get('RATELIMIT_ACTIVATION', '5 per 15 minutes')
    RATELIMIT_REFRESH = os.environ.get('RATELIMIT_REFRESH', '120 per hour')
    RATELIMIT_API_GENERAL = os.environ.get('RATELIMIT_API_GENERAL', '600 per minute')
    RATELIMIT_IMPORT = os.environ.get('RATELIMIT_IMPORT', '5 per hour')
    RATELIMIT_BACKUP = os.environ.get('RATELIMIT_BACKUP', '3 per hour')
    RATELIMIT_EXPORT = os.environ.get('RATELIMIT_EXPORT', '20 per hour')
    RATELIMIT_ADMIN = os.environ.get('RATELIMIT_ADMIN', '30 per hour')
    MASTER_DEFAULT_USERNAME = os.environ.get('MASTER_DEFAULT_USERNAME', 'master')
    MASTER_DEFAULT_PASSWORD = os.environ.get('MASTER_DEFAULT_PASSWORD', 'master123')
    PASSWORD_MIN_LENGTH = int(os.environ.get('PASSWORD_MIN_LENGTH', '8'))
    PASSWORD_MAX_LENGTH = int(os.environ.get('PASSWORD_MAX_LENGTH', '128'))
    CSRF_ENABLED = env_bool('CSRF_ENABLED', not TESTING)
    WTF_CSRF_ENABLED = CSRF_ENABLED
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', str(8 * 1024 * 1024)))
    PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL', '')
    MAIL_SMTP_SERVER = os.environ.get('MAIL_SMTP_SERVER', os.environ.get('GMAIL_SMTP_SERVER', os.environ.get('BREVO_SMTP_SERVER', 'smtp.gmail.com')))
    MAIL_SMTP_PORT = int(os.environ.get('MAIL_SMTP_PORT', os.environ.get('GMAIL_SMTP_PORT', os.environ.get('BREVO_SMTP_PORT', '587'))))
    MAIL_SMTP_LOGIN = os.environ.get('MAIL_SMTP_LOGIN', os.environ.get('GMAIL_SMTP_LOGIN', os.environ.get('BREVO_SMTP_LOGIN', '')))
    MAIL_SMTP_PASSWORD = os.environ.get('MAIL_SMTP_PASSWORD', os.environ.get('GMAIL_APP_PASSWORD', os.environ.get('BREVO_SMTP_PASSWORD', '')))
    MAIL_FROM_EMAIL = os.environ.get('MAIL_FROM_EMAIL', os.environ.get('BREVO_FROM_EMAIL', MAIL_SMTP_LOGIN))
    MAIL_FROM_NAME = os.environ.get('MAIL_FROM_NAME', os.environ.get('BREVO_FROM_NAME', 'Girofy'))
    MAIL_SUPPRESS_SEND = env_bool('MAIL_SUPPRESS_SEND', TESTING)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=int(os.environ.get('SESSION_LIFETIME_HOURS', '8')))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax')
    SESSION_COOKIE_SECURE = env_bool('SESSION_COOKIE_SECURE', ENVIRONMENT == 'production')
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = SESSION_COOKIE_SAMESITE
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    PREFERRED_URL_SCHEME = 'https' if SESSION_COOKIE_SECURE else 'http'
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        mysql_database_url(),
    )
    MYSQL_TENANT_DATABASE_PREFIX = os.environ.get('MYSQL_TENANT_DATABASE_PREFIX', 'adega')
    MYSQL_TENANT_DATABASE_URL_TEMPLATE = os.environ.get('MYSQL_TENANT_DATABASE_URL_TEMPLATE', '')
    MYSQL_SERVER_DATABASE_URL = os.environ.get('MYSQL_SERVER_DATABASE_URL', mysql_database_url('mysql'))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SCHEMA_MANAGEMENT_MODE = os.environ.get(
        'SCHEMA_MANAGEMENT_MODE',
        'test_create_all' if TESTING else ('verify' if ENVIRONMENT == 'production' else 'upgrade'),
    ).lower()

    if ENVIRONMENT == 'production' and SECRET_KEY == 'adega-jf-secret-key':
        raise RuntimeError('Defina SECRET_KEY seguro antes de rodar em produção.')
    if ENVIRONMENT == 'production' and MASTER_DEFAULT_PASSWORD == 'master123':
        raise RuntimeError('Defina MASTER_DEFAULT_PASSWORD seguro antes de rodar em produção.')
    if ENVIRONMENT == 'production' and RATELIMIT_ENABLED and RATELIMIT_STORAGE_URI.startswith('memory://'):
        raise RuntimeError('Configure RATELIMIT_STORAGE_URI com Redis antes de rodar em produção.')
    if ENVIRONMENT == 'production' and RATELIMIT_IN_MEMORY_FALLBACK_ENABLED:
        raise RuntimeError('Desative RATELIMIT_IN_MEMORY_FALLBACK_ENABLED em produção.')
