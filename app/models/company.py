from datetime import date, datetime, timedelta, timezone

from app.extensions import db


class Company(db.Model):
    __tablename__ = 'companies'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    database_path = db.Column(db.String(255), default='')
    active = db.Column(db.Boolean, default=True)
    allow_negative_stock = db.Column(db.Boolean, default=False)
    subscription_plan = db.Column(db.String(80), default='Essencial')
    billing_cycle = db.Column(db.String(20), default='monthly')
    subscription_started_at = db.Column(db.Date, default=date.today)
    subscription_renews_at = db.Column(db.Date, default=lambda: date.today() + timedelta(days=30))
    activation_key = db.Column(db.String(80), default='')
    activation_key_updated_at = db.Column(db.DateTime, nullable=True)
    card_fee_enabled = db.Column(db.Boolean, default=False)
    pix_fee_enabled = db.Column(db.Boolean, default=False)
    debit_fee_enabled = db.Column(db.Boolean, default=False)
    credit_fee_enabled = db.Column(db.Boolean, default=False)
    pix_fee_percent = db.Column(db.Float, default=0.0)
    debit_fee_percent = db.Column(db.Float, default=0.0)
    credit_fee_percent = db.Column(db.Float, default=0.0)
    backup_frequency = db.Column(db.String(20), default='manual')
    backup_last_at = db.Column(db.DateTime, nullable=True)
    backup_last_path = db.Column(db.String(255), default='')
    backup_last_status = db.Column(db.String(40), default='')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    users = db.relationship('User', back_populates='company')
    email_alert_settings = db.relationship('EmailAlertSetting', back_populates='company', cascade='all, delete-orphan')
    email_alert_deliveries = db.relationship('EmailAlertDelivery', back_populates='company', cascade='all, delete-orphan')

    @property
    def subscription_expired(self):
        return bool(self.subscription_renews_at and self.subscription_renews_at < date.today())

    @property
    def subscription_valid(self):
        return bool(
            self.active
            and self.subscription_renews_at
            and self.subscription_renews_at >= date.today()
        )
