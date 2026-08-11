from logging.config import fileConfig
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.extensions import db
import app.models  # noqa: F401
from config import Config as AppConfig


config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = db.Model.metadata


def database_url():
    return os.environ.get('MIGRATION_DATABASE_URL') or AppConfig.SQLALCHEMY_DATABASE_URI


def run_migrations_offline():
    context.configure(
        url=database_url(), target_metadata=target_metadata,
        literal_binds=True, dialect_opts={'paramstyle': 'named'}, compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    supplied_connection = config.attributes.get('connection')
    if supplied_connection is not None:
        context.configure(connection=supplied_connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    section = config.get_section(config.config_ini_section) or {}
    section['sqlalchemy.url'] = database_url()
    connectable = engine_from_config(section, prefix='sqlalchemy.', poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_offline() if context.is_offline_mode() else run_migrations_online()
