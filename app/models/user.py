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
    email = db.Column(db.String(255), default='')
    phone = db.Column(db.String(40), default='')
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), default='admin')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

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
