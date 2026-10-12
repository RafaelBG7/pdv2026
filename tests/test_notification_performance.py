import unittest
from time import perf_counter
from datetime import timedelta

from flask import Flask
from sqlalchemy import event

from app.extensions import db
from app.models import Company, Notification, Product, Payable
from app.services.notification_service import sync_operational_notifications
from app.time_utils import business_today


class NotificationPerformanceTestCase(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
        db.init_app(self.app)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        company = Company(name='Performance')
        db.session.add(company)
        db.session.flush()
        self.company_id = company.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()

    def test_repeated_poll_has_bounded_queries_with_one_thousand_products(self):
        db.session.add_all([
            Product(company_id=self.company_id, name=f'Product {index}',
                    sale_price=10, stock_quantity=0 if index % 2 else 20,
                    min_stock_quantity=2, active=True)
            for index in range(1000)
        ])
        db.session.commit()
        sync_operational_notifications(db.session, self.company_id)
        db.session.commit()
        statements = []
        def record(connection, cursor, statement, parameters, context, executemany):
            statements.append(statement)
        event.listen(db.engine, 'before_cursor_execute', record)
        started = perf_counter()
        try:
            sync_operational_notifications(db.session, self.company_id)
            db.session.commit()
        finally:
            event.remove(db.engine, 'before_cursor_execute', record)
        print(f'Notification poll: {len(statements)} statements, {perf_counter() - started:.3f}s')
        self.assertEqual(Notification.query.count(), 500)
        self.assertLessEqual(len(statements), 5)

    def test_stock_kit_and_payable_transitions_preserve_read_state_and_tenant_isolation(self):
        base = Product(company_id=self.company_id, name='Base', sale_price=10,
                       stock_quantity=4, min_stock_quantity=1, active=True)
        kit = Product(company_id=self.company_id, name='Kit', sale_price=20,
                      is_kit=True, kit_component=base, kit_component_quantity=2,
                      min_stock_quantity=3, active=True)
        payable = Payable(company_id=self.company_id, description='Bill', amount=10,
                          due_date=business_today(), paid=False)
        other = Company(name='Other tenant')
        db.session.add_all([base, kit, payable, other])
        db.session.flush()
        other_product = Product(company_id=other.id, name='Other product', sale_price=10,
                                stock_quantity=0, min_stock_quantity=1, active=True)
        db.session.add(other_product)
        db.session.commit()
        sync_operational_notifications(db.session, other.id)
        sync_operational_notifications(db.session, self.company_id)
        db.session.commit()
        low = Notification.query.filter_by(company_id=self.company_id, notification_type='product_low_stock').one()
        self.assertEqual(low.entity_id, kit.id)
        low.is_read = True
        db.session.commit()
        sync_operational_notifications(db.session, self.company_id)
        self.assertTrue(low.is_read)
        base.stock_quantity = 0
        payable.paid = True
        db.session.commit()
        sync_operational_notifications(db.session, self.company_id)
        self.assertTrue(low.is_resolved)
        self.assertTrue(Notification.query.filter_by(company_id=self.company_id, entity_type='payable').one().is_resolved)
        self.assertFalse(Notification.query.filter_by(company_id=other.id).one().is_resolved)
        base.stock_quantity = 4
        payable.paid = False
        payable.due_date = business_today() - timedelta(days=1)
        db.session.commit()
        sync_operational_notifications(db.session, self.company_id)
        self.assertFalse(low.is_resolved)
        self.assertFalse(low.is_read)
        self.assertEqual(Notification.query.filter_by(company_id=self.company_id, entity_id=kit.id,
                                                     entity_type='product', is_resolved=False).count(), 1)
        self.assertEqual(Notification.query.filter_by(company_id=self.company_id, entity_type='payable',
                                                     notification_type='payable_overdue', is_resolved=False).count(), 1)
