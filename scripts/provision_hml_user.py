#!/usr/bin/env python3
"""Provisiona, de forma idempotente, uma conta de teste no HML.

Esta rotina existe para operações controladas via GitHub Actions. Ela nunca copia
o hash de senha de outro ambiente: a senha é fornecida apenas pelo secret da
execução e não é impressa nos logs.
"""

from datetime import date, timedelta
import os
import sys
import unicodedata


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def normalized(value):
    text = unicodedata.normalize('NFKD', str(value or ''))
    return ''.join(char for char in text if not unicodedata.combining(char)).casefold().strip()


def required_secret(name):
    value = os.environ.get(name, '')
    if not value:
        raise RuntimeError(f'O secret {name} precisa ser informado.')
    return value


def provision():
    username = os.environ.get('HML_COPY_USERNAME', 'adegajf').strip()
    company_name = os.environ.get('HML_COPY_COMPANY_NAME', 'Adega JF').strip()
    password = required_secret('HML_COPY_USER_PASSWORD')
    if not username or len(username) > 80:
        raise RuntimeError('HML_COPY_USERNAME inválido.')
    if not company_name or len(company_name) > 160:
        raise RuntimeError('HML_COPY_COMPANY_NAME inválido.')
    if len(password) < 8:
        raise RuntimeError('A senha HML precisa possuir ao menos 8 caracteres.')

    from app import create_app
    from app.extensions import db
    from app.models import Company, User
    from app.services.audit_service import record_audit_event
    from app.tenant import tenant_engine

    app = create_app()
    with app.app_context():
        matches = User.query.filter(User.username.ilike(username)).all()
        if len(matches) > 1:
            raise RuntimeError(
                f'Foram encontradas {len(matches)} contas com o login {username!r}; operação recusada.'
            )
        if matches:
            existing = matches[0]
            print(
                'Conta HML já existente: '
                f'user_id={existing.id}, username={existing.username}, '
                f'company_id={existing.company_id}, role={existing.role}.'
            )
            return False

        company = next(
            (
                item
                for item in Company.query.filter(Company.is_system.is_(False)).all()
                if normalized(item.name) == normalized(company_name)
            ),
            None,
        )
        if company is None:
            today = date.today()
            company = Company(
                name=company_name,
                active=True,
                is_system=False,
                subscription_plan='Ultimate',
                billing_cycle='annual',
                subscription_started_at=today,
                subscription_renews_at=today + timedelta(days=365),
                activation_key='',
            )
            db.session.add(company)
            db.session.flush()
        else:
            if not company.active:
                company.active = True
            if not company.subscription_renews_at or company.subscription_renews_at < date.today():
                company.subscription_started_at = date.today()
                company.subscription_renews_at = date.today() + timedelta(days=365)

        # Garante o schema do tenant antes de disponibilizar o login.
        tenant_engine(company)

        user = User(
            username=username,
            first_name='Adega',
            last_name='JF',
            email='',
            phone='',
            cpf='',
            role='admin',
            company_id=company.id,
            is_active=True,
            email_verified=True,
        )
        for permission in (
            'can_view_products',
            'can_manage_products',
            'can_manage_categories',
            'can_manage_sales',
            'can_cancel_sales',
            'can_manage_cash_register',
            'can_view_reports',
            'can_manage_payables',
            'can_manage_settings',
            'can_view_stock_movements',
            'can_manage_stock',
            'can_view_audit_logs',
        ):
            setattr(user, permission, True)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        record_audit_event(
            'user_created',
            'user',
            user.id,
            f'Usuário HML {user.username} criado para homologação.',
            new_values={
                'username': user.username,
                'role': user.role,
                'company_id': company.id,
                'environment': 'homologation',
            },
            company_id=company.id,
            db_session=db.session,
        )
        db.session.commit()
        if not user.check_password(password):
            raise RuntimeError('A senha da conta HML não pôde ser validada após a gravação.')
        print(
            'Conta HML criada com sucesso: '
            f'user_id={user.id}, username={user.username}, '
            f'company_id={company.id}, company={company.name!r}, role={user.role}.'
        )
        return True


if __name__ == '__main__':
    provision()
