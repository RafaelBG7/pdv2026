from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db


class Sale(db.Model):
    __tablename__ = 'sales'

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    total_amount = db.Column(db.Numeric(18, 2), nullable=False, default=Decimal('0.00'), server_default='0')
    discount_amount = db.Column(db.Numeric(18, 2), nullable=False, default=Decimal('0.00'), server_default='0')
    final_amount = db.Column(db.Numeric(18, 2), nullable=False, default=Decimal('0.00'), server_default='0')
    payment_status = db.Column(db.String(20), default='pending')
    status = db.Column(db.String(20), nullable=False, default='completed', index=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    cancelled_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    cancellation_reason = db.Column(db.String(500), default='')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True)
    cash_register_id = db.Column(db.Integer, db.ForeignKey('cash_registers.id'))
    items = db.relationship('SaleItem', back_populates='sale', cascade='all, delete-orphan')
    payments = db.relationship('Payment', back_populates='sale', cascade='all, delete-orphan')
    cancelled_by_user = db.relationship('User', foreign_keys=[cancelled_by_user_id])

    @property
    def is_cancelled(self):
        return self.status == 'cancelled'

    @classmethod
    def valid_filter(cls):
        return cls.status != 'cancelled'
