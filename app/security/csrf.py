import hmac
import secrets

from flask import abort, current_app, g, render_template, request, session
from flask_login import current_user
from werkzeug.exceptions import BadRequest


CSRF_SESSION_KEY = '_csrf_token'
UNSAFE_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}


class CSRFError(BadRequest):
    description = 'Sua sessão expirou ou o formulário não pôde ser validado.'


def csrf_enabled():
    if current_app.config.get('WTF_CSRF_ENABLED') is False:
        return False
    return bool(current_app.config.get('CSRF_ENABLED', True))


def csrf_token():
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def request_csrf_token():
    return (
        request.form.get('_csrf_token')
        or request.headers.get('X-CSRFToken')
        or request.headers.get('X-CSRF-Token')
        or ''
    )


def validate_csrf_request():
    if request.method not in UNSAFE_METHODS or not csrf_enabled():
        return None
    expected_token = session.get(CSRF_SESSION_KEY)
    provided_token = request_csrf_token()
    if expected_token and provided_token and hmac.compare_digest(expected_token, provided_token):
        return None

    current_app.logger.warning(
        'CSRF inválido endpoint=%s method=%s path=%s user_id=%s request_id=%s',
        request.endpoint,
        request.method,
        request.path,
        current_user.id if current_user.is_authenticated else None,
        getattr(g, 'request_id', None),
    )
    raise CSRFError()


def init_csrf(app):
    @app.context_processor
    def inject_csrf_token():
        return {'csrf_token': csrf_token}

    @app.before_request
    def protect_unsafe_methods():
        return validate_csrf_request()

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return {'error': error.description}, 400
        return render_template('errors/400.html', message=error.description), 400

