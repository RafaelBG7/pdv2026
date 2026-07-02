from datetime import datetime, timezone

from app.extensions import db


class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    barcode = db.Column(db.String(100), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True)
    cost_price = db.Column(db.Float, default=0.0)
    sale_price = db.Column(db.Float, default=0.0)
    stock_quantity = db.Column(db.Integer, default=0)
    min_stock_quantity = db.Column(db.Integer, default=0)
    active = db.Column(db.Boolean, default=True)
    is_kit = db.Column(db.Boolean, default=False)
    kit_component_product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    kit_component_quantity = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    category = db.relationship('Category', back_populates='products')
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
        return (self.sale_price or 0.0) - (self.cost_price or 0.0)

    @property
    def profit_margin_percent(self):
        sale_price = self.sale_price or 0.0
        if sale_price <= 0:
            return 0.0
        return (self.profit_amount / sale_price) * 100
