from decimal import Decimal

from app.extensions import db


class SaleItem(db.Model):
    __tablename__ = 'sale_items'

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Numeric(18, 2), nullable=False, default=Decimal('0.00'), server_default='0')
    unit_cost_price = db.Column(db.Numeric(18, 2), nullable=False, default=Decimal('0.00'), server_default='0')
    total_price = db.Column(db.Numeric(18, 2), nullable=False, default=Decimal('0.00'), server_default='0')
    profit_amount = db.Column(db.Numeric(18, 2), nullable=False, default=Decimal('0.00'), server_default='0')
    sale = db.relationship('Sale', back_populates='items')
    product = db.relationship('Product')
