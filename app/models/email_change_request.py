from datetime import datetime, timezone

from app.extensions import db


class EmailChangeRequest(db.Model):
    __tablename__ = 'email_change_requests'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    old_email = db.Column(db.String(255), nullable=False)
    new_email = db.Column(db.String(255), nullable=False)
    token_hash = db.Column(db.String(255), nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    confirmed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', back_populates='email_change_requests')

