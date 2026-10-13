import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.extensions import db
from tests.test_routes import TestConfig, close_test_log_handlers
from scripts.verify_hml_promotion import verify


class SecurityReleaseTests(unittest.TestCase):
    def test_protected_environment_enforces_secure_cookies_and_hsts(self):
        with tempfile.TemporaryDirectory() as directory:
            class SecureConfig(TestConfig):
                ENVIRONMENT = 'homologation'
                SESSION_COOKIE_SECURE = False
                REMEMBER_COOKIE_SECURE = False
                LOG_DIR = Path(directory) / 'logs'
                BACKUP_DIR = Path(directory) / 'backups'
            app = create_app(SecureConfig)
            try:
                response = app.test_client().get('/login', base_url='https://localhost')
                self.assertTrue(app.config['SESSION_COOKIE_SECURE'])
                self.assertTrue(app.config['REMEMBER_COOKIE_SECURE'])
                self.assertIn('max-age=', response.headers['Strict-Transport-Security'])
                self.assertTrue(any('; Secure;' in value for value in response.headers.getlist('Set-Cookie')))
            finally:
                with app.app_context():
                    db.session.remove()
                    db.drop_all()
                    db.engine.dispose()
                close_test_log_handlers(app)

    def test_promotion_rejects_missing_sha(self):
        with patch.dict(os.environ, {'VALIDATED_HML_SHA': ''}):
            with self.assertRaises(SystemExit):
                verify()

    def test_promotion_rejects_nonproduction_branch(self):
        with patch.dict(os.environ, {'VALIDATED_HML_SHA': 'a' * 40, 'GITHUB_REF': 'refs/heads/develop'}):
            with self.assertRaises(SystemExit):
                verify()

    def test_promotion_rejects_different_content(self):
        with patch.dict(os.environ, {'VALIDATED_HML_SHA': 'a' * 40, 'GITHUB_REF': 'refs/heads/main'}):
            with patch('scripts.verify_hml_promotion.subprocess.check_output', side_effect=[b'aaa', b'bbb']):
                with self.assertRaises(SystemExit):
                    verify()
