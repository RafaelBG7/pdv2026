import json
import logging
import time
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import g, has_request_context, request
from flask.signals import got_request_exception
from flask_login import current_user


SENSITIVE_FIELDS = {
    'password',
    'confirm_password',
    'current_password',
    'new_password',
    'csrf_token',
    'secret',
    'token',
}


def _safe_value(value):
    if value is None:
        return None

    text = str(value)
    if len(text) > 500:
        return f'{text[:500]}...'
    return text


def _redact_mapping(mapping):
    redacted = {}
    for key in mapping:
        values = mapping.getlist(key) if hasattr(mapping, 'getlist') else [mapping.get(key)]
        if key.lower() in SENSITIVE_FIELDS:
            redacted[key] = '[protegido]'
            continue

        safe_values = [_safe_value(value) for value in values]
        redacted[key] = safe_values[0] if len(safe_values) == 1 else safe_values
    return redacted


def error_context():
    if not has_request_context():
        return {}

    user_context = {'authenticated': False}
    if current_user and current_user.is_authenticated:
        user_context = {
            'authenticated': True,
            'id': current_user.get_id(),
            'username': getattr(current_user, 'username', None),
            'role': getattr(current_user, 'role', None),
            'company_id': getattr(current_user, 'company_id', None),
        }

    started_at = getattr(g, 'request_started_at', None)
    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2) if started_at else None

    return {
        'request_id': getattr(g, 'request_id', None),
        'method': request.method,
        'path': request.path,
        'full_path': request.full_path,
        'endpoint': request.endpoint,
        'remote_addr': request.headers.get('X-Forwarded-For', request.remote_addr),
        'user_agent': request.headers.get('User-Agent'),
        'referrer': request.referrer,
        'args': _redact_mapping(request.args),
        'form': _redact_mapping(request.form),
        'elapsed_ms': elapsed_ms,
        'user': user_context,
    }


def _json_context():
    return json.dumps(error_context(), ensure_ascii=False, default=str)


def log_http_error(app, error):
    status_code = getattr(error, 'code', 500) or 500
    level = logging.ERROR if status_code >= 500 else logging.WARNING
    app.logger.log(
        level,
        'Erro HTTP %s: %s | contexto=%s',
        status_code,
        getattr(error, 'description', str(error)),
        _json_context(),
    )


def _log_unhandled_exception(sender, exception, **extra):
    sender.logger.error(
        'Falha não tratada: %s | contexto=%s',
        exception,
        _json_context(),
        exc_info=(type(exception), exception, exception.__traceback__),
    )


def setup_error_logging(app):
    log_dir = Path(app.config.get('LOG_DIR') or (Path(app.root_path).parent / 'logs'))
    log_dir.mkdir(parents=True, exist_ok=True)
    app.config['LOG_DIR'] = str(log_dir)

    error_log_path = log_dir / 'errors.log'

    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s [%(name)s] %(message)s'
    )

    for existing_handler in list(app.logger.handlers):
        if getattr(existing_handler, '_adega_error_log', False):
            app.logger.removeHandler(existing_handler)
            existing_handler.close()

    handler = RotatingFileHandler(
        error_log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8',
    )
    handler.setLevel(logging.WARNING)
    handler.setFormatter(formatter)
    handler._adega_error_log = True
    app.logger.addHandler(handler)

    app.logger.setLevel(logging.INFO)

    @app.before_request
    def start_error_context():
        g.request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
        g.request_started_at = time.perf_counter()

    @app.after_request
    def attach_request_id(response):
        response.headers['X-Request-ID'] = getattr(g, 'request_id', '')
        return response

    got_request_exception.connect(_log_unhandled_exception, app)
