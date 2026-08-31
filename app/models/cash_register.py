from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db


class CashRegister(db.Model):
    __tablename__ = 'cash_registers'

    id = db.Column(db.Integer, primary_key=True)
    opened_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    closed_at = db.Column(db.DateTime, nullable=True)
    opening_amount = db.Column(db.Numeric(18, 2), nullable=False, default=Decimal('0.00'), server_default='0')
    closing_amount = db.Column(db.Numeric(18, 2), nullable=False, default=Decimal('0.00'), server_default='0')
    status = db.Column(db.String(20), default='open')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True)
    sales = db.relationship('Sale', backref='cash_register')
