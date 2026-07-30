import secrets
from datetime import datetime, timedelta, timezone

from flask import current_app, url_for
from sqlalchemy import or_
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import PasswordResetToken, User
from app.services.email_service import send_password_reset_email


PASSWORD_RESET_TTL_MINUTES = 30


def _public_reset_url(token):
    base_url = (current_app.config.get('PUBLIC_BASE_URL') or '').rstrip('/')
    path = url_for('auth.reset_password', token=token)
    return f'{base_url}{path}' if base_url else url_for(
        'auth.reset_password',
        token=token,
        _external=True,
    )


def request_password_recovery(identifier):
    """Request recovery without revealing whether an eligible account exists."""
    normalized_identifier = str(identifier or '').strip()
    user = User.query.filter(or_(
        User.username == normalized_identifier,
        User.email == normalized_identifier,
    )).first()
    if not user or not user.is_active or not user.email or not user.email_verified:
        return False

    PasswordResetToken.query.filter_by(user_id=user.id, used=False).update({'used': True})
    token = secrets.token_urlsafe(32)
    reset_record = PasswordResetToken(
        user_id=user.id,
        token_hash=generate_password_hash(token, method='scrypt'),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=PASSWORD_RESET_TTL_MINUTES),
        used=False,
    )
    db.session.add(reset_record)
    db.session.commit()
    reset_url = _public_reset_url(token)
    if current_app.config.get('MAIL_SUPPRESS_SEND'):
        current_app.config['TEST_LAST_PASSWORD_RESET_TOKEN'] = token
        current_app.config['TEST_LAST_PASSWORD_RESET_URL'] = reset_url
    send_password_reset_email(user, reset_url)
    current_app.logger.info('Email de recuperação enviado para user_id=%s', user.id)
    return True
