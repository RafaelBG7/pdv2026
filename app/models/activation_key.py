from datetime import datetime, timezone

from app.extensions import db


class ActivationKey(db.Model):
    __tablename__ = 'activation_keys'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False)
    plan = db.Column(db.String(40), default='Basic')
    display_name = db.Column(db.String(160), default='')
    payment_cycle = db.Column(db.String(20), default='monthly')
    renews_at = db.Column(db.Date, nullable=False)
    active = db.Column(db.Boolean, default=True)
    assigned_company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True)
    used_by_company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True)
    used_at = db.Column(db.DateTime, nullable=True)
    revoked_at = db.Column(db.DateTime, nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    company = db.relationship('Company', foreign_keys=[used_by_company_id])
    assigned_company = db.relationship('Company', foreign_keys=[assigned_company_id])
    created_by = db.relationship('User', foreign_keys=[created_by_user_id])
