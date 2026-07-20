import hashlib
import hmac
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from flask import current_app, request
from itsdangerous import BadData, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import func, or_
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models import ApiRefreshToken, User


ACCESS_TOKEN_SALT = 'girofy-api-access-v1'
REFRESH_TOKEN_PREFIX = 'grf1'
PERMISSION_FIELDS = (
    'can_view_products',
    'can_manage_products',
    'can_manage_categories',
    'can_manage_sales',
    'can_manage_cash_register',
    'can_view_reports',
    'can_manage_payables',
    'can_manage_settings',
    'can_view_stock_movements',
    'can_manage_stock',
    'can_view_audit_logs',
)

_DUMMY_PASSWORD_HASH = generate_password_hash(
    'girofy-api-invalid-credential',
    method='scrypt',
)
_LOGIN_ATTEMPTS = {}
_LOGIN_ATTEMPTS_LOCK = threading.Lock()


def utc_now_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass(slots=True)
class ApiAuthError(Exception):
    message: str
    code: str
    status_code: int = 401
    field: str | None = None

    def __str__(self):
        return self.message


@dataclass(slots=True)
class AuthenticatedApiUser:
    user: User
    session: ApiRefreshToken


def access_token_lifetime_seconds():
    minutes = max(1, int(current_app.config.get('API_ACCESS_TOKEN_MINUTES', 15)))
    return minutes * 60


def refresh_token_lifetime_days():
    return max(1, int(current_app.config.get('API_REFRESH_TOKEN_DAYS', 30)))


def request_uses_secure_transport():
    if request.is_secure:
        return True
    if not current_app.config.get('TRUST_PROXY_HEADERS', False):
        return False
    forwarded_proto = request.headers.get('X-Forwarded-Proto', '').split(',', 1)[0].strip().lower()
    return forwarded_proto == 'https'


def require_secure_auth_transport():
    allow_insecure = current_app.config.get(
        'API_ALLOW_INSECURE_AUTH',
        bool(current_app.testing or current_app.debug),
    )
    if allow_insecure or request_uses_secure_transport():
        return
    raise ApiAuthError(
        'A autenticação do aplicativo exige uma conexão HTTPS segura.',
        'https_required',
        426,
    )


def _request_ip_address():
    remote_addr = request.remote_addr or ''
    if current_app.config.get('TRUST_PROXY_HEADERS', False):
        forwarded_for = request.headers.get('X-Forwarded-For', '')
        if forwarded_for:
            return forwarded_for.split(',', 1)[0].strip()
    return remote_addr


def _login_attempt_key(identifier):
    return f'{_request_ip_address()}:{(identifier or "").strip().casefold()}'


def _login_attempt_limit():
    return max(1, int(current_app.config.get('API_LOGIN_ATTEMPT_LIMIT', 5)))


def _login_block_seconds():
    return max(1, int(current_app.config.get('API_LOGIN_BLOCK_SECONDS', 15 * 60)))


def _login_is_blocked(identifier):
    key = _login_attempt_key(identifier)
    now = time.monotonic()
    with _LOGIN_ATTEMPTS_LOCK:
        attempt = _LOGIN_ATTEMPTS.get(key)
        if not attempt:
            return False
        blocked_until = attempt.get('blocked_until', 0)
        if blocked_until > now:
            return True
        if blocked_until:
            _LOGIN_ATTEMPTS.pop(key, None)
    return False


def _register_login_failure(identifier):
    key = _login_attempt_key(identifier)
    with _LOGIN_ATTEMPTS_LOCK:
        attempt = _LOGIN_ATTEMPTS.setdefault(key, {'count': 0, 'blocked_until': 0})
        attempt['count'] += 1
        if attempt['count'] >= _login_attempt_limit():
            attempt['blocked_until'] = time.monotonic() + _login_block_seconds()


def _clear_login_failures(identifier):
    with _LOGIN_ATTEMPTS_LOCK:
        _LOGIN_ATTEMPTS.pop(_login_attempt_key(identifier), None)


def clear_api_login_attempts():
    """Clear process-local throttling state. Intended for isolated test suites."""
    with _LOGIN_ATTEMPTS_LOCK:
        _LOGIN_ATTEMPTS.clear()


def _find_user(identifier):
    normalized = (identifier or '').strip().casefold()
    if not normalized:
        return None
    return User.query.filter(or_(
        func.lower(User.username) == normalized,
        func.lower(User.email) == normalized,
    )).first()


def _validate_user_access(user):
    if not user.is_active:
        raise ApiAuthError(
            'Este usuário está inativo. Fale com o administrador da adega.',
            'user_inactive',
            403,
        )
    if not user.email_verified:
        raise ApiAuthError(
            'Seu e-mail ainda não foi confirmado.',
            'email_not_verified',
            403,
        )
    if user.role == 'master':
        return
    company = user.company
    if not company or not company.active:
        raise ApiAuthError(
            'Esta adega está inativa. Fale com o administrador do sistema.',
            'company_inactive',
            403,
        )
    if not company.subscription_valid:
        raise ApiAuthError(
            'A assinatura desta adega precisa ser regularizada.',
            'subscription_required',
            403,
        )


def authenticate_credentials(identifier, password):
    if _login_is_blocked(identifier):
        raise ApiAuthError(
            'Muitas tentativas de login. Aguarde alguns minutos e tente novamente.',
            'login_rate_limited',
            429,
        )

    user = _find_user(identifier)
    password_matches = (
        user.check_password(password)
        if user is not None
        else check_password_hash(_DUMMY_PASSWORD_HASH, password or '')
    )
    if not password_matches:
        _register_login_failure(identifier)
        raise ApiAuthError(
            'Usuário, e-mail ou senha inválidos.',
            'invalid_credentials',
            401,
            'password',
        )

    _clear_login_failures(identifier)
    _validate_user_access(user)
    return user


def authenticate_credentials_for_activation(identifier, password):
    """Validate credentials for subscription activation without bypassing login rules.

    Normal API login intentionally blocks expired subscriptions. The Windows
    client uses this narrower path only to validate the user's password before
    applying an activation key to that same user's company.
    """
    if _login_is_blocked(identifier):
        raise ApiAuthError(
            'Muitas tentativas de login. Aguarde alguns minutos e tente novamente.',
            'login_rate_limited',
            429,
        )

    user = _find_user(identifier)
    password_matches = (
        user.check_password(password)
        if user is not None
        else check_password_hash(_DUMMY_PASSWORD_HASH, password or '')
    )
    if not password_matches:
        _register_login_failure(identifier)
        raise ApiAuthError(
            'Usuário, e-mail ou senha inválidos.',
            'invalid_credentials',
            401,
            'password',
        )

    _clear_login_failures(identifier)
    if not user.is_active:
        raise ApiAuthError(
            'Este usuário está inativo. Fale com o administrador da adega.',
            'user_inactive',
            403,
        )
    if not user.email_verified:
        raise ApiAuthError(
            'Seu e-mail ainda não foi confirmado.',
            'email_not_verified',
            403,
        )
    if user.role == 'master':
        raise ApiAuthError(
            'O painel master não precisa de ativação por key.',
            'company_context_required',
            403,
        )
    company = user.company
    if not company or not company.active:
        raise ApiAuthError(
            'Esta adega está inativa. Fale com o administrador do sistema.',
            'company_inactive',
            403,
        )
    return user


def _credential_hash(user):
    return hashlib.sha256((user.password_hash or '').encode('utf-8')).hexdigest()


def _refresh_token_hash(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _access_serializer():
    secret = current_app.config.get('API_TOKEN_SECRET') or current_app.config['SECRET_KEY']
    return URLSafeTimedSerializer(secret_key=secret, salt=ACCESS_TOKEN_SALT)


def _access_payload(user, session_id):
    return {
        'version': 1,
        'sub': user.id,
        'sid': session_id,
        'company_id': user.company_id,
        'role': user.role,
        'credential_hash': _credential_hash(user),
    }


def _new_refresh_token():
    session_id = secrets.token_urlsafe(32)
    secret = secrets.token_urlsafe(48)
    return session_id, f'{REFRESH_TOKEN_PREFIX}.{session_id}.{secret}'


def issue_token_pair(user):
    session_id, refresh_token = _new_refresh_token()
    now = utc_now_naive()
    refresh_expires_at = now + timedelta(days=refresh_token_lifetime_days())
    session = ApiRefreshToken(
        user_id=user.id,
        session_id=session_id,
        token_hash=_refresh_token_hash(refresh_token),
        credential_hash=_credential_hash(user),
        expires_at=refresh_expires_at,
        ip_address=_request_ip_address(),
        user_agent=request.headers.get('User-Agent', '')[:255],
    )
    db.session.add(session)
    access_token = _access_serializer().dumps(_access_payload(user, session_id))
    return {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'token_type': 'Bearer',
        'expires_in': access_token_lifetime_seconds(),
        'refresh_expires_at': f'{refresh_expires_at.isoformat()}Z',
    }, session


def _parse_refresh_token(refresh_token):
    parts = (refresh_token or '').split('.', 2)
    if len(parts) != 3 or parts[0] != REFRESH_TOKEN_PREFIX or not parts[1] or not parts[2]:
        raise ApiAuthError(
            'A sessão do aplicativo é inválida ou expirou.',
            'invalid_refresh_token',
            401,
        )
    return parts[1]


def _active_refresh_session(refresh_token):
    session_id = _parse_refresh_token(refresh_token)
    session = ApiRefreshToken.query.filter_by(session_id=session_id).first()
    valid_hash = bool(
        session
        and hmac.compare_digest(session.token_hash, _refresh_token_hash(refresh_token))
    )
    if not valid_hash or session.is_revoked or session.is_expired:
        raise ApiAuthError(
            'A sessão do aplicativo é inválida ou expirou.',
            'invalid_refresh_token',
            401,
        )
    if not hmac.compare_digest(session.credential_hash, _credential_hash(session.user)):
        session.revoked_at = utc_now_naive()
        raise ApiAuthError(
            'Sua senha foi alterada. Entre novamente no aplicativo.',
            'credentials_changed',
            401,
        )
    _validate_user_access(session.user)
    return session


def rotate_refresh_token(refresh_token):
    current_session = _active_refresh_session(refresh_token)
    user = current_session.user
    token_pair, replacement_session = issue_token_pair(user)
    current_session.last_used_at = utc_now_naive()
    current_session.revoked_at = current_session.last_used_at
    current_session.replaced_by_session_id = replacement_session.session_id
    return token_pair, user


def authenticate_access_token(access_token):
    try:
        payload = _access_serializer().loads(
            access_token,
            max_age=access_token_lifetime_seconds(),
        )
    except SignatureExpired as error:
        raise ApiAuthError(
            'Sua sessão expirou. Atualize o acesso para continuar.',
            'access_token_expired',
            401,
        ) from error
    except BadData as error:
        raise ApiAuthError(
            'O token de acesso é inválido.',
            'invalid_access_token',
            401,
        ) from error

    if not isinstance(payload, dict) or payload.get('version') != 1:
        raise ApiAuthError('O token de acesso é inválido.', 'invalid_access_token', 401)

    session_id = payload.get('sid')
    user_id = payload.get('sub')
    session = ApiRefreshToken.query.filter_by(session_id=session_id, user_id=user_id).first()
    if not session or session.is_revoked or session.is_expired:
        raise ApiAuthError('Esta sessão foi encerrada.', 'session_revoked', 401)

    user = session.user
    expected_credential_hash = _credential_hash(user)
    if not hmac.compare_digest(str(payload.get('credential_hash') or ''), expected_credential_hash):
        session.revoked_at = utc_now_naive()
        db.session.commit()
        raise ApiAuthError(
            'Sua senha foi alterada. Entre novamente no aplicativo.',
            'credentials_changed',
            401,
        )
    if payload.get('company_id') != user.company_id or payload.get('role') != user.role:
        session.revoked_at = utc_now_naive()
        db.session.commit()
        raise ApiAuthError('O token de acesso é inválido.', 'invalid_access_token', 401)

    _validate_user_access(user)
    return AuthenticatedApiUser(user=user, session=session)


def revoke_session(session):
    if session.revoked_at is None:
        session.revoked_at = utc_now_naive()


def user_permissions(user):
    return {
        permission: bool(user.has_permission(permission))
        for permission in PERMISSION_FIELDS
    }


def user_identity_data(user):
    company = user.company
    return {
        'user': {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name or '',
            'last_name': user.last_name or '',
            'full_name': user.full_name or user.username,
            'email': user.email or '',
            'phone': user.phone or '',
            'role': user.role,
            'role_label': user.role_label,
            'permissions': user_permissions(user),
        },
        'company': None if company is None else {
            'id': company.id,
            'name': company.name,
            'active': bool(company.active),
            'subscription_plan': company.subscription_plan,
            'subscription_renews_at': (
                company.subscription_renews_at.isoformat()
                if company.subscription_renews_at
                else None
            ),
            'subscription_valid': bool(company.subscription_valid),
        },
    }
