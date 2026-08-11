import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from alembic import command
from sqlalchemy import create_engine, inspect, text

from app.extensions import db
from app.services.migration_service import MigrationError, assert_database_at_head, database_revision, migration_head, upgrade_database
from app.services.migration_service import migration_config
import app.models  # noqa: F401


class VersionedMigrationTestCase(unittest.TestCase):
    def engine(self, directory, name):
        return create_engine(f'sqlite:///{Path(directory) / name}')

    def test_empty_central_and_tenant_reach_independent_heads(self):
        with tempfile.TemporaryDirectory() as directory:
            central = self.engine(directory, 'central.db')
            tenant = self.engine(directory, 'tenant.db')
            self.assertEqual(upgrade_database(central, 'central').current_revision, 'central_0002')
            self.assertEqual(upgrade_database(tenant, 'tenant').current_revision, 'tenant_0002')
            self.assertEqual(assert_database_at_head(central, 'central'), migration_head('central'))
            self.assertEqual(assert_database_at_head(tenant, 'tenant'), migration_head('tenant'))
            self.assertIn('sales', inspect(tenant).get_table_names())
            central.dispose()
            tenant.dispose()

    def test_upgrade_is_idempotent_and_preserves_existing_data(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = self.engine(directory, 'legacy.db')
            db.Model.metadata.create_all(engine)
            with engine.begin() as connection:
                connection.execute(text("INSERT INTO companies (id, name, database_path) VALUES (7, 'Cliente', 'tenant_7')"))
            first = upgrade_database(engine, 'central')
            second = upgrade_database(engine, 'central')
            with engine.connect() as connection:
                name = connection.execute(text('SELECT name FROM companies WHERE id = 7')).scalar_one()
            self.assertTrue(first.baseline_applied)
            self.assertFalse(second.baseline_applied)
            self.assertEqual(name, 'Cliente')
            self.assertEqual(database_revision(engine), 'central_0002')
            engine.dispose()

    def test_incompatible_legacy_database_fails_without_stamp(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = self.engine(directory, 'invalid.db')
            with engine.begin() as connection:
                connection.execute(text('CREATE TABLE unrelated (id INTEGER PRIMARY KEY)'))
            with self.assertRaises(MigrationError):
                upgrade_database(engine, 'central')
            self.assertNotIn('alembic_version', inspect(engine).get_table_names())
            engine.dispose()

    def test_multiple_tenants_are_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            engines = [self.engine(directory, f'tenant_{number}.db') for number in range(3)]
            for number, engine in enumerate(engines):
                upgrade_database(engine, 'tenant')
                with engine.begin() as connection:
                    connection.execute(text('INSERT INTO companies (id, name) VALUES (:id, :name)'), {'id': number + 1, 'name': f'Tenant {number}'})
            for number, engine in enumerate(engines):
                with engine.connect() as connection:
                    names = connection.execute(text('SELECT name FROM companies')).scalars().all()
                self.assertEqual(names, [f'Tenant {number}'])
                engine.dispose()

    def test_database_one_revision_behind_is_detected_and_upgraded(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = self.engine(directory, 'outdated.db')
            with engine.connect() as connection:
                command.upgrade(migration_config('central', connection), 'central_0001')
                connection.commit()
            with self.assertRaises(MigrationError):
                assert_database_at_head(engine, 'central')
            self.assertEqual(upgrade_database(engine, 'central').current_revision, 'central_0002')
            engine.dispose()

    def test_migration_failure_is_not_swallowed(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = self.engine(directory, 'failure.db')
            with patch('app.services.migration_service.command.upgrade', side_effect=RuntimeError('falha simulada')):
                with self.assertRaisesRegex(MigrationError, 'falha simulada'):
                    upgrade_database(engine, 'tenant')
            self.assertIsNone(database_revision(engine))
            engine.dispose()


if __name__ == '__main__':
    unittest.main()
