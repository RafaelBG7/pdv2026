from decimal import Decimal

from app.extensions import db


class Payment(db.Model):
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'))
    method = db.Column(db.String(50), default='money')
    amount = db.Column(db.Numeric(18, 2), nullable=False, default=Decimal('0.00'), server_default='0')
    sale = db.relationship('Sale', back_populates='payments')
