import hashlib
import json
import math
import time

from flask import current_app, flash, g, has_request_context, jsonify, render_template, request
from flask_login import current_user
from flask_limiter.errors import RateLimitExceeded
from redis import Redis
from redis.exceptions import RedisError


SENSITIVE_ENDPOINTS = {
    'auth.login',
    'auth.forgot_password',
    'auth.resend_verification_code',
    'auth.subscription_activation',
    'api_v1.api_login',
    'api_v1.api_request_password_recovery',
    'api_v1.api_activate_subscription',
    'api_v1.api_refresh',
}


def trusted_request_ip():
    """Return the client address after ProxyFix has validated trusted hops."""
    return request.remote_addr or 'unknown'


def _digest(value):
    normalized = (value or '').strip().casefold()
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:24] if normalized else 'anonymous'


def request_identifier():
    if request.is_json:
        payload = request.get_json(silent=True) or {}
        return str(payload.get('identifier') or payload.get('username') or payload.get('email') or '')
    return str(request.form.get('username') or request.form.get('email') or '')


def anonymous_identity_key():
    return f'ip:{trusted_request_ip()}'


def login_identity_key():
    return f'{anonymous_identity_key()}:identity:{_digest(request_identifier())}'


def token_identity_key():
    payload = request.get_json(silent=True) or {}
    token = str(payload.get('refresh_token') or '')
    return f'{anonymous_identity_key()}:refresh:{_digest(token)}'


def api_identity_key():
    authorization = request.headers.get('Authorization', '')
    if authorization.lower().startswith('bearer '):
        return f'api-token:{_digest(authorization[7:])}'
    return anonymous_identity_key()


def authenticated_identity_key():
    api_user = getattr(g, 'api_user', None)
    if api_user is not None:
        return f'company:{api_user.company_id}:user:{api_user.id}'
    if current_user and current_user.is_authenticated:
        return f'company:{current_user.company_id}:user:{current_user.id}'
    return anonymous_identity_key()


def default_rate_limit_key():
    if not has_request_context():
        return 'no-request'
    return authenticated_identity_key()


def configured_limit(name, fallback):
    def resolve():
        return str(current_app.config.get(name, fallback))
    return resolve


def _is_api_request():
    return request.path.startswith('/api/v1/')


def _retry_after(error):
    response = getattr(error, 'response', None)
    if response is not None:
        return response.headers.get('Retry-After')
    try:
        from app.extensions import limiter
        current_limit = limiter.current_limit
        if current_limit and current_limit.reset_at:
            return str(max(1, math.ceil(current_limit.reset_at - time.time())))
    except (AttributeError, RuntimeError, TypeError):
        pass
    return '60'


def log_rate_limit_event(error=None, event='rate_limit_exceeded'):
    limit = str(getattr(error, 'limit', '') or getattr(error, 'description', '') or '')
    context = {
        'event': event,
        'ip': trusted_request_ip(),
        'endpoint': request.endpoint,
        'method': request.method,
        'request_id': getattr(g, 'request_id', None),
        'limit': limit[:160],
    }
    api_user = getattr(g, 'api_user', None)
    actor = api_user if api_user is not None else (current_user if current_user.is_authenticated else None)
    if actor is not None:
        context['user_id'] = getattr(actor, 'id', None)
        context['company_id'] = getattr(actor, 'company_id', None)
    current_app.logger.warning(
        'Rate limit de segurança | contexto=%s',
        json.dumps(context, ensure_ascii=False, default=str),
        extra={'security_event': True},
    )


def rate_limit_error_response(error):
    log_rate_limit_event(error)
    retry_after = _retry_after(error)
    message = 'Muitas requisições foram realizadas. Aguarde alguns instantes e tente novamente.'
    if _is_api_request():
        payload = {
            'success': False,
            'data': None,
            'message': message,
            'errors': [{'code': 'rate_limit_exceeded', 'message': message}],
        }
        if retry_after:
            payload['retry_after'] = retry_after
        response = jsonify(payload)
    else:
        flash(message, 'warning')
        response = current_app.make_response(render_template('errors/429.html', retry_after=retry_after))
    response.status_code = 429
    if retry_after:
        response.headers['Retry-After'] = retry_after
    response.headers['Cache-Control'] = 'no-store'
    return response


def rate_limit_storage_error_response(error):
    log_rate_limit_event(event='rate_limit_storage_unavailable')
    message = 'A proteção de segurança está temporariamente indisponível. Tente novamente em instantes.'
    if _is_api_request():
        response = jsonify({
            'success': False,
            'data': None,
            'message': message,
            'errors': [{'code': 'rate_limit_unavailable', 'message': message}],
        })
    else:
        response = current_app.make_response(render_template('errors/503.html', message=message))
    response.status_code = 503
    response.headers['Retry-After'] = '30'
    response.headers['Cache-Control'] = 'no-store'
    return response


def redis_health_status():
    if not current_app.config.get('RATELIMIT_ENABLED', True):
        return 'disabled'
    storage_uri = str(current_app.config.get('RATELIMIT_STORAGE_URI', 'memory://'))
    if storage_uri.startswith('memory://'):
        return 'memory'
    client = None
    try:
        client = Redis.from_url(storage_uri, socket_connect_timeout=1, socket_timeout=1)
        return 'ok' if client.ping() else 'error'
    except RedisError:
        return 'error'
    finally:
        if client is not None:
            client.close()


def init_rate_limit_errors(app):
    app.register_error_handler(RateLimitExceeded, rate_limit_error_response)
    app.register_error_handler(RedisError, rate_limit_storage_error_response)
