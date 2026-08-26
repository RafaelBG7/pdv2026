import hashlib
from datetime import datetime, timezone

from app.extensions import db


def utc_now_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AppRegistrationCode(db.Model):
    __tablename__ = 'app_registration_codes'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    code_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    state_hash = db.Column(db.String(64), nullable=False)
    code_challenge = db.Column(db.String(64), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utc_now_naive, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True, index=True)

    user = db.relationship('User')

    @staticmethod
    def digest(value):
        return hashlib.sha256(value.encode('utf-8')).hexdigest()
