from datetime import datetime, timezone
import time
from threading import Lock

from flask import current_app

from app.extensions import db
from app.models import EmailAlertDelivery, EmailAlertSetting
from app.services.email_service import EmailAuthenticationError, send_alert_email


EMAIL_ALERT_TYPES = {
    'product_out_of_stock': {
        'label': 'Produto esgotado',
        'description': 'Quando um produto ativo chegar a 0 unidade.',
        'default_enabled': True,
    },
    'product_low_stock': {
        'label': 'Estoque baixo',
        'description': 'Quando um produto ficar igual ou abaixo do estoque mínimo.',
        'default_enabled': False,
    },
    'payable_due_today': {
        'label': 'Conta vence hoje',
        'description': 'Quando uma conta a pagar chegar ao dia do vencimento.',
        'default_enabled': True,
    },
    'payable_overdue': {
        'label': 'Conta vencida',
        'description': 'Quando uma conta a pagar estiver vencida.',
        'default_enabled': True,
    },
    'subscription_expiring': {
        'label': 'Assinatura perto do vencimento',
        'description': 'Quando faltarem até 3 dias para a assinatura vencer.',
        'default_enabled': True,
    },
}

_email_alert_check_times = {}
_email_alert_check_lock = Lock()


def claim_email_alert_check(company_id, interval_seconds=60):
    now = time.monotonic()
    with _email_alert_check_lock:
        last_check = _email_alert_check_times.get(company_id)
        if last_check is not None and now - last_check < interval_seconds:
            return False
        _email_alert_check_times[company_id] = now
        return True


def parse_recipients(value):
    raw_values = str(value or '').replace(';', ',').replace('\n', ',').split(',')
    return [email.strip() for email in raw_values if email.strip()]


def default_alert_recipients(company):
    if not company:
        return []
    return [
        user.email for user in company.users
        if user.is_active and user.email and user.email_verified and user.role in ('admin', 'master')
    ]


def ensure_email_alert_settings(company):
    existing = {
        setting.alert_type: setting
        for setting in EmailAlertSetting.query.filter_by(company_id=company.id).all()
    }
    default_recipients = ', '.join(default_alert_recipients(company))
    changed = False

    for alert_type, meta in EMAIL_ALERT_TYPES.items():
        if alert_type not in existing:
            setting = EmailAlertSetting(
                company_id=company.id,
                alert_type=alert_type,
                enabled=meta['default_enabled'],
                recipients=default_recipients,
            )
            db.session.add(setting)
            existing[alert_type] = setting
            changed = True

    if changed:
        db.session.commit()
    return existing


def alert_settings_for_company(company):
    if not company:
        return {}
    return ensure_email_alert_settings(company)


def send_configured_email_alert(company, alert_type, alert_key, title, message, url=None, settings=None):
    if not company or alert_type not in EMAIL_ALERT_TYPES:
        return False

    settings = settings if settings is not None else alert_settings_for_company(company)
    setting = settings.get(alert_type)
    if not setting or not setting.enabled:
        return False

    recipients = setting.recipient_list
    if not recipients:
        return False

    already_sent = EmailAlertDelivery.query.filter_by(
        company_id=company.id,
        alert_type=alert_type,
        alert_key=alert_key,
    ).first()
    if already_sent:
        return False

    try:
        send_alert_email(company, recipients, title, message, url)
    except EmailAuthenticationError as error:
        current_app.logger.error('Falha de autenticação SMTP ao enviar alerta %s: %s', alert_key, error, exc_info=True)
        return False
    except Exception as error:
        current_app.logger.error('Falha ao enviar alerta por email %s: %s', alert_key, error, exc_info=True)
        return False

    db.session.add(EmailAlertDelivery(
        company_id=company.id,
        alert_type=alert_type,
        alert_key=alert_key,
        recipients=', '.join(recipients),
        sent_at=datetime.now(timezone.utc),
    ))
    db.session.commit()
    return True
