from datetime import datetime, timezone

from app.extensions import db


class EmailAlertSetting(db.Model):
    __tablename__ = 'email_alert_settings'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False, index=True)
    alert_type = db.Column(db.String(80), nullable=False)
    enabled = db.Column(db.Boolean, default=False)
    recipients = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    company = db.relationship('Company', back_populates='email_alert_settings')

    @property
    def recipient_list(self):
        raw_values = (self.recipients or '').replace(';', ',').split(',')
        return [email.strip() for email in raw_values if email.strip()]

