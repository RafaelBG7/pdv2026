from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.time_utils import business_today


class Payable(db.Model):
    __tablename__ = 'payables'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True)
    description = db.Column(db.String(180), nullable=False)
    category = db.Column(db.String(80), default='Geral')
    amount = db.Column(db.Numeric(18, 2), nullable=False, default=Decimal('0.00'), server_default='0')
    due_date = db.Column(db.Date, nullable=False, default=business_today)
    paid = db.Column(db.Boolean, nullable=False, default=False)
    paid_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
