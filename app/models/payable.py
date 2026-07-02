from datetime import date, datetime, timezone

from app.extensions import db


class Payable(db.Model):
    __tablename__ = 'payables'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True)
    description = db.Column(db.String(180), nullable=False)
    category = db.Column(db.String(80), default='Geral')
    amount = db.Column(db.Float, default=0.0)
    due_date = db.Column(db.Date, nullable=False, default=date.today)
    paid = db.Column(db.Boolean, default=False)
    paid_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
