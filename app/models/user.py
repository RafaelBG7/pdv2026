from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    first_name = db.Column(db.String(120), default='')
    last_name = db.Column(db.String(120), default='')
    cpf = db.Column(db.String(20), default='')
    email = db.Column(db.String(255), default='')
    email_verified = db.Column(db.Boolean, default=True)
    email_verified_at = db.Column(db.DateTime, nullable=True)
    phone = db.Column(db.String(40), default='')
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), default='admin')
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    can_view_products = db.Column(db.Boolean, default=True)
    can_manage_products = db.Column(db.Boolean, default=True)
    can_manage_categories = db.Column(db.Boolean, default=True)
    can_manage_sales = db.Column(db.Boolean, default=True)
    can_manage_cash_register = db.Column(db.Boolean, default=True)
    can_view_reports = db.Column(db.Boolean, default=True)
    can_manage_payables = db.Column(db.Boolean, default=True)
    can_manage_settings = db.Column(db.Boolean, default=True)
    can_view_stock_movements = db.Column(db.Boolean, default=True)
    can_manage_stock = db.Column(db.Boolean, default=True)
    can_view_audit_logs = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    company = db.relationship('Company', back_populates='users')
    email_verification_codes = db.relationship('EmailVerificationCode', back_populates='user', cascade='all, delete-orphan')
    password_reset_tokens = db.relationship('PasswordResetToken', back_populates='user', cascade='all, delete-orphan')
    email_change_requests = db.relationship('EmailChangeRequest', back_populates='user', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='scrypt')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self):
        return ' '.join(part for part in (self.first_name, self.last_name) if part).strip()

    @property
    def masked_email(self):
        email = self.email or ''
        if '@' not in email:
            return 'Não informado'

        local, domain = email.split('@', 1)
        if len(local) <= 2:
            masked_local = f'{local[:1]}***'
        else:
            masked_local = f'{local[:2]}***{local[-1:]}'
        return f'{masked_local}@{domain}'

    @property
    def password_fingerprint(self):
        if not self.password_hash:
            return 'Senha não definida'
        return f'{self.password_hash[:18]}...'

    def has_permission(self, permission):
        if self.role in ('master', 'admin'):
            return True
        if permission == 'can_view_products':
            return True
        if permission == 'can_view_products' and self.can_manage_products:
            return True
        return bool(getattr(self, permission, False))

    @property
    def role_label(self):
        labels = {
            'master': 'Master do sistema',
            'admin': 'Admin',
            'manager': 'Gerente',
            'operator': 'Funcionário',
        }
        return labels.get(self.role, self.role)
