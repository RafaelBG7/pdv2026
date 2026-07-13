from datetime import date, datetime, timedelta
import io
from pathlib import Path
import re
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from flask import g

from app import create_app
from app.extensions import db
from app.models import ActivationKey, AuditLog, CashRegister, Category, Company, EmailAlertDelivery, EmailAlertSetting, EmailChangeRequest, EmailVerificationCode, PasswordResetToken, Payable, Payment, Product, Sale, SaleItem, StockMovement, User
from app.services.audit_service import changed_values, record_audit_event
from sqlalchemy.exc import SQLAlchemyError
from app import tenant as tenant_module
from app.services import alert_service


class TestConfig:
    TESTING = True
    SECRET_KEY = 'test-secret-key'
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    MAIL_SUPPRESS_SEND = True
    PUBLIC_BASE_URL = 'http://localhost'


class RouteTestCase(unittest.TestCase):
    STRONG_PASSWORD = 'SenhaForte123'

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        TestConfig.LOG_DIR = Path(self.temp_dir.name) / 'logs'
        TestConfig.BACKUP_DIR = Path(self.temp_dir.name) / 'backups'
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        self.temp_dir.cleanup()

    def login(self, username='master', password='master123', follow_redirects=False):
        return self.client.post(
            '/login',
            data={'username': username, 'password': password},
            follow_redirects=follow_redirects,
        )

    def open_cash_register(self, amount='100,00'):
        return self.client.post('/caixa/abrir', data={'opening_amount': amount}, follow_redirects=True)

    def master_company_id(self):
        return User.query.filter_by(username='master').one().company_id

    def test_login_page_loads(self):
        response = self.client.get('/login')

        self.assertEqual(response.status_code, 200)
        self.assertIn('Girofy'.encode(), response.data)
        self.assertNotIn('Gestão que faz girar o seu negócio'.encode(), response.data)
        self.assertNotIn('Sistema PDV Local'.encode(), response.data)
        self.assertIn('Entrar'.encode(), response.data)
        self.assertIn('Lembre de mim'.encode(), response.data)
        self.assertIn('name="remember_me"'.encode(), response.data)
        self.assertIn('Cadastrar'.encode(), response.data)
        self.assertNotIn('Key de ativação'.encode(), response.data)
        self.assertNotIn('Não tenho key'.encode(), response.data)

    def test_login_remember_me_sets_persistent_cookie(self):
        response = self.client.post(
            '/login',
            data={'username': 'master', 'password': 'master123', 'remember_me': '1'},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        cookies = response.headers.getlist('Set-Cookie')
        self.assertTrue(any('remember_token=' in cookie for cookie in cookies))

    def test_csrf_rejects_missing_token_when_enabled(self):
        class CSRFConfig(TestConfig):
            CSRF_ENABLED = True
            WTF_CSRF_ENABLED = True

        csrf_temp_dir = tempfile.TemporaryDirectory()
        CSRFConfig.LOG_DIR = Path(csrf_temp_dir.name) / 'logs'
        CSRFConfig.BACKUP_DIR = Path(csrf_temp_dir.name) / 'backups'
        csrf_app = create_app(CSRFConfig)
        csrf_client = csrf_app.test_client()

        try:
            rejected = csrf_client.post(
                '/login',
                data={'username': 'master', 'password': 'master123'},
            )

            self.assertEqual(rejected.status_code, 400)
            self.assertIn('formulário não pôde ser validado'.encode(), rejected.data)
        finally:
            with csrf_app.app_context():
                db.session.remove()
                db.drop_all()
                db.engine.dispose()
            csrf_temp_dir.cleanup()

    def test_csrf_accepts_valid_session_token_when_enabled(self):
        class CSRFConfig(TestConfig):
            CSRF_ENABLED = True
            WTF_CSRF_ENABLED = True

        csrf_temp_dir = tempfile.TemporaryDirectory()
        CSRFConfig.LOG_DIR = Path(csrf_temp_dir.name) / 'logs'
        CSRFConfig.BACKUP_DIR = Path(csrf_temp_dir.name) / 'backups'
        csrf_app = create_app(CSRFConfig)
        csrf_client = csrf_app.test_client()

        try:
            page = csrf_client.get('/login')
            match = re.search(br'<meta name="csrf-token" content="([^"]+)">', page.data)
            self.assertIsNotNone(match)
            token = match.group(1).decode()

            response = csrf_client.post(
                '/login',
                data={'username': 'master', 'password': 'master123', '_csrf_token': token},
            )

            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.location.endswith('/master'))
        finally:
            with csrf_app.app_context():
                db.session.remove()
                db.drop_all()
                db.engine.dispose()
            csrf_temp_dir.cleanup()

    def test_browser_default_favicon_route_loads(self):
        response = self.client.get('/favicon.ico')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'image/png')
        response.close()

    def test_security_headers_are_present(self):
        response = self.client.get('/login')

        self.assertEqual(response.headers.get('X-Content-Type-Options'), 'nosniff')
        self.assertEqual(response.headers.get('X-Frame-Options'), 'SAMEORIGIN')
        self.assertIn("default-src 'self'", response.headers.get('Content-Security-Policy', ''))
        self.assertIn("form-action 'self'", response.headers.get('Content-Security-Policy', ''))
        self.assertEqual(response.headers.get('Cross-Origin-Opener-Policy'), 'same-origin')

    def test_production_rejects_insecure_default_secrets(self):
        class ProductionConfig(TestConfig):
            ENVIRONMENT = 'production'
            SECRET_KEY = 'adega-jf-secret-key'
            MASTER_DEFAULT_PASSWORD = 'master123'

        with self.assertRaises(RuntimeError):
            create_app(ProductionConfig)

    def test_register_creates_user_but_requires_subscription(self):
        response = self.client.post(
            '/login',
            data={
                'form_type': 'register',
                'username': 'operador',
                'company_name': 'Adega Operador',
                'email': 'operador@example.com',
                'password': self.STRONG_PASSWORD,
                'confirm_password': self.STRONG_PASSWORD,
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Confirmar e-mail'.encode(), response.data)
        self.assertIn('Cadastro criado. Confirme seu e-mail para acessar o sistema.'.encode(), response.data)
        with self.app.app_context():
            user = User.query.filter_by(username='operador').one()
            self.assertEqual(user.email, 'operador@example.com')
            self.assertFalse(user.email_verified)
            self.assertEqual(user.company.name, 'Adega Operador')
            self.assertEqual(user.company.activation_key, '')
            self.assertIsNone(user.company.subscription_renews_at)
            self.assertTrue(user.check_password(self.STRONG_PASSWORD))
            self.assertEqual(EmailVerificationCode.query.filter_by(user_id=user.id).count(), 1)

        blocked_response = self.client.get('/dashboard', follow_redirects=True)

        self.assertEqual(blocked_response.status_code, 200)
        self.assertIn('Entrar'.encode(), blocked_response.data)

    def test_register_ignores_activation_key_and_shows_plans_after_email_confirmation(self):
        with self.app.app_context():
            db.session.add(ActivationKey(key='ABCD-1234-EFGH-5678', plan='Pro', renews_at=date.today() + timedelta(days=30)))
            db.session.commit()

        response = self.client.post(
            '/login',
            data={
                'form_type': 'register',
                'username': 'operadorcomkey',
                'company_name': 'Adega Com Key',
                'email': 'key@example.com',
                'activation_key': 'ABCD-1234-EFGH-5678',
                'password': self.STRONG_PASSWORD,
                'confirm_password': self.STRONG_PASSWORD,
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Confirmar e-mail'.encode(), response.data)
        code = self.app.config['TEST_LAST_VERIFICATION_CODE']
        verify_response = self.client.post('/verify-email', data={'code': code}, follow_redirects=True)

        self.assertEqual(verify_response.status_code, 200)
        self.assertIn('Escolha um plano para ativar sua assinatura'.encode(), verify_response.data)
        self.assertIn('Plano'.encode(), verify_response.data)
        self.assertNotIn('Dashboard'.encode(), verify_response.data)
        with self.app.app_context():
            user = User.query.filter_by(username='operadorcomkey').one()
            self.assertTrue(user.email_verified)
            self.assertIsNotNone(user.email_verified_at)
            self.assertEqual(user.company.activation_key, '')
            self.assertIsNone(user.company.subscription_renews_at)
            key = ActivationKey.query.filter_by(key='ABCD-1234-EFGH-5678').one()
            self.assertIsNone(key.used_by_company_id)

    def test_master_can_generate_standalone_activation_key(self):
        self.login()

        response = self.client.post(
            '/master/assinaturas/keys/gerar',
            data={
                'plan': 'Pro',
                'billing_cycle': 'monthly',
                'renews_at': (date.today() + timedelta(days=30)).isoformat(),
                'company_id': '',
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Key avulsa gerada'.encode(), response.data)
        self.assertIn('Assinaturas e keys'.encode(), response.data)
        with self.app.app_context():
            activation_key = ActivationKey.query.filter_by(plan='Pro').one()
            self.assertTrue(activation_key.active)
            self.assertIsNone(activation_key.used_by_company_id)
            self.assertIsNone(activation_key.used_at)
            self.assertIn(f'data-copy-key="{activation_key.key}"'.encode(), response.data)
        self.assertIn('Copiar'.encode(), response.data)

    def test_master_can_generate_batch_standalone_activation_keys(self):
        self.login()

        response = self.client.post(
            '/master/assinaturas/keys/gerar',
            data={
                'plan': 'Basic',
                'billing_cycle': 'monthly',
                'renews_at': (date.today() + timedelta(days=30)).isoformat(),
                'company_id': '',
                'quantity': '3',
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('3 keys avulsas geradas'.encode(), response.data)
        with self.app.app_context():
            activation_keys = ActivationKey.query.filter_by(plan='Basic').all()
            self.assertEqual(len(activation_keys), 3)
            self.assertTrue(all(key.active for key in activation_keys))
            self.assertTrue(all(key.used_by_company_id is None for key in activation_keys))
            self.assertEqual(len({key.key for key in activation_keys}), 3)

    def test_master_key_generation_does_not_link_company(self):
        self.login()
        with self.app.app_context():
            company = Company(name='Adega Renovar', activation_key='', subscription_renews_at=None)
            db.session.add(company)
            db.session.commit()
            company_id = company.id

        response = self.client.post(
            '/master/assinaturas/keys/gerar',
            data={
                'plan': 'Basic',
                'billing_cycle': 'annual',
                'renews_at': (date.today() + timedelta(days=365)).isoformat(),
                'company_id': str(company_id),
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Key avulsa gerada'.encode(), response.data)
        with self.app.app_context():
            company = db.session.get(Company, company_id)
            activation_key = ActivationKey.query.filter_by(plan='Basic').one()
            self.assertEqual(company.activation_key, '')
            self.assertIsNone(activation_key.used_by_company_id)
            self.assertIsNone(activation_key.used_at)

    def test_master_removing_available_key_deletes_it_from_list(self):
        self.login()
        with self.app.app_context():
            activation_key = ActivationKey(
                key='DROP-KEY1-DROP-KEY2',
                plan='Pro',
                renews_at=date.today() + timedelta(days=30),
            )
            db.session.add(activation_key)
            db.session.commit()
            key_id = activation_key.id

        response = self.client.post(
            f'/master/assinaturas/keys/{key_id}/cancelar',
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Key removida da lista com sucesso.'.encode(), response.data)
        self.assertNotIn('DROP-KEY1-DROP-KEY2'.encode(), response.data)
        with self.app.app_context():
            self.assertIsNone(db.session.get(ActivationKey, key_id))

    def test_master_can_renew_subscription_without_activation_key(self):
        self.login()
        with self.app.app_context():
            company = Company(
                name='Adega Renovada Sem Key',
                activation_key='',
                subscription_started_at=None,
                subscription_renews_at=None,
            )
            db.session.add(company)
            db.session.flush()
            user = User(
                username='renovadosemkey',
                email='renovado@example.com',
                email_verified=True,
                role='admin',
                company_id=company.id,
                is_active=True,
            )
            user.set_password('senha123')
            db.session.add(user)
            db.session.commit()
            company_id = company.id

        response = self.client.post(
            '/master/assinaturas/renovar',
            data={
                'plan': 'Premium',
                'billing_cycle': 'annual',
                'renews_at': (date.today() + timedelta(days=365)).isoformat(),
                'company_id': str(company_id),
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('renovada'.encode(), response.data)
        with self.app.app_context():
            company = db.session.get(Company, company_id)
            self.assertEqual(company.activation_key, '')
            self.assertEqual(company.subscription_plan, 'Premium')
            self.assertEqual(company.billing_cycle, 'annual')
            self.assertTrue(company.subscription_valid)

        self.client.post('/logout')
        login_response = self.login(username='renovadosemkey', password='senha123', follow_redirects=True)

        self.assertEqual(login_response.status_code, 200)
        self.assertIn('Dashboard'.encode(), login_response.data)

    def test_standalone_activation_key_unlocks_company_subscription(self):
        with self.app.app_context():
            activation_key = ActivationKey(
                key='FREE-KEY1-FREE-KEY2',
                plan='Pro',
                renews_at=date.today() + timedelta(days=90),
            )
            company = Company(name='Adega Sem Plano', activation_key='', subscription_renews_at=None)
            db.session.add_all([activation_key, company])
            db.session.flush()
            user = User(
                username='donosemplano',
                email='dono.sem.plano@example.com',
                email_verified=True,
                role='admin',
                company_id=company.id,
                is_active=True,
            )
            user.set_password('senha123')
            db.session.add(user)
            db.session.commit()
            company_id = company.id

        self.login(username='donosemplano', password='senha123')
        response = self.client.post(
            '/assinatura',
            data={'activation_key': 'FREE-KEY1-FREE-KEY2'},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Dashboard'.encode(), response.data)
        with self.app.app_context():
            company = db.session.get(Company, company_id)
            activation_key = ActivationKey.query.filter_by(key='FREE-KEY1-FREE-KEY2').one()
            self.assertEqual(company.activation_key, 'FREE-KEY1-FREE-KEY2')
            self.assertEqual(company.subscription_plan, 'Pro')
            self.assertTrue(company.subscription_valid)
            self.assertEqual(activation_key.used_by_company_id, company.id)
            self.assertIsNotNone(activation_key.used_at)

    def test_master_can_hire_user_for_same_company(self):
        self.login()

        response = self.client.post(
            '/configuracoes',
            data={
                'form_type': 'hire_user',
                'hire_username': 'caixa1',
                'hire_first_name': 'Pedro',
                'hire_last_name': 'Caixa',
                'hire_cpf': '123.456.789-00',
                'hire_email': 'caixa@example.com',
                'hire_password': '123',
                'hire_role': 'operator',
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Usuário contratado com sucesso.'.encode(), response.data)
        with self.app.app_context():
            master = User.query.filter_by(username='master').one()
            hired_user = User.query.filter_by(username='caixa1').one()
            self.assertEqual(hired_user.company_id, master.company_id)
            self.assertEqual(hired_user.role, 'operator')
            self.assertEqual(hired_user.first_name, 'Pedro')
            self.assertEqual(hired_user.last_name, 'Caixa')
            self.assertEqual(hired_user.cpf, '123.456.789-00')
            self.assertTrue(hired_user.check_password('123'))
            self.assertTrue(hired_user.can_manage_sales)
            self.assertTrue(hired_user.can_manage_cash_register)
            self.assertTrue(hired_user.can_view_products)
            self.assertFalse(hired_user.can_manage_products)
            self.assertFalse(hired_user.can_manage_settings)

        duplicate_response = self.client.post(
            '/configuracoes',
            data={
                'form_type': 'hire_user',
                'hire_username': 'caixa2',
                'hire_cpf': '12345678900',
                'hire_password': '123',
                'hire_role': 'operator',
            },
            follow_redirects=True,
        )

        self.assertEqual(duplicate_response.status_code, 200)
        self.assertIn('Já existe um funcionário com este CPF nesta adega.'.encode(), duplicate_response.data)

    def test_company_can_have_multiple_admin_users(self):
        self.login()

        first_response = self.client.post(
            '/configuracoes',
            data={
                'form_type': 'hire_user',
                'hire_username': 'admin1',
                'hire_password': '123',
                'hire_role': 'admin',
            },
            follow_redirects=True,
        )
        second_response = self.client.post(
            '/configuracoes',
            data={
                'form_type': 'hire_user',
                'hire_username': 'admin2',
                'hire_password': '123',
                'hire_role': 'admin',
            },
            follow_redirects=True,
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertIn('Usuário contratado com sucesso.'.encode(), first_response.data)
        self.assertIn('Usuário contratado com sucesso.'.encode(), second_response.data)
        with self.app.app_context():
            company_id = self.master_company_id()
            admins = User.query.filter_by(company_id=company_id, role='admin').all()
            usernames = {user.username for user in admins}
            self.assertIn('admin1', usernames)
            self.assertIn('admin2', usernames)

    def test_employee_permissions_allow_view_and_block_unallowed_actions_without_password(self):
        self.login()

        self.client.post(
            '/configuracoes',
            data={
                'form_type': 'hire_user',
                'hire_username': 'vendedor',
                'hire_password': '123',
                'hire_role': 'operator',
            },
            follow_redirects=True,
        )
        self.client.post('/logout')
        self.login(username='vendedor', password='123')

        products_response = self.client.get('/catalogo/produtos', follow_redirects=True)
        sales_response = self.client.get('/vendas')
        cash_response = self.client.get('/caixa')
        settings_response = self.client.get('/configuracoes')
        reports_response = self.client.get('/relatorios', follow_redirects=True)

        self.assertEqual(products_response.status_code, 200)
        self.assertIn('Produtos'.encode(), products_response.data)
        self.assertEqual(sales_response.status_code, 200)
        self.assertEqual(cash_response.status_code, 200)
        self.assertEqual(settings_response.status_code, 200)
        self.assertIn('Usuário'.encode(), settings_response.data)
        self.assertIn('data-accessibility-enabled-toggle'.encode(), settings_response.data)
        self.assertIn('data-accessibility-bold-toggle'.encode(), settings_response.data)
        self.assertIn('Autorizar Relatórios'.encode(), reports_response.data)

    def test_common_employee_can_view_products_but_needs_authorized_password_to_edit(self):
        self.login()
        with self.app.app_context():
            product = Product(name='Produto Consulta', sale_price=10, stock_quantity=5, active=True, company_id=self.master_company_id())
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        self.client.post(
            '/configuracoes',
            data={
                'form_type': 'hire_user',
                'hire_username': 'consulta',
                'hire_password': '123',
                'hire_role': 'operator',
            },
            follow_redirects=True,
        )
        self.client.post('/logout')
        self.login(username='consulta', password='123')

        products_response = self.client.get('/catalogo/produtos', follow_redirects=True)
        edit_response = self.client.post(
            f'/catalogo/produtos/{product_id}/atualizar',
            data={
                'name': 'Produto Alterado',
                'sale_price': '99,00',
                'stock_quantity': '1',
            },
            follow_redirects=True,
        )

        self.assertEqual(products_response.status_code, 200)
        self.assertIn('Produto Consulta'.encode(), products_response.data)
        self.assertNotIn('Novo produto'.encode(), products_response.data)
        self.assertNotIn('Salvar'.encode(), products_response.data)
        self.assertNotIn('Venda</label>'.encode(), products_response.data)
        self.assertIn('Informe a senha de um usuário autorizado'.encode(), edit_response.data)
        with self.app.app_context():
            unchanged = db.session.get(Product, product_id)
            self.assertEqual(unchanged.name, 'Produto Consulta')
            self.assertEqual(unchanged.sale_price, 10)

        authorized_response = self.client.post(
            f'/catalogo/produtos/{product_id}/atualizar',
            data={
                'name': 'Produto Alterado',
                'sale_price': '99,00',
                'stock_quantity': '1',
                '_permission_override_username': 'master',
                '_permission_override_password': 'master123',
            },
            follow_redirects=True,
        )

        self.assertIn('Produto atualizado com sucesso.'.encode(), authorized_response.data)
        with self.app.app_context():
            changed = db.session.get(Product, product_id)
            self.assertEqual(changed.name, 'Produto Alterado')
            self.assertEqual(changed.sale_price, 99)

    def test_manager_can_manage_operations_but_not_finance(self):
        self.login()
        with self.app.app_context():
            product = Product(name='Produto Gerente', sale_price=10, stock_quantity=5, active=True, company_id=self.master_company_id())
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        self.client.post(
            '/configuracoes',
            data={
                'form_type': 'hire_user',
                'hire_username': 'gerente',
                'hire_password': '123',
                'hire_role': 'manager',
            },
            follow_redirects=True,
        )
        self.client.post('/logout')
        self.login(username='gerente', password='123')

        products_response = self.client.get('/catalogo/produtos')
        edit_response = self.client.post(
            f'/catalogo/produtos/{product_id}/atualizar',
            data={'name': 'Produto Gerente Editado', 'sale_price': '12,00', 'stock_quantity': '4'},
            follow_redirects=True,
        )
        settings_response = self.client.get('/configuracoes')
        subscription_response = self.client.get('/assinaturas', follow_redirects=True)
        fees_response = self.client.post(
            '/configuracoes',
            data={'form_type': 'card_fees', 'debit_fee_enabled': 'on', 'debit_fee_percent': '2,00'},
            follow_redirects=True,
        )

        self.assertEqual(products_response.status_code, 200)
        self.assertIn('Produto Gerente'.encode(), products_response.data)
        self.assertEqual(edit_response.status_code, 200)
        self.assertIn('Produto atualizado com sucesso.'.encode(), edit_response.data)
        self.assertIn('Equipe'.encode(), settings_response.data)
        self.assertIn('Importação'.encode(), settings_response.data)
        self.assertIn('Backup'.encode(), settings_response.data)
        self.assertIn('Autorizar Financeiro'.encode(), settings_response.data)
        self.assertNotIn('Taxa da maquininha'.encode(), settings_response.data)
        self.assertIn('Autorizar Financeiro'.encode(), subscription_response.data)
        self.assertIn('Informe a senha de um admin'.encode(), fees_response.data)
        with self.app.app_context():
            changed = db.session.get(Product, product_id)
            self.assertEqual(changed.name, 'Produto Gerente Editado')
            company = User.query.filter_by(username='master').one().company
            self.assertFalse(company.debit_fee_enabled)

    def test_master_can_edit_employee_profile_fields(self):
        self.login()
        self.client.post(
            '/configuracoes',
            data={
                'form_type': 'hire_user',
                'hire_username': 'perfil',
                'hire_first_name': 'Nome',
                'hire_last_name': 'Antigo',
                'hire_cpf': '111.222.333-44',
                'hire_password': '123',
                'hire_role': 'operator',
            },
            follow_redirects=True,
        )
        with self.app.app_context():
            employee_id = User.query.filter_by(username='perfil').one().id

        response = self.client.post(
            '/configuracoes',
            data={
                'form_type': 'update_employee',
                'employee_id': employee_id,
                'employee_first_name': 'Nome',
                'employee_last_name': 'Novo',
                'employee_cpf': '555.666.777-88',
                'employee_role': 'manager',
                'is_active': 'on',
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Permissões do funcionário atualizadas.'.encode(), response.data)
        with self.app.app_context():
            employee = db.session.get(User, employee_id)
            self.assertEqual(employee.last_name, 'Novo')
            self.assertEqual(employee.cpf, '555.666.777-88')
            self.assertEqual(employee.role, 'manager')

    def test_manager_can_import_spreadsheet(self):
        self.login()

        self.client.post(
            '/configuracoes',
            data={
                'form_type': 'hire_user',
                'hire_username': 'gerenteimport',
                'hire_password': '123',
                'hire_role': 'manager',
            },
            follow_redirects=True,
        )
        self.client.post('/logout')
        self.login(username='gerenteimport', password='123')

        response = self.client.post(
            '/catalogo/produtos/importar',
            data={
                'spreadsheet': (io.BytesIO('categoria;produto;preco_custo;preco_venda\nTeste;Produto X;1;2\n'.encode('utf-8')), 'produtos.csv'),
            },
            content_type='multipart/form-data',
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Importação concluída: 1 produto(s) criado(s)'.encode(), response.data)
        with self.app.app_context():
            self.assertIsNotNone(Product.query.filter_by(name='Produto X').first())

    def test_admin_can_export_products_csv(self):
        self.login()
        with self.app.app_context():
            db.session.add(Product(
                name='Produto Exportado',
                barcode='789',
                cost_price=5,
                sale_price=10,
                stock_quantity=7,
                active=True,
                company_id=self.master_company_id(),
            ))
            db.session.commit()

        settings_response = self.client.get('/configuracoes')
        response = self.client.get('/exportacoes/produtos')

        self.assertEqual(settings_response.status_code, 200)
        self.assertIn('Exportação'.encode(), settings_response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'text/csv')
        self.assertIn('attachment;', response.headers.get('Content-Disposition', ''))
        self.assertIn('Produto Exportado'.encode(), response.data)
        self.assertIn('produto'.encode(), response.data)

    def test_manager_cannot_export_data(self):
        self.login()

        self.client.post(
            '/configuracoes',
            data={
                'form_type': 'hire_user',
                'hire_username': 'semexport',
                'hire_password': '123',
                'hire_role': 'manager',
            },
            follow_redirects=True,
        )
        self.client.post('/logout')
        self.login(username='semexport', password='123')

        settings_response = self.client.get('/configuracoes')
        response = self.client.get('/exportacoes/produtos', follow_redirects=True)
        authorized_response = self.client.post(
            '/exportacoes/produtos',
            data={
                '_permission_override_username': 'master',
                '_permission_override_password': 'master123',
            },
        )

        self.assertEqual(settings_response.status_code, 200)
        self.assertIn('Exportação'.encode(), settings_response.data)
        self.assertIn('Informe a senha de um admin'.encode(), response.data)
        self.assertEqual(authorized_response.status_code, 200)
        self.assertEqual(authorized_response.mimetype, 'text/csv')

    def test_common_employee_can_see_admin_tabs_but_actions_require_password(self):
        self.login()

        self.client.post(
            '/configuracoes',
            data={
                'form_type': 'hire_user',
                'hire_username': 'funcionario',
                'hire_password': '123',
                'hire_role': 'operator',
            },
            follow_redirects=True,
        )
        self.client.post('/logout')
        self.login(username='funcionario', password='123')

        response = self.client.get('/configuracoes')

        self.assertEqual(response.status_code, 200)
        self.assertIn('Usuário'.encode(), response.data)
        self.assertIn('Suporte'.encode(), response.data)
        self.assertNotIn('data-settings-tab="appearance"'.encode(), response.data)
        self.assertIn('Sair da conta'.encode(), response.data)
        self.assertIn('Autorizar Gestão'.encode(), response.data)
        self.assertNotIn('Equipe'.encode(), response.data)
        self.assertNotIn('Financeiro'.encode(), response.data)
        self.assertNotIn('Importação'.encode(), response.data)
        self.assertNotIn('Gestão de funcionários'.encode(), response.data)
        self.assertNotIn('Taxa da maquininha'.encode(), response.data)

        unlocked_response = self.client.post(
            '/autorizar-acesso',
            data={
                'permission': 'can_manage_settings',
                'next': '/configuracoes',
                '_permission_override_username': 'master',
                '_permission_override_password': 'master123',
            },
            follow_redirects=True,
        )

        self.assertIn('Equipe'.encode(), unlocked_response.data)
        self.assertIn('Importação'.encode(), unlocked_response.data)
        self.assertIn('Gestão de funcionários'.encode(), unlocked_response.data)

        denied_response = self.client.post(
            '/configuracoes',
            data={'form_type': 'hire_user', 'hire_username': 'novo', 'hire_password': '123'},
            follow_redirects=True,
        )
        self.assertIn('Informe a senha de um usuário autorizado'.encode(), denied_response.data)

    def test_common_employee_can_view_subscription_plan(self):
        self.login()

        self.client.post(
            '/configuracoes',
            data={
                'form_type': 'hire_user',
                'hire_username': 'semplano',
                'hire_password': '123',
                'hire_role': 'operator',
            },
            follow_redirects=True,
        )
        self.client.post('/logout')
        self.login(username='semplano', password='123')

        dashboard_response = self.client.get('/dashboard')
        subscription_response = self.client.get('/assinaturas', follow_redirects=True)

        self.assertEqual(dashboard_response.status_code, 200)
        self.assertNotIn('Assinaturas'.encode(), dashboard_response.data)
        self.assertEqual(subscription_response.status_code, 200)
        self.assertIn('Autorizar Financeiro'.encode(), subscription_response.data)

    def test_company_data_is_separated_between_logins(self):
        with self.app.app_context():
            company_a = Company(name='Adega A', activation_key='KEY-A')
            company_b = Company(name='Adega B', activation_key='KEY-B')
            db.session.add_all([company_a, company_b])
            db.session.flush()
            user_a = User(username='adegajf123', role='admin', company_id=company_a.id, is_active=True)
            user_b = User(username='adegadojorge123', role='admin', company_id=company_b.id, is_active=True)
            user_a.set_password('123')
            user_b.set_password('123')
            db.session.add_all([
                user_a,
                user_b,
                Product(name='Produto Girofy', sale_price=10, stock_quantity=5, active=True, company_id=company_a.id),
                Product(name='Produto Jorge', sale_price=20, stock_quantity=5, active=True, company_id=company_b.id),
            ])
            db.session.commit()

        self.login(username='adegajf123', password='123')
        response_a = self.client.get('/catalogo/produtos')
        self.assertEqual(response_a.status_code, 200)
        self.assertIn('Produto Girofy'.encode(), response_a.data)
        self.assertNotIn('Produto Jorge'.encode(), response_a.data)

        self.client.post('/logout')
        self.login(username='adegadojorge123', password='123')
        response_b = self.client.get('/catalogo/produtos')
        self.assertEqual(response_b.status_code, 200)
        self.assertIn('Produto Jorge'.encode(), response_b.data)
        self.assertNotIn('Produto Girofy'.encode(), response_b.data)

    def test_different_companies_can_create_category_with_same_name(self):
        with self.app.app_context():
            company_a = Company(name='Adega Categoria A', activation_key='KEY-CAT-A')
            company_b = Company(name='Adega Categoria B', activation_key='KEY-CAT-B')
            db.session.add_all([company_a, company_b])
            db.session.flush()
            user_a = User(username='cat_a', role='admin', company_id=company_a.id, is_active=True)
            user_b = User(username='cat_b', role='admin', company_id=company_b.id, is_active=True)
            user_a.set_password('123')
            user_b.set_password('123')
            db.session.add_all([user_a, user_b])
            db.session.commit()

        self.login(username='cat_a', password='123')
        first_response = self.client.post(
            '/catalogo/categorias',
            data={'name': 'Cerveja'},
            follow_redirects=True,
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertIn('Categoria cadastrada com sucesso.'.encode(), first_response.data)

        self.client.post('/logout')
        self.login(username='cat_b', password='123')
        second_response = self.client.post(
            '/catalogo/categorias',
            data={'name': 'Cerveja'},
            follow_redirects=True,
        )

        self.assertEqual(second_response.status_code, 200)
        self.assertIn('Categoria cadastrada com sucesso.'.encode(), second_response.data)
        self.assertNotIn('Já existe uma categoria com este nome.'.encode(), second_response.data)

        with self.app.app_context():
            self.assertEqual(Category.query.filter_by(name='Cerveja').count(), 2)

    def test_master_can_inactivate_and_delete_company(self):
        with self.app.app_context():
            company = Company(name='Adega Removivel', database_path='')
            db.session.add(company)
            db.session.flush()
            user = User(username='removivel', role='admin', company_id=company.id, is_active=True)
            user.set_password('123')
            db.session.add(user)
            db.session.flush()
            category = Category(name='Categoria Removivel', company_id=company.id)
            db.session.add(category)
            db.session.flush()
            product = Product(name='Produto Removivel', category_id=category.id, company_id=company.id, cost_price=5, sale_price=10, stock_quantity=2)
            db.session.add(product)
            cash_register = CashRegister(opening_amount=0, status='open', user_id=user.id, company_id=company.id)
            payable = Payable(description='Conta Removivel', amount=20, due_date=date.today(), company_id=company.id)
            alert_setting = EmailAlertSetting(company_id=company.id, alert_type='product_low_stock', enabled=True, recipients='')
            alert_delivery = EmailAlertDelivery(company_id=company.id, alert_type='product_low_stock', alert_key='old-alert', recipients='')
            db.session.add_all([cash_register, payable, alert_setting, alert_delivery])
            db.session.flush()
            sale = Sale(total_amount=10, final_amount=10, payment_status='paid', user_id=user.id, company_id=company.id, cash_register_id=cash_register.id)
            db.session.add(sale)
            db.session.flush()
            db.session.add(Payment(sale_id=sale.id, method='money', amount=10))
            db.session.add(SaleItem(sale_id=sale.id, product_id=product.id, quantity=1, unit_price=10, total_price=10))
            db.session.add(EmailVerificationCode(
                user_id=user.id,
                code_hash='verification-hash',
                expires_at=datetime.now() + timedelta(minutes=15),
            ))
            db.session.add(PasswordResetToken(
                user_id=user.id,
                token_hash='reset-hash',
                expires_at=datetime.now() + timedelta(minutes=30),
            ))
            db.session.add(EmailChangeRequest(
                user_id=user.id,
                old_email='antigo@example.com',
                new_email='novo@example.com',
                token_hash='change-hash',
                expires_at=datetime.now() + timedelta(minutes=30),
            ))
            db.session.commit()
            company_id = company.id
            user_id = user.id
            category_id = category.id
            product_id = product.id
            cash_register_id = cash_register.id
            sale_id = sale.id

        self.login()
        toggle_response = self.client.post(
            f'/master/adegas/{company_id}/alternar-status',
            follow_redirects=True,
        )

        self.assertEqual(toggle_response.status_code, 200)
        self.assertIn('Status da adega atualizado com sucesso.'.encode(), toggle_response.data)
        with self.app.app_context():
            self.assertFalse(db.session.get(Company, company_id).active)

        cards_response = self.client.get('/master/adegas', query_string={'view': 'cards'})

        self.assertEqual(cards_response.status_code, 200)
        self.assertIn('Blocos'.encode(), cards_response.data)
        self.assertIn('Adega Removivel'.encode(), cards_response.data)

        edit_response = self.client.post(
            f'/master/adegas/{company_id}/editar',
            data={
                'name': 'Adega Editada',
                'active': 'on',
                'view_mode': 'cards',
                'subscription_plan': 'Premium',
                'billing_cycle': 'annual',
                'subscription_started_at': '2026-07-01',
                'subscription_renews_at': '2027-07-01',
            },
            follow_redirects=True,
        )

        self.assertEqual(edit_response.status_code, 200)
        self.assertIn('Adega atualizada com sucesso.'.encode(), edit_response.data)
        self.assertIn('Adega Editada'.encode(), edit_response.data)
        self.assertIn('Premium'.encode(), edit_response.data)
        self.assertIn('Anual'.encode(), edit_response.data)
        with self.app.app_context():
            updated_company = db.session.get(Company, company_id)
            self.assertTrue(updated_company.active)
            self.assertEqual(updated_company.subscription_plan, 'Premium')
            self.assertEqual(updated_company.billing_cycle, 'annual')
            self.assertEqual(updated_company.activation_key, '')

        generate_key_response = self.client.post(
            f'/master/adegas/{company_id}/editar',
            data={
                'name': 'Adega Editada',
                'active': 'on',
                'view_mode': 'cards',
                'subscription_plan': 'Premium',
                'billing_cycle': 'annual',
                'subscription_started_at': '2026-07-01',
                'subscription_renews_at': '2027-07-01',
                'generate_activation_key': 'on',
            },
            follow_redirects=True,
        )

        self.assertEqual(generate_key_response.status_code, 200)
        with self.app.app_context():
            generated_company = db.session.get(Company, company_id)
            self.assertTrue(generated_company.activation_key)
            db.session.add(ActivationKey(
                key='USED-DELETE-COMPANY',
                plan='Pro',
                renews_at=date.today() + timedelta(days=30),
                used_by_company_id=company_id,
                used_at=datetime.now(),
            ))
            db.session.commit()

        access_response = self.client.post(
            f'/master/adegas/{company_id}/acessar',
            follow_redirects=True,
        )

        self.assertEqual(access_response.status_code, 200)
        self.assertIn('Master conectado em Adega Editada.'.encode(), access_response.data)
        self.assertIn('Dashboard'.encode(), access_response.data)

        leave_response = self.client.post('/master/adegas/sair-acesso', follow_redirects=True)

        self.assertEqual(leave_response.status_code, 200)
        self.assertIn('Você voltou para o painel master.'.encode(), leave_response.data)

        self.client.post(
            f'/master/adegas/{company_id}/alternar-status',
            follow_redirects=True,
        )
        with self.app.app_context():
            self.assertFalse(db.session.get(Company, company_id).active)

        self.client.post('/logout')
        inactive_login = self.login(username='removivel', password='123')

        self.assertEqual(inactive_login.status_code, 200)
        self.assertIn('Esta adega está inativa.'.encode(), inactive_login.data)

        self.login()
        delete_response = self.client.post(
            f'/master/adegas/{company_id}/excluir',
            follow_redirects=True,
        )

        self.assertEqual(delete_response.status_code, 200)
        self.assertIn('Adega excluída com sucesso.'.encode(), delete_response.data)
        with self.app.app_context():
            self.assertIsNone(db.session.get(Company, company_id))
            self.assertIsNone(User.query.filter_by(username='removivel').first())
            self.assertEqual(EmailVerificationCode.query.filter_by(user_id=user_id).count(), 0)
            self.assertEqual(PasswordResetToken.query.filter_by(user_id=user_id).count(), 0)
            self.assertEqual(EmailChangeRequest.query.filter_by(user_id=user_id).count(), 0)
            self.assertIsNone(db.session.get(Category, category_id))
            self.assertIsNone(db.session.get(Product, product_id))
            self.assertIsNone(db.session.get(CashRegister, cash_register_id))
            self.assertIsNone(db.session.get(Sale, sale_id))
            self.assertEqual(Payable.query.filter_by(company_id=company_id).count(), 0)
            self.assertEqual(EmailAlertSetting.query.filter_by(company_id=company_id).count(), 0)
            self.assertEqual(EmailAlertDelivery.query.filter_by(company_id=company_id).count(), 0)
            reusable_key = ActivationKey.query.filter_by(key='USED-DELETE-COMPANY').one()
            self.assertIsNone(reusable_key.used_by_company_id)
            self.assertIsNone(reusable_key.used_at)

    def test_master_settings_can_generate_standalone_key_with_plan_and_period(self):
        self.login()
        settings_response = self.client.get('/configuracoes')

        self.assertEqual(settings_response.status_code, 200)
        self.assertIn('Gerar key'.encode(), settings_response.data)
        self.assertIn('Keys são avulsas'.encode(), settings_response.data)

        response = self.client.post(
            '/configuracoes',
            data={
                'form_type': 'master_generate_key',
                'key_quantity': '2',
                'key_plan': 'Pro',
                'key_renews_at': '2026-12-31',
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('2 keys avulsas geradas'.encode(), response.data)
        self.assertIn('Copiar'.encode(), response.data)
        with self.app.app_context():
            keys = ActivationKey.query.filter_by(plan='Pro').all()
            self.assertEqual(len(keys), 2)
            self.assertTrue(all(key.renews_at.isoformat() == '2026-12-31' for key in keys))
            self.assertTrue(all(key.used_by_company_id is None for key in keys))

        avulsa_response = self.client.post(
            '/configuracoes',
            data={
                'form_type': 'master_generate_key',
                'key_plan': 'Basic',
                'key_renews_at': '2026-07-09',
            },
            follow_redirects=True,
        )

        self.assertEqual(avulsa_response.status_code, 200)
        self.assertIn('Key avulsa gerada'.encode(), avulsa_response.data)
        with self.app.app_context():
            free_key = ActivationKey.query.filter_by(plan='Basic', renews_at=date(2026, 7, 9), used_by_company_id=None).one()
            self.assertTrue(free_key.key)

    def test_expired_subscription_blocks_company_until_valid_activation_key(self):
        yesterday = date.today() - timedelta(days=1)
        next_month = date.today() + timedelta(days=30)
        with self.app.app_context():
            company = Company(
                name='Adega Vencida',
                subscription_renews_at=yesterday,
                activation_key='ABCD-1234-EFGH-5678',
            )
            db.session.add(company)
            db.session.flush()
            user = User(username='vencida', role='admin', company_id=company.id, is_active=True)
            user.set_password('123')
            db.session.add(user)
            db.session.commit()
            company_id = company.id

        login_response = self.login(username='vencida', password='123')

        self.assertEqual(login_response.status_code, 302)
        self.assertTrue(login_response.location.endswith('/assinatura'))

        dashboard_response = self.client.get('/dashboard')

        self.assertEqual(dashboard_response.status_code, 302)
        self.assertTrue(dashboard_response.location.endswith('/assinatura'))

        invalid_key_response = self.client.post(
            '/assinatura',
            data={'activation_key': 'KEY-ERRADA'},
            follow_redirects=True,
        )

        self.assertEqual(invalid_key_response.status_code, 200)
        self.assertIn('Key de ativação inválida.'.encode(), invalid_key_response.data)

        correct_but_expired_response = self.client.post(
            '/assinatura',
            data={'activation_key': 'ABCD-1234-EFGH-5678'},
            follow_redirects=True,
        )

        self.assertEqual(correct_but_expired_response.status_code, 200)
        self.assertIn('assinatura ainda está vencida'.encode(), correct_but_expired_response.data)

        with self.app.app_context():
            company = db.session.get(Company, company_id)
            company.subscription_renews_at = next_month
            db.session.commit()

        valid_response = self.client.post(
            '/assinatura',
            data={'activation_key': 'ABCD-1234-EFGH-5678'},
            follow_redirects=True,
        )

        self.assertEqual(valid_response.status_code, 200)
        self.assertIn('Assinatura ativada com sucesso.'.encode(), valid_response.data)
        self.assertIn('Dashboard'.encode(), valid_response.data)

    def test_company_without_key_is_allowed_with_active_subscription(self):
        next_month = date.today() + timedelta(days=30)
        with self.app.app_context():
            company = Company(
                name='Adega Sem Assinatura',
                activation_key='',
                subscription_renews_at=next_month,
                active=True,
            )
            db.session.add(company)
            db.session.flush()
            user = User(username='semkeyativa', role='admin', company_id=company.id, is_active=True)
            user.set_password('123')
            db.session.add(user)
            db.session.commit()

        login_response = self.login(username='semkeyativa', password='123')

        self.assertEqual(login_response.status_code, 302)
        self.assertTrue(login_response.location.endswith('/dashboard'))

        allowed_pages = (
            '/dashboard',
            '/catalogo/produtos',
            '/catalogo/categorias',
            '/vendas',
            '/caixa',
            '/configuracoes',
        )
        for path in allowed_pages:
            response = self.client.get(path, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('Ativação necessária'.encode(), response.data)

        plans_response = self.client.get('/assinaturas')

        self.assertEqual(plans_response.status_code, 200)
        self.assertIn('Plano'.encode(), plans_response.data)
        self.assertIn('Basic'.encode(), plans_response.data)
        self.assertIn('Pro'.encode(), plans_response.data)
        self.assertIn('Ver planos'.encode(), plans_response.data)
        self.assertNotIn('Key'.encode(), plans_response.data)
        self.assertNotIn('Produtos, categorias e kits'.encode(), plans_response.data)

    def test_register_rejects_duplicate_username(self):
        response = self.client.post(
            '/login',
            data={
                'form_type': 'register',
                'username': 'master',
                'email': 'master2@example.com',
                'password': self.STRONG_PASSWORD,
                'confirm_password': self.STRONG_PASSWORD,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Já existe um usuário com este login.'.encode(), response.data)
        self.assertIn('value="master"'.encode(), response.data)
        self.assertIn('value="master2@example.com"'.encode(), response.data)

    def test_register_error_preserves_entered_fields(self):
        response = self.client.post(
            '/login',
            data={
                'form_type': 'register',
                'username': 'cliente',
                'company_name': 'Adega Cliente',
                'email': 'email-invalido',
                'password': self.STRONG_PASSWORD,
                'confirm_password': self.STRONG_PASSWORD,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Este e-mail não parece válido.'.encode(), response.data)
        self.assertIn('value="cliente"'.encode(), response.data)
        self.assertIn('value="Adega Cliente"'.encode(), response.data)
        self.assertIn('value="email-invalido"'.encode(), response.data)
        self.assertNotIn('Key de ativação'.encode(), response.data)

    def test_dashboard_routes_redirect_anonymous_users_to_login(self):
        for route in ('/', '/dashboard'):
            with self.subTest(route=route):
                response = self.client.get(route)

                self.assertEqual(response.status_code, 302)
                self.assertIn('/login', response.location)

    def test_valid_login_redirects_master_to_company_panel(self):
        response = self.login()

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/master'))

    def test_valid_login_loads_company_panel_when_following_redirects(self):
        response = self.login(follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('Painel master'.encode(), response.data)
        self.assertIn('Visão geral'.encode(), response.data)
        self.assertIn('Acompanhe a operação da plataforma em um só lugar.'.encode(), response.data)
        self.assertIn('master'.encode(), response.data)

    def test_master_areas_are_available_on_separate_pages(self):
        self.login()

        expectations = {
            '/master': 'Visão geral',
            '/master/adegas': 'Gerencie, acesse e acompanhe as adegas cadastradas.',
            '/master/usuarios': 'Consulte os usuários',
            '/master/assinaturas': 'Assinaturas e keys',
            '/master/logs': 'Investigue falhas e avisos',
        }
        for route, expected_text in expectations.items():
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                self.assertIn(expected_text.encode(), response.data)

        companies_response = self.client.get('/master/adegas')
        self.assertNotIn('Gerar key'.encode(), companies_response.data)
        self.assertNotIn('Limpar logs'.encode(), companies_response.data)

    def test_low_stock_notification_appears_for_authenticated_user(self):
        self.login()

        with self.app.app_context():
            company_id = self.master_company_id()
            low_product = Product(name='Produto Baixo', sale_price=10, stock_quantity=2, min_stock_quantity=3, active=True, company_id=company_id)
            db.session.add(low_product)
            db.session.add(Product(name='Produto Sem Estoque', sale_price=10, stock_quantity=0, min_stock_quantity=5, active=True, company_id=company_id))
            db.session.commit()
            low_product_id = low_product.id

        response = self.client.get('/dashboard')

        self.assertEqual(response.status_code, 200)
        self.assertIn('Alertas'.encode(), response.data)
        self.assertIn('Estoque baixo'.encode(), response.data)
        self.assertIn('Produto Baixo está com 2 un. Mínimo: 3 un.'.encode(), response.data)
        self.assertIn('Produto Sem Estoque está sem estoque. Mínimo: 5 un.'.encode(), response.data)

        dismiss_response = self.client.post(f'/catalogo/produtos/{low_product_id}/notificacao-estoque', follow_redirects=True)

        self.assertEqual(dismiss_response.status_code, 200)
        self.assertNotIn('Produto Baixo está com 2 un. Mínimo: 3 un.'.encode(), dismiss_response.data)
        self.assertIn('Produto Sem Estoque está sem estoque. Mínimo: 5 un.'.encode(), dismiss_response.data)

    def test_payables_create_and_show_due_notification(self):
        self.login()
        due_date = date.today() + timedelta(days=2)

        create_response = self.client.post(
            '/contas-a-pagar',
            data={
                'description': 'Aluguel',
                'category': 'Aluguel',
                'amount': '1500,00',
                'due_date': due_date.isoformat(),
                'notes': 'Sala comercial',
            },
            follow_redirects=True,
        )

        self.assertEqual(create_response.status_code, 200)
        self.assertIn('Conta a pagar cadastrada com sucesso.'.encode(), create_response.data)
        self.assertIn('Aluguel'.encode(), create_response.data)
        self.assertIn('R$ 1500,00'.encode(), create_response.data)

        dashboard_response = self.client.get('/dashboard')

        self.assertEqual(dashboard_response.status_code, 200)
        self.assertIn('Conta próxima do vencimento'.encode(), dashboard_response.data)
        self.assertIn('Aluguel vence em 2 dias. Valor: R$ 1500,00.'.encode(), dashboard_response.data)

        with self.app.app_context():
            payable_id = Payable.query.filter_by(description='Aluguel').one().id

        pay_response = self.client.post(f'/contas-a-pagar/{payable_id}/pagar', follow_redirects=True)

        self.assertEqual(pay_response.status_code, 200)
        self.assertIn('Conta marcada como paga.'.encode(), pay_response.data)
        with self.app.app_context():
            self.assertTrue(db.session.get(Payable, payable_id).paid)

    def test_dashboard_shows_operational_summary(self):
        self.login()
        with self.app.app_context():
            company_id = self.master_company_id()
            product = Product(
                name='Produto Dashboard',
                cost_price=60,
                sale_price=100,
                stock_quantity=2,
                min_stock_quantity=3,
                active=True,
                company_id=company_id,
            )
            cash_register = CashRegister(
                company_id=company_id,
                opening_amount=100,
                status='open',
                opened_at=datetime.now(),
            )
            db.session.add_all([product, cash_register])
            db.session.flush()
            sale = Sale(
                company_id=company_id,
                cash_register_id=cash_register.id,
                created_at=datetime.now(),
                total_amount=100,
                final_amount=100,
                payment_status='paid',
            )
            db.session.add(sale)
            db.session.flush()
            db.session.add(SaleItem(
                sale_id=sale.id,
                product_id=product.id,
                quantity=1,
                unit_price=100,
                unit_cost_price=60,
                total_price=100,
                profit_amount=40,
            ))
            db.session.add(Payable(
                company_id=company_id,
                description='Internet',
                category='Internet',
                amount=120,
                due_date=date.today() + timedelta(days=1),
            ))
            db.session.commit()

        response = self.client.get('/dashboard')

        self.assertEqual(response.status_code, 200)
        self.assertIn('Vendido hoje'.encode(), response.data)
        self.assertIn('R$ 100,00'.encode(), response.data)
        self.assertIn('Lucro hoje'.encode(), response.data)
        self.assertIn('R$ 40,00'.encode(), response.data)
        self.assertIn('Produto Dashboard'.encode(), response.data)
        self.assertIn('Estoque baixo'.encode(), response.data)
        self.assertIn('Internet'.encode(), response.data)

    def test_operator_dashboard_hides_profit_and_payables(self):
        self.login()
        with self.app.app_context():
            company_id = self.master_company_id()
            product = Product(
                name='Produto Sem Financeiro',
                cost_price=10,
                sale_price=20,
                stock_quantity=2,
                min_stock_quantity=3,
                active=True,
                company_id=company_id,
            )
            employee = User(username='dashboard_func', role='operator', company_id=company_id, is_active=True)
            employee.set_password('123')
            employee.can_view_products = False
            employee.can_manage_products = False
            employee.can_manage_categories = False
            employee.can_manage_sales = True
            employee.can_manage_cash_register = True
            employee.can_view_reports = False
            employee.can_manage_payables = False
            employee.can_manage_settings = False
            db.session.add_all([
                product,
                employee,
                Payable(
                    company_id=company_id,
                    description='Conta Restrita',
                    category='Aluguel',
                    amount=300,
                    due_date=date.today() + timedelta(days=1),
                ),
            ])
            db.session.flush()
            sale = Sale(
                company_id=company_id,
                created_at=datetime.now(),
                total_amount=20,
                final_amount=20,
                payment_status='paid',
            )
            db.session.add(sale)
            db.session.flush()
            db.session.add(SaleItem(
                sale_id=sale.id,
                product_id=product.id,
                quantity=1,
                unit_price=20,
                unit_cost_price=10,
                total_price=20,
                profit_amount=10,
            ))
            db.session.commit()

        self.client.post('/logout')
        self.login(username='dashboard_func', password='123')
        response = self.client.get('/dashboard')

        self.assertEqual(response.status_code, 200)
        self.assertIn('Vendido hoje'.encode(), response.data)
        self.assertIn('Produto Sem Financeiro'.encode(), response.data)
        self.assertIn('Estoque baixo'.encode(), response.data)
        self.assertNotIn('Lucro hoje'.encode(), response.data)
        self.assertNotIn('Lucro do caixa'.encode(), response.data)
        self.assertNotIn('lucro R$'.encode(), response.data)
        self.assertNotIn('Relatórios'.encode(), response.data)
        self.assertNotIn('Contas próximas'.encode(), response.data)
        self.assertNotIn('Contas vencendo'.encode(), response.data)
        self.assertNotIn('Conta Restrita'.encode(), response.data)

    def test_invalid_login_stays_on_login_page(self):
        response = self.login(password='senha-errada')

        self.assertEqual(response.status_code, 200)
        self.assertIn('Usuário/e-mail ou senha inválidos.'.encode(), response.data)
        self.assertIn('value="master"'.encode(), response.data)
        self.assertIn('Entrar'.encode(), response.data)

    def test_login_accepts_email_and_reports_unknown_identifier(self):
        unknown_response = self.login(username='ninguem@example.com', password='master123')

        self.assertEqual(unknown_response.status_code, 200)
        self.assertIn('Usuário/e-mail ou senha inválidos.'.encode(), unknown_response.data)
        self.assertIn('value="ninguem@example.com"'.encode(), unknown_response.data)

        with self.app.app_context():
            master = User.query.filter_by(username='master').one()
            master.email = 'master@example.com'
            db.session.commit()

        response = self.login(username='master@example.com', password='master123')

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/master'))

    def test_unverified_email_blocks_login_and_allows_confirmation(self):
        with self.app.app_context():
            company = Company(name='Adega Verificar', activation_key='KEY-VERIFY', subscription_renews_at=date.today() + timedelta(days=30))
            db.session.add(company)
            db.session.flush()
            user = User(
                username='semconfirmar',
                email='semconfirmar@example.com',
                email_verified=False,
                role='admin',
                company_id=company.id,
                is_active=True,
            )
            user.set_password('senha123')
            db.session.add(user)
            db.session.commit()

        login_response = self.login(username='semconfirmar', password='senha123', follow_redirects=True)

        self.assertEqual(login_response.status_code, 200)
        self.assertIn('Seu e-mail ainda não foi confirmado.'.encode(), login_response.data)
        self.assertIn('Confirmar e-mail'.encode(), login_response.data)

        resend_response = self.client.post('/verify-email/resend', follow_redirects=True)

        self.assertEqual(resend_response.status_code, 200)
        self.assertIn('Código enviado para o e-mail cadastrado.'.encode(), resend_response.data)
        code = self.app.config['TEST_LAST_VERIFICATION_CODE']

        verify_response = self.client.post('/verify-email', data={'code': code}, follow_redirects=True)

        self.assertEqual(verify_response.status_code, 200)
        self.assertIn('Dashboard'.encode(), verify_response.data)
        with self.app.app_context():
            user = User.query.filter_by(username='semconfirmar').one()
            self.assertTrue(user.email_verified)
            self.assertIsNotNone(user.email_verified_at)

    def test_password_reset_sends_token_and_changes_password(self):
        with self.app.app_context():
            company = Company(name='Adega Reset', activation_key='KEY-RESET', subscription_renews_at=date.today() + timedelta(days=30))
            db.session.add(company)
            db.session.flush()
            user = User(
                username='resetavel',
                email='resetavel@example.com',
                email_verified=True,
                role='admin',
                company_id=company.id,
                is_active=True,
            )
            user.set_password('senha123')
            db.session.add(user)
            db.session.commit()

        request_response = self.client.post('/forgot-password', data={'email': 'resetavel@example.com'}, follow_redirects=True)

        self.assertEqual(request_response.status_code, 200)
        self.assertIn('Se este e-mail estiver cadastrado'.encode(), request_response.data)
        token = self.app.config['TEST_LAST_PASSWORD_RESET_TOKEN']
        with self.app.app_context():
            self.assertEqual(PasswordResetToken.query.count(), 1)

        reset_response = self.client.post(
            f'/reset-password/{token}',
            data={'password': 'nova1234', 'confirm_password': 'nova1234'},
            follow_redirects=True,
        )

        self.assertEqual(reset_response.status_code, 200)
        self.assertIn('Senha redefinida com sucesso'.encode(), reset_response.data)
        with self.app.app_context():
            user = User.query.filter_by(username='resetavel').one()
            token_record = PasswordResetToken.query.one()
            self.assertTrue(user.check_password('nova1234'))
            self.assertTrue(token_record.used)

    def test_authenticated_user_is_redirected_away_from_login(self):
        self.login()

        response = self.client.get('/login')

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/master'))

    def test_logout_redirects_to_login(self):
        self.login()

        get_response = self.client.get('/logout', follow_redirects=True)

        self.assertEqual(get_response.status_code, 405)

        response = self.client.post('/logout', follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('Você saiu do sistema.'.encode(), response.data)
        self.assertIn('Entrar'.encode(), response.data)

    def test_logout_redirects_anonymous_users_to_login(self):
        response = self.client.post('/logout')

        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.location)

    def test_settings_redirect_anonymous_users_to_login(self):
        response = self.client.get('/configuracoes')

        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.location)

    def test_unknown_route_returns_404_page(self):
        response = self.client.get('/rota-inexistente')

        self.assertEqual(response.status_code, 404)

    def test_anonymous_404_is_written_to_security_log_with_request_context(self):
        response = self.client.get('/rota-inexistente?origem=teste')

        self.assertEqual(response.status_code, 404)

        error_log_path = Path(self.app.config['LOG_DIR']) / 'errors.log'
        security_log_path = Path(self.app.config['LOG_DIR']) / 'security.log'
        security_log_content = security_log_path.read_text(encoding='utf-8')

        self.assertNotIn('/rota-inexistente', error_log_path.read_text(encoding='utf-8'))
        self.assertIn('Rota externa não encontrada', security_log_content)
        self.assertIn('/rota-inexistente', security_log_content)
        self.assertIn('origem', security_log_content)
        self.assertIn('X-Request-ID', response.headers)

    def test_master_panel_shows_recent_error_logs(self):
        self.login()
        self.client.get('/rota-inexistente?origem=painel-master')

        response = self.client.get('/master/logs')

        self.assertEqual(response.status_code, 200)
        self.assertIn('Logs recentes'.encode(), response.data)
        self.assertIn('Erro HTTP 404'.encode(), response.data)
        self.assertIn('/rota-inexistente'.encode(), response.data)
        self.assertIn('Request ID'.encode(), response.data)
        self.assertIn('Limpar logs'.encode(), response.data)

    def test_error_log_redacts_sensitive_query_and_form_values(self):
        self.login()

        response = self.client.post(
            '/rota-inexistente?token=query-secret&safe=visible-query',
            data={
                'password': 'form-secret',
                'apiKey': 'api-secret',
                'name': 'visible-form',
            },
        )

        self.assertEqual(response.status_code, 404)
        log_content = (Path(self.app.config['LOG_DIR']) / 'errors.log').read_text(encoding='utf-8')
        self.assertNotIn('query-secret', log_content)
        self.assertNotIn('form-secret', log_content)
        self.assertNotIn('api-secret', log_content)
        self.assertIn('visible-query', log_content)
        self.assertIn('visible-form', log_content)
        self.assertIn('[protegido]', log_content)

    def test_unhandled_exception_is_logged_once_with_request_id(self):
        request_id = 'test-request-id'
        original_handlers = list(self.app.logger.handlers)
        self.app.logger.handlers = [
            handler for handler in original_handlers
            if getattr(handler, '_adega_error_log', False)
        ]

        try:
            with self.app.test_request_context('/__test_unhandled_error'):
                g.request_id = request_id
                g.request_started_at = time.perf_counter()
                try:
                    raise RuntimeError('falha controlada para teste')
                except RuntimeError:
                    self.app.log_exception(sys.exc_info())
        finally:
            self.app.logger.handlers = original_handlers

        log_content = (Path(self.app.config['LOG_DIR']) / 'errors.log').read_text(encoding='utf-8')
        self.assertEqual(log_content.count('Falha não tratada: falha controlada para teste'), 1)
        self.assertNotIn('Exception on /__test_unhandled_error', log_content)
        self.assertIn(request_id, log_content)

    def test_master_panel_does_not_fail_when_tenant_stats_are_temporarily_locked(self):
        self.login()

        with patch('app.routes.auth.tenant_engine', side_effect=SQLAlchemyError('DDL concorrente')):
            response = self.client.get('/master/adegas')

        self.assertEqual(response.status_code, 200)
        self.assertIn('Painel master'.encode(), response.data)
        self.assertIn('Adegas'.encode(), response.data)

    def test_tenant_reference_data_is_not_resynced_on_every_request(self):
        cache_key = 'mysql:test-reference-cache'
        company = type('CompanyStub', (), {'id': 999, 'database_path': 'test_reference_cache'})()
        engine = object()
        tenant_module._reference_sync_times.pop(cache_key, None)
        tenant_module._reference_sync_locks.pop(cache_key, None)

        try:
            with (
                patch('app.tenant.time.monotonic', return_value=1000.0),
                patch('app.tenant.current_user_missing_from_tenant', return_value=False),
                patch('app.tenant.sync_tenant_reference_data') as sync_reference_data,
            ):
                tenant_module.ensure_tenant_reference_data(company, engine, cache_key)
                self.assertEqual(sync_reference_data.call_count, 1)

                tenant_module.ensure_tenant_reference_data(company, engine, cache_key)

            self.assertEqual(
                sync_reference_data.call_count,
                1,
                f'sync_tenant_reference_data foi chamado {sync_reference_data.call_count} vezes, esperado 1',
            )
        finally:
            tenant_module._reference_sync_times.pop(cache_key, None)
            tenant_module._reference_sync_locks.pop(cache_key, None)

    def test_email_alert_checks_are_throttled_per_company(self):
        company_id = 999
        alert_service._email_alert_check_times.pop(company_id, None)

        try:
            with patch('app.services.alert_service.time.monotonic', side_effect=[1.0, 2.0, 62.0]):
                self.assertTrue(alert_service.claim_email_alert_check(company_id, interval_seconds=60))
                self.assertFalse(alert_service.claim_email_alert_check(company_id, interval_seconds=60))
                self.assertTrue(alert_service.claim_email_alert_check(company_id, interval_seconds=60))
        finally:
            alert_service._email_alert_check_times.pop(company_id, None)

    def test_master_can_clear_error_logs(self):
        self.login()
        self.client.get('/rota-inexistente?origem=limpar')
        log_path = Path(self.app.config['LOG_DIR']) / 'errors.log'
        security_log_path = Path(self.app.config['LOG_DIR']) / 'security.log'
        self.assertIn('Erro HTTP 404', log_path.read_text(encoding='utf-8'))
        security_log_path.write_text('evento de segurança\n', encoding='utf-8')

        response = self.client.post('/master/logs/limpar', follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('Logs limpos com sucesso.'.encode(), response.data)
        self.assertEqual(log_path.read_text(encoding='utf-8'), '')
        self.assertEqual(security_log_path.read_text(encoding='utf-8'), '')

    def test_non_master_cannot_clear_error_logs(self):
        with self.app.app_context():
            company = Company(name='Adega Log', activation_key='KEY-LOG')
            db.session.add(company)
            db.session.flush()
            user = User(username='logadmin', role='admin', company_id=company.id, is_active=True)
            user.set_password('123')
            db.session.add(user)
            db.session.commit()

        self.login(username='logadmin', password='123')
        response = self.client.post('/master/logs/limpar', follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('Apenas o usuário master pode acessar este painel.'.encode(), response.data)

    def test_catalog_routes_redirect_anonymous_users_to_login(self):
        for route in ('/catalogo/produtos', '/catalogo/produtos/novo', '/catalogo/categorias'):
            with self.subTest(route=route):
                response = self.client.get(route)

                self.assertEqual(response.status_code, 302)
                self.assertIn('/login', response.location)

    def test_settings_page_loads_for_authenticated_user(self):
        self.login()

        response = self.client.get('/configuracoes')

        self.assertEqual(response.status_code, 200)
        self.assertIn('Configurações'.encode(), response.data)
        self.assertIn('Usuário'.encode(), response.data)
        self.assertIn('Suporte'.encode(), response.data)
        self.assertNotIn('data-settings-tab="appearance"'.encode(), response.data)
        self.assertIn('Claro'.encode(), response.data)
        self.assertIn('Escuro'.encode(), response.data)
        self.assertIn('Sair da conta'.encode(), response.data)
        self.assertIn('Senha criptografada'.encode(), response.data)
        self.assertIn('Email protegido'.encode(), response.data)
        self.assertIn('Importação'.encode(), response.data)
        self.assertIn('Baixar planilha exemplo'.encode(), response.data)

    def test_subscriptions_page_shows_basic_and_pro_plans(self):
        self.login()
        with self.app.app_context():
            company = Company(
                name='Adega Assinante',
                activation_key='',
                subscription_plan='Basic',
                subscription_renews_at=date.today() + timedelta(days=30),
                active=True,
            )
            db.session.add(company)
            db.session.commit()
            company_id = company.id
        self.client.post(f'/master/adegas/{company_id}/acessar', follow_redirects=True)

        response = self.client.get('/assinaturas?planos=1')

        self.assertEqual(response.status_code, 200)
        self.assertIn('Assinatura'.encode(), response.data)
        self.assertIn('Ver planos'.encode(), response.data)
        self.assertIn('Basic'.encode(), response.data)
        self.assertIn('Pro'.encode(), response.data)
        self.assertIn('R$ 89,90'.encode(), response.data)
        self.assertIn('R$ 149,90'.encode(), response.data)
        self.assertIn('Solicitar contratação'.encode(), response.data)
        self.assertNotIn('Key'.encode(), response.data)

    def test_settings_updates_profile_and_email(self):
        self.login()

        profile_response = self.client.post(
            '/configuracoes',
            data={
                'form_type': 'profile',
                'first_name': 'Rafael',
                'last_name': 'Borges',
                'phone': '(11) 99999-0000',
            },
            follow_redirects=True,
        )

        self.assertEqual(profile_response.status_code, 200)
        self.assertIn('Dados do usuário atualizados com sucesso.'.encode(), profile_response.data)

        email_response = self.client.post(
            '/configuracoes',
            data={'form_type': 'email', 'email': 'rafael@example.com'},
            follow_redirects=True,
        )

        self.assertEqual(email_response.status_code, 200)
        self.assertIn('Email atualizado com sucesso.'.encode(), email_response.data)
        self.assertIn('ra***l@example.com'.encode(), email_response.data)
        with self.app.app_context():
            user = User.query.filter_by(username='master').one()
            self.assertEqual(user.first_name, 'Rafael')
            self.assertEqual(user.last_name, 'Borges')
            self.assertEqual(user.phone, '(11) 99999-0000')
            self.assertEqual(user.email, 'rafael@example.com')
            self.assertTrue(user.email_verified)

    def test_settings_email_change_requires_old_email_confirmation(self):
        with self.app.app_context():
            user = User.query.filter_by(username='master').one()
            user.email = 'antigo@example.com'
            user.email_verified = True
            user.email_verified_at = datetime.now()
            db.session.commit()

        self.login()

        request_response = self.client.post(
            '/configuracoes',
            data={'form_type': 'email', 'email': 'novo@example.com'},
            follow_redirects=True,
        )

        self.assertEqual(request_response.status_code, 200)
        self.assertIn('Enviamos um link de confirmação para o e-mail antigo.'.encode(), request_response.data)
        with self.app.app_context():
            user = User.query.filter_by(username='master').one()
            self.assertEqual(user.email, 'antigo@example.com')
            self.assertEqual(EmailChangeRequest.query.count(), 1)

        token = self.app.config['TEST_LAST_EMAIL_CHANGE_TOKEN']
        confirm_response = self.client.get(f'/confirmar-troca-email/{token}', follow_redirects=True)

        self.assertEqual(confirm_response.status_code, 200)
        self.assertIn('E-mail alterado com sucesso.'.encode(), confirm_response.data)
        with self.app.app_context():
            user = User.query.filter_by(username='master').one()
            change_request = EmailChangeRequest.query.one()
            self.assertEqual(user.email, 'novo@example.com')
            self.assertTrue(user.email_verified)
            self.assertTrue(change_request.used)

    def test_settings_updates_email_alerts(self):
        self.login()

        response = self.client.post(
            '/configuracoes',
            data={
                'form_type': 'email_alerts',
                'alert_enabled_product_out_of_stock': 'on',
                'alert_recipients_product_out_of_stock': 'dono@example.com, gerente@example.com',
                'alert_recipients_product_low_stock': '',
                'alert_enabled_payable_due_today': 'on',
                'alert_recipients_payable_due_today': 'financeiro@example.com',
                'alert_recipients_payable_overdue': '',
                'alert_recipients_subscription_expiring': '',
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Alertas por e-mail atualizados com sucesso.'.encode(), response.data)
        with self.app.app_context():
            company_id = self.master_company_id()
            out_stock = EmailAlertSetting.query.filter_by(company_id=company_id, alert_type='product_out_of_stock').one()
            due_today = EmailAlertSetting.query.filter_by(company_id=company_id, alert_type='payable_due_today').one()
            self.assertTrue(out_stock.enabled)
            self.assertEqual(out_stock.recipient_list, ['dono@example.com', 'gerente@example.com'])
            self.assertTrue(due_today.enabled)

    def test_email_alert_for_out_of_stock_product_is_sent_once(self):
        self.login()

        with self.app.app_context():
            company_id = self.master_company_id()
            db.session.add(EmailAlertSetting(
                company_id=company_id,
                alert_type='product_out_of_stock',
                enabled=True,
                recipients='dono@example.com',
            ))
            db.session.add(Product(name='Produto Alerta Email', sale_price=10, stock_quantity=0, min_stock_quantity=1, active=True, company_id=company_id))
            db.session.commit()

        first_response = self.client.get('/dashboard')
        second_response = self.client.get('/dashboard')

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        with self.app.app_context():
            deliveries = EmailAlertDelivery.query.filter_by(alert_type='product_out_of_stock').all()
            self.assertEqual(len(deliveries), 1)
            self.assertIn('dono@example.com', deliveries[0].recipients)

    def test_settings_updates_card_machine_fees(self):
        self.login()

        response = self.client.post(
            '/configuracoes',
            data={
                'form_type': 'card_fees',
                'pix_fee_enabled': 'on',
                'pix_fee_percent': '0,99',
                'debit_fee_enabled': 'on',
                'debit_fee_percent': '1,75',
                'credit_fee_enabled': 'on',
                'credit_fee_percent': '3,20',
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Taxas da maquininha atualizadas com sucesso.'.encode(), response.data)
        with self.app.app_context():
            company = User.query.filter_by(username='master').one().company
            self.assertTrue(company.card_fee_enabled)
            self.assertTrue(company.pix_fee_enabled)
            self.assertTrue(company.debit_fee_enabled)
            self.assertTrue(company.credit_fee_enabled)
            self.assertEqual(company.pix_fee_percent, 0.99)
            self.assertEqual(company.debit_fee_percent, 1.75)
            self.assertEqual(company.credit_fee_percent, 3.20)

    def test_settings_updates_backup_frequency_and_runs_manual_backup(self):
        self.login()

        frequency_response = self.client.post(
            '/configuracoes',
            data={
                'form_type': 'backup_settings',
                'backup_frequency': 'weekly',
            },
            follow_redirects=True,
        )

        self.assertEqual(frequency_response.status_code, 200)
        self.assertIn('Backup'.encode(), frequency_response.data)
        self.assertIn('Configuração de backup salva com sucesso.'.encode(), frequency_response.data)
        with self.app.app_context():
            company = User.query.filter_by(username='master').one().company
            self.assertEqual(company.backup_frequency, 'weekly')

        manual_response = self.client.post(
            '/configuracoes',
            data={'form_type': 'manual_backup'},
            follow_redirects=True,
        )

        self.assertEqual(manual_response.status_code, 200)
        self.assertIn('Backup gerado com sucesso'.encode(), manual_response.data)
        with self.app.app_context():
            company = User.query.filter_by(username='master').one().company
            self.assertEqual(company.backup_last_status, 'success')
            self.assertTrue(Path(company.backup_last_path).exists())
            self.assertIn('Backup Girofy', Path(company.backup_last_path).read_text(encoding='utf-8'))

    def test_settings_updates_password_with_current_password(self):
        self.login()

        wrong_response = self.client.post(
            '/configuracoes',
            data={
                'form_type': 'password',
                'current_password': 'errada',
                'new_password': 'nova123',
                'confirm_password': 'nova123',
            },
            follow_redirects=True,
        )

        self.assertEqual(wrong_response.status_code, 200)
        self.assertIn('Senha atual incorreta.'.encode(), wrong_response.data)

        response = self.client.post(
            '/configuracoes',
            data={
                'form_type': 'password',
                'current_password': 'master123',
                'new_password': 'nova123',
                'confirm_password': 'nova123',
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Senha alterada com sucesso.'.encode(), response.data)
        with self.app.app_context():
            user = User.query.filter_by(username='master').one()
            self.assertTrue(user.check_password('nova123'))

    def test_reports_redirect_anonymous_users_to_login(self):
        response = self.client.get('/relatorios')

        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.location)

    def test_product_list_loads_for_authenticated_user(self):
        self.login()

        with self.app.app_context():
            db.session.add(Product(name='Produto Lucro', cost_price=6, sale_price=10, stock_quantity=3, active=True, company_id=self.master_company_id()))
            db.session.commit()

        response = self.client.get('/catalogo/produtos')

        self.assertEqual(response.status_code, 200)
        self.assertIn('Produtos'.encode(), response.data)
        self.assertIn('Novo produto'.encode(), response.data)
        self.assertNotIn('Importar planilha'.encode(), response.data)
        self.assertIn('Lucro R$ 4,00'.encode(), response.data)
        self.assertIn('40,00%'.encode(), response.data)
        self.assertIn('product-list-layout'.encode(), response.data)
        self.assertIn('category-chip-name'.encode(), response.data)
        self.assertIn('title="Produto Lucro"'.encode(), response.data)

    def test_product_list_is_paginated_and_reuses_kit_options(self):
        self.login()

        with self.app.app_context():
            company_id = self.master_company_id()
            db.session.add_all([
                Product(
                    name=f'Produto {index:03d}',
                    sale_price=float(index),
                    stock_quantity=10,
                    active=True,
                    company_id=company_id,
                )
                for index in range(1, 46)
            ])
            db.session.commit()

        first_page = self.client.get('/catalogo/produtos')
        second_page = self.client.get('/catalogo/produtos?page=2')
        third_page = self.client.get('/catalogo/produtos?page=3')

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(third_page.status_code, 200)
        self.assertEqual(first_page.data.count(b'class="product-summary-row"'), 20)
        self.assertEqual(second_page.data.count(b'class="product-summary-row"'), 20)
        self.assertEqual(third_page.data.count(b'class="product-summary-row"'), 5)
        self.assertIn('Exibindo 1'.encode(), first_page.data)
        self.assertIn('de 45 produtos'.encode(), first_page.data)
        self.assertIn('Próxima'.encode(), first_page.data)
        self.assertIn('Anterior'.encode(), second_page.data)
        self.assertIn('Anterior'.encode(), third_page.data)
        self.assertEqual(first_page.data.count(b'id="kit-product-autocomplete-options"'), 1)
        self.assertNotIn(b'<select class="form-select" id="kit_component_', first_page.data)

    def test_import_products_from_csv_creates_categories_and_products(self):
        self.login()
        csv_content = (
            'categoria;produto;preco_custo;preco_venda;estoque_minimo;estoque_atual\n'
            'Cervejas;Heineken 269ml;3,50;6,00;4;24\n'
            'Destilados;Whisky JF;50.00;89.90;2;7\n'
        )

        response = self.client.post(
            '/catalogo/produtos/importar',
            data={
                'spreadsheet': (io.BytesIO(csv_content.encode('utf-8')), 'produtos.csv'),
                'return_to': 'settings',
            },
            content_type='multipart/form-data',
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Importação concluída: 2 produto(s) criado(s), 0 atualizado(s), 0 linha(s) ignorada(s).'.encode(), response.data)
        self.assertIn('Configurações'.encode(), response.data)
        with self.app.app_context():
            beer = Product.query.filter_by(name='Heineken 269ml').one()
            whisky = Product.query.filter_by(name='Whisky JF').one()
            self.assertEqual(beer.category.name, 'Cervejas')
            self.assertEqual(beer.cost_price, 3.50)
            self.assertEqual(beer.sale_price, 6.00)
            self.assertEqual(beer.min_stock_quantity, 4)
            self.assertEqual(beer.stock_quantity, 24)
            self.assertEqual(whisky.category.name, 'Destilados')
            self.assertEqual(whisky.cost_price, 50.00)
            self.assertEqual(whisky.sale_price, 89.90)
            self.assertEqual(whisky.min_stock_quantity, 2)
            self.assertEqual(whisky.stock_quantity, 7)

    def test_import_template_can_be_downloaded_from_settings(self):
        self.login()

        response = self.client.get('/configuracoes/importacao/modelo')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertIn('attachment;', response.headers.get('Content-Disposition', ''))

    def test_create_edit_toggle_and_delete_product(self):
        self.login()

        create_response = self.client.post(
            '/catalogo/produtos/novo',
            data={
                'name': 'Vinho Tinto',
                'barcode': '789000000001',
                'cost_price': '25,50',
                'sale_price': '39,90',
                'stock_quantity': '12',
                'active': 'on',
            },
            follow_redirects=True,
        )

        self.assertEqual(create_response.status_code, 200)
        self.assertIn('Produto cadastrado com sucesso.'.encode(), create_response.data)
        with self.app.app_context():
            product = Product.query.filter_by(name='Vinho Tinto').first()
            self.assertIsNotNone(product)
            self.assertEqual(product.stock_quantity, 12)
            self.assertEqual(product.sale_price, 39.90)
            product_id = product.id

        edit_response = self.client.post(
            f'/catalogo/produtos/{product_id}/editar',
            data={
                'name': 'Vinho Tinto Reserva',
                'barcode': '789000000001',
                'cost_price': '26,00',
                'sale_price': '44,90',
                'stock_quantity': '10',
                'active': 'on',
            },
            follow_redirects=True,
        )

        self.assertEqual(edit_response.status_code, 200)
        self.assertIn('Produto atualizado com sucesso.'.encode(), edit_response.data)
        self.assertIn('Vinho Tinto Reserva'.encode(), edit_response.data)

        toggle_response = self.client.post(
            f'/catalogo/produtos/{product_id}/alternar-status',
            follow_redirects=True,
        )

        self.assertEqual(toggle_response.status_code, 200)
        self.assertIn('Produto desativado com sucesso.'.encode(), toggle_response.data)
        with self.app.app_context():
            self.assertFalse(db.session.get(Product, product_id).active)

        delete_response = self.client.post(
            f'/catalogo/produtos/{product_id}/excluir',
            follow_redirects=True,
        )

        self.assertEqual(delete_response.status_code, 200)
        self.assertIn('Produto excluído com sucesso.'.encode(), delete_response.data)
        with self.app.app_context():
            self.assertIsNone(db.session.get(Product, product_id))

    def test_create_duplicate_barcode_shows_error(self):
        self.login()

        payload = {
            'name': 'Produto 1',
            'barcode': '123456789',
            'cost_price': '1,00',
            'sale_price': '2,00',
            'stock_quantity': '1',
            'active': 'on',
        }
        self.client.post('/catalogo/produtos/novo', data=payload)
        payload['name'] = 'Produto 2'

        response = self.client.post('/catalogo/produtos/novo', data=payload)

        self.assertEqual(response.status_code, 200)
        self.assertIn('Já existe um produto com este código de barras.'.encode(), response.data)

    def test_product_price_is_saved_as_typed_currency_value(self):
        self.login()

        response = self.client.post(
            '/catalogo/produtos/novo',
            data={
                'name': 'Vodka',
                'barcode': '987654321',
                'cost_price': '20,00',
                'sale_price': '38,00',
                'stock_quantity': '4',
                'active': 'on',
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            product = Product.query.filter_by(name='Vodka').first()
            self.assertIsNotNone(product)
            self.assertEqual(product.sale_price, 38.00)
            self.assertFalse(product.is_kit)
            self.assertIsNone(product.kit_component_product_id)

    def test_kit_product_can_be_created_and_discounts_base_product_stock(self):
        self.login()
        self.open_cash_register()

        with self.app.app_context():
            company_id = self.master_company_id()
            base_product = Product(
                name='Heineken 269ml (1un)',
                sale_price=6,
                stock_quantity=16,
                active=True,
                company_id=company_id,
            )
            db.session.add(base_product)
            db.session.commit()
            base_product_id = base_product.id

        create_response = self.client.post(
            '/catalogo/produtos/novo',
            data={
                'name': 'Heineken 269ml caixa com 8',
                'barcode': 'kit-8',
                'cost_price': '30,00',
                'sale_price': '42,00',
                'stock_quantity': '0',
                'active': 'on',
                'is_kit': 'on',
                'kit_component_product_id': str(base_product_id),
                'kit_component_quantity': '8',
            },
            follow_redirects=True,
        )

        self.assertEqual(create_response.status_code, 200)
        with self.app.app_context():
            kit_product = Product.query.filter_by(name='Heineken 269ml caixa com 8').first()
            self.assertIsNotNone(kit_product)
            self.assertTrue(kit_product.is_kit)
            self.assertEqual(kit_product.effective_stock_quantity, 2)
            kit_product_id = kit_product.id

        sale_response = self.client.post(
            '/vendas/nova',
            data={
                'product_id[]': [str(kit_product_id)],
                'quantity[]': ['1'],
                'payment_money': '42,00',
            },
            follow_redirects=True,
        )

        self.assertEqual(sale_response.status_code, 200)
        self.assertIn('Venda finalizada com sucesso.'.encode(), sale_response.data)
        with self.app.app_context():
            self.assertEqual(db.session.get(Product, base_product_id).stock_quantity, 8)
            self.assertEqual(db.session.get(Product, kit_product_id).stock_quantity, 0)

    def test_kit_sale_requires_enough_base_product_stock(self):
        self.login()
        self.open_cash_register()

        with self.app.app_context():
            company_id = self.master_company_id()
            base_product = Product(
                name='Heineken unidade',
                sale_price=6,
                stock_quantity=7,
                active=True,
                company_id=company_id,
            )
            kit_product = Product(
                name='Heineken kit 8',
                sale_price=42,
                stock_quantity=0,
                active=True,
                is_kit=True,
                kit_component_quantity=8,
                company_id=company_id,
            )
            db.session.add_all([base_product, kit_product])
            db.session.flush()
            kit_product.kit_component_product_id = base_product.id
            db.session.commit()
            kit_product_id = kit_product.id

        response = self.client.post(
            '/vendas/nova',
            data={
                'product_id[]': [str(kit_product_id)],
                'quantity[]': ['1'],
                'payment_money': '42,00',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Estoque insuficiente para Heineken unidade.'.encode(), response.data)
        with self.app.app_context():
            self.assertEqual(Sale.query.count(), 0)

    def test_product_can_be_quick_updated_from_expanded_row(self):
        self.login()

        with self.app.app_context():
            company_id = self.master_company_id()
            product = Product(
                name='Produto Antigo',
                barcode='555',
                cost_price=10,
                sale_price=20,
                stock_quantity=2,
                active=True,
                company_id=company_id,
            )
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        response = self.client.post(
            f'/catalogo/produtos/{product_id}/atualizar',
            data={
                'name': 'Produto Novo',
                'barcode': '555',
                'cost_price': '12,00',
                'sale_price': '38,00',
                'stock_quantity': '9',
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Produto atualizado com sucesso.'.encode(), response.data)
        with self.app.app_context():
            product = db.session.get(Product, product_id)
            self.assertEqual(product.name, 'Produto Novo')
            self.assertEqual(product.sale_price, 38.00)
            self.assertEqual(product.stock_quantity, 9)

    def test_category_can_be_created_and_used_by_product(self):
        self.login()

        category_response = self.client.post(
            '/catalogo/categorias',
            data={'name': 'Bebidas'},
            follow_redirects=True,
        )

        self.assertEqual(category_response.status_code, 200)
        self.assertIn('Categoria cadastrada com sucesso.'.encode(), category_response.data)
        self.assertIn('Bebidas'.encode(), category_response.data)

    def test_category_filters_by_search_usage_and_sort(self):
        self.login()

        with self.app.app_context():
            company_id = User.query.filter_by(username='master').one().company_id
            wines = Category(name='Vinhos', company_id=company_id)
            empty = Category(name='Destilados', company_id=company_id)
            beers = Category(name='Cervejas', company_id=company_id)
            db.session.add_all([wines, empty, beers])
            db.session.flush()
            db.session.add_all([
                Product(name='Vinho 1', category_id=wines.id, company_id=company_id),
                Product(name='Vinho 2', category_id=wines.id, company_id=company_id),
                Product(name='Cerveja 1', category_id=beers.id, company_id=company_id),
            ])
            db.session.commit()

        response = self.client.get(
            '/catalogo/categorias',
            query_string={'q': 'vin', 'usage': 'with_products', 'sort': 'products_desc'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Vinhos'.encode(), response.data)
        self.assertNotIn('Destilados'.encode(), response.data)
        self.assertNotIn('Cervejas'.encode(), response.data)

        empty_response = self.client.get('/catalogo/categorias', query_string={'usage': 'empty'})

        self.assertEqual(empty_response.status_code, 200)
        self.assertIn('Destilados'.encode(), empty_response.data)
        self.assertNotIn('Vinhos'.encode(), empty_response.data)

    def test_category_can_be_quick_updated_from_expanded_row(self):
        self.login()

        with self.app.app_context():
            category = Category(name='Antiga', company_id=self.master_company_id())
            db.session.add(category)
            db.session.commit()
            category_id = category.id

        response = self.client.post(
            f'/catalogo/categorias/{category_id}/atualizar',
            data={'name': 'Nova'},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Categoria atualizada com sucesso.'.encode(), response.data)
        with self.app.app_context():
            self.assertEqual(db.session.get(Category, category_id).name, 'Nova')

    def test_product_filters_by_category_stock_price_and_sort(self):
        self.login()

        with self.app.app_context():
            company_id = self.master_company_id()
            wines = Category(name='Vinhos', company_id=company_id)
            beers = Category(name='Cervejas', company_id=company_id)
            db.session.add_all([wines, beers])
            db.session.flush()
            db.session.add_all([
                Product(name='Vinho Barato', category_id=wines.id, sale_price=30, stock_quantity=3, min_stock_quantity=5, active=True, company_id=company_id),
                Product(name='Vinho Premium', category_id=wines.id, sale_price=120, stock_quantity=8, active=True, company_id=company_id),
                Product(name='Cerveja Lager', category_id=beers.id, sale_price=8, stock_quantity=0, active=True, company_id=company_id),
                Product(name='Produto Inativo', category_id=wines.id, sale_price=50, stock_quantity=5, active=False, company_id=company_id),
            ])
            db.session.commit()
            wines_id = wines.id

        response = self.client.get(
            '/catalogo/produtos',
            query_string={
                'status': 'active',
                'category_id': str(wines_id),
                'stock': 'low',
                'min_price': '20,00',
                'max_price': '80,00',
                'sort': 'price_desc',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Vinho Barato'.encode(), response.data)
        self.assertNotIn('<span>Vinho Premium</span>'.encode(), response.data)
        self.assertNotIn('<span>Cerveja Lager</span>'.encode(), response.data)
        self.assertNotIn('<span>Produto Inativo</span>'.encode(), response.data)

    def test_sales_pages_load_for_authenticated_user(self):
        self.login()
        self.open_cash_register()

        response = self.client.get('/vendas')
        new_response = self.client.get('/vendas/nova')

        self.assertEqual(response.status_code, 200)
        self.assertIn('Realizar Venda - F3'.encode(), response.data)
        self.assertIn('sales-date-column'.encode(), response.data)
        self.assertIn('sales-total-column'.encode(), response.data)
        self.assertIn('sales-payment-column'.encode(), response.data)
        self.assertEqual(new_response.status_code, 200)
        self.assertIn('Finalizar venda'.encode(), new_response.data)
        self.assertIn('Escolha uma ou mais formas.'.encode(), new_response.data)
        self.assertIn('data-sale-picker-search'.encode(), new_response.data)
        self.assertIn('data-sale-quantity-modal'.encode(), new_response.data)
        self.assertIn('data-discount-new-total'.encode(), new_response.data)

    def test_sales_page_shows_only_today_sales(self):
        self.login()
        self.open_cash_register()

        with self.app.app_context():
            company_id = self.master_company_id()
            user = User.query.filter_by(username='master').one()
            cash_register = CashRegister.query.filter_by(company_id=company_id, status='open').one()
            today_sale = Sale(
                created_at=datetime.now().replace(hour=10, minute=0, second=0, microsecond=0),
                total_amount=11,
                final_amount=11,
                payment_status='paid',
                user_id=user.id,
                company_id=company_id,
                cash_register_id=cash_register.id,
            )
            old_sale = Sale(
                created_at=datetime.now() - timedelta(days=1),
                total_amount=99,
                final_amount=99,
                payment_status='paid',
                user_id=user.id,
                company_id=company_id,
                cash_register_id=cash_register.id,
            )
            db.session.add_all([today_sale, old_sale])
            db.session.flush()
            today_id = today_sale.id
            old_id = old_sale.id
            db.session.add_all([
                Payment(sale_id=today_id, method='money', amount=11),
                Payment(sale_id=old_id, method='pix', amount=99),
            ])
            db.session.commit()

        response = self.client.get('/vendas')

        self.assertEqual(response.status_code, 200)
        self.assertIn('histórico de vendas de hoje'.encode(), response.data)
        self.assertIn(f'#{today_id}'.encode(), response.data)
        self.assertNotIn(f'#{old_id}'.encode(), response.data)
        self.assertNotIn('R$ 99,00'.encode(), response.data)

    def test_global_f3_sale_shortcut_is_available_on_main_operational_pages(self):
        self.login()
        self.open_cash_register()

        for route in ('/dashboard', '/vendas', '/caixa'):
            response = self.client.get(route)
            self.assertEqual(response.status_code, 200)
            self.assertIn('data-global-new-sale'.encode(), response.data)
            self.assertIn('Realizar Venda - F3'.encode(), response.data)

        sale_response = self.client.get('/vendas/nova')
        self.assertEqual(sale_response.status_code, 200)
        self.assertNotIn('data-global-new-sale'.encode(), sale_response.data)
        self.assertIn('Aplicar desconto'.encode(), sale_response.data)

        script_response = self.client.get('/static/js/main.js')
        self.assertEqual(script_response.status_code, 200)
        self.assertIn("target.matches('input, textarea, select')".encode(), script_response.data)
        script_response.close()

    def test_sale_rejects_discount_greater_than_subtotal(self):
        self.login()
        self.open_cash_register()

        with self.app.app_context():
            product = Product(
                name='Produto com desconto',
                barcode='7891234567890',
                sale_price=10,
                stock_quantity=5,
                active=True,
                company_id=self.master_company_id(),
            )
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        response = self.client.post(
            '/vendas/nova',
            data={
                'product_id[]': [str(product_id)],
                'quantity[]': ['1'],
                'discount_amount': '11,00',
                'payment_pix': '10,00',
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('O desconto não pode ser maior que o subtotal de R$ 10,00.'.encode(), response.data)
        self.assertIn('data-barcode="7891234567890"'.encode(), response.data)
        with self.app.app_context():
            self.assertEqual(Sale.query.count(), 0)

    def test_reports_show_sales_totals_for_selected_period(self):
        self.login()
        self.open_cash_register()

        with self.app.app_context():
            product = Product(name='Tequila', cost_price=60, sale_price=100, stock_quantity=5, min_stock_quantity=3, active=True, company_id=self.master_company_id())
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        sale_response = self.client.post(
            '/vendas/nova',
            data={
                'product_id[]': [str(product_id)],
                'quantity[]': ['1'],
                'discount_amount': '10,00',
                'payment_pix': '90,00',
            },
            follow_redirects=True,
        )

        self.assertEqual(sale_response.status_code, 200)

        with self.app.app_context():
            saved_sale = Sale.query.one()
            sale_date = saved_sale.created_at.date().isoformat()
            self.assertEqual(saved_sale.discount_amount, 10.0)
            self.assertEqual(saved_sale.final_amount, 90.0)

        response = self.client.get(
            '/relatorios',
            query_string={'period': 'custom', 'start_date': sale_date, 'end_date': sale_date},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Relatórios'.encode(), response.data)
        self.assertIn('Gráfico de vendas'.encode(), response.data)
        self.assertIn('Total vendido por período'.encode(), response.data)
        self.assertIn('data-report-chart-tooltip'.encode(), response.data)
        self.assertIn('data-chart-value="R$ 90,00"'.encode(), response.data)
        self.assertIn('Total vendido'.encode(), response.data)
        self.assertIn('R$ 90,00'.encode(), response.data)
        self.assertIn('Descontos'.encode(), response.data)
        self.assertIn('R$ 10,00'.encode(), response.data)
        self.assertIn('Lucro'.encode(), response.data)
        self.assertIn('R$ 30,00'.encode(), response.data)
        self.assertIn('Pix'.encode(), response.data)
        self.assertIn('Tequila'.encode(), response.data)

        monthly_response = self.client.get('/relatorios', query_string={'period': 'monthly'})
        self.assertEqual(monthly_response.status_code, 200)
        self.assertIn('report-chart--very-dense'.encode(), monthly_response.data)
        self.assertIn('--chart-columns: 31'.encode(), monthly_response.data)

    def test_reports_auto_periods_use_rolling_date_ranges(self):
        self.login()

        with self.app.app_context():
            company_id = self.master_company_id()
            product = Product(name='Saquê', cost_price=20, sale_price=50, stock_quantity=6, active=True, company_id=company_id)
            sale = Sale(
                created_at=datetime.now() - timedelta(days=5),
                total_amount=50,
                final_amount=50,
                payment_status='paid',
                company_id=company_id,
            )
            db.session.add_all([product, sale])
            db.session.flush()
            db.session.add_all([
                SaleItem(
                    sale_id=sale.id,
                    product_id=product.id,
                    quantity=1,
                    unit_price=50,
                    unit_cost_price=20,
                    total_price=50,
                    profit_amount=30,
                ),
                Payment(sale_id=sale.id, method='money', amount=50),
            ])
            db.session.commit()

        daily_response = self.client.get('/relatorios', query_string={'period': 'daily'})
        weekly_response = self.client.get('/relatorios', query_string={'period': 'weekly'})
        monthly_response = self.client.get('/relatorios', query_string={'period': 'monthly'})
        annual_response = self.client.get('/relatorios', query_string={'period': 'annual'})

        self.assertEqual(daily_response.status_code, 200)
        self.assertNotIn('Saquê'.encode(), daily_response.data)
        self.assertIn('Saquê'.encode(), weekly_response.data)
        self.assertIn('Últimos 7 dias'.encode(), weekly_response.data)
        self.assertIn('Saquê'.encode(), monthly_response.data)
        self.assertIn('Últimos 30 dias'.encode(), monthly_response.data)
        self.assertIn('Saquê'.encode(), annual_response.data)
        self.assertIn('Último ano'.encode(), annual_response.data)

    def test_daily_report_shows_empty_24_hour_activity(self):
        self.login()

        response = self.client.get('/relatorios', query_string={
            'period': 'daily',
            'start_date': '2026-07-07',
            'chart_metric': 'quantity',
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn('Vendas por horário'.encode(), response.data)
        self.assertIn('--chart-columns: 24'.encode(), response.data)
        self.assertEqual(response.data.count(b'data-chart-count='), 24)
        self.assertIn('Sem vendas'.encode(), response.data)
        self.assertNotIn('report-chart-peak-badge'.encode(), response.data)

    def test_daily_report_calculates_quantity_and_revenue_peak_hours(self):
        self.login()

        with self.app.app_context():
            company_id = self.master_company_id()
            db.session.add_all([
                Sale(company_id=company_id, created_at=datetime(2026, 7, 7, 18, 10), total_amount=80, final_amount=80, payment_status='paid'),
                Sale(company_id=company_id, created_at=datetime(2026, 7, 7, 18, 10), total_amount=70, final_amount=70, payment_status='paid'),
                Sale(company_id=company_id, created_at=datetime(2026, 7, 7, 20, 5), total_amount=300, final_amount=300, payment_status='paid'),
            ])
            db.session.commit()

        quantity_response = self.client.get('/relatorios', query_string={
            'period': 'daily',
            'start_date': '2026-07-07',
            'chart_metric': 'quantity',
        })
        revenue_response = self.client.get('/relatorios', query_string={
            'period': 'daily',
            'start_date': '2026-07-07',
            'chart_metric': 'revenue',
        })

        self.assertEqual(quantity_response.status_code, 200)
        self.assertIn('18:00 às 18:59'.encode(), quantity_response.data)
        self.assertIn('2 vendas'.encode(), quantity_response.data)
        self.assertIn('data-chart-count="2" data-chart-peak="true"'.encode(), quantity_response.data)
        self.assertIn('20:00 às 20:59'.encode(), quantity_response.data)
        self.assertIn('R$ 300,00'.encode(), quantity_response.data)
        self.assertIn('Melhor hora em quantidade'.encode(), quantity_response.data)
        self.assertIn('Melhor hora em faturamento'.encode(), quantity_response.data)

        self.assertEqual(revenue_response.status_code, 200)
        self.assertIn(
            'data-chart-count="1" data-chart-peak="true"'.encode(),
            revenue_response.data,
        )

    def test_daily_report_aggregates_many_sales_in_same_hour(self):
        self.login()

        with self.app.app_context():
            company_id = self.master_company_id()
            db.session.add_all([
                Sale(
                    company_id=company_id,
                    created_at=datetime(2026, 7, 6, 13, minute % 60),
                    total_amount=5,
                    final_amount=5,
                    payment_status='paid',
                )
                for minute in range(120)
            ])
            db.session.commit()

        response = self.client.get('/relatorios', query_string={
            'period': 'daily',
            'start_date': '2026-07-06',
            'chart_metric': 'quantity',
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-chart-count="120" data-chart-peak="true"'.encode(), response.data)
        self.assertIn('120 vendas'.encode(), response.data)
        self.assertIn('R$ 600,00'.encode(), response.data)

    def test_create_sale_with_multiple_products_and_payment_methods(self):
        self.login()
        self.open_cash_register()

        with self.app.app_context():
            company_id = self.master_company_id()
            wine = Product(name='Vinho', sale_price=40, stock_quantity=10, active=True, company_id=company_id)
            beer = Product(name='Cerveja', sale_price=8, stock_quantity=20, active=True, company_id=company_id)
            db.session.add_all([wine, beer])
            db.session.commit()
            wine_id = wine.id
            beer_id = beer.id

        response = self.client.post(
            '/vendas/nova',
            data={
                'product_id[]': [str(wine_id), str(beer_id)],
                'quantity[]': ['2', '3'],
                'payment_money': '50,00',
                'payment_pix': '54,00',
                'payment_debit': '',
                'payment_credit': '',
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Venda finalizada com sucesso.'.encode(), response.data)
        self.assertIn('Troco'.encode(), response.data)

        with self.app.app_context():
            sale = Sale.query.one()
            self.assertEqual(round(sale.final_amount, 2), 104.00)
            self.assertIsNotNone(sale.cash_register_id)
            self.assertEqual(SaleItem.query.count(), 2)
            self.assertEqual(Payment.query.count(), 2)
            self.assertEqual(db.session.get(Product, wine_id).stock_quantity, 8)
            self.assertEqual(db.session.get(Product, beer_id).stock_quantity, 17)

    def test_sale_uses_registered_product_price(self):
        self.login()
        self.open_cash_register()

        with self.app.app_context():
            product = Product(name='Licor', sale_price=38.00, stock_quantity=5, active=True, company_id=self.master_company_id())
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        response = self.client.post(
            '/vendas/nova',
            data={
                'product_id[]': [str(product_id)],
                'quantity[]': ['1'],
                'payment_money': '38,00',
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            sale = Sale.query.one()
            self.assertEqual(sale.final_amount, 38.00)

    def test_debit_card_fee_discounts_product_final_profit(self):
        self.login()
        self.open_cash_register()

        with self.app.app_context():
            company = User.query.filter_by(username='master').one().company
            company.debit_fee_enabled = True
            company.debit_fee_percent = 2.0
            company.credit_fee_percent = 4.0
            product = Product(name='Combo', cost_price=60.00, sale_price=100.00, stock_quantity=5, active=True, company_id=company.id)
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        response = self.client.post(
            '/vendas/nova',
            data={
                'product_id[]': [str(product_id)],
                'quantity[]': ['1'],
                'payment_debit': '100,00',
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Lucro final'.encode(), response.data)
        with self.app.app_context():
            item = SaleItem.query.one()
            self.assertEqual(item.profit_amount, 38.00)
            sale = Sale.query.one()
            self.assertEqual(sale.final_amount, 100.00)

    def test_pix_fee_only_discounts_profit_when_enabled(self):
        self.login()
        self.open_cash_register()

        with self.app.app_context():
            company = User.query.filter_by(username='master').one().company
            company.pix_fee_enabled = True
            company.pix_fee_percent = 1.0
            product = Product(name='Pix Produto', cost_price=50.00, sale_price=100.00, stock_quantity=5, active=True, company_id=company.id)
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        response = self.client.post(
            '/vendas/nova',
            data={
                'product_id[]': [str(product_id)],
                'quantity[]': ['1'],
                'payment_pix': '100,00',
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            item = SaleItem.query.one()
            self.assertEqual(item.profit_amount, 49.00)

    def test_sale_rejects_invalid_product_id_without_server_error(self):
        self.login()
        self.open_cash_register()

        response = self.client.post(
            '/vendas/nova',
            data={
                'product_id[]': ['produto-invalido'],
                'quantity[]': ['1'],
                'payment_money': '10,00',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Selecione um produto válido'.encode(), response.data)
        with self.app.app_context():
            self.assertEqual(Sale.query.count(), 0)

    def test_sale_can_be_finished_with_discount_amount(self):
        self.login()
        self.open_cash_register()

        with self.app.app_context():
            product = Product(name='Vodka', cost_price=6.00, sale_price=10.00, stock_quantity=5, active=True, company_id=self.master_company_id())
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        response = self.client.post(
            '/vendas/nova',
            data={
                'product_id[]': [str(product_id)],
                'quantity[]': ['1'],
                'discount_amount': '1,00',
                'payment_money': '9,00',
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Venda finalizada com sucesso.'.encode(), response.data)
        self.assertIn('Desconto'.encode(), response.data)
        self.assertIn('Lucro'.encode(), response.data)
        self.assertIn('R$ 3,00'.encode(), response.data)
        with self.app.app_context():
            sale = Sale.query.one()
            self.assertEqual(sale.total_amount, 10.00)
            self.assertEqual(sale.discount_amount, 1.00)
            self.assertEqual(sale.final_amount, 9.00)
            sale_item = SaleItem.query.one()
            self.assertEqual(sale_item.unit_cost_price, 6.00)
            self.assertEqual(sale_item.profit_amount, 4.00)

        cash_response = self.client.get('/caixa')

        self.assertEqual(cash_response.status_code, 200)
        self.assertIn('Lucro do caixa'.encode(), cash_response.data)
        self.assertIn('R$ 3,00'.encode(), cash_response.data)

    def test_sale_requires_full_payment(self):
        self.login()
        self.open_cash_register()

        with self.app.app_context():
            product = Product(name='Whisky', sale_price=100, stock_quantity=5, active=True, company_id=self.master_company_id())
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        response = self.client.post(
            '/vendas/nova',
            data={
                'product_id[]': [str(product_id)],
                'quantity[]': ['1'],
                'payment_money': '80,00',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Falta pagar R$ 20,00.'.encode(), response.data)
        self.assertIn(f'value="{product_id}"'.encode(), response.data)
        self.assertIn('value="Whisky"'.encode(), response.data)
        self.assertIn('value="1"'.encode(), response.data)
        self.assertIn('value="80,00"'.encode(), response.data)
        with self.app.app_context():
            self.assertEqual(Sale.query.count(), 0)

    def test_sale_keeps_order_when_stock_is_insufficient(self):
        self.login()
        self.open_cash_register()

        with self.app.app_context():
            product = Product(name='Gin', sale_price=90, stock_quantity=1, active=True, company_id=self.master_company_id())
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        response = self.client.post(
            '/vendas/nova',
            data={
                'product_id[]': [str(product_id)],
                'quantity[]': ['3'],
                'payment_money': '270,00',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Estoque insuficiente para Gin.'.encode(), response.data)
        self.assertIn(f'value="{product_id}"'.encode(), response.data)
        self.assertIn('value="Gin"'.encode(), response.data)
        self.assertIn('value="3"'.encode(), response.data)
        self.assertIn('value="270,00"'.encode(), response.data)
        with self.app.app_context():
            self.assertEqual(Sale.query.count(), 0)

    def test_company_can_allow_sale_with_negative_stock_and_cash_history_keeps_details(self):
        self.login()
        self.open_cash_register()

        with self.app.app_context():
            company = db.session.get(Company, self.master_company_id())
            company.allow_negative_stock = True
            product = Product(
                name='Produto sem saldo',
                sale_price=10,
                stock_quantity=0,
                active=True,
                company_id=company.id,
            )
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        sale_response = self.client.post(
            '/vendas/nova',
            data={
                'product_id[]': [str(product_id)],
                'quantity[]': ['2'],
                'payment_money': '20,00',
            },
            follow_redirects=True,
        )

        self.assertEqual(sale_response.status_code, 200)
        self.assertIn('Venda finalizada com sucesso.'.encode(), sale_response.data)
        self.assertIn('Estoque insuficiente permitido.'.encode(), sale_response.data)
        with self.app.app_context():
            self.assertEqual(db.session.get(Product, product_id).stock_quantity, -2)
            sale = Sale.query.one()
            self.assertEqual(len(sale.items), 1)
            self.assertEqual(len(sale.payments), 1)
            cash_register_id = CashRegister.query.one().id

        close_response = self.client.post(
            '/caixa/fechar',
            data={'closing_amount': '120,00'},
            follow_redirects=True,
        )
        self.assertEqual(close_response.status_code, 200)
        self.assertIn('Caixa fechado com sucesso.'.encode(), close_response.data)

        cash_response = self.client.get('/caixa')
        self.assertIn(f'>#{cash_register_id}<'.encode(), cash_response.data)
        self.assertIn('data-cash-register-toggle'.encode(), cash_response.data)
        self.assertIn('Formas de pagamento'.encode(), cash_response.data)
        self.assertIn('Venda #1'.encode(), cash_response.data)
        self.assertIn('Nenhuma sangria ou suprimento'.encode(), cash_response.data)

    def test_admin_can_configure_negative_stock_rule(self):
        self.login()

        response = self.client.post(
            '/configuracoes',
            data={
                'form_type': 'inventory_settings',
                'allow_negative_stock': 'on',
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Regras de estoque atualizadas com sucesso.'.encode(), response.data)
        with self.app.app_context():
            company = db.session.get(Company, self.master_company_id())
            self.assertTrue(company.allow_negative_stock)

    def test_cash_register_can_be_opened_and_closed(self):
        self.login()

        open_response = self.client.post(
            '/caixa/abrir',
            data={'opening_amount': '150,50'},
            follow_redirects=True,
        )

        self.assertEqual(open_response.status_code, 200)
        self.assertIn('Caixa aberto com sucesso.'.encode(), open_response.data)
        self.assertIn('Realizar Venda - F3'.encode(), open_response.data)
        with self.app.app_context():
            cash_register = CashRegister.query.one()
            self.assertEqual(cash_register.status, 'open')
            self.assertEqual(cash_register.opening_amount, 150.50)

        close_response = self.client.post(
            '/caixa/fechar',
            data={'closing_amount': '220,00'},
            follow_redirects=True,
        )

        self.assertEqual(close_response.status_code, 200)
        self.assertIn('O valor está excedido em R$ 69,50. Valor esperado: R$ 150,50.'.encode(), close_response.data)
        with self.app.app_context():
            cash_register = CashRegister.query.one()
            self.assertEqual(cash_register.status, 'open')

        close_response = self.client.post(
            '/caixa/fechar',
            data={'closing_amount': '150,50'},
            follow_redirects=True,
        )

        self.assertEqual(close_response.status_code, 200)
        self.assertIn('Caixa fechado com sucesso.'.encode(), close_response.data)
        with self.app.app_context():
            cash_register = CashRegister.query.one()
            self.assertEqual(cash_register.status, 'closed')
            self.assertEqual(cash_register.closing_amount, 150.50)

    def test_master_accessing_other_company_can_open_cash_register_and_sell(self):
        self.login()

        with self.app.app_context():
            company = Company(
                name='Adega Externa',
                active=True,
                activation_key='EXTERNAL-KEY',
                subscription_renews_at=date.today() + timedelta(days=30),
            )
            db.session.add(company)
            db.session.commit()
            company_id = company.id

        access_response = self.client.post(f'/master/adegas/{company_id}/acessar', follow_redirects=True)
        self.assertEqual(access_response.status_code, 200)
        self.assertIn('Painel master'.encode(), access_response.data)
        self.assertIn('Você está acessando a adega'.encode(), access_response.data)
        self.assertIn('Abrir painel master'.encode(), access_response.data)

        open_response = self.client.post(
            '/caixa/abrir',
            data={'opening_amount': '0,00'},
            follow_redirects=True,
        )

        self.assertEqual(open_response.status_code, 200)
        self.assertIn('Caixa aberto com sucesso.'.encode(), open_response.data)

        with self.app.app_context():
            product = Product(name='Produto Externo', cost_price=5, sale_price=10, stock_quantity=2, active=True, company_id=company_id)
            db.session.add(product)
            db.session.commit()
            product_id = product.id
            cash_register = CashRegister.query.filter_by(company_id=company_id).one()
            self.assertIsNone(cash_register.user_id)

        sale_response = self.client.post(
            '/vendas/nova',
            data={
                'product_id[]': [str(product_id)],
                'quantity[]': ['1'],
                'payment_money': '10,00',
            },
            follow_redirects=True,
        )

        self.assertEqual(sale_response.status_code, 200)
        self.assertIn('Venda finalizada com sucesso.'.encode(), sale_response.data)
        with self.app.app_context():
            sale = Sale.query.filter_by(company_id=company_id).one()
            self.assertIsNone(sale.user_id)

    def test_cash_register_closes_only_with_opening_amount_plus_sales(self):
        self.login()
        self.open_cash_register(amount='100,00')

        with self.app.app_context():
            product = Product(name='Rum', cost_price=20, sale_price=50, stock_quantity=5, active=True, company_id=self.master_company_id())
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        sale_response = self.client.post(
            '/vendas/nova',
            data={
                'product_id[]': [str(product_id)],
                'quantity[]': ['1'],
                'payment_money': '50,00',
            },
            follow_redirects=True,
        )

        self.assertEqual(sale_response.status_code, 200)

        wrong_close_response = self.client.post(
            '/caixa/fechar',
            data={'closing_amount': '149,99'},
            follow_redirects=True,
        )

        self.assertEqual(wrong_close_response.status_code, 200)
        self.assertIn('Falta R$ 0,01 para fechar o caixa. Valor esperado: R$ 150,00.'.encode(), wrong_close_response.data)
        with self.app.app_context():
            self.assertEqual(CashRegister.query.one().status, 'open')

        close_response = self.client.post(
            '/caixa/fechar',
            data={'closing_amount': '150,00'},
            follow_redirects=True,
        )

        self.assertEqual(close_response.status_code, 200)
        self.assertIn('Caixa fechado com sucesso.'.encode(), close_response.data)
        with self.app.app_context():
            cash_register = CashRegister.query.one()
            self.assertEqual(cash_register.status, 'closed')
            self.assertEqual(cash_register.closing_amount, 150.00)

    def test_operator_cash_register_hides_financial_totals(self):
        self.login()
        with self.app.app_context():
            company_id = self.master_company_id()
            operator = User(username='caixa_sem_total', role='operator', company_id=company_id, is_active=True)
            operator.set_password('123')
            operator.can_manage_cash_register = True
            operator.can_manage_sales = True
            operator.can_view_reports = False
            cash_register = CashRegister(
                company_id=company_id,
                user_id=1,
                status='closed',
                opening_amount=100,
                closing_amount=150,
                opened_at=datetime(2026, 7, 1, 8, 30),
                closed_at=datetime(2026, 7, 1, 18, 45),
            )
            sale = Sale(
                company_id=company_id,
                cash_register=cash_register,
                total_amount=50,
                final_amount=50,
                payment_status='paid',
                created_at=datetime(2026, 7, 1, 12, 0),
            )
            db.session.add_all([operator, cash_register, sale])
            db.session.commit()
            cash_register_id = cash_register.id

        self.client.post('/logout')
        self.login(username='caixa_sem_total', password='123')

        cash_response = self.client.get('/caixa')
        detail_response = self.client.get(f'/caixa/{cash_register_id}')
        dashboard_response = self.client.get('/dashboard')

        self.assertEqual(cash_response.status_code, 200)
        self.assertIn('01/07/2026'.encode(), cash_response.data)
        self.assertIn('08:30'.encode(), cash_response.data)
        self.assertIn('18:45'.encode(), cash_response.data)
        self.assertNotIn('Total vendido'.encode(), cash_response.data)
        self.assertNotIn('Lucro'.encode(), cash_response.data)
        self.assertNotIn('Valor final'.encode(), cash_response.data)

        self.assertEqual(detail_response.status_code, 200)
        self.assertIn('Abertura'.encode(), detail_response.data)
        self.assertIn('Fechamento'.encode(), detail_response.data)
        self.assertNotIn('Total vendido'.encode(), detail_response.data)
        self.assertNotIn('Lucro'.encode(), detail_response.data)
        self.assertNotIn('Valor inicial'.encode(), detail_response.data)
        self.assertNotIn('Valor final'.encode(), detail_response.data)
        self.assertNotIn('Formas vendidas'.encode(), detail_response.data)
        self.assertNotIn('Produtos mais vendidos'.encode(), detail_response.data)

        self.assertNotIn('Vendas no caixa R$'.encode(), dashboard_response.data)

    def test_closed_cash_register_detail_shows_payments_peak_hour_and_top_products(self):
        self.login()
        self.open_cash_register(amount='100,00')

        with self.app.app_context():
            company_id = self.master_company_id()
            rum = Product(name='Rum Especial', cost_price=20, sale_price=50, stock_quantity=5, active=True, company_id=company_id)
            beer = Product(name='Cerveja Pilsen', cost_price=5, sale_price=10, stock_quantity=10, active=True, company_id=company_id)
            db.session.add_all([rum, beer])
            db.session.commit()
            rum_id = rum.id
            beer_id = beer.id

        first_sale = self.client.post(
            '/vendas/nova',
            data={
                'product_id[]': [str(rum_id)],
                'quantity[]': ['1'],
                'payment_money': '50,00',
            },
            follow_redirects=True,
        )
        second_sale = self.client.post(
            '/vendas/nova',
            data={
                'product_id[]': [str(beer_id)],
                'quantity[]': ['3'],
                'payment_pix': '30,00',
            },
            follow_redirects=True,
        )

        self.assertEqual(first_sale.status_code, 200)
        self.assertEqual(second_sale.status_code, 200)

        with self.app.app_context():
            sales = Sale.query.order_by(Sale.id.asc()).all()
            sales[0].created_at = datetime(2026, 6, 30, 18, 10)
            sales[1].created_at = datetime(2026, 6, 30, 18, 35)
            db.session.commit()
            cash_register_id = CashRegister.query.one().id

        close_response = self.client.post(
            '/caixa/fechar',
            data={'closing_amount': '180,00'},
            follow_redirects=True,
        )

        self.assertEqual(close_response.status_code, 200)
        self.assertIn(f'/caixa/{cash_register_id}'.encode(), close_response.data)

        detail_response = self.client.get(f'/caixa/{cash_register_id}')

        self.assertEqual(detail_response.status_code, 200)
        self.assertIn('Detalhes do caixa'.encode(), detail_response.data)
        self.assertIn('Formas vendidas'.encode(), detail_response.data)
        self.assertIn('Dinheiro'.encode(), detail_response.data)
        self.assertIn('Pix'.encode(), detail_response.data)
        self.assertIn('Horário de pico'.encode(), detail_response.data)
        self.assertIn('18:00 - 18:59'.encode(), detail_response.data)
        self.assertIn('2 vendas'.encode(), detail_response.data)
        self.assertIn('Produtos mais vendidos'.encode(), detail_response.data)
        self.assertIn('Rum Especial'.encode(), detail_response.data)
        self.assertIn('Cerveja Pilsen'.encode(), detail_response.data)

    def test_new_sale_requires_open_cash_register(self):
        self.login()

        response = self.client.get('/vendas/nova')

        self.assertEqual(response.status_code, 200)
        self.assertIn('Deseja abrir o caixa?'.encode(), response.data)
        self.assertIn('data-cash-required-page'.encode(), response.data)
        self.assertIn('data-cash-open-confirm'.encode(), response.data)
        self.assertIn('name="opening_amount" value="0,00"'.encode(), response.data)
        self.assertIn('name="next" value="/vendas/nova"'.encode(), response.data)
        self.assertIn('Sim, abrir caixa'.encode(), response.data)
        self.assertIn('Não, voltar'.encode(), response.data)

        open_response = self.client.post(
            '/caixa/abrir',
            data={'opening_amount': '0,00', 'next': '/vendas/nova'},
            follow_redirects=True,
        )

        self.assertEqual(open_response.status_code, 200)
        self.assertIn('Realizar venda'.encode(), open_response.data)
        with self.app.app_context():
            cash_register = CashRegister.query.filter_by(
                company_id=self.master_company_id(),
                status='open',
            ).one()
            self.assertEqual(cash_register.opening_amount, 0)

    def test_sales_list_renders_column_filters_and_sale_metadata(self):
        with self.app.app_context():
            company = Company(name='Adega Filtros Venda', activation_key='KEY-FILTROS-VENDA')
            db.session.add(company)
            db.session.flush()
            user = User(username='vendedor_filtro', role='admin', company_id=company.id, is_active=True, email_verified=True)
            user.set_password('123')
            product = Product(name='Filtro Venda', sale_price=12, stock_quantity=5, active=True, company_id=company.id)
            db.session.add_all([user, product])
            db.session.flush()
            cash_register = CashRegister(
                opened_at=datetime.now(),
                opening_amount=0,
                status='open',
                user_id=user.id,
                company_id=company.id,
            )
            db.session.add(cash_register)
            db.session.flush()
            sale = Sale(
                created_at=datetime.now(),
                total_amount=12,
                discount_amount=0,
                final_amount=12,
                payment_status='paid',
                user_id=user.id,
                company_id=company.id,
                cash_register_id=cash_register.id,
            )
            db.session.add(sale)
            db.session.flush()
            db.session.add_all([
                SaleItem(
                    sale_id=sale.id,
                    product_id=product.id,
                    quantity=1,
                    unit_price=12,
                    unit_cost_price=0,
                    total_price=12,
                    profit_amount=12,
                ),
                Payment(sale_id=sale.id, method='money', amount=12),
            ])
            db.session.commit()

        self.login(username='vendedor_filtro', password='123')

        response = self.client.get('/vendas')

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-sales-filters'.encode(), response.data)
        self.assertIn('data-sales-filter="id"'.encode(), response.data)
        self.assertIn('data-sales-filter="payment"'.encode(), response.data)
        self.assertIn('data-sale-payment'.encode(), response.data)
        self.assertIn('Vendedor'.encode(), response.data)
        self.assertNotIn('sales-status-column'.encode(), response.data)
        self.assertNotIn('sales-cash-column'.encode(), response.data)

    def test_product_list_renders_category_menu_and_combines_category_filter(self):
        self.login()

        with self.app.app_context():
            company_id = self.master_company_id()
            category = Category(name='Destilados', company_id=company_id)
            db.session.add(category)
            db.session.flush()
            db.session.add_all([
                Product(name='Whisky Categoria', sale_price=80, stock_quantity=3, active=True, category_id=category.id, company_id=company_id),
                Product(name='Produto Fora Categoria', sale_price=10, stock_quantity=3, active=True, company_id=company_id),
            ])
            db.session.commit()
            category_id = category.id

        response = self.client.get('/catalogo/produtos', query_string={'category_id': category_id, 'q': 'Whisky'})

        self.assertEqual(response.status_code, 200)
        self.assertIn('category-chip'.encode(), response.data)
        self.assertIn('Destilados'.encode(), response.data)
        self.assertIn('Whisky Categoria'.encode(), response.data)
        self.assertIn(f'category_id={category_id}'.encode(), response.data)

    def test_product_report_calculates_sales_cost_profit_and_stock(self):
        self.login()
        self.open_cash_register(amount='0,00')

        with self.app.app_context():
            company_id = self.master_company_id()
            category = Category(name='Relatorio Categoria', company_id=company_id)
            db.session.add(category)
            db.session.flush()
            product = Product(
                name='Produto Relatorio',
                category_id=category.id,
                cost_price=4,
                sale_price=10,
                stock_quantity=9,
                active=True,
                company_id=company_id,
            )
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        self.client.post(
            '/vendas/nova',
            data={
                'product_id[]': [str(product_id)],
                'quantity[]': ['2'],
                'payment_pix': '20,00',
            },
            follow_redirects=True,
        )

        response = self.client.get('/relatorios', query_string={
            'view': 'products',
            'product_sort': 'quantity_desc',
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn('Relatório por produto'.encode(), response.data)
        self.assertIn('Produto Relatorio'.encode(), response.data)
        self.assertIn('Relatorio Categoria'.encode(), response.data)
        self.assertIn('R$ 20,00'.encode(), response.data)
        self.assertIn('R$ 8,00'.encode(), response.data)
        self.assertIn('R$ 12,00'.encode(), response.data)
        self.assertIn('7'.encode(), response.data)

    def test_product_report_can_show_products_without_sales(self):
        self.login()

        with self.app.app_context():
            db.session.add(Product(
                name='Produto Sem Venda Relatorio',
                sale_price=15,
                stock_quantity=4,
                active=True,
                company_id=self.master_company_id(),
            ))
            db.session.commit()

        response = self.client.get('/relatorios', query_string={
            'view': 'products',
            'product_sort': 'no_sales',
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn('Produtos sem venda'.encode(), response.data)
        self.assertIn('Produto Sem Venda Relatorio'.encode(), response.data)
        self.assertIn('R$ 0,00'.encode(), response.data)

    def test_current_cash_register_shows_payment_totals_and_timeline(self):
        self.login()
        self.open_cash_register(amount='0,00')

        with self.app.app_context():
            product = Product(name='Timeline Atual', sale_price=25, stock_quantity=5, active=True, company_id=self.master_company_id())
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        self.client.post(
            '/vendas/nova',
            data={
                'product_id[]': [str(product_id)],
                'quantity[]': ['1'],
                'payment_debit': '25,00',
            },
            follow_redirects=True,
        )

        response = self.client.get('/caixa')

        self.assertEqual(response.status_code, 200)
        self.assertIn('Ticket médio'.encode(), response.data)
        self.assertIn('Débito'.encode(), response.data)
        self.assertIn('R$ 25,00'.encode(), response.data)
        self.assertIn('Ver linha do tempo de vendas'.encode(), response.data)
        self.assertIn('Timeline Atual'.encode(), response.data)

    def test_cash_register_detail_renders_expandable_sale_timeline(self):
        self.login()
        self.open_cash_register(amount='0,00')

        with self.app.app_context():
            product = Product(name='Timeline Fechada', sale_price=30, stock_quantity=5, active=True, company_id=self.master_company_id())
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        self.client.post(
            '/vendas/nova',
            data={
                'product_id[]': [str(product_id)],
                'quantity[]': ['1'],
                'payment_credit': '30,00',
            },
            follow_redirects=True,
        )
        with self.app.app_context():
            cash_register_id = CashRegister.query.one().id

        self.client.post('/caixa/fechar', data={'closing_amount': '30,00'}, follow_redirects=True)
        response = self.client.get(f'/caixa/{cash_register_id}')

        self.assertEqual(response.status_code, 200)
        self.assertIn('Linha do tempo de vendas'.encode(), response.data)
        self.assertIn('Venda #'.encode(), response.data)
        self.assertIn('Crédito'.encode(), response.data)
        self.assertIn('Timeline Fechada'.encode(), response.data)

    def test_product_creation_generates_initial_stock_movement_and_audit(self):
        self.login()

        response = self.client.post(
            '/catalogo/produtos/novo',
            data={
                'name': 'Produto Auditavel',
                'cost_price': '4,00',
                'sale_price': '10,00',
                'stock_quantity': '8',
                'min_stock_quantity': '1',
                'active': 'on',
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            product = Product.query.filter_by(name='Produto Auditavel').one()
            movement = StockMovement.query.filter_by(product_id=product.id).one()
            self.assertEqual(movement.movement_type, 'initial_stock')
            self.assertEqual(movement.source_type, 'product_creation')
            self.assertEqual(movement.previous_stock, 0)
            self.assertEqual(movement.new_stock, 8)
            self.assertEqual(AuditLog.query.filter_by(action='product_created', entity_id=product.id).count(), 1)

    def test_manual_stock_entry_and_adjustment_use_stock_service(self):
        self.login()
        with self.app.app_context():
            product = Product(name='Produto Estoque Manual', cost_price=3, sale_price=9, stock_quantity=2, active=True, company_id=self.master_company_id())
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        entry_response = self.client.post(
            '/estoque/entrada',
            data={
                'product_id': str(product_id),
                'quantity': '5',
                'unit_cost': '3,50',
                'reason': 'Compra de reposição',
                'notes': 'Fornecedor teste',
            },
            follow_redirects=True,
        )
        self.assertEqual(entry_response.status_code, 200)
        self.assertIn('Entrada registrada'.encode(), entry_response.data)

        adjustment_response = self.client.post(
            '/estoque/ajuste',
            data={
                'product_id': str(product_id),
                'adjustment_mode': 'target',
                'target_stock': '4',
                'reason': 'Contagem física',
            },
            follow_redirects=True,
        )
        self.assertEqual(adjustment_response.status_code, 200)
        self.assertIn('Ajuste registrado'.encode(), adjustment_response.data)

        with self.app.app_context():
            product = db.session.get(Product, product_id)
            self.assertEqual(product.stock_quantity, 4)
            self.assertEqual(StockMovement.query.filter_by(product_id=product_id).count(), 2)
            self.assertEqual(StockMovement.query.filter_by(product_id=product_id, movement_type='entry').count(), 1)
            self.assertEqual(StockMovement.query.filter_by(product_id=product_id, movement_type='adjustment_out').count(), 1)
            self.assertGreaterEqual(AuditLog.query.filter_by(entity_type='stock_movement').count(), 2)

    def test_stock_adjustment_blocks_negative_stock_unless_company_allows_it(self):
        self.login()
        with self.app.app_context():
            company_id = self.master_company_id()
            company = db.session.get(Company, company_id)
            company.allow_negative_stock = False
            product = Product(name='Produto Sem Negativo', cost_price=1, sale_price=5, stock_quantity=1, active=True, company_id=company_id)
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        blocked = self.client.post(
            '/estoque/ajuste',
            data={'product_id': str(product_id), 'adjustment_mode': 'target', 'target_stock': '-2', 'reason': 'Teste negativo'},
            follow_redirects=True,
        )
        self.assertIn('não pode ficar negativo'.encode(), blocked.data)

        with self.app.app_context():
            company = db.session.get(Company, self.master_company_id())
            company.allow_negative_stock = True
            db.session.commit()

        allowed = self.client.post(
            '/estoque/ajuste',
            data={'product_id': str(product_id), 'adjustment_mode': 'target', 'target_stock': '-2', 'reason': 'Teste negativo permitido'},
            follow_redirects=True,
        )
        self.assertIn('Ajuste registrado'.encode(), allowed.data)
        with self.app.app_context():
            self.assertEqual(db.session.get(Product, product_id).stock_quantity, -2)

    def test_sale_and_kit_create_stock_sale_movements(self):
        self.login()
        self.open_cash_register(amount='0,00')
        with self.app.app_context():
            company_id = self.master_company_id()
            base = Product(name='Base Kit Movimento', cost_price=2, sale_price=5, stock_quantity=10, active=True, company_id=company_id)
            kit = Product(name='Kit Movimento', cost_price=4, sale_price=12, stock_quantity=0, active=True, company_id=company_id, is_kit=True, kit_component=base, kit_component_quantity=2)
            db.session.add_all([base, kit])
            db.session.commit()
            base_id = base.id
            kit_id = kit.id

        response = self.client.post(
            '/vendas/nova',
            data={'product_id[]': [str(kit_id)], 'quantity[]': ['2'], 'payment_money': '24,00'},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            base = db.session.get(Product, base_id)
            self.assertEqual(base.stock_quantity, 6)
            movement = StockMovement.query.filter_by(product_id=base_id, movement_type='sale').one()
            self.assertEqual(movement.quantity, 4)
            self.assertEqual(movement.source_type, 'sale')
            self.assertIsNotNone(movement.source_id)
            self.assertEqual(AuditLog.query.filter_by(action='sale_completed').count(), 1)

    def test_stock_routes_require_stock_permission(self):
        with self.app.app_context():
            company_id = self.master_company_id()
            employee = User(username='semestoque', role='operator', company_id=company_id, is_active=True, can_view_stock_movements=False, can_manage_stock=False)
            employee.set_password('123')
            db.session.add(employee)
            db.session.commit()

        self.login(username='semestoque', password='123')
        response = self.client.get('/estoque/movimentacoes', follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('Autorização necessária'.encode(), response.data)

    def test_audit_masks_sensitive_fields_and_diff_values(self):
        self.login()
        with self.app.app_context():
            old_values, new_values = changed_values({'sale_price': '10.00'}, {'sale_price': '12.00'})
            record_audit_event(
                'activation_key_generated',
                'activation_key',
                None,
                'Teste de mascaramento',
                old_values={'activation_key': 'ABCD-1234-EFGH-5678', 'password': 'segredo'},
                new_values={**new_values, 'activation_key': 'ZZZZ-9999-YYYY-8888'},
                company_id=self.master_company_id(),
                db_session=db.session,
            )
            db.session.commit()
            log = AuditLog.query.filter_by(description='Teste de mascaramento').one()
            self.assertIn('****5678', log.old_values)
            self.assertIn('[protegido]', log.old_values)
            self.assertIn('sale_price', log.new_values)
            self.assertNotIn('ABCD-1234-EFGH-5678', log.old_values)
            self.assertNotIn('ZZZZ-9999-YYYY-8888', log.new_values)

    def test_audit_page_is_available_to_authorized_user(self):
        self.login()
        with self.app.app_context():
            record_audit_event(
                'settings_updated',
                'settings',
                None,
                'Evento de auditoria visível',
                company_id=self.master_company_id(),
                db_session=db.session,
            )
            db.session.commit()

        response = self.client.get('/auditoria')

        self.assertEqual(response.status_code, 200)
        self.assertIn('Auditoria'.encode(), response.data)
        self.assertIn('Evento de auditoria visível'.encode(), response.data)

    def test_audit_detail_translates_technical_fields_to_brazilian_portuguese(self):
        self.login()
        with self.app.app_context():
            record_audit_event(
                'stock_sale',
                'stock_movement',
                15,
                'Venda de estoque traduzida',
                old_values={'stock_quantity': 10},
                new_values={
                    'stock_quantity': 8,
                    'source_type': 'sale',
                    'product_id': 3,
                    'quantity': 2,
                },
                company_id=self.master_company_id(),
                db_session=db.session,
            )
            db.session.commit()

        response = self.client.get('/auditoria')

        self.assertEqual(response.status_code, 200)
        self.assertIn('Estoque'.encode(), response.data)
        self.assertIn('Origem'.encode(), response.data)
        self.assertIn('Venda'.encode(), response.data)
        self.assertIn('Produto'.encode(), response.data)
        self.assertIn('Quantidade'.encode(), response.data)
        self.assertNotIn('stock_quantity'.encode(), response.data)
        self.assertNotIn('source_type'.encode(), response.data)


if __name__ == '__main__':
    unittest.main()
