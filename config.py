import os
from pathlib import Path
from urllib.parse import quote_plus


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
    BASE_DIR = Path(__file__).resolve().parent
    LOG_DIR = BASE_DIR / 'logs'
    LOG_DIR.mkdir(exist_ok=True)

    SECRET_KEY = os.environ.get('SECRET_KEY', 'adega-jf-secret-key')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        mysql_database_url(),
    )
    MYSQL_TENANT_DATABASE_PREFIX = os.environ.get('MYSQL_TENANT_DATABASE_PREFIX', 'adega')
    MYSQL_TENANT_DATABASE_URL_TEMPLATE = os.environ.get('MYSQL_TENANT_DATABASE_URL_TEMPLATE', '')
    MYSQL_SERVER_DATABASE_URL = os.environ.get('MYSQL_SERVER_DATABASE_URL', mysql_database_url('mysql'))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = True
