from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db


class Product(db.Model):
    __tablename__ = 'products'
    __table_args__ = (
        db.UniqueConstraint(
            'company_id',
            'barcode',
            name='uq_products_company_barcode',
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    barcode = db.Column(db.String(100), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True)
    cost_price = db.Column(db.Numeric(18, 2), nullable=False, default=Decimal('0.00'), server_default='0')
    sale_price = db.Column(db.Numeric(18, 2), nullable=False, default=Decimal('0.00'), server_default='0')
    stock_quantity = db.Column(db.Integer, default=0)
    min_stock_quantity = db.Column(db.Integer, default=0)
    active = db.Column(db.Boolean, default=True)
    is_kit = db.Column(db.Boolean, default=False)
    kit_component_product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    kit_component_quantity = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    category = db.relationship('Category', back_populates='products')
    stock_movements = db.relationship('StockMovement', back_populates='product', passive_deletes=True)
    kit_component = db.relationship(
        'Product',
        remote_side=[id],
        foreign_keys=[kit_component_product_id],
        post_update=True,
    )

    @property
    def effective_stock_quantity(self):
        if self.is_kit and self.kit_component and self.kit_component_quantity:
            return self.kit_component.stock_quantity // self.kit_component_quantity
        return self.stock_quantity or 0

    @property
    def profit_amount(self):
        return (self.sale_price or Decimal('0.00')) - (self.cost_price or Decimal('0.00'))

    @property
    def profit_margin_percent(self):
        sale_price = self.sale_price or Decimal('0.00')
        if sale_price <= 0:
            return Decimal('0.00')
        return (self.profit_amount / sale_price) * 100
