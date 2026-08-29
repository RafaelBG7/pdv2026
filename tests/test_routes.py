from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import io
import logging
from pathlib import Path
import re
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from flask import g

from app import create_app
from app.extensions import db
from app.models import ActivationKey, ApiRefreshToken, ApiSaleRequest, AuditLog, CashRegister, Category, Company, EmailAlertDelivery, EmailAlertSetting, EmailChangeRequest, EmailVerificationCode, Notification, NotificationPreference, PasswordResetToken, Payable, Payment, Product, Sale, SaleItem, StockMovement, User
from app.services.api_auth_service import clear_api_login_attempts
from app.services.audit_service import changed_values, record_audit_event
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app import tenant as tenant_module
from app.services import alert_service
from app.services.notification_service import create_notification
from app.time_utils import business_date_range_utc, business_today


class TestConfig:
    TESTING = True
    SECRET_KEY = 'test-secret-key'
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    MAIL_SUPPRESS_SEND = True
    PUBLIC_BASE_URL = 'http://localhost'
    API_ALLOW_INSECURE_AUTH = True
    API_ACCESS_TOKEN_MINUTES = 15
    API_REFRESH_TOKEN_DAYS = 30
    RATELIMIT_ENABLED = False
    RATELIMIT_STORAGE_URI = 'memory://'


def close_test_log_handlers(app):
    configured_log_dir = app.config.get('LOG_DIR')
    if not configured_log_dir:
        return
    log_dir = Path(configured_log_dir).resolve()

    for handler in list(app.logger.handlers):
        base_filename = getattr(handler, 'baseFilename', None)
        if not base_filename:
            continue

        try:
            handler_path = Path(base_filename).resolve()
        except (OSError, RuntimeError):
            continue

        if handler_path == log_dir or log_dir in handler_path.parents:
            app.logger.removeHandler(handler)
            try:
                handler.flush()
            finally:
                handler.close()

    # Windows keeps files locked while logging handlers are alive. Shutting down
    # logging here releases RotatingFileHandler handles before temp dir cleanup.
    logging.shutdown()


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
        close_test_log_handlers(self.app)
        clear_api_login_attempts()
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

    def create_api_user(
        self,
        username='api-operador',
        password='SenhaApi123',
        company_name='Adega API',
        **user_values,
    ):
        with self.app.app_context():
            company = Company(
                name=company_name,
                active=True,
                subscription_started_at=date.today(),
                subscription_renews_at=date.today() + timedelta(days=30),
            )
            db.session.add(company)
            db.session.flush()
            user_data = {
                'username': username,
                'email': f'{username}@girofy.test',
                'email_verified': True,
                'role': 'admin',
                'company_id': company.id,
                'is_active': True,
            }
            user_data.update(user_values)
            user = User(**user_data)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            # Return immutable scalar snapshots so callers never depend on a
            # detached SQLAlchemy instance outside the Flask app context.
            user_snapshot = SimpleNamespace(id=user.id, username=user.username)
            company_snapshot = SimpleNamespace(id=company.id)
            return user_snapshot, company_snapshot

    def api_login(self, identifier, password):
        return self.client.post(
            '/api/v1/auth/login',
            json={'identifier': identifier, 'password': password},
        )

    @staticmethod
    def bearer_header(access_token):
        return {'Authorization': f'Bearer {access_token}'}

    def test_login_page_loads(self):
        response = self.client.get('/login')

        self.assertEqual(response.status_code, 200)
        self.assertIn('SkyGest'.encode(), response.data)
        self.assertIn('brand/skygest-logo-horizontal.png'.encode(), response.data)
        self.assertIn('data-authenticated="false"'.encode(), response.data)
        self.assertNotIn('login-theme-toggle'.encode(), response.data)
        self.assertIn('brand/favicon.ico'.encode(), response.data)
        self.assertNotIn('Logo Girofy'.encode(), response.data)
        self.assertNotIn('logo-girofy'.encode(), response.data)
        self.assertNotIn('Gestão que faz girar o seu negócio'.encode(), response.data)
        self.assertNotIn('Sistema PDV Local'.encode(), response.data)
        self.assertIn('Entrar'.encode(), response.data)
        self.assertIn('Lembre de mim'.encode(), response.data)
        self.assertIn('name="remember_me"'.encode(), response.data)
        self.assertIn('Cadastrar'.encode(), response.data)
        self.assertNotIn('Key de ativação'.encode(), response.data)
        self.assertNotIn('Não tenho key'.encode(), response.data)
        self.assertNotIn('data-theme-toggle'.encode(), response.data)
        self.assertIn(": 'dark'".encode(), response.data)
        self.assertIn("localStorage.getItem('girofy-theme')".encode(), response.data)
        self.assertIn("prefers-color-scheme: dark".encode(), response.data)

    def test_authenticated_layout_exposes_accessible_theme_toggle(self):
        self.login()

        response = self.client.get('/dashboard')

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-theme-toggle'.encode(), response.data)
        self.assertIn('aria-label="Ativar tema escuro"'.encode(), response.data)
        self.assertNotIn('class="user-theme-options"'.encode(), response.data)

    def test_health_check_is_public_and_minimal(self):
        response = self.client.get('/health')
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get('Cache-Control'), 'no-store')
        self.assertEqual(data, {'status': 'ok', 'service': 'girofy'})

    def test_api_v1_health_check_is_public_and_versioned(self):
        response = self.client.get('/api/v1/health')
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get('Cache-Control'), 'no-store')
        self.assertEqual(data, {
            'success': True,
            'data': {
                'status': 'ok',
                'service': 'girofy',
                'api_version': 'v1',
            },
            'message': None,
            'errors': [],
        })

    def test_distributed_rate_limit_returns_web_and_api_429_and_separates_ips(self):
        class RateLimitConfig(TestConfig):
            RATELIMIT_ENABLED = True
            RATELIMIT_STORAGE_URI = 'memory://'
            RATELIMIT_LOGIN = '2 per minute'
            RATELIMIT_API_GENERAL = '100 per minute'
            RATELIMIT_KEY_PREFIX = 'test-login-limit'

        rate_temp_dir = tempfile.TemporaryDirectory()
        RateLimitConfig.LOG_DIR = Path(rate_temp_dir.name) / 'logs'
        RateLimitConfig.BACKUP_DIR = Path(rate_temp_dir.name) / 'backups'
        rate_app = create_app(RateLimitConfig)
        rate_client = rate_app.test_client()
        try:
            api_payload = {'identifier': 'desconhecido', 'password': 'SenhaErrada123'}
            first = rate_client.post('/api/v1/auth/login', json=api_payload, environ_base={'REMOTE_ADDR': '10.0.0.1'})
            second = rate_client.post('/api/v1/auth/login', json=api_payload, environ_base={'REMOTE_ADDR': '10.0.0.1'})
            blocked = rate_client.post('/api/v1/auth/login', json=api_payload, environ_base={'REMOTE_ADDR': '10.0.0.1'})
            other_ip = rate_client.post('/api/v1/auth/login', json=api_payload, environ_base={'REMOTE_ADDR': '10.0.0.2'})

            self.assertEqual(first.status_code, 401)
            self.assertEqual(second.status_code, 401)
            self.assertEqual(blocked.status_code, 429)
            self.assertEqual(blocked.get_json()['errors'][0]['code'], 'rate_limit_exceeded')
            self.assertIsNotNone(blocked.headers.get('Retry-After'))
            self.assertEqual(other_ip.status_code, 401)

            form = {'form_type': 'login', 'username': 'web-user', 'password': 'incorreta'}
            rate_client.post('/login', data=form, environ_base={'REMOTE_ADDR': '10.0.0.3'})
            rate_client.post('/login', data=form, environ_base={'REMOTE_ADDR': '10.0.0.3'})
            web_blocked = rate_client.post('/login', data=form, environ_base={'REMOTE_ADDR': '10.0.0.3'})
            self.assertEqual(web_blocked.status_code, 429)
            self.assertIn('Muitas tentativas'.encode(), web_blocked.data)
            security_log = (Path(RateLimitConfig.LOG_DIR) / 'security.log').read_text(encoding='utf-8')
            self.assertIn('rate_limit_exceeded', security_log)
            self.assertNotIn('SenhaErrada123', security_log)
            self.assertNotIn('incorreta', security_log)
        finally:
            with rate_app.app_context():
                db.session.remove()
                db.drop_all()
                db.engine.dispose()
            close_test_log_handlers(rate_app)
            rate_temp_dir.cleanup()

    def test_login_allows_three_errors_and_blocks_only_after_ten_attempts(self):
        class FriendlyLoginRateLimitConfig(TestConfig):
            RATELIMIT_ENABLED = True
            RATELIMIT_STORAGE_URI = 'memory://'
            RATELIMIT_LOGIN = '10 per 5 minutes'
            RATELIMIT_API_GENERAL = '100 per minute'
            RATELIMIT_KEY_PREFIX = 'test-friendly-login-limit'

        rate_temp_dir = tempfile.TemporaryDirectory()
        FriendlyLoginRateLimitConfig.LOG_DIR = Path(rate_temp_dir.name) / 'logs'
        FriendlyLoginRateLimitConfig.BACKUP_DIR = Path(rate_temp_dir.name) / 'backups'
        rate_app = create_app(FriendlyLoginRateLimitConfig)
        rate_client = rate_app.test_client()
        form = {'form_type': 'login', 'username': 'usuario-real', 'password': 'incorreta'}
        try:
            for _ in range(3):
                response = rate_client.post('/login', data=form, environ_base={'REMOTE_ADDR': '10.0.0.9'})
                self.assertEqual(response.status_code, 200)

            for _ in range(7):
                response = rate_client.post('/login', data=form, environ_base={'REMOTE_ADDR': '10.0.0.9'})
                self.assertEqual(response.status_code, 200)

            blocked = rate_client.post('/login', data=form, environ_base={'REMOTE_ADDR': '10.0.0.9'})
            self.assertEqual(blocked.status_code, 429)
            self.assertIn('minutos'.encode(), blocked.data)
            self.assertLessEqual(int(blocked.headers['Retry-After']), 360)
        finally:
            with rate_app.app_context():
                db.session.remove()
                db.drop_all()
                db.engine.dispose()
            close_test_log_handlers(rate_app)
            rate_temp_dir.cleanup()

    def test_rate_limit_can_be_disabled_in_development(self):
        for _ in range(8):
            response = self.client.post(
                '/api/v1/auth/login',
                json={'identifier': 'sem-limite', 'password': 'SenhaErrada123'},
            )
            self.assertEqual(response.status_code, 401)

    def test_dependency_health_reports_database_and_rate_limit_storage(self):
        response = self.client.get('/health/dependencies')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['dependencies']['database'], 'ok')
        self.assertEqual(data['dependencies']['redis'], 'disabled')

    def test_rate_limit_uses_proxyfix_only_when_proxy_is_trusted(self):
        class ProxyRateLimitConfig(TestConfig):
            RATELIMIT_ENABLED = True
            RATELIMIT_STORAGE_URI = 'memory://'
            RATELIMIT_LOGIN = '1 per minute'
            RATELIMIT_API_GENERAL = '100 per minute'
            RATELIMIT_KEY_PREFIX = 'test-proxy-limit'
            TRUST_PROXY_HEADERS = True
            TRUSTED_PROXY_COUNT = 1

        proxy_temp_dir = tempfile.TemporaryDirectory()
        ProxyRateLimitConfig.LOG_DIR = Path(proxy_temp_dir.name) / 'logs'
        ProxyRateLimitConfig.BACKUP_DIR = Path(proxy_temp_dir.name) / 'backups'
        proxy_app = create_app(ProxyRateLimitConfig)
        proxy_client = proxy_app.test_client()
        try:
            payload = {'identifier': 'proxy-user', 'password': 'SenhaErrada123'}
            headers = {'X-Forwarded-For': '203.0.113.10'}
            first = proxy_client.post('/api/v1/auth/login', json=payload, headers=headers)
            blocked = proxy_client.post('/api/v1/auth/login', json=payload, headers=headers)
            other_client = proxy_client.post(
                '/api/v1/auth/login',
                json=payload,
                headers={'X-Forwarded-For': '203.0.113.11'},
            )
            self.assertEqual(first.status_code, 401)
            self.assertEqual(blocked.status_code, 429)
            self.assertEqual(other_client.status_code, 401)
        finally:
            with proxy_app.app_context():
                db.session.remove()
                db.drop_all()
                db.engine.dispose()
            close_test_log_handlers(proxy_app)
            proxy_temp_dir.cleanup()

    def test_rate_limit_fails_closed_when_redis_is_unavailable(self):
        class BrokenRedisConfig(TestConfig):
            RATELIMIT_ENABLED = True
            RATELIMIT_STORAGE_URI = 'redis://127.0.0.1:1/15'
            RATELIMIT_LOGIN = '2 per minute'
            RATELIMIT_API_GENERAL = '100 per minute'
            RATELIMIT_IN_MEMORY_FALLBACK_ENABLED = False
            RATELIMIT_KEY_PREFIX = 'test-broken-redis'

        redis_temp_dir = tempfile.TemporaryDirectory()
        BrokenRedisConfig.LOG_DIR = Path(redis_temp_dir.name) / 'logs'
        BrokenRedisConfig.BACKUP_DIR = Path(redis_temp_dir.name) / 'backups'
        redis_app = create_app(BrokenRedisConfig)
        redis_client = redis_app.test_client()
        try:
            response = redis_client.post(
                '/api/v1/auth/login',
                json={'identifier': 'redis-offline', 'password': 'SenhaErrada123'},
            )
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.get_json()['errors'][0]['code'], 'rate_limit_unavailable')
            self.assertEqual(response.headers.get('Retry-After'), '30')
        finally:
            with redis_app.app_context():
                db.session.remove()
                db.drop_all()
                db.engine.dispose()
            close_test_log_handlers(redis_app)
            redis_temp_dir.cleanup()

    def test_api_general_rate_limit_isolated_by_authenticated_token_and_tenant(self):
        class ApiLimitConfig(TestConfig):
            RATELIMIT_ENABLED = True
            RATELIMIT_STORAGE_URI = 'memory://'
            RATELIMIT_LOGIN = '10 per minute'
            RATELIMIT_API_GENERAL = '1 per minute'
            RATELIMIT_KEY_PREFIX = 'test-api-tenant-limit'

        api_temp_dir = tempfile.TemporaryDirectory()
        ApiLimitConfig.LOG_DIR = Path(api_temp_dir.name) / 'logs'
        ApiLimitConfig.BACKUP_DIR = Path(api_temp_dir.name) / 'backups'
        api_app = create_app(ApiLimitConfig)
        api_client = api_app.test_client()
        try:
            with api_app.app_context():
                users = []
                for index in (1, 2):
                    company = Company(
                        name=f'Empresa limite {index}', active=True,
                        subscription_started_at=date.today(),
                        subscription_renews_at=date.today() + timedelta(days=30),
                    )
                    db.session.add(company)
                    db.session.flush()
                    user = User(
                        username=f'limite-{index}', email=f'limite-{index}@girofy.test',
                        email_verified=True, role='admin', company_id=company.id, is_active=True,
                    )
                    user.set_password('SenhaApi123')
                    db.session.add(user)
                    users.append(user.username)
                db.session.commit()

            tokens = []
            for index, username in enumerate(users, start=1):
                login_response = api_client.post(
                    '/api/v1/auth/login',
                    json={'identifier': username, 'password': 'SenhaApi123'},
                    environ_base={'REMOTE_ADDR': f'10.10.0.{index}'},
                )
                self.assertEqual(login_response.status_code, 200)
                tokens.append(login_response.get_json()['data']['access_token'])

            first_user = api_client.get('/api/v1/auth/me', headers=self.bearer_header(tokens[0]))
            first_user_blocked = api_client.get('/api/v1/auth/me', headers=self.bearer_header(tokens[0]))
            second_tenant = api_client.get('/api/v1/auth/me', headers=self.bearer_header(tokens[1]))
            self.assertEqual(first_user.status_code, 200)
            self.assertEqual(first_user_blocked.status_code, 429)
            self.assertEqual(second_tenant.status_code, 200)
        finally:
            with api_app.app_context():
                db.session.remove()
                db.drop_all()
                db.engine.dispose()
            close_test_log_handlers(api_app)
            api_temp_dir.cleanup()

    def test_api_login_returns_tokens_and_current_tenant_identity(self):
        user, company = self.create_api_user()

        response = self.api_login(user.username, 'SenhaApi123')
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['token_type'], 'Bearer')
        self.assertTrue(data['data']['access_token'])
        self.assertTrue(data['data']['refresh_token'].startswith('grf1.'))
        self.assertEqual(data['data']['user']['id'], user.id)
        self.assertEqual(data['data']['company']['id'], company.id)
        self.assertTrue(data['data']['user']['permissions']['can_manage_sales'])
        with self.app.app_context():
            token_count = ApiRefreshToken.query.filter_by(user_id=user.id).count()
        self.assertEqual(token_count, 1)

        me_response = self.client.get(
            '/api/v1/auth/me?company_id=999999',
            headers=self.bearer_header(data['data']['access_token']),
        )
        me_data = me_response.get_json()

        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_data['data']['user']['id'], user.id)
        self.assertEqual(me_data['data']['company']['id'], company.id)

    def test_api_login_rejects_invalid_credentials_without_user_enumeration(self):
        self.create_api_user()

        wrong_password = self.api_login('api-operador', 'senha-incorreta')
        missing_user = self.api_login('usuario-inexistente', 'senha-incorreta')

        self.assertEqual(wrong_password.status_code, 401)
        self.assertEqual(missing_user.status_code, 401)
        self.assertEqual(wrong_password.get_json()['message'], missing_user.get_json()['message'])
        self.assertEqual(wrong_password.get_json()['errors'][0]['code'], 'invalid_credentials')

    def test_api_login_enforces_user_and_subscription_status(self):
        inactive_user, _ = self.create_api_user(username='api-inativo', is_active=False)
        expired_user, expired_company = self.create_api_user(
            username='api-vencido',
            company_name='Adega vencida',
        )
        with self.app.app_context():
            company = db.session.get(Company, expired_company.id)
            company.subscription_renews_at = date.today() - timedelta(days=1)
            db.session.commit()

        inactive_response = self.api_login(inactive_user.username, 'SenhaApi123')
        expired_response = self.api_login(expired_user.username, 'SenhaApi123')

        self.assertEqual(inactive_response.status_code, 403)
        self.assertEqual(inactive_response.get_json()['errors'][0]['code'], 'user_inactive')
        self.assertEqual(expired_response.status_code, 403)
        self.assertEqual(expired_response.get_json()['errors'][0]['code'], 'subscription_required')

    def test_api_subscription_activation_applies_key_and_returns_session(self):
        expired_user, expired_company = self.create_api_user(
            username='api-ativacao',
            company_name='Adega ativacao',
        )
        with self.app.app_context():
            company = db.session.get(Company, expired_company.id)
            company.subscription_renews_at = date.today() - timedelta(days=1)
            db.session.add(ActivationKey(
                key='WIN-KEY1-WIN-KEY2',
                plan='Pro',
                renews_at=date.today() + timedelta(days=45),
                active=True,
            ))
            db.session.commit()

        blocked_response = self.api_login(expired_user.username, 'SenhaApi123')
        activation_response = self.client.post(
            '/api/v1/subscription/activate',
            json={
                'identifier': expired_user.username,
                'password': 'SenhaApi123',
                'activation_key': 'win-key1-win-key2',
            },
        )
        activation_data = activation_response.get_json()

        self.assertEqual(blocked_response.status_code, 403)
        self.assertEqual(blocked_response.get_json()['errors'][0]['code'], 'subscription_required')
        self.assertEqual(activation_response.status_code, 200)
        self.assertTrue(activation_data['success'])
        self.assertTrue(activation_data['data']['access_token'])
        self.assertEqual(activation_data['data']['company']['subscription_plan'], 'Pro')
        self.assertTrue(activation_data['data']['company']['subscription_valid'])

        with self.app.app_context():
            company = db.session.get(Company, expired_company.id)
            activation_key = ActivationKey.query.filter_by(key='WIN-KEY1-WIN-KEY2').one()
            self.assertTrue(company.subscription_valid)
            self.assertEqual(company.subscription_plan, 'Pro')
            self.assertEqual(activation_key.used_by_company_id, company.id)
            self.assertIsNotNone(activation_key.used_at)
            self.assertEqual(ApiRefreshToken.query.filter_by(user_id=expired_user.id).count(), 1)

    def test_api_refresh_rotates_token_and_revokes_previous_session(self):
        user, _ = self.create_api_user()
        login_data = self.api_login(user.username, 'SenhaApi123').get_json()['data']

        refresh_response = self.client.post(
            '/api/v1/auth/refresh',
            json={'refresh_token': login_data['refresh_token']},
        )
        refresh_data = refresh_response.get_json()['data']

        self.assertEqual(refresh_response.status_code, 200)
        self.assertNotEqual(refresh_data['refresh_token'], login_data['refresh_token'])
        self.assertNotEqual(refresh_data['access_token'], login_data['access_token'])

        old_refresh_response = self.client.post(
            '/api/v1/auth/refresh',
            json={'refresh_token': login_data['refresh_token']},
        )
        old_access_response = self.client.get(
            '/api/v1/auth/me',
            headers=self.bearer_header(login_data['access_token']),
        )
        new_access_response = self.client.get(
            '/api/v1/auth/me',
            headers=self.bearer_header(refresh_data['access_token']),
        )

        self.assertEqual(old_refresh_response.status_code, 401)
        self.assertEqual(old_access_response.status_code, 401)
        self.assertEqual(new_access_response.status_code, 200)

    def test_api_refresh_rejects_expired_refresh_session(self):
        user, _ = self.create_api_user(username='api-refresh-expirado')
        login_data = self.api_login(user.username, 'SenhaApi123').get_json()['data']
        with self.app.app_context():
            session = ApiRefreshToken.query.filter_by(user_id=user.id).one()
            session.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
            db.session.commit()

        response = self.client.post(
            '/api/v1/auth/refresh',
            json={'refresh_token': login_data['refresh_token']},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()['errors'][0]['code'], 'invalid_refresh_token')

    def test_api_refresh_revalidates_user_company_subscription_and_credentials(self):
        scenarios = (
            ('usuario', 'user_inactive'),
            ('empresa', 'company_inactive'),
            ('assinatura', 'subscription_required'),
            ('senha', 'credentials_changed'),
        )
        for index, (scenario, expected_code) in enumerate(scenarios, start=1):
            with self.subTest(scenario=scenario):
                user, company = self.create_api_user(
                    username=f'api-refresh-{index}',
                    company_name=f'Adega refresh {index}',
                )
                login_data = self.api_login(user.username, 'SenhaApi123').get_json()['data']
                with self.app.app_context():
                    stored_user = db.session.get(User, user.id)
                    stored_company = db.session.get(Company, company.id)
                    if scenario == 'usuario':
                        stored_user.is_active = False
                    elif scenario == 'empresa':
                        stored_company.active = False
                    elif scenario == 'assinatura':
                        stored_company.subscription_renews_at = date.today() - timedelta(days=1)
                    else:
                        stored_user.set_password('OutraSenha123')
                    db.session.commit()

                response = self.client.post(
                    '/api/v1/auth/refresh',
                    json={'refresh_token': login_data['refresh_token']},
                )

                self.assertIn(response.status_code, (401, 403))
                self.assertEqual(response.get_json()['errors'][0]['code'], expected_code)

    def test_api_logout_revokes_desktop_session(self):
        user, _ = self.create_api_user()
        login_data = self.api_login(user.username, 'SenhaApi123').get_json()['data']
        headers = self.bearer_header(login_data['access_token'])

        logout_response = self.client.post('/api/v1/auth/logout', headers=headers)
        me_response = self.client.get('/api/v1/auth/me', headers=headers)
        refresh_response = self.client.post(
            '/api/v1/auth/refresh',
            json={'refresh_token': login_data['refresh_token']},
        )

        self.assertEqual(logout_response.status_code, 200)
        self.assertTrue(logout_response.get_json()['data']['logged_out'])
        self.assertEqual(me_response.status_code, 401)
        self.assertEqual(refresh_response.status_code, 401)

    def test_api_authentication_requires_https_outside_development(self):
        user, _ = self.create_api_user()
        self.app.config['API_ALLOW_INSECURE_AUTH'] = False

        response = self.api_login(user.username, 'SenhaApi123')

        self.assertEqual(response.status_code, 426)
        self.assertEqual(response.get_json()['errors'][0]['code'], 'https_required')

    def test_api_settings_account_returns_profile_and_company_settings(self):
        user, company = self.create_api_user(
            first_name='Ana',
            last_name='Silva',
            phone='11999999999',
        )
        with self.app.app_context():
            company_record = db.session.get(Company, company.id)
            company_record.allow_negative_stock = True
            company_record.backup_frequency = 'daily'
            company_record.pix_fee_enabled = True
            company_record.pix_fee_percent = 1.25
            company_record.debit_fee_enabled = True
            company_record.debit_fee_percent = 2.5
            company_record.credit_fee_enabled = False
            company_record.credit_fee_percent = 0
            db.session.commit()
        login_data = self.api_login(user.username, 'SenhaApi123').get_json()['data']

        response = self.client.get(
            '/api/v1/settings/account',
            headers=self.bearer_header(login_data['access_token']),
        )
        data = response.get_json()['data']

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['user']['id'], user.id)
        self.assertEqual(data['company']['id'], company.id)
        self.assertEqual(data['profile']['first_name'], 'Ana')
        self.assertEqual(data['profile']['last_name'], 'Silva')
        self.assertEqual(data['profile']['phone'], '11999999999')
        self.assertEqual(data['profile']['role_label'], 'Admin')
        self.assertTrue(data['company_settings']['allow_negative_stock'])
        self.assertEqual(data['company_settings']['backup_frequency'], 'daily')
        self.assertTrue(data['company_settings']['pix_fee_enabled'])
        self.assertEqual(data['company_settings']['pix_fee_percent'], 1.25)
        self.assertTrue(data['company_settings']['debit_fee_enabled'])
        self.assertEqual(data['company_settings']['debit_fee_percent'], 2.5)
        self.assertFalse(data['company_settings']['credit_fee_enabled'])

    def test_api_settings_company_updates_stock_and_fee_rules_and_audits(self):
        user, company = self.create_api_user()
        login_data = self.api_login(user.username, 'SenhaApi123').get_json()['data']

        response = self.client.put(
            '/api/v1/settings/company',
            json={
                'allow_negative_stock': True,
                'pix_fee_enabled': True,
                'pix_fee_percent': '1,25',
                'debit_fee_enabled': True,
                'debit_fee_percent': '2.50',
                'credit_fee_enabled': False,
                'credit_fee_percent': '0',
            },
            headers=self.bearer_header(login_data['access_token']),
        )
        data = response.get_json()['data']

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['company_settings']['allow_negative_stock'])
        self.assertTrue(data['company_settings']['pix_fee_enabled'])
        self.assertEqual(data['company_settings']['pix_fee_percent'], 1.25)
        self.assertTrue(data['company_settings']['debit_fee_enabled'])
        self.assertEqual(data['company_settings']['debit_fee_percent'], 2.5)
        self.assertFalse(data['company_settings']['credit_fee_enabled'])
        self.assertEqual(data['company_settings']['credit_fee_percent'], 0)
        with self.app.app_context():
            updated_company = db.session.get(Company, company.id)
            audit_log = AuditLog.query.filter_by(
                action='company_settings_updated',
                entity_type='company',
                entity_id=str(company.id),
            ).one()
        self.assertTrue(updated_company.allow_negative_stock)
        self.assertTrue(updated_company.card_fee_enabled)
        self.assertEqual(updated_company.pix_fee_percent, 1.25)
        self.assertEqual(updated_company.debit_fee_percent, 2.5)
        self.assertIn('aplicativo Windows', audit_log.description)
        self.assertIn('"client": "windows_native"', audit_log.new_values)

    def test_api_settings_company_rejects_operator_user(self):
        user, _ = self.create_api_user(
            role='operator',
            can_manage_settings=False,
        )
        login_data = self.api_login(user.username, 'SenhaApi123').get_json()['data']

        response = self.client.put(
            '/api/v1/settings/company',
            json={
                'allow_negative_stock': True,
                'pix_fee_enabled': False,
                'pix_fee_percent': '0',
                'debit_fee_enabled': False,
                'debit_fee_percent': '0',
                'credit_fee_enabled': False,
                'credit_fee_percent': '0',
            },
            headers=self.bearer_header(login_data['access_token']),
        )
        error = response.get_json()['errors'][0]

        self.assertEqual(response.status_code, 403)
        self.assertEqual(error['code'], 'permission_denied')

    def test_api_settings_company_rejects_invalid_fee_percent(self):
        user, _ = self.create_api_user()
        login_data = self.api_login(user.username, 'SenhaApi123').get_json()['data']

        response = self.client.put(
            '/api/v1/settings/company',
            json={
                'allow_negative_stock': True,
                'pix_fee_enabled': True,
                'pix_fee_percent': '101',
                'debit_fee_enabled': False,
                'debit_fee_percent': '0',
                'credit_fee_enabled': False,
                'credit_fee_percent': '0',
            },
            headers=self.bearer_header(login_data['access_token']),
        )
        error = response.get_json()['errors'][0]

        self.assertEqual(response.status_code, 422)
        self.assertEqual(error['code'], 'invalid_percent')
        self.assertEqual(error['field'], 'pix_fee_percent')

    def test_api_settings_backup_updates_frequency_and_audits(self):
        user, company = self.create_api_user()
        login_data = self.api_login(user.username, 'SenhaApi123').get_json()['data']

        response = self.client.put(
            '/api/v1/settings/backup',
            json={'backup_frequency': 'weekly'},
            headers=self.bearer_header(login_data['access_token']),
        )
        data = response.get_json()['data']

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['company_settings']['backup_frequency'], 'weekly')
        with self.app.app_context():
            updated_company = db.session.get(Company, company.id)
            audit_log = AuditLog.query.filter_by(
                action='backup_settings_updated',
                entity_type='company',
                entity_id=str(company.id),
            ).one()
        self.assertEqual(updated_company.backup_frequency, 'weekly')
        self.assertIn('aplicativo Windows', audit_log.description)

    def test_api_settings_backup_rejects_invalid_frequency(self):
        user, _ = self.create_api_user()
        login_data = self.api_login(user.username, 'SenhaApi123').get_json()['data']

        response = self.client.put(
            '/api/v1/settings/backup',
            json={'backup_frequency': 'hourly'},
            headers=self.bearer_header(login_data['access_token']),
        )
        error = response.get_json()['errors'][0]

        self.assertEqual(response.status_code, 422)
        self.assertEqual(error['code'], 'invalid_backup_frequency')
        self.assertEqual(error['field'], 'backup_frequency')

    def test_api_settings_backup_runs_manual_backup(self):
        user, company = self.create_api_user()
        login_data = self.api_login(user.username, 'SenhaApi123').get_json()['data']

        response = self.client.post(
            '/api/v1/settings/backup/run',
            json={},
            headers=self.bearer_header(login_data['access_token']),
        )
        data = response.get_json()['data']

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['backup']['status'], 'success')
        self.assertTrue(data['backup']['file_name'].endswith('_windows_manual.sql'))
        self.assertEqual(data['company_settings']['backup_last_status'], 'success')
        with self.app.app_context():
            updated_company = db.session.get(Company, company.id)
            audit_log = AuditLog.query.filter_by(
                action='backup_created',
                entity_type='company',
                entity_id=str(company.id),
            ).one()
            backup_path = Path(updated_company.backup_last_path)
        self.assertEqual(updated_company.backup_last_status, 'success')
        self.assertTrue(backup_path.exists())
        self.assertIn('Backup SkyGest', backup_path.read_text(encoding='utf-8'))
        self.assertIn(data['backup']['file_name'], audit_log.description)

    def test_api_settings_export_products_returns_tenant_csv_for_admin(self):
        user, company = self.create_api_user()
        with self.app.app_context():
            category = Category(name='Cerveja', company_id=company.id)
            db.session.add(category)
            db.session.flush()
            product = Product(
                name='Skol 269ml unidade',
                barcode='789000000001',
                category_id=category.id,
                company_id=company.id,
                cost_price=2.5,
                sale_price=4.0,
                stock_quantity=12,
                min_stock_quantity=3,
                active=True,
            )
            db.session.add(product)
            db.session.commit()
        login_data = self.api_login(user.username, 'SenhaApi123').get_json()['data']

        response = self.client.get(
            '/api/v1/settings/export/produtos',
            headers=self.bearer_header(login_data['access_token']),
        )
        csv_text = response.data.decode('utf-8-sig')

        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response.content_type)
        self.assertIn('attachment;', response.headers.get('Content-Disposition', ''))
        self.assertIn('skygest_produtos_', response.headers.get('Content-Disposition', ''))
        self.assertIn('Nome;Código de barras;Categoria', csv_text)
        self.assertIn('Skol 269ml unidade;789000000001;Cerveja', csv_text)
        self.assertIn('2,50;4,00;12;3;Sim;Não', csv_text)
        with self.app.app_context():
            audit_log = AuditLog.query.filter_by(
                action='data_exported',
                entity_type='export',
                company_id=company.id,
            ).one()
        self.assertIn('Exportação de Produtos', audit_log.description)
        self.assertIn('"export_type": "produtos"', audit_log.new_values)

    def test_api_settings_export_rejects_non_admin_user(self):
        user, _ = self.create_api_user(
            role='operator',
            can_manage_settings=True,
        )
        login_data = self.api_login(user.username, 'SenhaApi123').get_json()['data']

        response = self.client.get(
            '/api/v1/settings/export/vendas',
            headers=self.bearer_header(login_data['access_token']),
        )
        error = response.get_json()['errors'][0]

        self.assertEqual(response.status_code, 403)
        self.assertEqual(error['code'], 'permission_denied')

    def test_api_settings_export_rejects_invalid_type(self):
        user, _ = self.create_api_user()
        login_data = self.api_login(user.username, 'SenhaApi123').get_json()['data']

        response = self.client.get(
            '/api/v1/settings/export/desconhecido',
            headers=self.bearer_header(login_data['access_token']),
        )
        error = response.get_json()['errors'][0]

        self.assertEqual(response.status_code, 422)
        self.assertEqual(error['code'], 'invalid_export_type')
        self.assertEqual(error['field'], 'export_type')

    def test_api_settings_import_products_creates_product_category_stock_and_audit(self):
        user, company = self.create_api_user()
        login_data = self.api_login(user.username, 'SenhaApi123').get_json()['data']
        csv_bytes = (
            'produto;categoria;valor de custo;valor de venda;estoque atual;estoque minimo;codigo de barras\n'
            'Skol 269ml unidade;Cerveja;2,50;4,00;12;3;789000000001\n'
            ';Sem nome;1,00;2,00;5;1;\n'
        ).encode('utf-8')

        response = self.client.post(
            '/api/v1/settings/import/products',
            data={'spreadsheet': (io.BytesIO(csv_bytes), 'produtos.csv')},
            content_type='multipart/form-data',
            headers=self.bearer_header(login_data['access_token']),
        )
        data = response.get_json()['data']

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['created'], 1)
        self.assertEqual(data['updated'], 0)
        self.assertEqual(data['skipped'], 1)
        self.assertEqual(data['movements'], 1)
        self.assertEqual(data['total_rows'], 2)
        with self.app.app_context():
            product = Product.query.filter_by(
                company_id=company.id,
                name='Skol 269ml unidade',
            ).one()
            category = Category.query.filter_by(company_id=company.id, name='Cerveja').one()
            movement = StockMovement.query.filter_by(
                product_id=product.id,
                source_type='spreadsheet_import',
            ).one()
            product_audit = AuditLog.query.filter_by(
                action='product_created',
                entity_type='product',
                entity_id=str(product.id),
            ).one()
            import_audit = AuditLog.query.filter_by(
                action='products_imported',
                entity_type='product',
                company_id=company.id,
            ).one()

        self.assertEqual(product.category_id, category.id)
        self.assertEqual(product.barcode, '789000000001')
        self.assertEqual(float(product.cost_price), 2.5)
        self.assertEqual(float(product.sale_price), 4.0)
        self.assertEqual(product.stock_quantity, 12)
        self.assertEqual(product.min_stock_quantity, 3)
        self.assertEqual(movement.movement_type, 'import')
        self.assertEqual(movement.quantity, 12)
        self.assertIn('aplicativo Windows', product_audit.description)
        self.assertIn('"created": 1', import_audit.new_values)

    def test_api_settings_import_products_updates_existing_product_and_stock(self):
        user, company = self.create_api_user()
        with self.app.app_context():
            category = Category(name='Cerveja', company_id=company.id)
            db.session.add(category)
            db.session.flush()
            product = Product(
                name='Skol antiga',
                barcode='789000000001',
                category_id=category.id,
                company_id=company.id,
                cost_price=1,
                sale_price=2,
                stock_quantity=3,
                min_stock_quantity=0,
                active=True,
            )
            db.session.add(product)
            db.session.commit()
            product_id = product.id
        login_data = self.api_login(user.username, 'SenhaApi123').get_json()['data']
        csv_bytes = (
            'produto;categoria;custo;venda;estoque;estoque_minimo;barcode\n'
            'Skol 269ml unidade;Cerveja;2,50;4,00;9;2;789000000001\n'
        ).encode('utf-8')

        response = self.client.post(
            '/api/v1/settings/import/products',
            data={'spreadsheet': (io.BytesIO(csv_bytes), 'produtos.csv')},
            content_type='multipart/form-data',
            headers=self.bearer_header(login_data['access_token']),
        )
        data = response.get_json()['data']

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['created'], 0)
        self.assertEqual(data['updated'], 1)
        self.assertEqual(data['movements'], 1)
        with self.app.app_context():
            product = db.session.get(Product, product_id)
            movement = StockMovement.query.filter_by(
                product_id=product.id,
                source_type='spreadsheet_import',
            ).one()
            audit_log = AuditLog.query.filter_by(
                action='product_updated',
                entity_type='product',
                entity_id=str(product.id),
            ).one()

        self.assertEqual(product.name, 'Skol 269ml unidade')
        self.assertEqual(float(product.cost_price), 2.5)
        self.assertEqual(float(product.sale_price), 4.0)
        self.assertEqual(product.stock_quantity, 9)
        self.assertEqual(product.min_stock_quantity, 2)
        self.assertEqual(movement.previous_stock, 3)
        self.assertEqual(movement.new_stock, 9)
        self.assertIn('atualizado por importação', audit_log.description)

    def test_api_settings_import_products_rejects_operator_user(self):
        user, _ = self.create_api_user(
            role='operator',
            can_manage_settings=True,
            can_manage_products=True,
        )
        login_data = self.api_login(user.username, 'SenhaApi123').get_json()['data']
        csv_bytes = (
            'produto;categoria;valor de custo;valor de venda;estoque atual\n'
            'Skol 269ml unidade;Cerveja;2,50;4,00;12\n'
        ).encode('utf-8')

        response = self.client.post(
            '/api/v1/settings/import/products',
            data={'spreadsheet': (io.BytesIO(csv_bytes), 'produtos.csv')},
            content_type='multipart/form-data',
            headers=self.bearer_header(login_data['access_token']),
        )
        error = response.get_json()['errors'][0]

        self.assertEqual(response.status_code, 403)
        self.assertEqual(error['code'], 'permission_denied')

    def test_api_settings_profile_updates_current_user_and_audits(self):
        user, _ = self.create_api_user(first_name='Nome antigo', phone='1111')
        login_data = self.api_login(user.username, 'SenhaApi123').get_json()['data']

        response = self.client.put(
            '/api/v1/settings/profile',
            json={
                'first_name': 'Rafael',
                'last_name': 'Borges',
                'phone': '32999990000',
            },
            headers=self.bearer_header(login_data['access_token']),
        )
        data = response.get_json()['data']

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['profile']['first_name'], 'Rafael')
        self.assertEqual(data['profile']['last_name'], 'Borges')
        self.assertEqual(data['profile']['phone'], '32999990000')
        with self.app.app_context():
            updated_user = db.session.get(User, user.id)
            audit_log = AuditLog.query.filter_by(
                action='profile_updated',
                entity_type='user',
                entity_id=str(user.id),
            ).one()
        self.assertEqual(updated_user.first_name, 'Rafael')
        self.assertEqual(updated_user.last_name, 'Borges')
        self.assertEqual(updated_user.phone, '32999990000')
        self.assertIn('aplicativo Windows', audit_log.description)

    def test_api_settings_password_changes_password_and_revokes_desktop_sessions(self):
        user, _ = self.create_api_user()
        login_data = self.api_login(user.username, 'SenhaApi123').get_json()['data']

        response = self.client.put(
            '/api/v1/settings/password',
            json={
                'current_password': 'SenhaApi123',
                'new_password': 'NovaSenha123',
                'confirm_password': 'NovaSenha123',
            },
            headers=self.bearer_header(login_data['access_token']),
        )
        data = response.get_json()['data']
        old_access_response = self.client.get(
            '/api/v1/auth/me',
            headers=self.bearer_header(login_data['access_token']),
        )
        old_password_response = self.api_login(user.username, 'SenhaApi123')
        new_password_response = self.api_login(user.username, 'NovaSenha123')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['password_changed'])
        self.assertTrue(data['requires_login'])
        self.assertEqual(old_access_response.status_code, 401)
        self.assertEqual(old_password_response.status_code, 401)
        self.assertEqual(new_password_response.status_code, 200)
        with self.app.app_context():
            revoked_count = ApiRefreshToken.query.filter(
                ApiRefreshToken.user_id == user.id,
                ApiRefreshToken.revoked_at.isnot(None),
            ).count()
            audit_log = AuditLog.query.filter_by(
                action='password_changed',
                entity_type='user',
                entity_id=str(user.id),
            ).one()
        self.assertGreaterEqual(revoked_count, 1)
        self.assertIn('aplicativo Windows', audit_log.description)

    def test_api_settings_team_requires_management_permission(self):
        user, _ = self.create_api_user(
            role='operator',
            can_manage_settings=False,
        )
        login_data = self.api_login(user.username, 'SenhaApi123').get_json()['data']

        response = self.client.get(
            '/api/v1/settings/team',
            headers=self.bearer_header(login_data['access_token']),
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()['errors'][0]['code'], 'permission_denied')

    def test_api_settings_team_creates_employee_with_role_defaults(self):
        admin, company = self.create_api_user()
        login_data = self.api_login(admin.username, 'SenhaApi123').get_json()['data']

        response = self.client.post(
            '/api/v1/settings/team',
            json={
                'username': 'pedro-operador',
                'password': 'Senha123',
                'first_name': 'Pedro',
                'last_name': 'Souza',
                'cpf': '123.456.789-00',
                'email': 'pedro@example.com',
                'phone': '32999990000',
                'role': 'operator',
            },
            headers=self.bearer_header(login_data['access_token']),
        )
        data = response.get_json()['data']

        self.assertEqual(response.status_code, 201)
        self.assertEqual(data['username'], 'pedro-operador')
        self.assertEqual(data['role'], 'operator')
        self.assertEqual(data['role_label'], 'Funcionário')
        self.assertTrue(data['permissions']['can_view_products'])
        self.assertTrue(data['permissions']['can_manage_sales'])
        self.assertTrue(data['permissions']['can_manage_cash_register'])
        self.assertFalse(data['permissions']['can_manage_products'])
        self.assertFalse(data['permissions']['can_view_reports'])
        with self.app.app_context():
            employee = User.query.filter_by(username='pedro-operador').one()
            audit_log = AuditLog.query.filter_by(
                action='employee_created',
                entity_type='user',
                entity_id=str(employee.id),
            ).one()
        self.assertEqual(employee.company_id, company.id)
        self.assertTrue(employee.email_verified)
        self.assertTrue(employee.check_password('Senha123'))
        self.assertIn('contratado pelo aplicativo Windows', audit_log.description)

    def test_api_settings_team_lists_and_updates_employee(self):
        admin, company = self.create_api_user()
        with self.app.app_context():
            employee = User(
                username='maria-operadora',
                first_name='Maria',
                cpf='111.222.333-44',
                email='maria@example.com',
                role='operator',
                company_id=company.id,
                is_active=True,
            )
            employee.set_password('Senha123')
            db.session.add(employee)
            db.session.commit()
            employee_id = employee.id
        login_data = self.api_login(admin.username, 'SenhaApi123').get_json()['data']

        list_response = self.client.get(
            '/api/v1/settings/team?search=maria',
            headers=self.bearer_header(login_data['access_token']),
        )
        update_response = self.client.put(
            f'/api/v1/settings/team/{employee_id}',
            json={
                'first_name': 'Maria Clara',
                'last_name': 'Oliveira',
                'cpf': '555.666.777-88',
                'email': 'mariaclara@example.com',
                'phone': '32988887777',
                'role': 'manager',
                'is_active': False,
            },
            headers=self.bearer_header(login_data['access_token']),
        )
        data = update_response.get_json()['data']

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.get_json()['data']['employees']), 1)
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(data['first_name'], 'Maria Clara')
        self.assertEqual(data['last_name'], 'Oliveira')
        self.assertEqual(data['cpf'], '555.666.777-88')
        self.assertEqual(data['role'], 'manager')
        self.assertFalse(data['is_active'])
        self.assertTrue(data['permissions']['can_manage_products'])
        self.assertTrue(data['permissions']['can_view_reports'])
        self.assertTrue(data['permissions']['can_view_audit_logs'])
        with self.app.app_context():
            updated = db.session.get(User, employee_id)
            audit_log = AuditLog.query.filter_by(
                action='employee_updated',
                entity_type='user',
                entity_id=str(employee_id),
            ).one()
        self.assertEqual(updated.first_name, 'Maria Clara')
        self.assertEqual(updated.phone, '32988887777')
        self.assertEqual(updated.role, 'manager')
        self.assertIn('atualizado pelo aplicativo Windows', audit_log.description)

    def test_api_settings_team_rejects_duplicate_company_cpf(self):
        admin, company = self.create_api_user()
        with self.app.app_context():
            existing = User(
                username='cpf-existente',
                cpf='123.456.789-00',
                role='operator',
                company_id=company.id,
                is_active=True,
            )
            existing.set_password('Senha123')
            db.session.add(existing)
            db.session.commit()
            existing_id = existing.id
        login_data = self.api_login(admin.username, 'SenhaApi123').get_json()['data']

        response = self.client.post(
            '/api/v1/settings/team',
            json={
                'username': 'novo-cpf-duplicado',
                'password': 'Senha123',
                'cpf': '12345678900',
                'role': 'operator',
            },
            headers=self.bearer_header(login_data['access_token']),
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()['errors'][0]['code'], 'cpf_exists')

    def test_api_catalog_lists_only_current_company_products_with_pagination(self):
        user, company = self.create_api_user(
            role='operator',
            can_manage_products=False,
        )
        _, other_company = self.create_api_user(
            username='api-outra-adega',
            company_name='Outra adega',
        )
        with self.app.app_context():
            beverages = Category(name='Bebidas', company_id=company.id)
            snacks = Category(name='Aperitivos', company_id=company.id)
            other_category = Category(name='Bebidas', company_id=other_company.id)
            db.session.add_all([beverages, snacks, other_category])
            db.session.flush()
            db.session.add_all([
                Product(
                    name='Água mineral',
                    barcode='7890001',
                    category_id=beverages.id,
                    company_id=company.id,
                    cost_price=2,
                    sale_price=5,
                    stock_quantity=12,
                    min_stock_quantity=3,
                    active=True,
                ),
                Product(
                    name='Coca Cola 2L',
                    barcode='7890002',
                    category_id=beverages.id,
                    company_id=company.id,
                    cost_price=8,
                    sale_price=12,
                    stock_quantity=7,
                    min_stock_quantity=2,
                    active=True,
                ),
                Product(
                    name='Amendoim',
                    category_id=snacks.id,
                    company_id=company.id,
                    cost_price=3,
                    sale_price=6,
                    stock_quantity=4,
                    active=False,
                ),
                Product(
                    name='Produto de outra adega',
                    category_id=other_category.id,
                    company_id=other_company.id,
                    sale_price=99,
                    stock_quantity=99,
                    active=True,
                ),
            ])
            db.session.commit()

        access_token = self.api_login(user.username, 'SenhaApi123').get_json()['data']['access_token']
        headers = self.bearer_header(access_token)
        first_page = self.client.get(
            '/api/v1/catalog/products?per_page=2&page=1&active=all&sort=name',
            headers=headers,
        )
        search_page = self.client.get(
            '/api/v1/catalog/products?q=7890002',
            headers=headers,
        )

        self.assertEqual(first_page.status_code, 200)
        first_data = first_page.get_json()['data']
        self.assertEqual(first_data['pagination'], {
            'page': 1,
            'per_page': 2,
            'total': 3,
            'total_pages': 2,
        })
        self.assertEqual(
            [product['name'] for product in first_data['items']],
            ['Amendoim', 'Coca Cola 2L'],
        )
        self.assertNotIn('cost_price', first_data['items'][0])
        self.assertEqual(search_page.get_json()['data']['items'][0]['name'], 'Coca Cola 2L')

    def test_api_catalog_products_supports_stock_price_and_creation_filters(self):
        user, company = self.create_api_user(role='operator', can_manage_products=False)
        with self.app.app_context():
            db.session.add_all([
                Product(
                    name='Produto antigo', company_id=company.id,
                    sale_price=5, stock_quantity=0, min_stock_quantity=2,
                    created_at=datetime(2026, 1, 1, 10, 0),
                ),
                Product(
                    name='Produto baixo', company_id=company.id,
                    sale_price=10, stock_quantity=1, min_stock_quantity=3,
                    created_at=datetime(2026, 2, 1, 10, 0),
                ),
                Product(
                    name='Produto novo', company_id=company.id,
                    sale_price=20, stock_quantity=8, min_stock_quantity=2,
                    created_at=datetime(2026, 3, 1, 10, 0),
                ),
            ])
            db.session.commit()

        headers = self.bearer_header(
            self.api_login(user.username, 'SenhaApi123').get_json()['data']['access_token'],
        )
        filtered = self.client.get(
            '/api/v1/catalog/products?active=all&stock=low&min_price=8&max_price=12',
            headers=headers,
        )
        newest = self.client.get(
            '/api/v1/catalog/products?active=all&sort=created_desc',
            headers=headers,
        )
        oldest = self.client.get(
            '/api/v1/catalog/products?active=all&sort=created_asc',
            headers=headers,
        )
        invalid_range = self.client.get(
            '/api/v1/catalog/products?min_price=20&max_price=10',
            headers=headers,
        )

        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(
            [item['name'] for item in filtered.get_json()['data']['items']],
            ['Produto baixo'],
        )
        self.assertEqual(newest.get_json()['data']['items'][0]['name'], 'Produto novo')
        self.assertEqual(oldest.get_json()['data']['items'][0]['name'], 'Produto antigo')
        self.assertEqual(invalid_range.status_code, 422)
        self.assertEqual(invalid_range.get_json()['errors'][0]['field'], 'min_price')

    def test_api_catalog_product_barcode_contract_is_exact_normalized_and_tenant_scoped(self):
        manager, company = self.create_api_user()
        other_manager, other_company = self.create_api_user(
            username='api-barcode-outra-adega',
            company_name='Outra adega barcode',
        )
        with self.app.app_context():
            inactive = Product(
                name='Produto inativo',
                barcode='INATIVO-01',
                company_id=company.id,
                sale_price=4,
                active=False,
            )
            external = Product(
                name='Produto externo',
                barcode='EXTERNO-01',
                company_id=other_company.id,
                sale_price=5,
                active=True,
            )
            shared_other = Product(
                name='Mesmo código em outro tenant',
                barcode='7894900011517',
                company_id=other_company.id,
                sale_price=6,
                active=True,
            )
            db.session.add_all([inactive, external, shared_other])
            db.session.commit()

        manager_headers = self.bearer_header(
            self.api_login(manager.username, 'SenhaApi123').get_json()['data']['access_token'],
        )
        created = self.client.post(
            '/api/v1/catalog/products',
            headers=manager_headers,
            json={
                'name': 'Coca-Cola',
                'barcode': '  7894900011517\r\n',
                'cost_price': 5,
                'sale_price': 10,
                'stock_quantity': 3,
                'min_stock_quantity': 1,
                'active': True,
            },
        )
        exact = self.client.get(
            '/api/v1/catalog/products?barcode=%207894900011517%20&active=all',
            headers=manager_headers,
        )
        partial = self.client.get(
            '/api/v1/catalog/products?barcode=789490001151&active=all',
            headers=manager_headers,
        )
        inactive_hidden = self.client.get(
            '/api/v1/catalog/products?barcode=INATIVO-01&active=active',
            headers=manager_headers,
        )
        inactive_visible = self.client.get(
            '/api/v1/catalog/products?barcode=INATIVO-01&active=all',
            headers=manager_headers,
        )
        cross_tenant = self.client.get(
            '/api/v1/catalog/products?barcode=EXTERNO-01&active=all',
            headers=manager_headers,
        )
        not_found = self.client.get(
            '/api/v1/catalog/products?barcode=NAO-EXISTE&active=all',
            headers=manager_headers,
        )

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.get_json()['data']['barcode'], '7894900011517')
        self.assertEqual(exact.status_code, 200)
        self.assertEqual([item['name'] for item in exact.get_json()['data']['items']], ['Coca-Cola'])
        self.assertEqual(partial.get_json()['data']['items'], [])
        self.assertEqual(inactive_hidden.get_json()['data']['items'], [])
        self.assertEqual(inactive_visible.get_json()['data']['items'][0]['name'], 'Produto inativo')
        self.assertEqual(cross_tenant.get_json()['data']['items'], [])
        self.assertEqual(not_found.get_json()['data']['items'], [])

        other_headers = self.bearer_header(
            self.api_login(other_manager.username, 'SenhaApi123').get_json()['data']['access_token'],
        )
        other_exact = self.client.get(
            '/api/v1/catalog/products?barcode=7894900011517&active=all',
            headers=other_headers,
        )
        self.assertEqual(other_exact.get_json()['data']['items'][0]['name'], 'Mesmo código em outro tenant')

    def test_api_catalog_categories_are_alphabetical_and_company_scoped(self):
        user, company = self.create_api_user()
        with self.app.app_context():
            beverages = Category(name='Bebidas', company_id=company.id)
            snacks = Category(name='Aperitivos', company_id=company.id)
            db.session.add_all([beverages, snacks])
            db.session.flush()
            db.session.add_all([
                Product(name='Água', category_id=beverages.id, company_id=company.id),
                Product(name='Refrigerante', category_id=beverages.id, company_id=company.id),
            ])
            db.session.commit()

        access_token = self.api_login(user.username, 'SenhaApi123').get_json()['data']['access_token']
        response = self.client.get(
            '/api/v1/catalog/categories',
            headers=self.bearer_header(access_token),
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertEqual([category['name'] for category in data['items']], ['Aperitivos', 'Bebidas'])
        self.assertEqual(data['items'][1]['product_count'], 2)

    def test_api_catalog_category_manager_creates_updates_and_deletes_category(self):
        user, company = self.create_api_user()
        access_token = self.api_login(user.username, 'SenhaApi123').get_json()['data']['access_token']
        headers = self.bearer_header(access_token)

        create_response = self.client.post(
            '/api/v1/catalog/categories',
            headers=headers,
            json={'name': 'Destilados'},
        )

        self.assertEqual(create_response.status_code, 201)
        created = create_response.get_json()['data']
        self.assertEqual(created['name'], 'Destilados')
        self.assertEqual(created['product_count'], 0)
        category_id = created['id']
        with self.app.app_context():
            category = db.session.get(Category, category_id)
            self.assertIsNotNone(category)
            self.assertEqual(category.company_id, company.id)
            self.assertEqual(AuditLog.query.filter_by(action='category_created').count(), 1)

        update_response = self.client.put(
            f'/api/v1/catalog/categories/{category_id}',
            headers=headers,
            json={'name': 'Whisky'},
        )

        self.assertEqual(update_response.status_code, 200)
        updated = update_response.get_json()['data']
        self.assertEqual(updated['name'], 'Whisky')
        with self.app.app_context():
            self.assertEqual(db.session.get(Category, category_id).name, 'Whisky')
            self.assertEqual(AuditLog.query.filter_by(action='category_updated').count(), 1)

        delete_response = self.client.delete(
            f'/api/v1/catalog/categories/{category_id}',
            headers=headers,
        )

        self.assertEqual(delete_response.status_code, 200)
        self.assertTrue(delete_response.get_json()['data']['deleted'])
        with self.app.app_context():
            self.assertIsNone(db.session.get(Category, category_id))
            self.assertEqual(AuditLog.query.filter_by(action='category_deleted').count(), 1)

    def test_api_catalog_category_mutation_requires_permission_and_unique_name(self):
        manager, company = self.create_api_user()
        operator, _ = self.create_api_user(
            username='api-categoria-sem-editar',
            company_name='Adega API categoria operador',
            role='operator',
            can_manage_categories=False,
        )
        with self.app.app_context():
            db.session.add(Category(name='Cerveja', company_id=company.id))
            db.session.commit()

        manager_token = self.api_login(manager.username, 'SenhaApi123').get_json()['data']['access_token']
        operator_token = self.api_login(operator.username, 'SenhaApi123').get_json()['data']['access_token']
        duplicate_response = self.client.post(
            '/api/v1/catalog/categories',
            headers=self.bearer_header(manager_token),
            json={'name': 'cerveja'},
        )
        blocked_response = self.client.post(
            '/api/v1/catalog/categories',
            headers=self.bearer_header(operator_token),
            json={'name': 'Sem permissão'},
        )

        self.assertEqual(duplicate_response.status_code, 409)
        self.assertEqual(duplicate_response.get_json()['errors'][0]['code'], 'category_already_exists')
        self.assertEqual(blocked_response.status_code, 403)
        self.assertEqual(blocked_response.get_json()['errors'][0]['code'], 'permission_denied')

    def test_api_catalog_category_delete_rejects_category_with_products(self):
        user, company = self.create_api_user()
        with self.app.app_context():
            category = Category(name='Refrigerantes', company_id=company.id)
            db.session.add(category)
            db.session.flush()
            db.session.add(Product(
                name='Coca Cola 2L',
                category_id=category.id,
                company_id=company.id,
                sale_price=12,
                stock_quantity=5,
                active=True,
            ))
            db.session.commit()
            category_id = category.id

        access_token = self.api_login(user.username, 'SenhaApi123').get_json()['data']['access_token']
        response = self.client.delete(
            f'/api/v1/catalog/categories/{category_id}',
            headers=self.bearer_header(access_token),
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()['errors'][0]['code'], 'category_has_products')
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Category, category_id))

    def test_api_catalog_includes_cost_only_for_product_managers(self):
        user, company = self.create_api_user()
        with self.app.app_context():
            product = Product(
                name='Produto com custo',
                company_id=company.id,
                cost_price=10,
                sale_price=15,
                stock_quantity=5,
            )
            db.session.add(product)
            db.session.commit()

        access_token = self.api_login(user.username, 'SenhaApi123').get_json()['data']['access_token']
        response = self.client.get(
            '/api/v1/catalog/products',
            headers=self.bearer_header(access_token),
        )
        product_data = response.get_json()['data']['items'][0]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(product_data['cost_price'], 10.0)
        self.assertEqual(product_data['profit_amount'], 5.0)
        self.assertEqual(product_data['profit_margin_percent'], 33.33)

    def test_api_catalog_product_manager_creates_product_with_stock_movement(self):
        user, company = self.create_api_user()
        with self.app.app_context():
            category = Category(name='Refrigerantes', company_id=company.id)
            db.session.add(category)
            db.session.commit()
            category_id = category.id

        access_token = self.api_login(user.username, 'SenhaApi123').get_json()['data']['access_token']
        response = self.client.post(
            '/api/v1/catalog/products',
            headers=self.bearer_header(access_token),
            json={
                'name': 'Coca Cola 1L',
                'barcode': '789111',
                'category_id': category_id,
                'cost_price': '6,50',
                'sale_price': '11,00',
                'stock_quantity': 12,
                'min_stock_quantity': 3,
                'active': True,
            },
        )

        self.assertEqual(response.status_code, 201)
        product_data = response.get_json()['data']
        self.assertEqual(product_data['name'], 'Coca Cola 1L')
        self.assertEqual(product_data['category']['name'], 'Refrigerantes')
        self.assertEqual(product_data['stock_quantity'], 12)
        with self.app.app_context():
            product = Product.query.filter_by(company_id=company.id, barcode='789111').one()
            self.assertEqual(product.stock_quantity, 12)
            self.assertEqual(StockMovement.query.filter_by(product_id=product.id).count(), 1)
            self.assertEqual(AuditLog.query.filter_by(action='product_created').count(), 1)

    def test_api_catalog_product_manager_creates_kit_and_validates_component_tenant(self):
        user, company = self.create_api_user()
        _, other_company = self.create_api_user(
            username='api-kit-outra-adega',
            company_name='Outra adega kit',
        )
        with self.app.app_context():
            component = Product(
                name='Garrafa base',
                company_id=company.id,
                cost_price=4,
                sale_price=8,
                stock_quantity=20,
                active=True,
            )
            foreign_component = Product(
                name='Base de outra adega',
                company_id=other_company.id,
                cost_price=3,
                sale_price=7,
                stock_quantity=10,
                active=True,
            )
            db.session.add_all([component, foreign_component])
            db.session.commit()
            component_id = component.id
            foreign_component_id = foreign_component.id

        access_token = self.api_login(user.username, 'SenhaApi123').get_json()['data']['access_token']
        invalid_response = self.client.post(
            '/api/v1/catalog/products',
            headers=self.bearer_header(access_token),
            json={
                'name': 'Kit inválido',
                'sale_price': 20,
                'stock_quantity': 0,
                'min_stock_quantity': 0,
                'is_kit': True,
                'kit_component_product_id': foreign_component_id,
                'kit_component_quantity': 2,
            },
        )
        valid_response = self.client.post(
            '/api/v1/catalog/products',
            headers=self.bearer_header(access_token),
            json={
                'name': 'Kit duas garrafas',
                'sale_price': 20,
                'stock_quantity': 0,
                'min_stock_quantity': 0,
                'is_kit': True,
                'kit_component_product_id': component_id,
                'kit_component_quantity': 2,
            },
        )

        self.assertEqual(invalid_response.status_code, 422)
        self.assertEqual(invalid_response.get_json()['errors'][0]['code'], 'kit_component_not_found')
        self.assertEqual(valid_response.status_code, 201)
        data = valid_response.get_json()['data']
        self.assertTrue(data['is_kit'])
        self.assertEqual(data['kit_component']['id'], component_id)
        self.assertEqual(data['kit_component_quantity'], 2)
        with self.app.app_context():
            kit = Product.query.filter_by(company_id=company.id, name='Kit duas garrafas').one()
            self.assertTrue(kit.is_kit)
            self.assertEqual(kit.kit_component_product_id, component_id)
            self.assertEqual(kit.kit_component_quantity, 2)

    def test_api_catalog_product_update_adjusts_stock_and_rejects_foreign_category(self):
        user, company = self.create_api_user()
        _, other_company = self.create_api_user(
            username='api-produto-outra-adega',
            company_name='Outra adega produto',
        )
        with self.app.app_context():
            category = Category(name='Cervejas', company_id=company.id)
            other_category = Category(name='Cervejas', company_id=other_company.id)
            db.session.add_all([category, other_category])
            db.session.flush()
            product = Product(
                name='Skol',
                barcode='111',
                category_id=category.id,
                company_id=company.id,
                cost_price=3,
                sale_price=5,
                stock_quantity=10,
                min_stock_quantity=2,
                active=True,
            )
            db.session.add(product)
            db.session.commit()
            product_id = product.id
            category_id = category.id
            other_category_id = other_category.id

        access_token = self.api_login(user.username, 'SenhaApi123').get_json()['data']['access_token']
        invalid_response = self.client.put(
            f'/api/v1/catalog/products/{product_id}',
            headers=self.bearer_header(access_token),
            json={
                'name': 'Skol 269ml',
                'barcode': '111',
                'category_id': other_category_id,
                'cost_price': 3,
                'sale_price': 6,
                'stock_quantity': 7,
                'min_stock_quantity': 2,
                'active': True,
            },
        )
        valid_response = self.client.put(
            f'/api/v1/catalog/products/{product_id}',
            headers=self.bearer_header(access_token),
            json={
                'name': 'Skol 269ml',
                'barcode': '111',
                'category_id': category_id,
                'cost_price': 3,
                'sale_price': 6,
                'stock_quantity': 7,
                'min_stock_quantity': 1,
                'active': False,
            },
        )

        self.assertEqual(invalid_response.status_code, 422)
        self.assertEqual(invalid_response.get_json()['errors'][0]['code'], 'category_not_found')
        self.assertEqual(valid_response.status_code, 200)
        data = valid_response.get_json()['data']
        self.assertEqual(data['name'], 'Skol 269ml')
        self.assertEqual(data['stock_quantity'], 7)
        self.assertFalse(data['active'])
        with self.app.app_context():
            product = db.session.get(Product, product_id)
            self.assertEqual(product.stock_quantity, 7)
            self.assertEqual(product.min_stock_quantity, 1)
            self.assertEqual(StockMovement.query.filter_by(product_id=product_id).count(), 1)
            self.assertEqual(AuditLog.query.filter_by(action='product_updated').count(), 1)

    def test_api_catalog_product_manager_deletes_unreferenced_product(self):
        user, company = self.create_api_user()
        with self.app.app_context():
            product = Product(
                name='Produto descartável',
                company_id=company.id,
                cost_price=1,
                sale_price=2,
                stock_quantity=0,
            )
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        access_token = self.api_login(user.username, 'SenhaApi123').get_json()['data']['access_token']
        response = self.client.delete(
            f'/api/v1/catalog/products/{product_id}',
            headers=self.bearer_header(access_token),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['data']['deleted'])
        with self.app.app_context():
            self.assertIsNone(db.session.get(Product, product_id))
            self.assertEqual(AuditLog.query.filter_by(action='product_deleted').count(), 1)

    def test_api_catalog_product_delete_rejects_product_used_by_kit(self):
        user, company = self.create_api_user()
        with self.app.app_context():
            base_product = Product(
                name='Produto base',
                company_id=company.id,
                cost_price=1,
                sale_price=2,
                stock_quantity=10,
            )
            db.session.add(base_product)
            db.session.flush()
            kit = Product(
                name='Kit dependente',
                company_id=company.id,
                cost_price=2,
                sale_price=5,
                stock_quantity=0,
                is_kit=True,
                kit_component_product_id=base_product.id,
                kit_component_quantity=2,
            )
            db.session.add(kit)
            db.session.commit()
            product_id = base_product.id

        access_token = self.api_login(user.username, 'SenhaApi123').get_json()['data']['access_token']
        response = self.client.delete(
            f'/api/v1/catalog/products/{product_id}',
            headers=self.bearer_header(access_token),
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()['errors'][0]['code'], 'product_used_by_kit')
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Product, product_id))

    def test_api_catalog_product_mutation_requires_manager_permission_and_unique_barcode(self):
        manager, company = self.create_api_user()
        operator, _ = self.create_api_user(
            username='api-catalogo-sem-editar',
            company_name='Adega API Operador',
            role='operator',
            can_view_products=True,
            can_manage_products=False,
        )
        with self.app.app_context():
            existing = Product(
                name='Produto existente',
                barcode='789dup',
                company_id=company.id,
                cost_price=1,
                sale_price=2,
            )
            db.session.add(existing)
            db.session.commit()
            existing_id = existing.id

        manager_token = self.api_login(manager.username, 'SenhaApi123').get_json()['data']['access_token']
        operator_token = self.api_login(operator.username, 'SenhaApi123').get_json()['data']['access_token']
        duplicate_response = self.client.post(
            '/api/v1/catalog/products',
            headers=self.bearer_header(manager_token),
            json={
                'name': 'Duplicado',
                'barcode': '789dup',
                'cost_price': 1,
                'sale_price': 3,
                'stock_quantity': 0,
                'min_stock_quantity': 0,
                'active': True,
            },
        )
        forbidden_response = self.client.post(
            '/api/v1/catalog/products',
            headers=self.bearer_header(operator_token),
            json={
                'name': 'Produto operador',
                'cost_price': 1,
                'sale_price': 3,
                'stock_quantity': 0,
                'min_stock_quantity': 0,
                'active': True,
            },
        )
        forbidden_delete_response = self.client.delete(
            f'/api/v1/catalog/products/{existing_id}',
            headers=self.bearer_header(operator_token),
        )

        self.assertEqual(duplicate_response.status_code, 409)
        self.assertEqual(duplicate_response.get_json()['errors'][0]['code'], 'barcode_already_exists')
        self.assertEqual(forbidden_response.status_code, 403)
        self.assertEqual(forbidden_delete_response.status_code, 403)

    def test_api_stock_movements_filters_and_summarizes_company_scope(self):
        user, company = self.create_api_user()
        _, other_company = self.create_api_user(
            username='api-estoque-outra-adega',
            company_name='Outra adega estoque',
        )
        with self.app.app_context():
            category = Category(name='Bebidas', company_id=company.id)
            product = Product(
                name='Coca Cola 1L',
                category=category,
                company_id=company.id,
                cost_price=5,
                sale_price=11,
                stock_quantity=5,
                active=True,
            )
            other_product = Product(
                name='Produto externo',
                company_id=other_company.id,
                cost_price=1,
                sale_price=2,
                stock_quantity=99,
                active=True,
            )
            db.session.add_all([category, product, other_product])
            db.session.flush()
            movement = StockMovement(
                company_id=company.id,
                product_id=product.id,
                user_id=user.id,
                movement_type='entry',
                source_type='manual',
                quantity=5,
                previous_stock=0,
                new_stock=5,
                unit_cost=5,
                total_cost=25,
                reason='Compra fornecedor',
            )
            other_movement = StockMovement(
                company_id=other_company.id,
                product_id=other_product.id,
                movement_type='entry',
                source_type='manual',
                quantity=99,
                previous_stock=0,
                new_stock=99,
                unit_cost=1,
                total_cost=99,
                reason='Outra adega',
            )
            db.session.add_all([movement, other_movement])
            db.session.commit()
            category_id = category.id

        access_token = self.api_login(user.username, 'SenhaApi123').get_json()['data']['access_token']
        response = self.client.get(
            f'/api/v1/stock/movements?q=fornecedor&category_id={category_id}&movement_type=entry&source_type=manual',
            headers=self.bearer_header(access_token),
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertEqual(len(data['items']), 1)
        self.assertEqual(data['items'][0]['product']['name'], 'Coca Cola 1L')
        self.assertEqual(data['summary']['entries_quantity'], 5)
        self.assertEqual(data['summary']['movement_count'], 1)
        self.assertEqual(data['summary']['product_count'], 1)
        item = data['items'][0]
        self.assertEqual(item['movement_type'], 'entry')
        self.assertEqual(item['movement_type_label'], 'Entrada')
        self.assertEqual(item['origin'], 'manual')
        self.assertEqual(item['origin_label'], 'Entrada manual')
        self.assertEqual(item['signed_quantity'], 5)
        self.assertTrue(item['balance_consistent'])
        self.assertEqual(item['unit_cost'], 5.0)
        self.assertIn({'value': 'entry', 'label': 'Entrada'}, data['movement_types'])
        self.assertIn({'value': str(user.id), 'label': user.username}, data['responsible_users'])
        self.assertTrue(data['costs_visible'])

    def test_api_stock_entry_and_adjustment_mutate_product_stock(self):
        user, company = self.create_api_user()
        with self.app.app_context():
            product = Product(
                name='Skol 269ml',
                company_id=company.id,
                cost_price=3,
                sale_price=6,
                stock_quantity=2,
                active=True,
            )
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        access_token = self.api_login(user.username, 'SenhaApi123').get_json()['data']['access_token']
        entry_response = self.client.post(
            '/api/v1/stock/entries',
            headers=self.bearer_header(access_token),
            json={
                'product_id': product_id,
                'quantity': 3,
                'unit_cost': '4,50',
                'reason': 'Compra de reposição',
                'notes': 'Nota 123',
                'update_cost': True,
            },
        )
        adjustment_response = self.client.post(
            '/api/v1/stock/adjustments',
            headers=self.bearer_header(access_token),
            json={
                'product_id': product_id,
                'adjustment_mode': 'delta',
                'direction': 'out',
                'quantity': 2,
                'reason': 'Quebra',
            },
        )
        positive_adjustment_response = self.client.post(
            '/api/v1/stock/adjustments',
            headers=self.bearer_header(access_token),
            json={
                'product_id': product_id,
                'adjustment_mode': 'delta',
                'direction': 'in',
                'quantity': 4,
                'reason': 'Contagem física',
            },
        )

        self.assertEqual(entry_response.status_code, 201)
        entry_data = entry_response.get_json()['data']
        self.assertEqual(entry_data['movement_type'], 'entry')
        self.assertEqual(entry_data['movement_type_label'], 'Entrada')
        self.assertEqual(entry_data['origin_label'], 'Entrada manual')
        self.assertEqual(entry_data['signed_quantity'], 3)
        self.assertEqual(entry_data['previous_stock'], 2)
        self.assertEqual(entry_data['new_stock'], 5)
        self.assertEqual(entry_data['unit_cost'], 4.5)
        self.assertEqual(entry_data['total_cost'], 13.5)
        self.assertEqual(adjustment_response.status_code, 201)
        adjustment_data = adjustment_response.get_json()['data']
        self.assertTrue(adjustment_data['changed'])
        self.assertEqual(adjustment_data['movement']['movement_type'], 'adjustment_out')
        self.assertEqual(adjustment_data['movement']['movement_type_label'], 'Ajuste -')
        self.assertEqual(adjustment_data['movement']['origin_label'], 'Ajuste manual')
        self.assertEqual(adjustment_data['movement']['signed_quantity'], -2)
        self.assertEqual(adjustment_data['movement']['previous_stock'], 5)
        self.assertEqual(adjustment_data['movement']['new_stock'], 3)
        self.assertEqual(positive_adjustment_response.status_code, 201)
        positive_movement = positive_adjustment_response.get_json()['data']['movement']
        self.assertEqual(positive_movement['movement_type'], 'adjustment_in')
        self.assertEqual(positive_movement['movement_type_label'], 'Ajuste +')
        self.assertEqual(positive_movement['origin_label'], 'Ajuste manual')
        self.assertEqual(positive_movement['signed_quantity'], 4)
        self.assertEqual(positive_movement['previous_stock'], 3)
        self.assertEqual(positive_movement['new_stock'], 7)
        with self.app.app_context():
            product = db.session.get(Product, product_id)
            self.assertEqual(product.stock_quantity, 7)
            self.assertEqual(float(product.cost_price), 4.5)
            self.assertEqual(StockMovement.query.filter_by(product_id=product_id).count(), 3)

    def test_api_stock_movements_redacts_costs_and_falls_back_for_legacy_labels(self):
        user, company = self.create_api_user(
            username='api-estoque-sem-custos',
            role='operator',
            can_view_stock_movements=True,
            can_view_reports=False,
        )
        with self.app.app_context():
            product = Product(
                name='Produto legado', company_id=company.id, cost_price=9,
                sale_price=15, stock_quantity=4, active=True,
            )
            db.session.add(product)
            db.session.flush()
            movement = StockMovement(
                company_id=company.id,
                product_id=product.id,
                user_id=user.id,
                movement_type='',
                source_type='',
                quantity=4,
                previous_stock=0,
                new_stock=4,
                unit_cost=9,
                total_cost=36,
                created_at=datetime.now(timezone.utc),
            )
            db.session.add(movement)
            db.session.commit()

        token = self.api_login(user.username, 'SenhaApi123').get_json()['data']['access_token']
        today = business_today().isoformat()
        response = self.client.get(
            f'/api/v1/stock/movements?user_id={user.id}&start_date={today}&end_date={today}',
            headers=self.bearer_header(token),
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertEqual(len(data['items']), 1)
        item = data['items'][0]
        self.assertEqual(item['movement_type_label'], 'Não informado')
        self.assertEqual(item['origin_label'], 'Não informado')
        self.assertNotIn('unit_cost', item)
        self.assertNotIn('total_cost', item)
        self.assertFalse(data['costs_visible'])

        invalid_range = self.client.get(
            '/api/v1/stock/movements?start_date=2026-08-23&end_date=2026-08-22',
            headers=self.bearer_header(token),
        )
        self.assertEqual(invalid_range.status_code, 422)
        self.assertEqual(invalid_range.get_json()['errors'][0]['code'], 'invalid_date_range')

    def test_api_dashboard_summary_is_aggregated_and_company_scoped(self):
        user, company = self.create_api_user()
        _, other_company = self.create_api_user(
            username='api-dashboard-outra',
            company_name='Outra adega dashboard',
        )
        today = business_today()
        today_start_utc, _ = business_date_range_utc(today, today)
        today_at_ten = today_start_utc + timedelta(hours=10)
        with self.app.app_context():
            product = Product(
                name='Coca Cola 2L',
                company_id=company.id,
                cost_price=7,
                sale_price=12,
                stock_quantity=1,
                min_stock_quantity=2,
                active=True,
            )
            other_product = Product(
                name='Produto de outra adega',
                company_id=other_company.id,
                cost_price=1,
                sale_price=500,
                stock_quantity=0,
                min_stock_quantity=10,
                active=True,
            )
            cash_register = CashRegister(
                company_id=company.id,
                user_id=user.id,
                status='open',
                opening_amount=100,
                opened_at=today_at_ten - timedelta(hours=1),
            )
            db.session.add_all([product, other_product, cash_register])
            db.session.flush()

            first_sale = Sale(
                company_id=company.id,
                user_id=user.id,
                cash_register_id=cash_register.id,
                created_at=today_at_ten,
                total_amount=24,
                final_amount=24,
                payment_status='paid',
            )
            second_sale = Sale(
                company_id=company.id,
                user_id=user.id,
                cash_register_id=cash_register.id,
                created_at=today_at_ten + timedelta(hours=1),
                total_amount=12,
                final_amount=10,
                discount_amount=2,
                payment_status='paid',
            )
            other_sale = Sale(
                company_id=other_company.id,
                created_at=today_at_ten,
                total_amount=500,
                final_amount=500,
                payment_status='paid',
            )
            db.session.add_all([first_sale, second_sale, other_sale])
            db.session.flush()
            second_sale_id = second_sale.id
            db.session.add_all([
                SaleItem(
                    sale_id=first_sale.id,
                    product_id=product.id,
                    quantity=2,
                    unit_price=12,
                    unit_cost_price=7,
                    total_price=24,
                    profit_amount=10,
                ),
                SaleItem(
                    sale_id=second_sale.id,
                    product_id=product.id,
                    quantity=1,
                    unit_price=12,
                    unit_cost_price=7,
                    total_price=12,
                    profit_amount=5,
                ),
                SaleItem(
                    sale_id=other_sale.id,
                    product_id=other_product.id,
                    quantity=1,
                    unit_price=500,
                    unit_cost_price=1,
                    total_price=500,
                    profit_amount=499,
                ),
                Payment(sale_id=first_sale.id, method='money', amount=24),
                Payment(sale_id=second_sale.id, method='pix', amount=10),
                Payment(sale_id=other_sale.id, method='credit', amount=500),
                Payable(
                    company_id=company.id,
                    description='Energia',
                    amount=180,
                    due_date=today + timedelta(days=2),
                    paid=False,
                ),
                Payable(
                    company_id=other_company.id,
                    description='Conta de outra adega',
                    amount=999,
                    due_date=today,
                    paid=False,
                ),
            ])
            db.session.commit()

        token = self.api_login(user.username, 'SenhaApi123').get_json()['data']['access_token']
        response = self.client.get(
            '/api/v1/dashboard/summary?company_id=999999',
            headers=self.bearer_header(token),
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertEqual(data['summary']['sales_count'], 2)
        self.assertEqual(data['summary']['sales_total'], 34.0)
        self.assertEqual(data['summary']['average_ticket'], 17.0)
        self.assertEqual(data['summary']['profit'], 15.0)
        self.assertEqual(data['summary']['low_stock_count'], 1)
        self.assertEqual(data['summary']['payables_due_count'], 1)
        self.assertEqual(data['cash_register']['status'], 'open')
        self.assertEqual(data['cash_register']['sales_total'], 34.0)
        self.assertEqual(data['cash_register']['profit'], 15.0)
        self.assertEqual(
            {item['method']: item['amount'] for item in data['payment_totals']},
            {'money': 24.0, 'pix': 10.0, 'debit': 0.0, 'credit': 0.0},
        )
        self.assertEqual(data['top_products'][0]['name'], 'Coca Cola 2L')
        self.assertEqual(data['top_products'][0]['quantity'], 3)
        self.assertEqual(data['low_stock_products'][0]['name'], 'Coca Cola 2L')
        self.assertEqual(data['recent_sales'][0]['id'], second_sale_id)
        self.assertEqual(data['upcoming_payables'][0]['description'], 'Energia')
        self.assertNotIn('Produto de outra adega', str(data))
        self.assertNotIn('Conta de outra adega', str(data))

    def test_api_dashboard_redacts_financial_details_without_permissions(self):
        user, company = self.create_api_user(
            username='api-dashboard-operador',
            role='operator',
            can_view_reports=False,
            can_manage_payables=False,
        )
        with self.app.app_context():
            cash_register = CashRegister(
                company_id=company.id,
                user_id=user.id,
                status='open',
                opening_amount=50,
            )
            db.session.add(cash_register)
            db.session.flush()
            sale = Sale(
                company_id=company.id,
                user_id=user.id,
                cash_register_id=cash_register.id,
                created_at=datetime.now(),
                total_amount=20,
                final_amount=20,
                payment_status='paid',
            )
            db.session.add(sale)
            db.session.flush()
            db.session.add(Payment(sale_id=sale.id, method='money', amount=20))
            db.session.commit()

        token = self.api_login(user.username, 'SenhaApi123').get_json()['data']['access_token']
        response = self.client.get(
            '/api/v1/dashboard/summary',
            headers=self.bearer_header(token),
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertEqual(data['summary']['sales_total'], 20.0)
        self.assertIsNone(data['summary']['profit'])
        self.assertIsNone(data['summary']['average_ticket'])
        self.assertIsNone(data['summary']['payables_due_count'])
        self.assertIsNone(data['cash_register']['sales_total'])
        self.assertIsNone(data['cash_register']['profit'])
        self.assertEqual(data['payment_totals'], [])
        self.assertEqual(data['upcoming_payables'], [])

    def test_api_reports_summary_aggregates_sales_and_chart_by_company(self):
        user, company = self.create_api_user(username='api-relatorio')
        _, other_company = self.create_api_user(
            username='api-relatorio-outra',
            company_name='Outra adega relatório',
        )
        report_day = date(2026, 7, 10)
        morning = datetime.combine(report_day, datetime.min.time()).replace(hour=9, minute=30)
        evening = datetime.combine(report_day, datetime.min.time()).replace(hour=18, minute=15)
        with self.app.app_context():
            category = Category(name='Bebidas', company_id=company.id)
            product = Product(
                name='Coca Cola 2L',
                category=category,
                company_id=company.id,
                cost_price=7,
                sale_price=12,
                stock_quantity=10,
                active=True,
            )
            snack = Product(
                name='Amendoim',
                company_id=company.id,
                cost_price=3,
                sale_price=6,
                stock_quantity=5,
                active=True,
            )
            other_product = Product(
                name='Produto outra adega',
                company_id=other_company.id,
                cost_price=1,
                sale_price=999,
                stock_quantity=1,
                active=True,
            )
            db.session.add_all([category, product, snack, other_product])
            db.session.flush()
            first_sale = Sale(
                company_id=company.id,
                user_id=user.id,
                created_at=morning,
                total_amount=24,
                discount_amount=0,
                final_amount=24,
                payment_status='paid',
            )
            second_sale = Sale(
                company_id=company.id,
                user_id=user.id,
                created_at=evening,
                total_amount=18,
                discount_amount=2,
                final_amount=16,
                payment_status='paid',
            )
            other_sale = Sale(
                company_id=other_company.id,
                created_at=morning,
                total_amount=999,
                discount_amount=0,
                final_amount=999,
                payment_status='paid',
            )
            db.session.add_all([first_sale, second_sale, other_sale])
            db.session.flush()
            db.session.add_all([
                SaleItem(
                    sale_id=first_sale.id,
                    product_id=product.id,
                    quantity=2,
                    unit_price=12,
                    unit_cost_price=7,
                    total_price=24,
                    profit_amount=10,
                ),
                SaleItem(
                    sale_id=second_sale.id,
                    product_id=product.id,
                    quantity=1,
                    unit_price=12,
                    unit_cost_price=7,
                    total_price=12,
                    profit_amount=5,
                ),
                SaleItem(
                    sale_id=second_sale.id,
                    product_id=snack.id,
                    quantity=1,
                    unit_price=6,
                    unit_cost_price=3,
                    total_price=6,
                    profit_amount=3,
                ),
                SaleItem(
                    sale_id=other_sale.id,
                    product_id=other_product.id,
                    quantity=1,
                    unit_price=999,
                    unit_cost_price=1,
                    total_price=999,
                    profit_amount=998,
                ),
                Payment(sale_id=first_sale.id, method='money', amount=24),
                Payment(sale_id=second_sale.id, method='pix', amount=16),
                Payment(sale_id=other_sale.id, method='credit', amount=999),
            ])
            db.session.commit()

        token = self.api_login(user.username, 'SenhaApi123').get_json()['data']['access_token']
        response = self.client.get(
            '/api/v1/reports/summary?period=custom&start_date=2026-07-10&end_date=2026-07-10&chart_metric=quantity',
            headers=self.bearer_header(token),
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertEqual(data['period'], 'custom')
        self.assertEqual(data['summary']['sales_count'], 2)
        self.assertEqual(data['summary']['items_count'], 4)
        self.assertEqual(data['summary']['subtotal'], 42.0)
        self.assertEqual(data['summary']['discount'], 2.0)
        self.assertEqual(data['summary']['final'], 40.0)
        self.assertEqual(data['summary']['profit'], 18.0)
        self.assertEqual(data['summary']['average_ticket'], 20.0)
        self.assertEqual(
            {payment['method']: payment['amount'] for payment in data['payment_totals']},
            {'money': 24.0, 'pix': 16.0, 'debit': 0.0, 'credit': 0.0},
        )
        self.assertEqual(data['top_products'][0]['name'], 'Coca Cola 2L')
        self.assertEqual(data['top_products'][0]['quantity'], 3)
        self.assertEqual(data['chart']['metric'], 'quantity')
        self.assertEqual(data['chart']['buckets'][0]['sales_count'], 2)
        self.assertEqual(data['chart']['buckets'][0]['total'], 40.0)
        self.assertTrue(data['chart']['buckets'][0]['is_peak'])
        self.assertNotIn('Produto outra adega', str(data))

    def test_api_reports_summary_requires_reports_permission(self):
        user, _ = self.create_api_user(
            username='api-relatorio-bloqueado',
            role='operator',
            can_view_reports=False,
        )
        token = self.api_login(user.username, 'SenhaApi123').get_json()['data']['access_token']

        response = self.client.get(
            '/api/v1/reports/summary',
            headers=self.bearer_header(token),
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()['errors'][0]['code'], 'permission_denied')

    def test_api_reports_products_calculates_product_performance(self):
        user, company = self.create_api_user(username='api-relatorio-produto')
        _, other_company = self.create_api_user(
            username='api-relatorio-produto-outra',
            company_name='Outra adega relatório produto',
        )
        report_day = date(2026, 7, 11)
        sale_time = datetime.combine(report_day, datetime.min.time()).replace(hour=14)
        with self.app.app_context():
            category = Category(name='Cervejas', company_id=company.id)
            product = Product(
                name='Heineken 269ml',
                category=category,
                company_id=company.id,
                cost_price=4,
                sale_price=8,
                stock_quantity=12,
                active=True,
            )
            unsold = Product(
                name='Produto parado',
                category=category,
                company_id=company.id,
                cost_price=2,
                sale_price=5,
                stock_quantity=3,
                active=True,
            )
            other_product = Product(
                name='Produto de outra adega',
                company_id=other_company.id,
                cost_price=1,
                sale_price=99,
                stock_quantity=1,
                active=True,
            )
            db.session.add_all([category, product, unsold, other_product])
            db.session.flush()
            sale = Sale(
                company_id=company.id,
                user_id=user.id,
                created_at=sale_time,
                total_amount=24,
                discount_amount=0,
                final_amount=24,
                payment_status='paid',
            )
            other_sale = Sale(
                company_id=other_company.id,
                created_at=sale_time,
                total_amount=99,
                discount_amount=0,
                final_amount=99,
                payment_status='paid',
            )
            db.session.add_all([sale, other_sale])
            db.session.flush()
            db.session.add_all([
                SaleItem(
                    sale_id=sale.id,
                    product_id=product.id,
                    quantity=3,
                    unit_price=8,
                    unit_cost_price=4,
                    total_price=24,
                    profit_amount=12,
                ),
                SaleItem(
                    sale_id=other_sale.id,
                    product_id=other_product.id,
                    quantity=1,
                    unit_price=99,
                    unit_cost_price=1,
                    total_price=99,
                    profit_amount=98,
                ),
            ])
            db.session.commit()

        token = self.api_login(user.username, 'SenhaApi123').get_json()['data']['access_token']
        response = self.client.get(
            '/api/v1/reports/products?period=custom&start_date=2026-07-11&end_date=2026-07-11&sort=quantity_desc',
            headers=self.bearer_header(token),
        )
        no_sales_response = self.client.get(
            '/api/v1/reports/products?period=custom&start_date=2026-07-11&end_date=2026-07-11&sort=no_sales',
            headers=self.bearer_header(token),
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertEqual(data['summary']['products'], 2)
        self.assertEqual(data['summary']['quantity'], 3)
        self.assertEqual(data['summary']['revenue'], 24.0)
        self.assertEqual(data['summary']['cost'], 12.0)
        self.assertEqual(data['summary']['profit'], 12.0)
        self.assertEqual(data['items'][0]['product_name'], 'Heineken 269ml')
        self.assertEqual(data['items'][0]['quantity'], 3)
        self.assertEqual(data['items'][0]['average_ticket'], 8.0)
        self.assertEqual(data['items'][0]['stock'], 12)
        self.assertNotIn('Produto de outra adega', str(data))

        self.assertEqual(no_sales_response.status_code, 200)
        no_sales_data = no_sales_response.get_json()['data']
        self.assertEqual(no_sales_data['summary']['products'], 1)
        self.assertEqual(no_sales_data['items'][0]['product_name'], 'Produto parado')

    def test_api_cash_register_opens_once_and_returns_current_snapshot(self):
        user, company = self.create_api_user()
        token = self.api_login(user.username, 'SenhaApi123').get_json()['data']['access_token']
        headers = self.bearer_header(token)

        empty_response = self.client.get('/api/v1/cash-registers/summary', headers=headers)
        opened_response = self.client.post(
            '/api/v1/cash-registers/open',
            headers=headers,
            json={'opening_amount': '100,50'},
        )
        duplicate_response = self.client.post(
            '/api/v1/cash-registers/open',
            headers=headers,
            json={'opening_amount': 10},
        )

        self.assertEqual(empty_response.status_code, 200)
        self.assertIsNone(empty_response.get_json()['data']['current_register'])
        self.assertEqual(opened_response.status_code, 201)
        opened = opened_response.get_json()['data']['current_register']
        self.assertEqual(opened['status'], 'open')
        self.assertEqual(opened['opening_amount'], 100.5)
        self.assertEqual(opened['sales_count'], 0)
        self.assertEqual(opened['expected_amount'], 100.5)
        self.assertEqual(duplicate_response.status_code, 409)
        self.assertEqual(
            duplicate_response.get_json()['errors'][0]['code'],
            'cash_register_already_open',
        )
        with self.app.app_context():
            self.assertEqual(
                CashRegister.query.filter_by(company_id=company.id, status='open').count(),
                1,
            )
            self.assertEqual(
                AuditLog.query.filter_by(
                    company_id=company.id,
                    action='cash_register_opened',
                ).count(),
                1,
            )

    def test_api_cash_register_rejects_wrong_close_amount_and_closes_exact_value(self):
        user, company = self.create_api_user()
        token = self.api_login(user.username, 'SenhaApi123').get_json()['data']['access_token']
        headers = self.bearer_header(token)
        opened = self.client.post(
            '/api/v1/cash-registers/open',
            headers=headers,
            json={'opening_amount': 100},
        ).get_json()['data']['current_register']

        with self.app.app_context():
            sale = Sale(
                company_id=company.id,
                user_id=user.id,
                cash_register_id=opened['id'],
                total_amount=25,
                final_amount=25,
                payment_status='paid',
            )
            db.session.add(sale)
            db.session.flush()
            db.session.add(Payment(sale_id=sale.id, method='pix', amount=25))
            db.session.commit()

        mismatch_response = self.client.post(
            '/api/v1/cash-registers/close',
            headers=headers,
            json={
                'cash_register_id': opened['id'],
                'closing_amount': '124,00',
            },
        )
        close_response = self.client.post(
            '/api/v1/cash-registers/close',
            headers=headers,
            json={
                'cash_register_id': opened['id'],
                'closing_amount': '125,00',
            },
        )

        self.assertEqual(mismatch_response.status_code, 422)
        mismatch = mismatch_response.get_json()
        self.assertEqual(mismatch['errors'][0]['code'], 'cash_register_amount_mismatch')
        self.assertIn('Falta R$ 1,00', mismatch['message'])
        self.assertEqual(close_response.status_code, 200)
        closed_data = close_response.get_json()['data']
        self.assertIsNone(closed_data['current_register'])
        self.assertEqual(closed_data['recent_registers'][0]['id'], opened['id'])
        self.assertEqual(closed_data['recent_registers'][0]['closing_amount'], 125.0)
        self.assertEqual(closed_data['recent_registers'][0]['sales_total'], 25.0)
        self.assertEqual(
            {item['method']: item['amount'] for item in closed_data['recent_registers'][0]['payment_totals']},
            {'money': 0.0, 'pix': 25.0, 'debit': 0.0, 'credit': 0.0},
        )
        with self.app.app_context():
            cash_register = db.session.get(CashRegister, opened['id'])
            self.assertEqual(cash_register.status, 'closed')
            self.assertIsNotNone(cash_register.closed_at)
            self.assertEqual(
                AuditLog.query.filter_by(
                    company_id=company.id,
                    action='cash_register_closed',
                ).count(),
                1,
            )

    def test_api_cash_register_redacts_financials_without_reports_permission(self):
        user, _ = self.create_api_user(
            username='api-caixa-operador',
            role='operator',
            can_manage_cash_register=True,
            can_view_reports=False,
        )
        token = self.api_login(user.username, 'SenhaApi123').get_json()['data']['access_token']
        response = self.client.post(
            '/api/v1/cash-registers/open',
            headers=self.bearer_header(token),
            json={'opening_amount': 50},
        )

        self.assertEqual(response.status_code, 201)
        data = response.get_json()['data']
        self.assertFalse(data['permissions']['can_view_financials'])
        self.assertIsNone(data['current_register']['opening_amount'])
        self.assertIsNone(data['current_register']['sales_total'])
        self.assertIsNone(data['current_register']['expected_amount'])
        self.assertEqual(data['current_register']['payment_totals'], [])

    def test_api_cash_register_detail_returns_sale_timeline(self):
        user, company = self.create_api_user(username='api-caixa-timeline')
        token = self.api_login(user.username, 'SenhaApi123').get_json()['data']['access_token']
        headers = self.bearer_header(token)

        with self.app.app_context():
            product = Product(
                name='Heineken unidade',
                company_id=company.id,
                cost_price=4,
                sale_price=8,
                stock_quantity=10,
                active=True,
            )
            cash_register = CashRegister(
                company_id=company.id,
                user_id=user.id,
                status='closed',
                opening_amount=100,
                closing_amount=119,
                opened_at=datetime(2026, 7, 12, 15, 0),
                closed_at=datetime(2026, 7, 12, 18, 0),
            )
            db.session.add_all([product, cash_register])
            db.session.flush()
            sale = Sale(
                company_id=company.id,
                user_id=user.id,
                cash_register_id=cash_register.id,
                created_at=datetime(2026, 7, 12, 16, 15),
                total_amount=16,
                discount_amount=1,
                final_amount=15,
                payment_status='paid',
            )
            db.session.add(sale)
            db.session.flush()
            db.session.add_all([
                SaleItem(
                    sale_id=sale.id,
                    product_id=product.id,
                    quantity=2,
                    unit_price=8,
                    total_price=16,
                ),
                Payment(sale_id=sale.id, method='money', amount=10),
                Payment(sale_id=sale.id, method='pix', amount=5),
            ])
            second_sale = Sale(
                company_id=company.id,
                user_id=user.id,
                cash_register_id=cash_register.id,
                created_at=datetime(2026, 7, 12, 17, 0),
                total_amount=4,
                discount_amount=0,
                final_amount=4,
                payment_status='paid',
            )
            db.session.add(second_sale)
            db.session.flush()
            db.session.add_all([
                SaleItem(
                    sale_id=second_sale.id,
                    product_id=product.id,
                    quantity=1,
                    unit_price=4,
                    total_price=4,
                ),
                Payment(sale_id=second_sale.id, method='money', amount=4),
            ])
            db.session.commit()
            cash_register_id = cash_register.id
            sale_id = sale.id

        response = self.client.get(
            f'/api/v1/cash-registers/{cash_register_id}',
            headers=headers,
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertTrue(data['permissions']['can_view_financials'])
        self.assertEqual(data['cash_register']['id'], cash_register_id)
        self.assertEqual(data['cash_register']['sales_total'], 19.0)
        self.assertEqual(data['cash_register']['payment_totals'][0]['method'], 'money')
        self.assertEqual(len(data['timeline']), 2)
        sale_data = data['timeline'][0]
        self.assertEqual(sale_data['id'], sale_id)
        self.assertEqual(sale_data['time'], '13:15')
        self.assertEqual(sale_data['created_at'], '2026-07-12T16:15:00Z')
        self.assertEqual(sale_data['seller'], user.username)
        self.assertEqual(sale_data['payments_text'], 'Dinheiro, Pix')
        self.assertEqual(sale_data['final_amount'], 15.0)
        self.assertEqual(sale_data['balance_before_sale'], 100.0)
        self.assertEqual(sale_data['balance_after_sale'], 115.0)
        self.assertEqual(sale_data['payments'][0]['amount'], 10.0)
        self.assertEqual(sale_data['items'][0]['product_name'], 'Heineken unidade')
        self.assertEqual(sale_data['items'][0]['quantity'], 2)
        self.assertEqual(data['timeline'][1]['balance_before_sale'], 115.0)
        self.assertEqual(data['timeline'][1]['balance_after_sale'], 119.0)

    def test_api_cash_register_detail_redacts_financials_without_reports_permission(self):
        user, company = self.create_api_user(
            username='api-caixa-detalhe-operador',
            role='operator',
            can_manage_cash_register=True,
            can_view_reports=False,
        )
        token = self.api_login(user.username, 'SenhaApi123').get_json()['data']['access_token']

        with self.app.app_context():
            product = Product(
                name='Produto operador',
                company_id=company.id,
                cost_price=2,
                sale_price=5,
                stock_quantity=4,
                active=True,
            )
            cash_register = CashRegister(
                company_id=company.id,
                user_id=user.id,
                status='open',
                opening_amount=50,
            )
            db.session.add_all([product, cash_register])
            db.session.flush()
            sale = Sale(
                company_id=company.id,
                user_id=user.id,
                cash_register_id=cash_register.id,
                total_amount=5,
                final_amount=5,
                payment_status='paid',
            )
            db.session.add(sale)
            db.session.flush()
            db.session.add_all([
                SaleItem(
                    sale_id=sale.id,
                    product_id=product.id,
                    quantity=1,
                    unit_price=5,
                    total_price=5,
                ),
                Payment(sale_id=sale.id, method='credit', amount=5),
            ])
            db.session.commit()
            cash_register_id = cash_register.id

        response = self.client.get(
            f'/api/v1/cash-registers/{cash_register_id}',
            headers=self.bearer_header(token),
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertFalse(data['permissions']['can_view_financials'])
        self.assertIsNone(data['cash_register']['opening_amount'])
        self.assertEqual(data['cash_register']['payment_totals'], [])
        self.assertIsNone(data['timeline'][0]['final_amount'])
        self.assertIsNone(data['timeline'][0]['balance_before_sale'])
        self.assertIsNone(data['timeline'][0]['balance_after_sale'])
        self.assertIsNone(data['timeline'][0]['payments'][0]['amount'])
        self.assertIsNone(data['timeline'][0]['items'][0]['unit_price'])

    def test_api_cash_register_requires_permission_and_is_company_scoped(self):
        blocked_user, _ = self.create_api_user(
            username='api-caixa-bloqueado',
            role='operator',
            can_manage_cash_register=False,
        )
        allowed_user, allowed_company = self.create_api_user(
            username='api-caixa-permitido',
            company_name='Adega caixa permitida',
        )
        _, other_company = self.create_api_user(
            username='api-caixa-outra',
            company_name='Outra adega caixa',
        )
        with self.app.app_context():
            db.session.add(CashRegister(
                company_id=other_company.id,
                status='open',
                opening_amount=999,
            ))
            db.session.commit()

        blocked_token = self.api_login(
            blocked_user.username,
            'SenhaApi123',
        ).get_json()['data']['access_token']
        blocked_response = self.client.get(
            '/api/v1/cash-registers/summary',
            headers=self.bearer_header(blocked_token),
        )
        allowed_token = self.api_login(
            allowed_user.username,
            'SenhaApi123',
        ).get_json()['data']['access_token']
        scoped_response = self.client.get(
            '/api/v1/cash-registers/summary',
            headers=self.bearer_header(allowed_token),
        )

        self.assertEqual(blocked_response.status_code, 403)
        self.assertEqual(blocked_response.get_json()['errors'][0]['code'], 'permission_denied')
        self.assertEqual(scoped_response.status_code, 200)
        self.assertIsNone(scoped_response.get_json()['data']['current_register'])
        self.assertEqual(scoped_response.get_json()['data']['recent_registers'], [])
        with self.app.app_context():
            self.assertEqual(
                CashRegister.query.filter_by(company_id=allowed_company.id).count(),
                0,
            )

    def test_api_sale_is_atomic_and_idempotent(self):
        user, company = self.create_api_user()
        with self.app.app_context():
            product = Product(
                name='Refrigerante lata',
                company_id=company.id,
                cost_price=3,
                sale_price=5,
                stock_quantity=10,
                active=True,
            )
            cash_register = CashRegister(
                company_id=company.id,
                user_id=user.id,
                status='open',
                opening_amount=100,
            )
            db.session.add_all([product, cash_register])
            db.session.commit()
            product_id = product.id
            cash_register_id = cash_register.id

        token = self.api_login(user.username, 'SenhaApi123').get_json()['data']['access_token']
        idempotency_key = 'sale-api-test-0001'
        headers = {
            **self.bearer_header(token),
            'Idempotency-Key': idempotency_key,
        }
        payload = {
            'idempotency_key': idempotency_key,
            'items': [
                {'product_id': product_id, 'quantity': 1},
                {'product_id': product_id, 'quantity': 2},
            ],
            'discount_amount': '1,00',
            'payments': [
                {'method': 'money', 'amount': '10,00'},
                {'method': 'pix', 'amount': '5,00'},
            ],
        }

        created_response = self.client.post('/api/v1/sales', headers=headers, json=payload)
        repeated_response = self.client.post('/api/v1/sales', headers=headers, json=payload)

        self.assertEqual(created_response.status_code, 201)
        created = created_response.get_json()['data']
        self.assertFalse(created['already_processed'])
        self.assertEqual(created['cash_register_id'], cash_register_id)
        self.assertEqual(created['subtotal'], 15.0)
        self.assertEqual(created['discount_amount'], 1.0)
        self.assertEqual(created['final_amount'], 14.0)
        self.assertEqual(created['paid_amount'], 15.0)
        self.assertEqual(created['change_amount'], 1.0)
        self.assertEqual(created['items'][0]['quantity'], 3)
        self.assertEqual(
            {payment['method']: payment['amount'] for payment in created['payments']},
            {'money': 10.0, 'pix': 5.0},
        )

        self.assertEqual(repeated_response.status_code, 200)
        repeated = repeated_response.get_json()['data']
        self.assertTrue(repeated['already_processed'])
        self.assertEqual(repeated['id'], created['id'])
        with self.app.app_context():
            self.assertEqual(Sale.query.filter_by(company_id=company.id).count(), 1)
            self.assertEqual(SaleItem.query.filter_by(sale_id=created['id']).count(), 1)
            self.assertEqual(Payment.query.filter_by(sale_id=created['id']).count(), 2)
            self.assertEqual(ApiSaleRequest.query.filter_by(company_id=company.id).count(), 1)
            self.assertEqual(db.session.get(Product, product_id).stock_quantity, 7)
            self.assertEqual(
                StockMovement.query.filter_by(
                    company_id=company.id,
                    source_type='sale',
                    source_id=created['id'],
                ).count(),
                1,
            )

    def test_api_sale_failure_rolls_back_and_allows_safe_retry(self):
        user, company = self.create_api_user()
        with self.app.app_context():
            product = Product(
                name='Água mineral',
                company_id=company.id,
                cost_price=2,
                sale_price=6,
                stock_quantity=4,
                active=True,
            )
            cash_register = CashRegister(
                company_id=company.id,
                user_id=user.id,
                status='open',
                opening_amount=50,
            )
            db.session.add_all([product, cash_register])
            db.session.commit()
            product_id = product.id

        token = self.api_login(user.username, 'SenhaApi123').get_json()['data']['access_token']
        idempotency_key = 'sale-api-test-retry'
        headers = {
            **self.bearer_header(token),
            'Idempotency-Key': idempotency_key,
        }
        payload = {
            'items': [{'product_id': product_id, 'quantity': 2}],
            'discount_amount': 0,
            'payments': [{'method': 'pix', 'amount': 10}],
        }

        rejected_response = self.client.post('/api/v1/sales', headers=headers, json=payload)
        payload['payments'][0]['amount'] = 12
        retried_response = self.client.post('/api/v1/sales', headers=headers, json=payload)

        self.assertEqual(rejected_response.status_code, 422)
        self.assertEqual(
            rejected_response.get_json()['errors'][0]['code'],
            'payment_insufficient',
        )
        self.assertEqual(retried_response.status_code, 201)
        with self.app.app_context():
            self.assertEqual(Sale.query.filter_by(company_id=company.id).count(), 1)
            self.assertEqual(ApiSaleRequest.query.filter_by(company_id=company.id).count(), 1)
            self.assertEqual(db.session.get(Product, product_id).stock_quantity, 2)

    def test_api_sale_cancellation_restores_exact_stock_and_is_idempotent(self):
        user, company = self.create_api_user(username='api-cancelamento')
        with self.app.app_context():
            component = Product(
                name='Garrafa unitária', company_id=company.id, cost_price=4,
                sale_price=10, stock_quantity=20, active=True,
            )
            kit = Product(
                name='Kit 3 garrafas', company_id=company.id, cost_price=12,
                sale_price=25, stock_quantity=0, active=True, is_kit=True,
                kit_component=component, kit_component_quantity=3,
            )
            cash_register = CashRegister(
                company_id=company.id, user_id=user.id, status='open', opening_amount=50,
            )
            db.session.add_all([component, kit, cash_register])
            db.session.commit()
            component_id = component.id
            kit_id = kit.id

        token = self.api_login(user.username, 'SenhaApi123').get_json()['data']['access_token']
        headers = {**self.bearer_header(token), 'Idempotency-Key': 'sale-to-cancel-001'}
        created_response = self.client.post('/api/v1/sales', headers=headers, json={
            'items': [{'product_id': kit_id, 'quantity': 2}],
            'payments': [{'method': 'pix', 'amount': 50}],
        })
        self.assertEqual(created_response.status_code, 201)
        sale_id = created_response.get_json()['data']['id']

        cancelled_response = self.client.post(
            f'/api/v1/sales/{sale_id}/cancel',
            headers=self.bearer_header(token),
            json={'reason': 'Cliente desistiu antes de retirar.'},
        )
        repeated_response = self.client.post(
            f'/api/v1/sales/{sale_id}/cancel',
            headers=self.bearer_header(token),
            json={'reason': 'Tentativa duplicada.'},
        )

        self.assertEqual(cancelled_response.status_code, 200)
        cancelled = cancelled_response.get_json()['data']
        self.assertTrue(cancelled['is_cancelled'])
        self.assertEqual(cancelled['status'], 'cancelled')
        self.assertEqual(cancelled['cancellation_reason'], 'Cliente desistiu antes de retirar.')
        self.assertEqual(cancelled['stock_movements'][0]['quantity'], 6)
        self.assertEqual(repeated_response.status_code, 409)
        self.assertEqual(repeated_response.get_json()['errors'][0]['code'], 'sale_already_cancelled')

        with self.app.app_context():
            sale = db.session.get(Sale, sale_id)
            sale_movement = StockMovement.query.filter_by(
                source_type='kit_sale', source_id=sale_id, movement_type='sale',
            ).one()
            self.assertEqual(db.session.get(Product, component_id).stock_quantity, 20)
            self.assertEqual(sale_movement.quantity, 6)
            self.assertEqual(sale_movement.previous_stock, 20)
            self.assertEqual(sale_movement.new_stock, 14)
            self.assertEqual(Payment.query.filter_by(sale_id=sale_id).count(), 1)
            self.assertEqual(SaleItem.query.filter_by(sale_id=sale_id).count(), 1)
            self.assertEqual(
                StockMovement.query.filter_by(
                    source_type='sale_cancellation', source_id=sale_id,
                    movement_type='cancellation',
                ).count(),
                1,
            )
            self.assertEqual(
                AuditLog.query.filter_by(action='sale_cancelled', entity_id=sale_id).count(),
                1,
            )
            self.assertIsNotNone(sale.cancelled_at)
            self.assertEqual(sale.cancelled_by_user_id, user.id)

        report_response = self.client.get('/api/v1/reports/summary', headers=self.bearer_header(token))
        self.assertEqual(report_response.status_code, 200)
        self.assertEqual(report_response.get_json()['data']['summary']['sales_count'], 0)

    def test_api_sale_cancellation_requires_explicit_permission(self):
        user, _ = self.create_api_user(
            username='api-sem-cancelar', role='operator',
            can_manage_sales=True, can_cancel_sales=False,
        )
        token = self.api_login(user.username, 'SenhaApi123').get_json()['data']['access_token']
        response = self.client.post(
            '/api/v1/sales/999/cancel',
            headers=self.bearer_header(token),
            json={'reason': 'Sem permissão.'},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()['errors'][0]['code'], 'permission_denied')

    def test_api_sale_cancellation_is_tenant_scoped(self):
        attacker, _ = self.create_api_user(username='api-empresa-a', company_name='Empresa A')
        owner, owner_company = self.create_api_user(username='api-empresa-b', company_name='Empresa B')
        with self.app.app_context():
            foreign_sale = Sale(
                company_id=owner_company.id,
                user_id=owner.id,
                status='completed',
                total_amount=30,
                final_amount=30,
                payment_status='paid',
            )
            db.session.add(foreign_sale)
            db.session.commit()
            foreign_sale_id = foreign_sale.id

        token = self.api_login(attacker.username, 'SenhaApi123').get_json()['data']['access_token']
        missing_reason_response = self.client.post(
            f'/api/v1/sales/{foreign_sale_id}/cancel',
            headers=self.bearer_header(token),
            json={},
        )
        self.assertEqual(missing_reason_response.status_code, 422)
        self.assertEqual(
            missing_reason_response.get_json()['errors'][0]['code'],
            'text_required',
        )
        response = self.client.post(
            f'/api/v1/sales/{foreign_sale_id}/cancel',
            headers=self.bearer_header(token),
            json={'reason': 'Tentativa entre empresas.'},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()['errors'][0]['code'], 'sale_not_found')
        with self.app.app_context():
            self.assertEqual(db.session.get(Sale, foreign_sale_id).status, 'completed')

    def test_api_sale_requires_open_cash_register(self):
        user, company = self.create_api_user()
        with self.app.app_context():
            product = Product(
                name='Produto sem caixa',
                company_id=company.id,
                sale_price=9,
                stock_quantity=3,
                active=True,
            )
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        token = self.api_login(user.username, 'SenhaApi123').get_json()['data']['access_token']
        response = self.client.post(
            '/api/v1/sales',
            headers={
                **self.bearer_header(token),
                'Idempotency-Key': 'sale-api-no-cash',
            },
            json={
                'items': [{'product_id': product_id, 'quantity': 1}],
                'payments': [{'method': 'money', 'amount': 9}],
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()['errors'][0]['code'], 'cash_register_required')
        with self.app.app_context():
            self.assertEqual(Sale.query.filter_by(company_id=company.id).count(), 0)
            self.assertEqual(ApiSaleRequest.query.filter_by(company_id=company.id).count(), 0)
            self.assertEqual(db.session.get(Product, product_id).stock_quantity, 3)

    def test_api_sale_requires_sales_permission(self):
        user, _ = self.create_api_user(
            username='api-venda-bloqueada',
            role='operator',
            can_manage_sales=False,
        )
        token = self.api_login(user.username, 'SenhaApi123').get_json()['data']['access_token']

        response = self.client.post(
            '/api/v1/sales',
            headers={
                **self.bearer_header(token),
                'Idempotency-Key': 'sale-api-permission',
            },
            json={'items': [], 'payments': []},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()['errors'][0]['code'], 'permission_denied')

    def test_api_today_sales_is_paginated_and_bounded(self):
        user, company = self.create_api_user(username='api-sales-history')
        with self.app.app_context():
            cash_register = CashRegister(
                company_id=company.id,
                user_id=user.id,
                status='open',
                opening_amount=100,
            )
            db.session.add(cash_register)
            db.session.flush()
            db.session.add_all([
                Sale(
                    company_id=company.id,
                    user_id=user.id,
                    cash_register_id=cash_register.id,
                    final_amount=index,
                    payment_status='paid',
                )
                for index in range(1, 66)
            ])
            db.session.commit()

        token = self.api_login(user.username, 'SenhaApi123').get_json()['data']['access_token']
        headers = self.bearer_header(token)
        first = self.client.get('/api/v1/sales/today?page=1&per_page=30', headers=headers)
        third = self.client.get('/api/v1/sales/today?page=3&per_page=30', headers=headers)

        self.assertEqual(first.status_code, 200)
        first_data = first.get_json()['data']
        self.assertEqual(len(first_data['sales']), 30)
        self.assertEqual(first_data['total'], 65)
        self.assertTrue(first_data['has_more'])
        self.assertEqual(first_data['page'], 1)
        third_data = third.get_json()['data']
        self.assertEqual(len(third_data['sales']), 5)
        self.assertFalse(third_data['has_more'])
        self.assertEqual(third_data['page'], 3)

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
            close_test_log_handlers(csrf_app)
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
            close_test_log_handlers(csrf_app)
            csrf_temp_dir.cleanup()

    def test_browser_default_favicon_route_loads(self):
        response = self.client.get('/favicon.ico')

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            response.mimetype,
            {'image/x-icon', 'image/vnd.microsoft.icon'},
        )
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
                'email': 'operador@example.com',
                'password': self.STRONG_PASSWORD,
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Confirmar e-mail'.encode(), response.data)
        self.assertIn('Cadastro criado. Confirme seu e-mail para acessar o sistema.'.encode(), response.data)
        self.assertEqual(response.data.count(b'data-auto-dismiss-ms="6000"'), 2)
        with self.app.app_context():
            user = User.query.filter_by(username='operador').one()
            self.assertEqual(user.email, 'operador@example.com')
            self.assertFalse(user.email_verified)
            self.assertEqual(user.company.name, 'operador')
            self.assertEqual(user.company.activation_key, '')
            self.assertIsNone(user.company.subscription_renews_at)
            self.assertTrue(user.check_password(self.STRONG_PASSWORD))
            self.assertEqual(EmailVerificationCode.query.filter_by(user_id=user.id).count(), 1)

        blocked_response = self.client.get('/dashboard', follow_redirects=True)

        self.assertEqual(blocked_response.status_code, 200)
        self.assertIn('Entrar'.encode(), blocked_response.data)

    def test_register_form_requests_only_username_email_and_password(self):
        response = self.client.get('/login?auth_tab=register')

        self.assertEqual(response.status_code, 200)
        register_panel = response.data.split(b'id="register-panel"', 1)[1]
        self.assertIn(b'name="username"', register_panel)
        self.assertIn(b'name="email"', register_panel)
        self.assertIn(b'name="password"', register_panel)
        self.assertNotIn(b'name="company_name"', register_panel)
        self.assertNotIn(b'name="confirm_password"', register_panel)
        self.assertIn(b'data-register-form', register_panel)
        self.assertIn(b'data-register-submit', register_panel)

    def test_registration_identifier_does_not_commit_orphan_company(self):
        with self.app.app_context():
            company = Company(name='cadastro-concorrente')
            db.session.add(company)
            db.session.flush()
            tenant_module.tenant_database_identifier(company, persist=False)

            duplicate_user = User(
                username='master',
                email='duplicado@example.com',
                role='admin',
                company_id=company.id,
            )
            duplicate_user.set_password(self.STRONG_PASSWORD)
            db.session.add(duplicate_user)

            with self.assertRaises(IntegrityError):
                db.session.flush()
            db.session.rollback()

            self.assertEqual(Company.query.filter_by(name='cadastro-concorrente').count(), 0)

    def test_register_ignores_activation_key_and_shows_plans_after_email_confirmation(self):
        with self.app.app_context():
            db.session.add(ActivationKey(key='ABCD-1234-EFGH-5678', plan='Pro', renews_at=date.today() + timedelta(days=30)))
            db.session.commit()

        response = self.client.post(
            '/login',
            data={
                'form_type': 'register',
                'username': 'operadorcomkey',
                'email': 'key@example.com',
                'activation_key': 'ABCD-1234-EFGH-5678',
                'password': self.STRONG_PASSWORD,
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

    def test_master_can_manage_filter_and_renew_assigned_activation_key(self):
        self.login()
        with self.app.app_context():
            company = Company(name='Adega Licenciada', activation_key='')
            db.session.add(company)
            db.session.commit()
            company_id = company.id

        generated = self.client.post(
            '/master/assinaturas/keys/gerar',
            data={
                'display_name': 'Unidade Centro',
                'plan': 'Pro',
                'billing_cycle': 'quarterly',
                'preset_days': '90',
                'company_id': str(company_id),
            },
            follow_redirects=True,
        )
        self.assertEqual(generated.status_code, 200)
        self.assertIn('Unidade Centro'.encode(), generated.data)
        with self.app.app_context():
            activation_key = ActivationKey.query.filter_by(display_name='Unidade Centro').one()
            key_id = activation_key.id
            original_expiry = activation_key.renews_at
            self.assertEqual(activation_key.assigned_company_id, company_id)
            self.assertEqual(activation_key.payment_cycle, 'quarterly')

        filtered = self.client.get('/master/assinaturas?q=Licenciada&plan=Pro')
        self.assertEqual(filtered.status_code, 200)
        self.assertIn('Unidade Centro'.encode(), filtered.data)

        edited = self.client.post(
            f'/master/assinaturas/keys/{key_id}/editar',
            data={'display_name': 'Unidade Norte', 'plan': 'Basic', 'payment_cycle': 'annual', 'company_id': ''},
            follow_redirects=True,
        )
        self.assertIn('Key atualizada com sucesso.'.encode(), edited.data)

        renewed = self.client.post(
            f'/master/assinaturas/keys/{key_id}/renovar',
            data={'preset_days': '30'},
            follow_redirects=True,
        )
        self.assertIn('Key renovada até'.encode(), renewed.data)
        with self.app.app_context():
            activation_key = db.session.get(ActivationKey, key_id)
            self.assertEqual(activation_key.display_name, 'Unidade Norte')
            self.assertEqual(activation_key.plan, 'Basic')
            self.assertEqual(activation_key.payment_cycle, 'annual')
            self.assertIsNone(activation_key.assigned_company_id)
            self.assertEqual(activation_key.renews_at, original_expiry + timedelta(days=30))

    def test_master_key_generation_can_assign_company_without_activating_it(self):
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
        self.assertIn('Key vinculada gerada'.encode(), response.data)
        with self.app.app_context():
            company = db.session.get(Company, company_id)
            activation_key = ActivationKey.query.filter_by(plan='Basic').one()
            self.assertEqual(company.activation_key, '')
            self.assertEqual(activation_key.assigned_company_id, company_id)
            self.assertIsNone(activation_key.used_by_company_id)
            self.assertIsNone(activation_key.used_at)

    def test_master_revoking_available_key_preserves_history(self):
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
        self.assertIn('Key revogada com sucesso'.encode(), response.data)
        self.assertIn('DROP-KEY1-DROP-KEY2'.encode(), response.data)
        with self.app.app_context():
            activation_key = db.session.get(ActivationKey, key_id)
            self.assertIsNotNone(activation_key)
            self.assertFalse(activation_key.active)
            self.assertIsNotNone(activation_key.revoked_at)

    def test_master_can_clear_unused_key_history_and_preserve_used_keys(self):
        self.login()
        with self.app.app_context():
            company = Company(name='Adega com histórico')
            db.session.add(company)
            db.session.flush()
            revoked = ActivationKey(key='OLD1-OLD2-OLD3-OLD4', plan='Basic', renews_at=date.today(), active=False)
            expired = ActivationKey(key='EXP1-EXP2-EXP3-EXP4', plan='Pro', renews_at=date.today() - timedelta(days=1), active=True)
            used = ActivationKey(key='USED-KEY1-KEY2-KEY3', plan='Pro', renews_at=date.today() - timedelta(days=1), active=False, used_by_company_id=company.id)
            db.session.add_all([revoked, expired, used])
            db.session.commit()
            used_id = used.id

        refused = self.client.post('/master/assinaturas/keys/historico/limpar', data={'confirmation': 'errado'}, follow_redirects=True)
        self.assertIn('confirmação não confere'.encode(), refused.data)

        response = self.client.post('/master/assinaturas/keys/historico/limpar', data={'confirmation': 'LIMPAR HISTORICO'}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Histórico limpo: 2 key(s) removida(s).'.encode(), response.data)
        with self.app.app_context():
            self.assertIsNone(ActivationKey.query.filter_by(key='OLD1-OLD2-OLD3-OLD4').first())
            self.assertIsNone(ActivationKey.query.filter_by(key='EXP1-EXP2-EXP3-EXP4').first())
            self.assertIsNotNone(db.session.get(ActivationKey, used_id))

    def test_master_company_table_is_an_expandable_list(self):
        self.login()
        with self.app.app_context():
            db.session.add(Company(name='Adega expansível', is_system=False))
            db.session.commit()
        response = self.client.get('/master/adegas?view=table')
        self.assertEqual(response.status_code, 200)
        self.assertIn('>Lista<'.encode(), response.data)
        self.assertIn('data-company-row-toggle='.encode(), response.data)
        self.assertIn('role="button"'.encode(), response.data)
        self.assertIn('Clique para ver detalhes'.encode(), response.data)
        self.assertIn('Detalhes da adega'.encode(), response.data)
        self.assertNotIn('<th>Usuários</th>'.encode(), response.data)
        self.assertNotIn('<th>Produtos</th>'.encode(), response.data)
        self.assertNotIn('<th>Vendas</th>'.encode(), response.data)

    def test_master_system_context_is_not_treated_as_customer_company(self):
        self.login()
        with self.app.app_context():
            system_company = db.session.get(Company, self.master_company_id())
            system_company.is_system = True
            customer = Company(name='Adega Cliente Real', is_system=False)
            db.session.add(customer)
            db.session.commit()
            system_company_id = system_company.id

        companies_response = self.client.get('/master/adegas')
        subscriptions_response = self.client.get('/master/assinaturas')
        audit_response = self.client.get('/master/auditoria')
        self.assertIn('Adega Cliente Real'.encode(), companies_response.data)
        self.assertNotIn('Painel Master'.encode(), companies_response.data)
        self.assertIn('Adega Cliente Real'.encode(), subscriptions_response.data)
        self.assertNotIn('Painel Master'.encode(), subscriptions_response.data)
        self.assertIn('Adega Cliente Real'.encode(), audit_response.data)
        self.assertNotIn('>Painel Master<'.encode(), audit_response.data)

        blocked_access = self.client.post(f'/master/adegas/{system_company_id}/acessar', follow_redirects=True)
        self.assertIn('não é uma adega'.encode(), blocked_access.data)

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
                'plan': 'Ultimate',
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
            self.assertEqual(company.subscription_plan, 'Ultimate')
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
        self.assertIn(b'https://wa.me/5511944876166', response.data)
        self.assertIn(b'mailto:suporte.girofy@gmail.com', response.data)
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
                'subscription_plan': 'Ultimate',
                'billing_cycle': 'annual',
                'subscription_started_at': '2026-07-01',
                'subscription_renews_at': '2027-07-01',
            },
            follow_redirects=True,
        )

        self.assertEqual(edit_response.status_code, 200)
        self.assertIn('Adega atualizada com sucesso.'.encode(), edit_response.data)
        self.assertIn('Adega Editada'.encode(), edit_response.data)
        self.assertIn('Ultimate'.encode(), edit_response.data)
        self.assertIn('Anual'.encode(), edit_response.data)
        with self.app.app_context():
            updated_company = db.session.get(Company, company_id)
            self.assertTrue(updated_company.active)
            self.assertEqual(updated_company.subscription_plan, 'Ultimate')
            self.assertEqual(updated_company.billing_cycle, 'annual')
            self.assertEqual(updated_company.activation_key, '')

        generate_key_response = self.client.post(
            f'/master/adegas/{company_id}/editar',
            data={
                'name': 'Adega Editada',
                'active': 'on',
                'view_mode': 'cards',
                'subscription_plan': 'Ultimate',
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
            data={'confirmation': '  ADEGA   editada  '},
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

    def test_master_can_delete_user_but_cannot_delete_own_account(self):
        with self.app.app_context():
            master = User.query.filter_by(username='master').one()
            target = User(
                username='usuario-removivel',
                role='operator',
                company_id=master.company_id,
                is_active=True,
            )
            target.set_password('SenhaForte123')
            db.session.add(target)
            db.session.flush()
            historical_log = AuditLog(
                company_id=master.company_id,
                user_id=target.id,
                user_name=target.username,
                user_role=target.role,
                action='sale_created',
                entity_type='sale',
                entity_id=99,
                description='Registro histórico do usuário.',
            )
            db.session.add(historical_log)
            db.session.commit()
            master_id = master.id
            target_id = target.id
            historical_log_id = historical_log.id

        self.login()
        wrong_confirmation = self.client.post(
            f'/master/usuarios/{target_id}/excluir',
            data={'confirmation': 'outro-usuario'},
            follow_redirects=True,
        )

        self.assertEqual(wrong_confirmation.status_code, 200)
        self.assertIn('usuário informado não confere'.encode(), wrong_confirmation.data)
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(User, target_id))

        delete_response = self.client.post(
            f'/master/usuarios/{target_id}/excluir',
            data={'confirmation': 'usuario-removivel'},
            follow_redirects=True,
        )

        self.assertEqual(delete_response.status_code, 200)
        self.assertIn('Usuário excluído do banco de dados com sucesso.'.encode(), delete_response.data)
        with self.app.app_context():
            self.assertIsNone(db.session.get(User, target_id))
            self.assertIsNone(db.session.get(AuditLog, historical_log_id).user_id)
            deletion_log = AuditLog.query.filter_by(
                action='user_deleted',
                entity_type='user',
                entity_id=target_id,
            ).one()
            self.assertEqual(deletion_log.user_name, 'master')

        self_delete_response = self.client.post(
            f'/master/usuarios/{master_id}/excluir',
            data={'confirmation': 'master'},
            follow_redirects=True,
        )

        self.assertEqual(self_delete_response.status_code, 200)
        self.assertIn('conta master que está em uso'.encode(), self_delete_response.data)
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(User, master_id))

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
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Já existe um usuário com este login.'.encode(), response.data)
        self.assertIn('value="master"'.encode(), response.data)
        self.assertIn('value="master2@example.com"'.encode(), response.data)

    def test_register_resumes_an_unverified_registration_with_the_same_email(self):
        registration_data = {
            'form_type': 'register',
            'username': 'cadastro-pendente',
            'email': 'pendente@example.com',
            'password': self.STRONG_PASSWORD,
        }
        first_response = self.client.post('/login', data=registration_data)
        second_response = self.client.post('/login', data=registration_data, follow_redirects=True)

        self.assertEqual(first_response.status_code, 302)
        self.assertEqual(second_response.status_code, 200)
        self.assertIn('Confirmar e-mail'.encode(), second_response.data)
        self.assertIn('Seu cadastro já foi iniciado. Continue pela confirmação do e-mail.'.encode(), second_response.data)
        self.assertNotIn('Já existe um usuário com este login.'.encode(), second_response.data)
        with self.app.app_context():
            user = User.query.filter_by(username='cadastro-pendente').one()
            self.assertFalse(user.email_verified)
            self.assertEqual(Company.query.filter_by(name='cadastro-pendente').count(), 1)
            self.assertEqual(EmailVerificationCode.query.filter_by(user_id=user.id, used=False).count(), 1)

    def test_register_error_preserves_entered_fields(self):
        response = self.client.post(
            '/login',
            data={
                'form_type': 'register',
                'username': 'cliente',
                'email': 'email-invalido',
                'password': self.STRONG_PASSWORD,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Este e-mail não parece válido.'.encode(), response.data)
        self.assertIn('value="cliente"'.encode(), response.data)
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
        due_date = business_today() + timedelta(days=2)

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
        self.assertIn('R$ 1.500,00'.encode(), create_response.data)

        dashboard_response = self.client.get('/dashboard')

        self.assertEqual(dashboard_response.status_code, 200)
        self.assertIn('Conta próxima do vencimento'.encode(), dashboard_response.data)
        self.assertIn('Aluguel vence em 2 dias. Valor: R$ 1.500,00.'.encode(), dashboard_response.data)

        with self.app.app_context():
            payable_id = Payable.query.filter_by(description='Aluguel').one().id

        pay_response = self.client.post(f'/contas-a-pagar/{payable_id}/pagar', follow_redirects=True)

        self.assertEqual(pay_response.status_code, 200)
        self.assertIn('Conta marcada como paga.'.encode(), pay_response.data)
        with self.app.app_context():
            self.assertTrue(db.session.get(Payable, payable_id).paid)

    def test_payables_reject_invalid_amount_and_preserve_decimal_value(self):
        self.login()
        invalid_response = self.client.post(
            '/contas-a-pagar',
            data={'description': 'Inválida', 'amount': 'abc', 'due_date': '2026-08-30'},
            follow_redirects=True,
        )
        self.assertEqual(invalid_response.status_code, 200)
        self.assertIn('valor monetário válido'.encode(), invalid_response.data)

        valid_response = self.client.post(
            '/contas-a-pagar',
            data={'description': 'Fornecedor decimal', 'amount': '2.480,35', 'due_date': '2026-08-30'},
            follow_redirects=True,
        )
        self.assertEqual(valid_response.status_code, 200)
        with self.app.app_context():
            self.assertEqual(Payable.query.filter_by(description='Inválida').count(), 0)
            payable = Payable.query.filter_by(description='Fornecedor decimal').one()
            self.assertEqual(payable.amount, Decimal('2480.35'))

    def test_api_payables_create_list_pay_reopen_and_validate_contract(self):
        user, _ = self.create_api_user(username='financeiro-api')
        login_response = self.api_login(user.username, 'SenhaApi123')
        token = login_response.get_json()['data']['access_token']
        headers = self.bearer_header(token)

        create_response = self.client.post(
            '/api/v1/payables',
            headers=headers,
            json={
                'description': 'Energia API',
                'category': 'Luz',
                'amount': '2.480,35',
                'due_date': '2026-08-30',
                'notes': 'Competência agosto',
            },
        )
        self.assertEqual(create_response.status_code, 201)
        created = create_response.get_json()['data']
        self.assertEqual(created['amount'], '2480.35')
        self.assertEqual(created['due_date'], '2026-08-30')
        self.assertTrue(created['created_at'].endswith('Z'))

        list_response = self.client.get('/api/v1/payables?status=all', headers=headers)
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.get_json()['data']['items'][0]['amount'], '2480.35')

        categories_response = self.client.get('/api/v1/payables/categories', headers=headers)
        self.assertEqual(categories_response.status_code, 200)
        self.assertIn('Luz', categories_response.get_json()['data'])

        filtered_response = self.client.get(
            '/api/v1/payables?status=open&q=Energia&category=Luz&start_date=2026-08-01&end_date=2026-08-31',
            headers=headers,
        )
        self.assertEqual(filtered_response.status_code, 200)
        self.assertEqual([item['description'] for item in filtered_response.get_json()['data']['items']], ['Energia API'])

        payable_id = created['id']
        paid_response = self.client.post(f'/api/v1/payables/{payable_id}/pay', headers=headers)
        self.assertEqual(paid_response.status_code, 200)
        self.assertTrue(paid_response.get_json()['data']['paid'])
        self.assertTrue(paid_response.get_json()['data']['paid_at'].endswith('Z'))

        reopened_response = self.client.post(f'/api/v1/payables/{payable_id}/reopen', headers=headers)
        self.assertEqual(reopened_response.status_code, 200)
        self.assertFalse(reopened_response.get_json()['data']['paid'])
        self.assertIsNone(reopened_response.get_json()['data']['paid_at'])

        invalid_money = self.client.post(
            '/api/v1/payables',
            headers=headers,
            json={'description': 'Inválida', 'amount': 'abc', 'due_date': '2026-08-30'},
        )
        self.assertEqual(invalid_money.status_code, 422)
        self.assertEqual(invalid_money.get_json()['errors'][0]['field'], 'amount')

        invalid_date = self.client.post(
            '/api/v1/payables',
            headers=headers,
            json={'description': 'Data impossível', 'amount': '10.00', 'due_date': '2025-02-29'},
        )
        self.assertEqual(invalid_date.status_code, 422)
        self.assertEqual(invalid_date.get_json()['errors'][0]['field'], 'due_date')

        inverted_range = self.client.get(
            '/api/v1/payables?start_date=2026-09-01&end_date=2026-08-01',
            headers=headers,
        )
        self.assertEqual(inverted_range.status_code, 422)

        other_user, _ = self.create_api_user(username='outro-financeiro', company_name='Outro tenant')
        other_login = self.api_login(other_user.username, 'SenhaApi123')
        other_headers = self.bearer_header(other_login.get_json()['data']['access_token'])
        cross_tenant_pay = self.client.post(f'/api/v1/payables/{payable_id}/pay', headers=other_headers)
        self.assertEqual(cross_tenant_pay.status_code, 404)

        restricted_user, _ = self.create_api_user(
            username='sem-contas',
            company_name='Tenant restrito',
            role='operator',
            can_manage_payables=False,
        )
        restricted_login = self.api_login(restricted_user.username, 'SenhaApi123')
        restricted_headers = self.bearer_header(restricted_login.get_json()['data']['access_token'])
        self.assertEqual(self.client.get('/api/v1/payables', headers=restricted_headers).status_code, 403)

    def test_api_payables_list_survives_legacy_amount_above_transaction_limit(self):
        user, company = self.create_api_user(username='financeiro-legado')
        login_response = self.api_login(user.username, 'SenhaApi123')
        token = login_response.get_json()['data']['access_token']
        headers = self.bearer_header(token)

        with self.app.app_context():
            db.session.add(Payable(
                company_id=company.id,
                description='Conta legada de alto valor',
                category='Outros',
                amount=Decimal('7898630000000.00'),
                due_date=date(2026, 8, 30),
            ))
            db.session.commit()

        list_response = self.client.get('/api/v1/payables?status=all', headers=headers)

        self.assertEqual(list_response.status_code, 200)
        data = list_response.get_json()['data']
        self.assertEqual(data['items'][0]['amount'], '7898630000000.00')
        self.assertEqual(data['summary']['open_amount'], '7898630000000.00')

        create_response = self.client.post(
            '/api/v1/payables',
            headers=headers,
            json={
                'description': 'Conta nova após legado',
                'category': 'Outros',
                'amount': '25,90',
                'due_date': '2026-08-31',
            },
        )
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.get_json()['data']['amount'], '25.90')

    def test_web_payable_search_and_status_filters_work_together(self):
        self.login()
        with self.app.app_context():
            company_id = self.master_company_id()
            db.session.add_all([
                Payable(company_id=company_id, description='Internet', category='Internet', amount=Decimal('65.99'), due_date=business_today()),
                Payable(company_id=company_id, description='Aluguel antigo', category='Aluguel', amount=Decimal('900.00'), due_date=business_today() - timedelta(days=1)),
                Payable(company_id=company_id, description='Energia paga', category='Luz', amount=Decimal('100.00'), due_date=business_today(), paid=True),
            ])
            db.session.commit()

        response = self.client.get('/contas-a-pagar?status=due_today&q=internet&category=Internet')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<strong>Internet</strong>', response.data)
        self.assertNotIn(b'<strong>Aluguel antigo</strong>', response.data)
        self.assertNotIn(b'<strong>Energia paga</strong>', response.data)

    def test_paying_payable_resolves_due_notification_and_reopen_restores_it(self):
        user, _ = self.create_api_user(username='alerta-conta')
        login_response = self.api_login(user.username, 'SenhaApi123')
        headers = self.bearer_header(login_response.get_json()['data']['access_token'])
        created = self.client.post(
            '/api/v1/payables',
            headers=headers,
            json={
                'description': 'Conta vence hoje',
                'amount': '65,99',
                'due_date': business_today().isoformat(),
            },
        ).get_json()['data']

        initial_notifications = self.client.get('/api/v1/notifications', headers=headers).get_json()['data']['items']
        self.assertIn('payable_due_today', {item['notification_type'] for item in initial_notifications})

        self.client.post(f"/api/v1/payables/{created['id']}/pay", headers=headers)
        paid_notifications = self.client.get('/api/v1/notifications', headers=headers).get_json()['data']['items']
        self.assertNotIn('payable_due_today', {item['notification_type'] for item in paid_notifications})

        self.client.post(f"/api/v1/payables/{created['id']}/reopen", headers=headers)
        reopened_notifications = self.client.get('/api/v1/notifications', headers=headers).get_json()['data']['items']
        self.assertIn('payable_due_today', {item['notification_type'] for item in reopened_notifications})

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

    def test_api_password_recovery_accepts_username_and_keeps_response_generic(self):
        self.create_api_user(username='recuperavel')

        existing = self.client.post(
            '/api/v1/auth/password-recovery/request',
            json={'identifier': '  recuperavel  '},
        )
        missing = self.client.post(
            '/api/v1/auth/password-recovery/request',
            json={'identifier': 'nao-existe'},
        )

        self.assertEqual(existing.status_code, 200)
        self.assertEqual(existing.get_json(), missing.get_json())
        self.assertEqual(existing.get_json()['data'], {'requested': True})
        self.assertNotIn('token', existing.get_data(as_text=True).lower())
        self.assertNotIn('email', existing.get_data(as_text=True).lower())
        with self.app.app_context():
            self.assertEqual(PasswordResetToken.query.count(), 1)
            self.assertTrue(
                self.app.config['TEST_LAST_PASSWORD_RESET_URL'].startswith(
                    'http://localhost/reset-password/'
                )
            )

    def test_api_password_recovery_rejects_empty_identifier(self):
        response = self.client.post(
            '/api/v1/auth/password-recovery/request',
            json={'identifier': '   '},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()['errors'][0]['code'], 'identifier_required')

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
        self.assertNotIn('data-user-theme-choice'.encode(), response.data)
        self.assertIn('Sair da conta'.encode(), response.data)
        self.assertIn('Senha criptografada'.encode(), response.data)
        self.assertIn('Email protegido'.encode(), response.data)
        self.assertIn('Importação'.encode(), response.data)
        self.assertIn('Baixar planilha exemplo'.encode(), response.data)

    def test_subscriptions_page_shows_only_the_three_supported_plans(self):
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
        self.assertIn('Ultimate'.encode(), response.data)
        self.assertNotIn('Essencial'.encode(), response.data)
        self.assertNotIn('Profissional'.encode(), response.data)
        self.assertNotIn('Premium'.encode(), response.data)
        self.assertIn('R$ 89,90'.encode(), response.data)
        self.assertIn('R$ 149,90'.encode(), response.data)
        self.assertIn('Solicitar contratação'.encode(), response.data)
        self.assertNotIn('Ativar assinatura com key'.encode(), response.data)

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

    @patch('app.routes.auth.send_alert_email', return_value=2)
    def test_settings_sends_email_alert_test_without_changing_settings(self, send_alert_email_mock):
        self.login()

        response = self.client.post(
            '/configuracoes',
            data={
                'form_type': 'email_alerts',
                'email_alert_action': 'test',
                'alert_recipients_product_out_of_stock': 'dono@example.com, gerente@example.com',
                'alert_recipients_product_low_stock': 'dono@example.com',
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('E-mail de teste enviado para 2 destinatário(s).'.encode(), response.data)
        recipients = send_alert_email_mock.call_args.args[1]
        self.assertEqual(recipients, ['dono@example.com', 'gerente@example.com'])

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
            self.assertIn('Backup SkyGest', Path(company.backup_last_path).read_text(encoding='utf-8'))

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

    def test_product_form_uses_responsive_sections_and_remote_kit_search(self):
        self.login()
        with self.app.app_context():
            company_id = self.master_company_id()
            db.session.add(Product(
                name='Coca-Cola Zero 2L',
                barcode='7894900700046',
                sale_price=12.9,
                stock_quantity=12,
                active=True,
                company_id=company_id,
            ))
            db.session.commit()

        response = self.client.get('/catalogo/produtos/novo')

        self.assertEqual(response.status_code, 200)
        self.assertIn('product-create-form'.encode(), response.data)
        self.assertIn('Informações básicas'.encode(), response.data)
        self.assertIn('data-product-profit-margin'.encode(), response.data)
        self.assertIn('data-autocomplete-show-on-focus'.encode(), response.data)
        self.assertIn('data-autocomplete-url="/catalogo/produtos/sugestoes-kit"'.encode(), response.data)
        self.assertIn('Pesquisar por nome ou código de barras...'.encode(), response.data)
        self.assertNotIn('Coca-Cola Zero 2L'.encode(), response.data)

        by_name = self.client.get('/catalogo/produtos/sugestoes-kit?q=coca')
        by_barcode = self.client.get('/catalogo/produtos/sugestoes-kit?q=7894900700046')
        too_short = self.client.get('/catalogo/produtos/sugestoes-kit?q=c')

        self.assertEqual(by_name.status_code, 200)
        self.assertEqual(by_barcode.status_code, 200)
        self.assertEqual(by_name.get_json()['items'][0]['value'], 'Coca-Cola Zero 2L')
        self.assertEqual(by_barcode.get_json()['items'][0]['barcode'], '7894900700046')
        self.assertEqual(too_short.get_json(), {'items': []})

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

    def test_web_sale_uses_shared_idempotency_contract(self):
        self.login()
        self.open_cash_register(amount='0,00')
        with self.app.app_context():
            product = Product(
                name='Produto idempotente', sale_price=12.50, stock_quantity=3,
                active=True, company_id=self.master_company_id(),
            )
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        payload = {
            'idempotency_key': 'web-sale-idempotency-test',
            'product_id[]': [str(product_id)],
            'quantity[]': ['1'],
            'payment_money': '12,50',
        }
        first = self.client.post('/vendas/nova', data=payload, follow_redirects=True)
        second = self.client.post('/vendas/nova', data=payload, follow_redirects=True)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertIn('Venda já processada.'.encode(), second.data)
        with self.app.app_context():
            self.assertEqual(Sale.query.count(), 1)
            self.assertEqual(ApiSaleRequest.query.count(), 1)
            self.assertEqual(db.session.get(Product, product_id).stock_quantity, 2)
            audit = AuditLog.query.filter_by(action='sale_completed').one()
            self.assertIn('"client": "web"', audit.new_values)

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

    def test_new_sale_searches_products_on_demand(self):
        self.login()

        with self.app.app_context():
            company_id = self.master_company_id()
            user_id = User.query.filter_by(username='master').one().id
            db.session.add(CashRegister(company_id=company_id, user_id=user_id, status='open', opening_amount=0))
            db.session.add_all([
                Product(name='Cerveja Alpha', barcode='111', sale_price=10, stock_quantity=5, active=True, company_id=company_id),
                Product(name='Cerveja Beta', barcode='222', sale_price=11, stock_quantity=3, active=True, company_id=company_id),
                Product(name='Whisky Oculto', barcode='333', sale_price=80, stock_quantity=2, active=True, company_id=company_id),
            ])
            db.session.commit()

        page = self.client.get('/vendas/nova')
        self.assertEqual(page.status_code, 200)
        self.assertIn('data-product-search-url="/api/produtos/busca"'.encode(), page.data)
        self.assertNotIn('Cerveja Alpha'.encode(), page.data)

        search = self.client.get('/api/produtos/busca?q=cerveja')
        self.assertEqual(search.status_code, 200)
        payload = search.get_json()
        self.assertEqual([item['name'] for item in payload['products']], ['Cerveja Alpha', 'Cerveja Beta'])
        self.assertNotIn('Whisky Oculto', [item['name'] for item in payload['products']])

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
            self.assertEqual(movement.source_type, 'kit_sale')
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


    def test_notification_api_lists_marks_and_dismisses_only_current_company(self):
        user, company = self.create_api_user(username='notify-admin')
        other_user, other_company = self.create_api_user(
            username='notify-other', company_name='Outra Adega',
        )
        login_response = self.api_login('notify-admin', 'SenhaApi123')
        token = login_response.get_json()['data']['access_token']

        with self.app.app_context():
            own, _ = create_notification(
                db.session,
                company_id=company.id,
                notification_type='product_low_stock',
                category='stock',
                severity='warning',
                title='Estoque baixo',
                message='Produto com estoque baixo.',
                deduplication_key=f'low:{company.id}:1',
            )
            create_notification(
                db.session,
                company_id=other_company.id,
                notification_type='payable_overdue',
                category='payables',
                severity='critical',
                title='Conta de outra adega',
                message='Não pode aparecer.',
                deduplication_key=f'overdue:{other_company.id}:1',
            )
            db.session.commit()
            own_id = own.id

        response = self.client.get(
            '/api/v1/notifications?severity=warning',
            headers=self.bearer_header(token),
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['unread_count'], 1)
        self.assertEqual(data['items'][0]['title'], 'Estoque baixo')

        read_response = self.client.put(
            f'/api/v1/notifications/{own_id}/read',
            headers=self.bearer_header(token),
        )
        self.assertEqual(read_response.status_code, 200)
        self.assertTrue(read_response.get_json()['data']['is_read'])

        dismiss_response = self.client.put(
            f'/api/v1/notifications/{own_id}/dismiss',
            headers=self.bearer_header(token),
        )
        self.assertEqual(dismiss_response.status_code, 200)
        count_response = self.client.get(
            '/api/v1/notifications/unread-count',
            headers=self.bearer_header(token),
        )
        self.assertEqual(count_response.get_json()['data']['unread_count'], 0)

    def test_notification_deduplication_and_preferences(self):
        user, company = self.create_api_user(username='notify-preferences')
        login_response = self.api_login('notify-preferences', 'SenhaApi123')
        token = login_response.get_json()['data']['access_token']

        with self.app.app_context():
            first, created_first = create_notification(
                db.session,
                company_id=company.id,
                notification_type='payable_overdue',
                category='payables',
                severity='critical',
                title='Conta vencida',
                message='Conta vencida.',
                deduplication_key=f'payable:{company.id}:9',
            )
            second, created_second = create_notification(
                db.session,
                company_id=company.id,
                notification_type='payable_overdue',
                category='payables',
                severity='critical',
                title='Conta vencida novamente',
                message='Não deve duplicar.',
                deduplication_key=f'payable:{company.id}:9',
            )
            db.session.commit()
            self.assertTrue(created_first)
            self.assertFalse(created_second)
            self.assertEqual(first.id, second.id)
            self.assertEqual(Notification.query.filter_by(company_id=company.id).count(), 1)

        preference_response = self.client.put(
            '/api/v1/notifications/preferences',
            headers=self.bearer_header(token),
            json={
                'in_app_enabled': True,
                'desktop_enabled': True,
                'email_enabled': True,
                'minimum_severity': 'warning',
                'email_recipients': 'alertas@girofy.test',
                'quiet_hours_start': '22:00',
                'quiet_hours_end': '07:00',
                'daily_digest_enabled': True,
                'daily_digest_time': '08:30',
            },
        )
        self.assertEqual(preference_response.status_code, 200)
        preference = preference_response.get_json()['data']
        self.assertEqual(preference['minimum_severity'], 'warning')
        self.assertEqual(preference['email_recipients'], 'alertas@girofy.test')
        self.assertEqual(preference['quiet_hours_start'], '22:00')
        self.assertEqual(preference['quiet_hours_end'], '07:00')
        self.assertTrue(preference['daily_digest_enabled'])
        self.assertEqual(preference['daily_digest_time'], '08:30')

        invalid_time = self.client.put(
            '/api/v1/notifications/preferences',
            headers=self.bearer_header(token),
            json={'quiet_hours_start': '25:00', 'quiet_hours_end': '07:00'},
        )
        self.assertEqual(invalid_time.status_code, 422)
        self.assertEqual(invalid_time.get_json()['errors'][0]['field'], 'quiet_hours_start')

        with self.app.app_context():
            self.assertEqual(NotificationPreference.query.filter_by(
                company_id=company.id, user_id=user.id,
            ).count(), 1)

    def test_email_alert_settings_api_matches_web_contract(self):
        user, company = self.create_api_user(username='email-alert-settings')
        token = self.api_login('email-alert-settings', 'SenhaApi123').get_json()['data']['access_token']
        headers = self.bearer_header(token)

        response = self.client.get('/api/v1/notifications/email-alert-settings', headers=headers)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertEqual(data['company_name'], 'Adega API')
        self.assertEqual(len(data['items']), 5)

        items = data['items']
        items[0]['enabled'] = True
        items[0]['recipients'] = 'primeiro@girofy.test, segundo@girofy.test'
        update = self.client.put(
            '/api/v1/notifications/email-alert-settings',
            headers=headers,
            json={'items': items},
        )
        self.assertEqual(update.status_code, 200)
        updated = update.get_json()['data']['items'][0]
        self.assertTrue(updated['enabled'])
        self.assertEqual(updated['recipients'], ['primeiro@girofy.test', 'segundo@girofy.test'])

        with self.app.app_context():
            saved = EmailAlertSetting.query.filter_by(
                company_id=company.id,
                alert_type=items[0]['alert_type'],
            ).one()
            self.assertEqual(saved.recipient_list, ['primeiro@girofy.test', 'segundo@girofy.test'])

    @patch('app.routes.api.v1.send_alert_email', return_value=2)
    def test_email_alert_settings_api_sends_test_message(self, send_alert_email_mock):
        self.create_api_user(username='email-alert-test')
        token = self.api_login('email-alert-test', 'SenhaApi123').get_json()['data']['access_token']

        response = self.client.post(
            '/api/v1/notifications/email-alert-settings/test',
            headers=self.bearer_header(token),
            json={'recipients': ['dono@girofy.test', 'dono@girofy.test', 'gerente@girofy.test']},
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertEqual(data['sent_count'], 2)
        self.assertEqual(data['recipients'], ['dono@girofy.test', 'gerente@girofy.test'])
        self.assertEqual(send_alert_email_mock.call_args.args[1], data['recipients'])

    def test_email_alert_settings_api_rejects_invalid_test_recipient(self):
        self.create_api_user(username='email-alert-invalid')
        token = self.api_login('email-alert-invalid', 'SenhaApi123').get_json()['data']['access_token']

        response = self.client.post(
            '/api/v1/notifications/email-alert-settings/test',
            headers=self.bearer_header(token),
            json={'recipients': ['email-invalido']},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()['errors'][0]['code'], 'invalid_email')

    def test_email_alert_settings_are_shared_between_web_and_windows_api(self):
        user, company = self.create_api_user(username='shared-email-alert-settings')
        token = self.api_login('shared-email-alert-settings', 'SenhaApi123').get_json()['data']['access_token']
        headers = self.bearer_header(token)

        with self.app.app_context():
            db.session.add(EmailAlertSetting(
                company_id=company.id,
                alert_type='product_low_stock',
                enabled=True,
                recipients='web@girofy.test',
            ))
            db.session.commit()

        loaded_by_app = self.client.get('/api/v1/notifications/email-alert-settings', headers=headers)
        self.assertEqual(loaded_by_app.status_code, 200)
        app_items = loaded_by_app.get_json()['data']['items']
        low_stock = next(item for item in app_items if item['alert_type'] == 'product_low_stock')
        self.assertTrue(low_stock['enabled'])
        self.assertEqual(low_stock['recipients'], ['web@girofy.test'])

        low_stock['enabled'] = False
        low_stock['recipients'] = ['app@girofy.test']
        updated_by_app = self.client.put(
            '/api/v1/notifications/email-alert-settings',
            headers=headers,
            json={'items': app_items},
        )
        self.assertEqual(updated_by_app.status_code, 200)

        with self.app.app_context():
            loaded_by_web = EmailAlertSetting.query.filter_by(
                company_id=company.id,
                alert_type='product_low_stock',
            ).one()
            self.assertFalse(loaded_by_web.enabled)
            self.assertEqual(loaded_by_web.recipient_list, ['app@girofy.test'])

    def test_notification_api_materializes_web_stock_and_payable_alerts(self):
        user, company = self.create_api_user(username='notify-operational')
        token = self.api_login('notify-operational', 'SenhaApi123').get_json()['data']['access_token']
        with self.app.app_context():
            db.session.add(Product(
                name='Produto crítico', sale_price=10, stock_quantity=0,
                min_stock_quantity=2, active=True, company_id=company.id,
            ))
            db.session.add(Payable(
                description='Fornecedor vencido', amount=125.50,
                due_date=date.today() - timedelta(days=2), paid=False, company_id=company.id,
            ))
            db.session.commit()

        response = self.client.get('/api/v1/notifications', headers=self.bearer_header(token))

        self.assertEqual(response.status_code, 200)
        items = response.get_json()['data']['items']
        self.assertIn('product_out_of_stock', {item['notification_type'] for item in items})
        self.assertIn('payable_overdue', {item['notification_type'] for item in items})
        self.assertEqual(len(items), 2)

        repeated = self.client.get('/api/v1/notifications', headers=self.bearer_header(token))
        self.assertEqual(repeated.get_json()['data']['total'], 2)


if __name__ == '__main__':
    unittest.main()
