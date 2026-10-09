import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask
from sqlalchemy import text

from app import tenant


class TenantConnectionTestCase(unittest.TestCase):
    def test_cached_tenant_engine_replaces_disconnected_idle_connection(self):
        app = Flask(__name__)
        app.config.update(TESTING=False, SCHEMA_MANAGEMENT_MODE='off')
        company = SimpleNamespace(id=999, database_path='connection_regression', is_system=False)
        with (
            tempfile.TemporaryDirectory() as directory,
            app.app_context(),
            patch.dict(tenant._engines, {}, clear=True),
            patch('app.tenant.create_mysql_database_if_needed'),
            patch('app.tenant.mysql_tenant_url', return_value=f'sqlite:///{Path(directory) / "tenant.db"}'),
            patch('app.tenant.inspect') as inspector,
            patch('app.tenant.ensure_tenant_reference_data'),
        ):
            inspector.return_value.get_table_names.return_value = ['users']
            engine = tenant.tenant_engine(company)
            try:
                with engine.begin() as connection:
                    connection.execute(text('CREATE TABLE probe (value INTEGER)'))
                    connection.execute(text('INSERT INTO probe VALUES (42)'))
                    idle_connection = connection.connection.driver_connection

                # Simulate the server closing a connection after it was returned
                # to the pool, as happens between a logout and a later login.
                idle_connection.close()
                self.assertIs(tenant.tenant_engine(company), engine)
                with engine.connect() as connection:
                    self.assertEqual(connection.execute(text('SELECT value FROM probe')).scalar_one(), 42)
                    self.assertIsNot(connection.connection.driver_connection, idle_connection)
            finally:
                engine.dispose()
