from datetime import datetime, timezone

from app.extensions import db


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    user_name = db.Column(db.String(160), default='')
    user_role = db.Column(db.String(60), default='')
    action = db.Column(db.String(80), nullable=False, index=True)
    entity_type = db.Column(db.String(80), nullable=False, index=True)
    entity_id = db.Column(db.Integer, nullable=True, index=True)
    description = db.Column(db.Text, default='')
    old_values = db.Column(db.Text, default='')
    new_values = db.Column(db.Text, default='')
    ip_address = db.Column(db.String(80), default='')
    user_agent = db.Column(db.Text, default='')
    request_id = db.Column(db.String(80), default='')
    route = db.Column(db.String(180), default='')
    http_method = db.Column(db.String(10), default='')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    user = db.relationship('User')
