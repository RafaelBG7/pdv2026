from datetime import datetime, timezone

from app.extensions import db


def utc_now_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ApiRefreshToken(db.Model):
    __tablename__ = 'api_refresh_tokens'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    session_id = db.Column(db.String(96), unique=True, nullable=False, index=True)
    token_hash = db.Column(db.String(64), nullable=False)
    credential_hash = db.Column(db.String(64), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utc_now_naive, nullable=False)
    last_used_at = db.Column(db.DateTime, nullable=True)
    revoked_at = db.Column(db.DateTime, nullable=True, index=True)
    replaced_by_session_id = db.Column(db.String(96), nullable=True)
    ip_address = db.Column(db.String(80), default='')
    user_agent = db.Column(db.String(255), default='')

    user = db.relationship('User', back_populates='api_refresh_tokens')

    @property
    def is_revoked(self):
        return self.revoked_at is not None

    @property
    def is_expired(self):
        return self.expires_at <= utc_now_naive()
