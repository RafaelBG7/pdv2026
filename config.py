import os
from pathlib import Path


class Config:
    BASE_DIR = Path(__file__).resolve().parent
    DATABASE_DIR = BASE_DIR / 'database'
    DATABASE_DIR.mkdir(exist_ok=True)

    SECRET_KEY = os.environ.get('SECRET_KEY', 'adega-jf-secret-key')
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATABASE_DIR / 'adega_jf.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = True
