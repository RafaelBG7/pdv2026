import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models import AppRegistrationCode
from app.services.api_auth_service import ApiAuthError


APP_CALLBACK_URI = 'girofy://auth/callback'
CODE_TTL_MINUTES = 5


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def valid_callback_request(state, code_challenge):
    if not isinstance(state, str) or not 16 <= len(state) <= 128:
        return False
    if not isinstance(code_challenge, str) or len(code_challenge) != 43:
        return False
    allowed = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_')
    return set(state) <= allowed and set(code_challenge) <= allowed


def create_registration_code(user, state, code_challenge):
    code = secrets.token_urlsafe(32)
    record = AppRegistrationCode(
        user_id=user.id,
        code_hash=AppRegistrationCode.digest(code),
        state_hash=AppRegistrationCode.digest(state),
        code_challenge=code_challenge,
        expires_at=_now() + timedelta(minutes=CODE_TTL_MINUTES),
    )
    db.session.add(record)
    db.session.commit()
    return code


def exchange_registration_code(code, state, code_verifier):
    if not all(isinstance(value, str) and value for value in (code, state, code_verifier)):
        raise ApiAuthError('O callback de cadastro é inválido.', 'invalid_registration_callback', 422)
    record = AppRegistrationCode.query.filter_by(code_hash=AppRegistrationCode.digest(code)).first()
    if record is None or not hmac.compare_digest(record.state_hash, AppRegistrationCode.digest(state)):
        raise ApiAuthError('O callback de cadastro é inválido.', 'invalid_registration_callback', 400)
    if record.used_at is not None:
        raise ApiAuthError('Este callback de cadastro já foi utilizado.', 'registration_code_used', 409)
    if record.expires_at <= _now():
        raise ApiAuthError('O callback de cadastro expirou. Inicie o cadastro novamente.', 'registration_code_expired', 410)
    verifier_digest = hashlib.sha256(code_verifier.encode('ascii')).digest()
    challenge = base64.urlsafe_b64encode(verifier_digest).decode('ascii').rstrip('=')
    if not hmac.compare_digest(record.code_challenge, challenge):
        raise ApiAuthError('O callback de cadastro é inválido.', 'invalid_registration_callback', 400)
    record.used_at = _now()
    db.session.commit()
    return record.user
