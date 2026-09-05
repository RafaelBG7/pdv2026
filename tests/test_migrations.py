import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from alembic import command
from decimal import Decimal

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
            self.assertEqual(upgrade_database(central, 'central').current_revision, 'central_0010')
            self.assertEqual(upgrade_database(tenant, 'tenant').current_revision, 'tenant_0010')
            self.assertEqual(assert_database_at_head(central, 'central'), migration_head('central'))
            self.assertEqual(assert_database_at_head(tenant, 'tenant'), migration_head('tenant'))
            self.assertIn('sales', inspect(tenant).get_table_names())
            central.dispose()
            tenant.dispose()

    def test_payable_decimal_migration_preserves_and_quantizes_legacy_amount(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = self.engine(directory, 'payables-legacy.db')
            with engine.connect() as connection:
                command.upgrade(migration_config('tenant', connection), 'tenant_0003')
                connection.execute(text("INSERT INTO companies (id, name) VALUES (7, 'Tenant')"))
                connection.execute(text(
                    "INSERT INTO payables "
                    "(id, company_id, description, amount, due_date, paid) "
                    "VALUES (3, 7, 'Energia', 2480.349, '2026-08-30', 0)",
                ))
                connection.commit()

            self.assertEqual(upgrade_database(engine, 'tenant').current_revision, 'tenant_0010')
            columns = {column['name']: column for column in inspect(engine).get_columns('payables')}
            with engine.connect() as connection:
                amount = connection.execute(text('SELECT amount FROM payables WHERE id = 3')).scalar_one()

            self.assertEqual(Decimal(str(amount)), Decimal('2480.35'))
            self.assertFalse(columns['amount']['nullable'])
            self.assertEqual(columns['amount']['type'].precision, 18)
            self.assertEqual(columns['amount']['type'].scale, 2)
            engine.dispose()

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
            self.assertEqual(database_revision(engine), 'central_0010')
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
            self.assertEqual(upgrade_database(engine, 'central').current_revision, 'central_0010')
            engine.dispose()

    def test_system_company_is_detached_from_tenant_database(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = self.engine(directory, 'system-context.db')
            with engine.connect() as connection:
                command.upgrade(migration_config('central', connection), 'central_0007')
                connection.execute(text(
                    "INSERT INTO companies (id, name, database_path, is_system, activation_key) VALUES "
                    "(1, 'Painel Master', 'adega_1_painel_master', 1, 'MASTER-SYSTEM-KEY'), "
                    "(29, 'Adega Real', 'adega_29_adega_real', 0, '')"
                ))
                connection.commit()

            self.assertEqual(upgrade_database(engine, 'central').current_revision, 'central_0010')
            with engine.connect() as connection:
                paths = dict(connection.execute(text(
                    'SELECT id, database_path FROM companies ORDER BY id'
                )).all())

            self.assertEqual(paths[1], '')
            self.assertEqual(paths[29], 'adega_29_adega_real')
            engine.dispose()

    def test_legacy_subscription_plan_names_are_standardized(self):
        cases = (
            ('central', 'central_0006'),
            ('tenant', 'tenant_0007'),
        )
        for database_kind, previous_revision in cases:
            with self.subTest(database_kind=database_kind), tempfile.TemporaryDirectory() as directory:
                engine = self.engine(directory, f'{database_kind}-legacy-plans.db')
                with engine.connect() as connection:
                    command.upgrade(migration_config(database_kind, connection), previous_revision)
                    connection.execute(text(
                        "INSERT INTO companies (id, name, subscription_plan) VALUES "
                        "(1, 'Essencial', 'Essencial'), "
                        "(2, 'Profissional', 'Profissional'), "
                        "(3, 'Premium', 'Premium')"
                    ))
                    connection.execute(text(
                        "INSERT INTO activation_keys (key, plan, renews_at, created_at) VALUES "
                        "('KEY-BASIC', 'Essencial', '2027-08-28', '2026-08-28'), "
                        "('KEY-ULTIMATE', 'Premium', '2027-08-28', '2026-08-28')"
                    ))
                    connection.commit()

                upgrade_database(engine, database_kind)
                with engine.connect() as connection:
                    company_plans = connection.execute(text(
                        'SELECT subscription_plan FROM companies ORDER BY id'
                    )).scalars().all()
                    key_plans = connection.execute(text(
                        'SELECT plan FROM activation_keys ORDER BY key'
                    )).scalars().all()

                self.assertEqual(company_plans, ['Basic', 'Ultimate', 'Ultimate'])
                self.assertEqual(key_plans, ['Basic', 'Ultimate'])
                engine.dispose()

    def test_financial_decimal_migration_rounds_legacy_values_for_central_and_tenant(self):
        cases = (
            ('central', 'central_0008'),
            ('tenant', 'tenant_0008'),
        )
        for database_kind, previous_revision in cases:
            with self.subTest(database_kind=database_kind), tempfile.TemporaryDirectory() as directory:
                engine = self.engine(directory, f'{database_kind}-legacy-money.db')
                with engine.connect() as connection:
                    command.upgrade(migration_config(database_kind, connection), previous_revision)
                    connection.execute(text(
                        "INSERT INTO companies "
                        "(id, name, pix_fee_percent, debit_fee_percent, credit_fee_percent) "
                        "VALUES (7, 'Tenant', 2.34567, 1.23454, NULL)"
                    ))
                    connection.execute(text(
                        "INSERT INTO products (id, company_id, name, cost_price, sale_price) "
                        "VALUES (11, 7, 'Produto', 10.125, 7898630000000.004)"
                    ))
                    connection.execute(text(
                        "INSERT INTO cash_registers (id, company_id, opening_amount, closing_amount) "
                        "VALUES (13, 7, 0.30000000000000004, NULL)"
                    ))
                    connection.execute(text(
                        "INSERT INTO sales "
                        "(id, company_id, cash_register_id, total_amount, discount_amount, final_amount, status) "
                        "VALUES (17, 7, 13, 19.899999999, 0.105, 19.794999999, 'completed')"
                    ))
                    connection.execute(text(
                        "INSERT INTO sale_items "
                        "(id, sale_id, product_id, quantity, unit_price, unit_cost_price, total_price, profit_amount) "
                        "VALUES (19, 17, 11, 1, 19.899999999, 10.125, 19.899999999, 9.775)"
                    ))
                    connection.execute(text(
                        "INSERT INTO payments (id, sale_id, method, amount) "
                        "VALUES (23, 17, 'money', 19.899999999)"
                    ))
                    connection.commit()

                result = upgrade_database(engine, database_kind)
                self.assertEqual(result.current_revision, f'{database_kind}_0010')
                with engine.connect() as connection:
                    company = connection.execute(text(
                        'SELECT pix_fee_percent, debit_fee_percent, credit_fee_percent '
                        'FROM companies WHERE id = 7'
                    )).one()
                    product = connection.execute(text(
                        'SELECT cost_price, sale_price FROM products WHERE id = 11'
                    )).one()
                    cash = connection.execute(text(
                        'SELECT opening_amount, closing_amount FROM cash_registers WHERE id = 13'
                    )).one()
                    sale = connection.execute(text(
                        'SELECT total_amount, discount_amount, final_amount FROM sales WHERE id = 17'
                    )).one()
                    item = connection.execute(text(
                        'SELECT unit_price, unit_cost_price, total_price, profit_amount '
                        'FROM sale_items WHERE id = 19'
                    )).one()
                    payment = connection.execute(text(
                        'SELECT amount FROM payments WHERE id = 23'
                    )).scalar_one()

                decimal_row = lambda row, quantum: tuple(
                    Decimal(str(value)).quantize(quantum) for value in row
                )
                self.assertEqual(decimal_row(company, Decimal('0.0001')), (
                    Decimal('2.3457'), Decimal('1.2345'), Decimal('0.0000'),
                ))
                self.assertEqual(decimal_row(product, Decimal('0.01')), (Decimal('10.13'), Decimal('7898630000000.00')))
                self.assertEqual(decimal_row(cash, Decimal('0.01')), (Decimal('0.30'), Decimal('0.00')))
                self.assertEqual(decimal_row(sale, Decimal('0.01')), (
                    Decimal('19.90'), Decimal('0.11'), Decimal('19.79'),
                ))
                self.assertEqual(decimal_row(item, Decimal('0.01')), (
                    Decimal('19.90'), Decimal('10.13'), Decimal('19.90'), Decimal('9.78'),
                ))
                self.assertEqual(Decimal(str(payment)), Decimal('19.90'))

                columns = {
                    (table, column['name']): column
                    for table in (
                        'companies', 'products', 'cash_registers', 'sales', 'sale_items',
                        'payments', 'payables', 'stock_movements',
                    )
                    for column in inspect(engine).get_columns(table)
                }
                for table, names in {
                    'products': ('cost_price', 'sale_price'),
                    'cash_registers': ('opening_amount', 'closing_amount'),
                    'sales': ('total_amount', 'discount_amount', 'final_amount'),
                    'sale_items': ('unit_price', 'unit_cost_price', 'total_price', 'profit_amount'),
                    'payments': ('amount',),
                    'payables': ('amount',),
                    'stock_movements': ('unit_cost', 'total_cost'),
                }.items():
                    for name in names:
                        column = columns[(table, name)]
                        self.assertEqual((column['type'].precision, column['type'].scale), (18, 2))
                        self.assertFalse(column['nullable'])
                for name in ('pix_fee_percent', 'debit_fee_percent', 'credit_fee_percent'):
                    column = columns[('companies', name)]
                    self.assertEqual((column['type'].precision, column['type'].scale), (8, 4))
                    self.assertFalse(column['nullable'])
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
