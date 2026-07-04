from datetime import datetime, timezone

from app.extensions import db


class EmailAlertDelivery(db.Model):
    __tablename__ = 'email_alert_deliveries'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False, index=True)
    alert_type = db.Column(db.String(80), nullable=False)
    alert_key = db.Column(db.String(255), nullable=False, index=True)
    recipients = db.Column(db.Text, default='')
    sent_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    company = db.relationship('Company', back_populates='email_alert_deliveries')

