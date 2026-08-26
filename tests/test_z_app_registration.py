import base64
import hashlib
from datetime import timedelta
import unittest

from app import create_app
from app.extensions import db
from app.models import Company, User, AppRegistrationCode
from app.services.api_auth_service import ApiAuthError
from app.services.app_registration_service import create_registration_code, exchange_registration_code


class TestConfig:
    TESTING = True
    SECRET_KEY = 'registration-test-secret'
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    MAIL_SUPPRESS_SEND = True
    API_ALLOW_INSECURE_AUTH = True
    RATELIMIT_ENABLED = False
    RATELIMIT_STORAGE_URI = 'memory://'
    MASTER_DEFAULT_USERNAME = 'master'
    MASTER_DEFAULT_PASSWORD = 'MasterTest123!'


class AppRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.context = self.app.app_context()
        self.context.push()
        company = Company(name='Cadastro App')
        db.session.add(company)
        db.session.flush()
        self.user = User(
            username='cadastro-app', email='cadastro@app.test', role='admin',
            company_id=company.id, is_active=True, email_verified=True,
        )
        self.user.set_password('SenhaCadastro123!')
        db.session.add(self.user)
        db.session.commit()
        self.state = 'state_' + ('a' * 24)
        self.verifier = 'verifier_' + ('b' * 48)
        self.challenge = base64.urlsafe_b64encode(
            hashlib.sha256(self.verifier.encode('ascii')).digest()
        ).decode('ascii').rstrip('=')

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_code_is_exchanged_once_and_returns_the_registered_user(self):
        code = create_registration_code(self.user, self.state, self.challenge)

        exchanged_user = exchange_registration_code(code, self.state, self.verifier)

        self.assertEqual(exchanged_user.id, self.user.id)
        with self.assertRaises(ApiAuthError) as replay:
            exchange_registration_code(code, self.state, self.verifier)
        self.assertEqual(replay.exception.code, 'registration_code_used')

    def test_expired_and_invalid_callbacks_are_rejected(self):
        code = create_registration_code(self.user, self.state, self.challenge)
        record = AppRegistrationCode.query.one()
        record.expires_at -= timedelta(minutes=10)
        db.session.commit()

        with self.assertRaises(ApiAuthError) as expired:
            exchange_registration_code(code, self.state, self.verifier)
        self.assertEqual(expired.exception.code, 'registration_code_expired')

        with self.assertRaises(ApiAuthError) as invalid:
            exchange_registration_code('invalid', self.state, self.verifier)
        self.assertEqual(invalid.exception.code, 'invalid_registration_callback')


if __name__ == '__main__':
    unittest.main()
