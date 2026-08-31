from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db


class StockMovement(db.Model):
    __tablename__ = 'stock_movements'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='SET NULL'), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    movement_type = db.Column(db.String(40), nullable=False, index=True)
    source_type = db.Column(db.String(60), nullable=False, index=True)
    source_id = db.Column(db.Integer, nullable=True, index=True)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    previous_stock = db.Column(db.Integer, nullable=False, default=0)
    new_stock = db.Column(db.Integer, nullable=False, default=0)
    unit_cost = db.Column(db.Numeric(18, 2), nullable=False, default=Decimal('0.00'), server_default='0')
    total_cost = db.Column(db.Numeric(18, 2), nullable=False, default=Decimal('0.00'), server_default='0')
    reason = db.Column(db.String(180), default='')
    notes = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    product = db.relationship('Product', back_populates='stock_movements')
    user = db.relationship('User')
