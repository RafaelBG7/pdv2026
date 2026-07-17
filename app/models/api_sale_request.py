from datetime import datetime, timezone

from app.extensions import db


class ApiSaleRequest(db.Model):
    __tablename__ = 'api_sale_requests'
    __table_args__ = (
        db.UniqueConstraint(
            'company_id',
            'idempotency_key',
            name='uq_api_sale_request_company_key',
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    idempotency_key = db.Column(db.String(128), nullable=False)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    sale = db.relationship('Sale')
