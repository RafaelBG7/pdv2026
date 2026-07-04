from datetime import datetime, timezone

from app.extensions import db


class ActivationKey(db.Model):
    __tablename__ = 'activation_keys'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False)
    plan = db.Column(db.String(40), default='Basic')
    renews_at = db.Column(db.Date, nullable=False)
    active = db.Column(db.Boolean, default=True)
    used_by_company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    company = db.relationship('Company')
