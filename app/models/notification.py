from datetime import datetime, timezone

from app.extensions import db


class Notification(db.Model):
    __tablename__ = 'notifications'
    __table_args__ = (
        db.UniqueConstraint('company_id', 'deduplication_key', name='uq_notification_company_dedup'),
    )

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    notification_type = db.Column(db.String(80), nullable=False, index=True)
    category = db.Column(db.String(40), nullable=False, index=True)
    severity = db.Column(db.String(20), nullable=False, default='info', index=True)
    title = db.Column(db.String(180), nullable=False)
    message = db.Column(db.String(1000), nullable=False)
    entity_type = db.Column(db.String(80), default='', index=True)
    entity_id = db.Column(db.Integer, nullable=True, index=True)
    action_url = db.Column(db.String(500), default='')
    deduplication_key = db.Column(db.String(255), nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    read_at = db.Column(db.DateTime, nullable=True)
    is_dismissed = db.Column(db.Boolean, default=False, nullable=False, index=True)
    dismissed_at = db.Column(db.DateTime, nullable=True)
    is_resolved = db.Column(db.Boolean, default=False, nullable=False, index=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    email_status = db.Column(db.String(20), default='not_requested')
    email_sent_at = db.Column(db.DateTime, nullable=True)
    email_error = db.Column(db.String(500), default='')
    metadata_json = db.Column(db.Text, default='{}')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    expires_at = db.Column(db.DateTime, nullable=True, index=True)


class NotificationPreference(db.Model):
    __tablename__ = 'notification_preferences'
    __table_args__ = (
        db.UniqueConstraint('company_id', 'user_id', 'notification_type', name='uq_notification_preference'),
    )

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    notification_type = db.Column(db.String(80), nullable=False, default='*')
    in_app_enabled = db.Column(db.Boolean, default=True, nullable=False)
    email_enabled = db.Column(db.Boolean, default=False, nullable=False)
    desktop_enabled = db.Column(db.Boolean, default=True, nullable=False)
    minimum_severity = db.Column(db.String(20), default='info', nullable=False)
    email_recipients = db.Column(db.String(1000), default='')
    quiet_hours_start = db.Column(db.String(5), default='')
    quiet_hours_end = db.Column(db.String(5), default='')
    daily_digest_enabled = db.Column(db.Boolean, default=False, nullable=False)
    daily_digest_time = db.Column(db.String(5), default='08:00')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
