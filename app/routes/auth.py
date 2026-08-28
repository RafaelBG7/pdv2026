from datetime import date, datetime, timedelta, timezone
import io
import json
from pathlib import Path
import re
import secrets
import string
import unicodedata
from urllib.parse import urlencode

from flask import Blueprint, current_app, redirect, render_template, request, send_file, session, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import or_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash

from app.backup import BACKUP_FREQUENCIES, backup_frequency_label, create_company_backup
from app.extensions import db
from app.models import ActivationKey, ApiRefreshToken, ApiSaleRequest, AuditLog, CashRegister, Category, Company, EmailAlertDelivery, EmailAlertSetting, EmailChangeRequest, EmailVerificationCode, Notification, NotificationPreference, PasswordResetToken, Payable, Payment, Product, Sale, SaleItem, StockMovement, User
from app.permissions import (
    PERMISSION_LABELS,
    authorize_permission_override,
    authorize_role_override,
    grant_permission_view_override,
    has_permission_view_override,
    user_can_override_permission,
)
from app.security.passwords import validate_password_strength
from app.extensions import limiter
from app.security.rate_limit import (
    anonymous_identity_key,
    authenticated_identity_key,
    configured_limit,
    login_identity_key,
)
from app.services.alert_service import EMAIL_ALERT_TYPES, alert_settings_for_company, parse_recipients
from app.services.audit_service import record_audit_event
from app.services.email_service import EmailAuthenticationError, send_alert_email, send_email_change_confirmation, send_verification_code_email
from app.services.password_recovery_service import request_password_recovery
from app.services.app_registration_service import APP_CALLBACK_URI, create_registration_code, valid_callback_request
from app.tenant import current_tenant_company, drop_mysql_database, tenant_database_identifier, tenant_engine


auth_bp = Blueprint('auth', __name__)
SUBSCRIPTION_PLANS = ('Basic', 'Pro', 'Ultimate')
MASTER_KEY_PLANS = SUBSCRIPTION_PLANS
KEY_PAYMENT_CYCLES = {
    'monthly': 'Mensal',
    'quarterly': 'Trimestral',
    'semiannual': 'Semestral',
    'annual': 'Anual',
    'custom': 'Personalizado',
}
BASIC_PRO_PLANS = (
    {
        'name': 'Basic',
        'monthly_price': 'R$ 89,90',
        'annual_price': 'R$ 899,00',
        'tagline': 'Para adegas começando a controlar vendas e estoque.',
        'features': (
            'Produtos, categorias e kits',
            'Vendas com múltiplas formas de pagamento',
            'Abertura e fechamento de caixa',
            'Alertas de estoque baixo',
            'Relatórios essenciais',
        ),
    },
    {
        'name': 'Pro',
        'monthly_price': 'R$ 149,90',
        'annual_price': 'R$ 1.499,00',
        'tagline': 'Para adegas que precisam de gestão completa.',
        'highlight': True,
        'features': (
            'Tudo do plano Basic',
            'Funcionários e permissões',
            'Contas a pagar com notificações',
            'Taxas de maquininha no lucro',
            'Relatórios completos e gráfico',
            'Controle de assinatura e key',
        ),
    },
    {
        'name': 'Ultimate',
        'monthly_price': 'Sob consulta',
        'annual_price': 'Sob consulta',
        'tagline': 'Para operações que precisam do máximo de controle e escala.',
        'features': (
            'Tudo do plano Pro',
            'Recursos avançados de gestão',
            'Relatórios e auditoria completos',
            'Prioridade no suporte',
        ),
    },
)
BILLING_CYCLES = {
    'monthly': 'Mensal',
    'quarterly': 'Trimestral',
    'semiannual': 'Semestral',
    'annual': 'Anual',
    'custom': 'Personalizado',
}
KEY_PRESETS = (
    ('1d', '1 dia', 1),
    ('3d', '3 dias', 3),
    ('7d', '7 dias', 7),
    ('1m', '1 mês', 30),
    ('3m', '3 meses', 90),
    ('6m', '6 meses', 180),
    ('1y', '1 ano', 365),
)
LOGIN_FAILED_MESSAGE = 'Usuário/e-mail ou senha inválidos.'
VERIFICATION_CODE_TTL_MINUTES = 15
VERIFICATION_ATTEMPT_LIMIT = 5
VERIFICATION_RESEND_SECONDS = 60
VERIFICATION_RESEND_HOURLY_LIMIT = 3


def _normalized_deletion_confirmation(value):
    """Normalize harmless typing differences in destructive confirmations."""
    normalized = unicodedata.normalize('NFKC', value or '')
    return ' '.join(normalized.split()).casefold()
PASSWORD_RESET_TTL_MINUTES = 30
EMAIL_CHANGE_TTL_MINUTES = 30
LOG_ENTRY_PATTERN = re.compile(
    r'^(?P<created_at>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) '
    r'(?P<level>[A-Z]+) \[(?P<logger>[^\]]+)\] (?P<message>.*)$'
)
EMPLOYEE_PERMISSIONS = (
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
)
EMPLOYEE_ROLES = {
    'operator': {
        'label': 'Funcionário',
        'description': 'Realiza vendas, abre caixa e acessa configurações pessoais.',
    },
    'manager': {
        'label': 'Gerente',
        'description': 'Pode operar e gerenciar a adega, exceto a área financeira.',
    },
    'admin': {
        'label': 'Admin',
        'description': 'Acesso completo à adega, incluindo financeiro.',
    },
}
ROLE_PERMISSION_DEFAULTS = {
    'operator': {
        'can_view_products': True,
        'can_manage_products': False,
        'can_manage_categories': False,
        'can_manage_sales': True,
        'can_cancel_sales': False,
        'can_manage_cash_register': True,
        'can_view_reports': False,
        'can_manage_payables': False,
        'can_manage_settings': False,
        'can_view_stock_movements': False,
        'can_manage_stock': False,
        'can_view_audit_logs': False,
    },
    'manager': {
        'can_view_products': True,
        'can_manage_products': True,
        'can_manage_categories': True,
        'can_manage_sales': True,
        'can_cancel_sales': True,
        'can_manage_cash_register': True,
        'can_view_reports': True,
        'can_manage_payables': True,
        'can_manage_settings': True,
        'can_view_stock_movements': True,
        'can_manage_stock': True,
        'can_view_audit_logs': True,
    },
    'admin': {
        permission: True
        for permission in EMPLOYEE_PERMISSIONS
    },
}


def parse_date_field(value):
    try:
        return datetime.strptime(value or '', '%Y-%m-%d').date()
    except ValueError:
        return None


def parse_percent(value):
    try:
        normalized = str(value or '0').replace(',', '.')
        return max(float(normalized), 0.0)
    except ValueError:
        return 0.0


def password_min_length():
    configured = current_app.config.get('PASSWORD_MIN_LENGTH')
    if configured:
        return int(configured)
    return 3 if current_app.config.get('TESTING') else 8


def password_too_short(password):
    return len(password or '') < password_min_length()


def password_validation_messages(password, username='', email=''):
    return validate_password_strength(
        password,
        username=username,
        email=email,
        min_length=password_min_length(),
        max_length=int(current_app.config.get('PASSWORD_MAX_LENGTH') or 128),
    )


def password_first_error(password, username='', email=''):
    messages = password_validation_messages(password, username=username, email=email)
    return messages[0] if messages else ''


def valid_email(value):
    return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', value or ''))


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def generate_verification_code():
    return f'{secrets.randbelow(1_000_000):06d}'


def verification_user_from_session():
    user_id = session.get('pending_verification_user_id')
    if not user_id:
        return None
    return db.session.get(User, int(user_id))


def remember_verification_user(user):
    session['pending_verification_user_id'] = user.id


def clear_verification_user():
    session.pop('pending_verification_user_id', None)


def create_email_verification_code(user, force=False):
    now = utc_now()
    recent_codes = EmailVerificationCode.query.filter_by(user_id=user.id).order_by(EmailVerificationCode.created_at.desc()).all()
    if not force:
        recent_sent = [code for code in recent_codes if code.created_at and code.created_at > now - timedelta(hours=1)]
        if len(recent_sent) >= VERIFICATION_RESEND_HOURLY_LIMIT:
            return False, 'Limite de reenvios atingido. Tente novamente mais tarde.'
        last_code = recent_codes[0] if recent_codes else None
        if last_code and last_code.created_at and last_code.created_at > now - timedelta(seconds=VERIFICATION_RESEND_SECONDS):
            return False, 'Aguarde 1 minuto antes de reenviar o código.'

    for code_record in recent_codes:
        if not code_record.used:
            code_record.used = True

    code = generate_verification_code()
    code_record = EmailVerificationCode(
        user_id=user.id,
        code_hash=generate_password_hash(code, method='scrypt'),
        expires_at=now + timedelta(minutes=VERIFICATION_CODE_TTL_MINUTES),
        used=False,
        attempts=0,
    )
    db.session.add(code_record)
    db.session.commit()

    try:
        if current_app.config.get('MAIL_SUPPRESS_SEND'):
            current_app.config['TEST_LAST_VERIFICATION_CODE'] = code
        send_verification_code_email(user, code)
    except EmailAuthenticationError as error:
        current_app.logger.error('Falha de autenticação SMTP ao enviar código para %s: %s', user.email, error, exc_info=True)
        return False, 'Gmail recusou o envio. Confira se MAIL_SMTP_LOGIN é o e-mail correto e se MAIL_SMTP_PASSWORD é uma senha de app válida.'
    except Exception as error:
        current_app.logger.error('Falha ao enviar código de verificação para %s: %s', user.email, error, exc_info=True)
        return False, 'Não foi possível enviar o e-mail agora. Verifique as configurações de envio.'

    return True, 'Código enviado para o e-mail cadastrado.'


def active_verification_code_for_user(user):
    return EmailVerificationCode.query.filter_by(user_id=user.id, used=False).order_by(EmailVerificationCode.created_at.desc()).first()


def public_url_for(endpoint, **values):
    base_url = (current_app.config.get('PUBLIC_BASE_URL') or '').rstrip('/')
    path = url_for(endpoint, **values)
    if base_url:
        return f'{base_url}{path}'
    return url_for(endpoint, _external=True, **values)


def request_email_change(user, new_email):
    EmailChangeRequest.query.filter_by(user_id=user.id, used=False).update({'used': True})
    token = secrets.token_urlsafe(32)
    change_request = EmailChangeRequest(
        user_id=user.id,
        old_email=user.email,
        new_email=new_email,
        token_hash=generate_password_hash(token, method='scrypt'),
        expires_at=utc_now() + timedelta(minutes=EMAIL_CHANGE_TTL_MINUTES),
        used=False,
    )
    db.session.add(change_request)
    db.session.commit()

    confirmation_url = public_url_for('auth.confirm_email_change', token=token)
    if current_app.config.get('MAIL_SUPPRESS_SEND'):
        current_app.config['TEST_LAST_EMAIL_CHANGE_TOKEN'] = token
        current_app.config['TEST_LAST_EMAIL_CHANGE_URL'] = confirmation_url
    send_email_change_confirmation(user, new_email, confirmation_url)


def normalize_digits(value):
    return ''.join(char for char in str(value or '') if char.isdigit())


def generate_activation_key():
    alphabet = string.ascii_uppercase + string.digits
    groups = [
        ''.join(secrets.choice(alphabet) for _ in range(4))
        for _ in range(4)
    ]
    return '-'.join(groups)


def generate_unique_activation_key():
    for _ in range(20):
        key = generate_activation_key()
        if not ActivationKey.query.filter_by(key=key).first():
            return key
    raise RuntimeError('Não foi possível gerar uma key única.')


def available_activation_key(value, company=None):
    key = (value or '').strip().upper()
    if not key:
        return None
    activation_key = ActivationKey.query.filter_by(key=key, active=True, used_by_company_id=None).first()
    if not activation_key:
        return None
    if activation_key.renews_at and activation_key.renews_at < date.today():
        return None
    if activation_key.assigned_company_id and (not company or activation_key.assigned_company_id != company.id):
        return None
    return activation_key


def apply_activation_key_to_company(activation_key, company):
    company.activation_key = activation_key.key
    company.activation_key_updated_at = datetime.now(timezone.utc)
    company.subscription_plan = activation_key.plan
    company.subscription_started_at = date.today()
    company.subscription_renews_at = activation_key.renews_at
    company.billing_cycle = 'annual' if (activation_key.renews_at - date.today()).days >= 365 else 'monthly'
    company.active = True
    activation_key.used_by_company_id = company.id
    activation_key.used_at = datetime.now(timezone.utc)


def renewal_date_from_request(default_cycle='monthly'):
    billing_cycle = request.form.get('billing_cycle', default_cycle).strip()
    if billing_cycle not in BILLING_CYCLES:
        billing_cycle = default_cycle if default_cycle in BILLING_CYCLES else 'monthly'

    preset_days = request.form.get('preset_days', '').strip()
    custom_renews_at = parse_date_field(request.form.get('renews_at'))
    days = None
    if preset_days:
        try:
            days = max(int(preset_days), 1)
        except ValueError:
            days = None

    if custom_renews_at:
        renews_at = custom_renews_at
    elif days:
        renews_at = date.today() + timedelta(days=days)
    else:
        renews_at = date.today() + timedelta(days={
            'monthly': 30,
            'quarterly': 90,
            'semiannual': 180,
            'annual': 365,
            'custom': 30,
        }.get(billing_cycle, 30))

    return billing_cycle, renews_at


def apply_subscription_to_company(company, plan, billing_cycle, renews_at, activation_key=''):
    company.subscription_plan = plan
    company.billing_cycle = billing_cycle
    company.subscription_started_at = date.today()
    company.subscription_renews_at = renews_at
    company.active = True
    if activation_key:
        company.activation_key = activation_key
        company.activation_key_updated_at = datetime.now(timezone.utc)


def activation_key_status(activation_key):
    today = date.today()
    if not activation_key.active:
        return {
            'label': 'Revogada',
            'state': 'danger',
            'available': False,
        }
    if activation_key.renews_at and activation_key.renews_at < today:
        return {
            'label': 'Vencida',
            'state': 'danger',
            'available': False,
        }
    if activation_key.used_by_company_id:
        return {
            'label': 'Utilizada',
            'state': 'ok',
            'available': False,
        }
    if activation_key.renews_at and (activation_key.renews_at - today).days <= 7:
        return {
            'label': 'Vencendo',
            'state': 'warning',
            'available': True,
        }
    return {
        'label': 'Disponível',
        'state': 'ok',
        'available': True,
    }


def read_recent_error_logs(limit=20):
    log_path = Path(current_app.config.get('LOG_DIR') or '') / 'errors.log'
    if not log_path.exists():
        return []

    try:
        lines = log_path.read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError:
        return []

    entries = []
    current_entry = None
    for line in lines[-1000:]:
        match = LOG_ENTRY_PATTERN.match(line)
        if match:
            if current_entry:
                entries.append(current_entry)
            current_entry = {
                'created_at': match.group('created_at'),
                'level': match.group('level'),
                'logger': match.group('logger'),
                'message': match.group('message'),
                'traceback': '',
                'context': {},
            }
        elif current_entry:
            current_entry['traceback'] = f"{current_entry['traceback']}\n{line}".strip()

    if current_entry:
        entries.append(current_entry)

    parsed_entries = []
    for entry in entries[-limit:]:
        message = entry['message']
        context = {}
        if ' | contexto=' in message:
            message, raw_context = message.split(' | contexto=', 1)
            try:
                context = json.loads(raw_context)
            except json.JSONDecodeError:
                context = {}

        entry['message'] = message
        entry['context'] = context
        parsed_entries.append(entry)

    parsed_entries.reverse()
    return parsed_entries


def clear_error_log_file():
    log_dir = Path(current_app.config.get('LOG_DIR') or '')
    log_dir.mkdir(parents=True, exist_ok=True)
    for filename in ('errors.log', 'security.log'):
        (log_dir / filename).write_text('', encoding='utf-8')


def can_manage_company_users():
    return current_user.role in ('admin', 'manager', 'master') or current_user.has_permission('can_manage_settings')


def can_view_admin_settings():
    return (
        current_user.is_authenticated
        and (
            can_manage_company_users()
            or has_permission_view_override('can_manage_settings')
        )
    )


def can_view_finance_settings():
    return (
        current_user.is_authenticated
        and (
            current_user.role in ('admin', 'master')
            or has_permission_view_override('can_view_finance')
        )
    )


def can_import_products_settings():
    return can_view_admin_settings()


def can_export_data_settings():
    return (
        current_user.is_authenticated
        and current_tenant_company() is not None
        and (
            current_user.role in ('admin', 'master')
            or has_permission_view_override('can_export_data')
        )
    )


def apply_employee_permissions(user, form):
    defaults = ROLE_PERMISSION_DEFAULTS.get(user.role, ROLE_PERMISSION_DEFAULTS['operator'])
    for permission in EMPLOYEE_PERMISSIONS:
        setattr(user, permission, defaults.get(permission, False))


def company_cpf_exists(company_id, cpf, user_id=None):
    cpf_digits = normalize_digits(cpf)
    if not cpf_digits:
        return False

    query = User.query.filter_by(company_id=company_id)
    if user_id:
        query = query.filter(User.id != user_id)

    for user in query.all():
        if normalize_digits(user.cpf) == cpf_digits:
            return True
    return False


def subscription_status(company):
    if not company:
        return {
            'renewal_label': '-',
            'days_left': None,
            'days_label': 'Sem adega vinculada',
            'state': 'danger',
            'locked': True,
        }
    if not company.active:
        return {
            'renewal_label': company.subscription_renews_at.strftime('%d/%m/%Y') if company.subscription_renews_at else '-',
            'days_left': None,
            'days_label': 'Adega inativa',
            'state': 'danger',
            'locked': True,
        }
    renewal = company.subscription_renews_at
    today = date.today()
    if not renewal:
        return {
            'renewal_label': '-',
            'days_left': None,
            'days_label': 'Sem renovação',
            'state': 'neutral',
            'locked': True,
        }

    days_left = (renewal - today).days
    if days_left < 0:
        days_label = f'Vencido há {abs(days_left)} dia{"s" if abs(days_left) != 1 else ""}'
        state = 'danger'
    elif days_left == 0:
        days_label = 'Renova hoje'
        state = 'warning'
    else:
        days_label = f'Faltam {days_left} dia{"s" if days_left != 1 else ""}'
        state = 'ok' if days_left > 7 else 'warning'

    return {
        'renewal_label': renewal.strftime('%d/%m/%Y'),
        'days_left': days_left,
        'days_label': days_label,
        'state': state,
        'locked': days_left < 0,
    }


def company_requires_activation(company):
    return not bool(company and company.subscription_valid)


def company_uses_key_license(company):
    return bool(company and (company.activation_key or '').strip())


def current_basic_pro_plan(company):
    if not company:
        return None
    if company.subscription_plan in ('Ultimate', 'Premium', 'Profissional'):
        return 'Ultimate'
    if company.subscription_plan == 'Pro':
        return 'Pro'
    return 'Basic'


def login_form_values():
    return {
        'username': request.form.get('username', '').strip(),
        'remember_me': request.form.get('remember_me') == '1',
    }


def register_form_values():
    return {
        'username': request.form.get('username', '').strip(),
        'company_name': request.form.get('company_name', '').strip(),
        'email': request.form.get('email', '').strip(),
    }


def pending_registration_matches(user, email):
    return bool(
        user
        and not user.email_verified
        and (user.email or '').strip().casefold() == (email or '').strip().casefold()
    )


def resume_pending_registration(user):
    remember_verification_user(user)
    sent, message = create_email_verification_code(user, force=True)
    flash(message, 'success' if sent else 'warning')
    flash('Seu cadastro já foi iniciado. Continue pela confirmação do e-mail.', 'info')
    return redirect(url_for('auth.verify_email'))


def render_auth_form(auth_tab='login', form_values=None, field_errors=None):
    return render_template(
        'login.html',
        auth_tab=auth_tab,
        form_values=form_values or {},
        field_errors=field_errors or {},
    )


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit(
    configured_limit('RATELIMIT_LOGIN', '5 per minute;20 per hour'),
    key_func=login_identity_key,
    methods=['POST'],
    exempt_when=lambda: request.form.get('form_type', 'login') == 'register',
)
@limiter.limit(
    configured_limit('RATELIMIT_REGISTRATION', '3 per hour'),
    key_func=anonymous_identity_key,
    methods=['POST'],
    exempt_when=lambda: request.form.get('form_type', 'login') != 'register',
)
def login():
    if current_user.is_authenticated:
        if current_user.role == 'master':
            return redirect(url_for('auth.master_dashboard'))
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        form_type = request.form.get('form_type', 'login')
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if form_type == 'register':
            email = request.form.get('email', '').strip()
            company_name = request.form.get('company_name', '').strip() or username
            confirm_password = request.form.get('confirm_password', '')
            form_values = register_form_values()

            if not username:
                flash('Informe o usuário para cadastro.', 'danger')
                return render_auth_form('register', form_values, {'username': 'Informe um usuário.'})
            if not email:
                flash('Informe um e-mail para receber o código de verificação.', 'danger')
                return render_auth_form('register', form_values, {'email': 'Informe um e-mail.'})
            if not valid_email(email):
                flash('Informe um e-mail válido.', 'danger')
                return render_auth_form('register', form_values, {'email': 'Este e-mail não parece válido.'})
            password_error = password_first_error(password, username=username, email=email)
            if password_error:
                flash(password_error, 'danger')
                return render_auth_form('register', form_values, {'password': password_error})
            if password != confirm_password:
                flash('A confirmação da senha não confere.', 'danger')
                return render_auth_form('register', form_values, {'confirm_password': 'A confirmação não confere com a senha.'})
            existing_user = User.query.filter_by(username=username).first()
            if pending_registration_matches(existing_user, email):
                return resume_pending_registration(existing_user)
            if existing_user:
                flash('Já existe um usuário com este login.', 'danger')
                return render_auth_form('register', form_values, {'username': 'Este usuário já está em uso.'})

            company = Company(
                name=company_name,
                activation_key='',
                activation_key_updated_at=None,
                subscription_started_at=None,
                subscription_renews_at=None,
            )
            db.session.add(company)
            db.session.flush()
            tenant_database_identifier(company)
            company.subscription_started_at = None
            company.subscription_renews_at = None
            user = User(
                username=username,
                email=email,
                email_verified=False,
                email_verified_at=None,
                role='admin',
                company_id=company.id,
                is_active=True,
            )
            user.set_password(password)
            db.session.add(user)
            try:
                db.session.flush()
                # Provisiona e migra o banco do novo tenant antes de concluir o cadastro.
                tenant_engine(company)
                record_audit_event(
                    'company_created',
                    'company',
                    company.id,
                    f'Adega {company.name} criada no cadastro.',
                    new_values={'company_id': company.id, 'name': company.name},
                    company_id=company.id,
                    db_session=db.session,
                )
                record_audit_event(
                    'user_created',
                    'user',
                    user.id,
                    f'Usuário {user.username} criado no cadastro.',
                    new_values={'username': user.username, 'email': user.email, 'role': user.role},
                    company_id=company.id,
                    user=user,
                    db_session=db.session,
                )
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                existing_user = User.query.filter_by(username=username).first()
                if pending_registration_matches(existing_user, email):
                    return resume_pending_registration(existing_user)
                flash('Já existe um usuário com este login.', 'danger')
                return render_auth_form('register', form_values, {'username': 'Este usuário já está em uso.'})

            remember_verification_user(user)
            sent, message = create_email_verification_code(user, force=True)
            flash(message, 'success' if sent else 'warning')
            flash('Cadastro criado. Confirme seu e-mail para acessar o sistema.', 'info')
            return redirect(url_for('auth.verify_email'))

        if not username:
            flash('Informe usuário ou e-mail para entrar.', 'danger')
            return render_auth_form('login', login_form_values(), {'username': 'Informe usuário ou e-mail.'})
        if not password:
            flash('Informe a senha para entrar.', 'danger')
            return render_auth_form('login', login_form_values(), {'password': 'Informe a senha.'})

        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()

        if user and user.check_password(password):
            if not user.is_active:
                flash('Este usuário está inativo. Fale com o master da adega.', 'danger')
                return render_auth_form('login', login_form_values(), {'username': 'Este usuário está inativo.'})
            if not user.email_verified:
                remember_verification_user(user)
                flash('Seu e-mail ainda não foi confirmado.', 'warning')
                return redirect(url_for('auth.verify_email'))
            if user.role != 'master' and user.company and not user.company.active:
                flash('Esta adega está inativa. Fale com o usuário master.', 'danger')
                return render_auth_form('login', login_form_values(), {'username': 'A adega deste usuário está inativa.'})
            remember_me = request.form.get('remember_me') == '1'
            login_user(user, remember=remember_me)
            record_audit_event(
                'login_success',
                'auth',
                user.id,
                f'Login realizado por {user.username}.',
                company_id=user.company_id,
                user=user,
                db_session=db.session,
            )
            db.session.commit()
            flash('Login realizado com sucesso.', 'success')
            if user.role == 'master':
                return redirect(url_for('auth.master_dashboard'))
            if company_requires_activation(user.company):
                flash('A assinatura desta adega está bloqueada.', 'warning')
                if company_uses_key_license(user.company):
                    return redirect(url_for('auth.subscription_activation'))
                return redirect(url_for('auth.subscriptions'))
            return redirect(url_for('main.dashboard'))

        record_audit_event(
            'login_failed',
            'auth',
            None,
            f'Tentativa de login falhou para {username}.',
            new_values={'identifier': username},
            company_id=user.company_id if user else None,
            user=user,
            db_session=db.session,
        )
        db.session.commit()
        flash(LOGIN_FAILED_MESSAGE, 'danger')
        return render_auth_form('login', login_form_values(), {'password': LOGIN_FAILED_MESSAGE})

    if request.args.get('source') == 'desktop':
        state = request.args.get('state', '')
        code_challenge = request.args.get('code_challenge', '')
        if valid_callback_request(state, code_challenge):
            session['app_registration'] = {
                'state': state,
                'code_challenge': code_challenge,
            }
        else:
            session.pop('app_registration', None)
            flash('O retorno ao aplicativo é inválido. Você ainda pode se cadastrar pela Web.', 'warning')

    return render_auth_form(
        'register' if request.args.get('auth_tab') == 'register' else 'login'
    )


@auth_bp.route('/verify-email', methods=['GET', 'POST'])
def verify_email():
    user = verification_user_from_session()
    if not user:
        flash('Faça login para confirmar seu e-mail.', 'warning')
        return redirect(url_for('auth.login'))
    if user.email_verified:
        clear_verification_user()
        flash('Seu e-mail já está confirmado.', 'info')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        code = normalize_digits(request.form.get('code', ''))
        if len(code) != 6:
            flash('Informe o código de 6 dígitos.', 'danger')
            return render_template('verify_email.html', user=user)

        code_record = active_verification_code_for_user(user)
        now = utc_now()
        if not code_record:
            flash('Código inválido ou já utilizado. Solicite um novo código.', 'danger')
            return render_template('verify_email.html', user=user)
        if code_record.expires_at < now:
            code_record.used = True
            db.session.commit()
            flash('Este código expirou. Solicite um novo código.', 'danger')
            return render_template('verify_email.html', user=user)
        if code_record.attempts >= VERIFICATION_ATTEMPT_LIMIT:
            code_record.used = True
            db.session.commit()
            flash('Limite de tentativas atingido. Solicite um novo código.', 'danger')
            return render_template('verify_email.html', user=user)

        code_record.attempts += 1
        if not check_password_hash(code_record.code_hash, code):
            db.session.commit()
            flash('Código incorreto.', 'danger')
            return render_template('verify_email.html', user=user)

        code_record.used = True
        user.email_verified = True
        user.email_verified_at = now
        record_audit_event(
            'email_changed',
            'user',
            user.id,
            f'E-mail confirmado para {user.username}.',
            new_values={'email_verified': True, 'email_verified_at': user.email_verified_at},
            company_id=user.company_id,
            user=user,
            db_session=db.session,
        )
        db.session.commit()
        clear_verification_user()
        login_user(user)
        app_registration = session.pop('app_registration', None)
        if app_registration and valid_callback_request(
            app_registration.get('state'),
            app_registration.get('code_challenge'),
        ):
            code = create_registration_code(
                user,
                app_registration['state'],
                app_registration['code_challenge'],
            )
            callback_uri = f"{APP_CALLBACK_URI}?{urlencode({'code': code, 'state': app_registration['state']})}"
            return render_template(
                'app_registration_complete.html',
                callback_uri=callback_uri,
                web_continue_url=url_for('auth.subscriptions') if company_requires_activation(user.company)
                else url_for('main.dashboard'),
            )
        current_app.logger.info('Email confirmado para user_id=%s', user.id)
        flash('E-mail confirmado com sucesso.', 'success')
        if user.role == 'master':
            return redirect(url_for('auth.master_dashboard'))
        if company_requires_activation(user.company):
            flash('Cadastro realizado. Escolha um plano para ativar sua assinatura.', 'warning')
            return redirect(url_for('auth.subscriptions'))
        flash('Cadastro realizado com sucesso.', 'success')
        return redirect(url_for('main.dashboard'))

    return render_template('verify_email.html', user=user)


@auth_bp.route('/verify-email/resend', methods=['POST'])
@limiter.limit(
    configured_limit('RATELIMIT_EMAIL_RESEND', '3 per 15 minutes'),
    key_func=anonymous_identity_key,
)
def resend_verification_code():
    user = verification_user_from_session()
    if not user:
        flash('Faça login para reenviar o código.', 'warning')
        return redirect(url_for('auth.login'))
    if user.email_verified:
        clear_verification_user()
        flash('Seu e-mail já está confirmado.', 'info')
        return redirect(url_for('auth.login'))

    sent, message = create_email_verification_code(user)
    flash(message, 'success' if sent else 'warning')
    return redirect(url_for('auth.verify_email'))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit(
    configured_limit('RATELIMIT_PASSWORD_RESET', '3 per 15 minutes'),
    key_func=login_identity_key,
    methods=['POST'],
)
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if not valid_email(email):
            flash('Informe um e-mail válido.', 'danger')
            return render_template('forgot_password.html')

        try:
            request_password_recovery(email)
        except EmailAuthenticationError as error:
            current_app.logger.error('Falha de autenticação SMTP na recuperação de senha.', exc_info=True)
            flash('Gmail recusou o envio. Confira as configurações de envio.', 'danger')
            return render_template('forgot_password.html')
        except Exception:
            current_app.logger.error('Falha ao enviar recuperação de senha.', exc_info=True)
            flash('Não foi possível enviar o e-mail agora. Verifique a configuração de envio.', 'danger')
            return render_template('forgot_password.html')

        flash('Se este e-mail estiver cadastrado, enviaremos um link de redefinição.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    now = utc_now()
    reset_record = None
    active_tokens = PasswordResetToken.query.filter(
        PasswordResetToken.used.is_(False),
        PasswordResetToken.expires_at >= now,
    ).order_by(PasswordResetToken.created_at.desc()).all()
    for candidate in active_tokens:
        if check_password_hash(candidate.token_hash, token):
            reset_record = candidate
            break

    if not reset_record:
        flash('Link de redefinição inválido ou expirado.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    user = reset_record.user
    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        password_error = password_first_error(password, username=user.username, email=user.email)
        if password_error:
            flash(password_error, 'danger')
            return render_template('reset_password.html', token=token)
        if password != confirm_password:
            flash('A confirmação da senha não confere.', 'danger')
            return render_template('reset_password.html', token=token)

        user.set_password(password)
        reset_record.used = True
        db.session.commit()
        current_app.logger.info('Senha redefinida para user_id=%s', user.id)
        flash('Senha redefinida com sucesso. Faça login novamente.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('reset_password.html', token=token)


@auth_bp.route('/confirmar-troca-email/<token>')
def confirm_email_change(token):
    now = utc_now()
    change_request = None
    active_requests = EmailChangeRequest.query.filter(
        EmailChangeRequest.used.is_(False),
        EmailChangeRequest.expires_at >= now,
    ).order_by(EmailChangeRequest.created_at.desc()).all()
    for candidate in active_requests:
        if check_password_hash(candidate.token_hash, token):
            change_request = candidate
            break

    if not change_request:
        flash('Link de troca de e-mail inválido ou expirado.', 'danger')
        return redirect(url_for('auth.login'))

    user = change_request.user
    user.email = change_request.new_email
    user.email_verified = True
    user.email_verified_at = now
    change_request.used = True
    change_request.confirmed_at = now
    db.session.commit()
    current_app.logger.info('Email alterado com confirmação antiga para user_id=%s', user.id)
    flash('E-mail alterado com sucesso.', 'success')

    if current_user.is_authenticated and current_user.id == user.id:
        return redirect(url_for('auth.settings'))
    return redirect(url_for('auth.login'))


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    record_audit_event(
        'logout',
        'auth',
        current_user.id,
        f'Logout realizado por {current_user.username}.',
        company_id=current_user.company_id,
        db_session=db.session,
    )
    db.session.commit()
    session.pop('permission_view_overrides', None)
    logout_user()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/autorizar-acesso', methods=['GET', 'POST'])
@login_required
def permission_unlock():
    permission = request.values.get('permission', '')
    next_url = request.values.get('next') or url_for('main.dashboard')
    if permission not in PERMISSION_LABELS:
        flash('Permissão inválida.', 'danger')
        return redirect(url_for('main.dashboard'))
    if not next_url.startswith('/'):
        next_url = url_for('main.dashboard')

    if current_user.has_permission(permission) or current_user.role == 'master':
        return redirect(next_url)

    authorizers = [
        user for user in User.query.order_by(User.username.asc()).all()
        if user_can_override_permission(user, permission)
    ]

    if request.method == 'POST':
        if authorize_permission_override(permission):
            grant_permission_view_override(permission)
            flash(f'Acesso liberado para {PERMISSION_LABELS.get(permission, "esta área")}.', 'success')
            return redirect(next_url)
        flash('Usuário ou senha de autorização inválidos.', 'danger')

    return render_template(
        'permission_unlock.html',
        permission=permission,
        permission_label=PERMISSION_LABELS.get(permission, 'esta área'),
        next_url=next_url,
        authorizers=authorizers,
    )


@auth_bp.route('/assinatura', methods=['GET', 'POST'])
@login_required
@limiter.limit(
    configured_limit('RATELIMIT_ACTIVATION', '5 per 15 minutes'),
    key_func=authenticated_identity_key,
    methods=['POST'],
)
def subscription_activation():
    if current_user.role == 'master':
        return redirect(url_for('auth.master_dashboard'))

    company = current_user.company
    status = subscription_status(company) if company else {}

    if request.method == 'POST':
        activation_key = request.form.get('activation_key', '').strip().upper()
        expected_key = (company.activation_key or '').strip().upper() if company else ''

        if not expected_key:
            generated_key = available_activation_key(activation_key, company)
            if not generated_key:
                flash('Key de ativação inválida ou já utilizada.', 'danger')
                return redirect(url_for('auth.subscription_activation'))
            apply_activation_key_to_company(generated_key, company)
            record_audit_event(
                'activation_key_applied',
                'activation_key',
                generated_key.id,
                f'Key aplicada na adega {company.name}.',
                new_values={'plan': generated_key.plan, 'renews_at': generated_key.renews_at, 'activation_key': generated_key.key},
                company_id=company.id,
                db_session=db.session,
            )
            db.session.commit()
            flash('Assinatura ativada com sucesso.', 'success')
            return redirect(url_for('main.dashboard'))
        if activation_key != expected_key:
            generated_key = available_activation_key(activation_key, company)
            if not generated_key:
                flash('Key de ativação inválida.', 'danger')
                return redirect(url_for('auth.subscription_activation'))
            apply_activation_key_to_company(generated_key, company)
            record_audit_event(
                'activation_key_applied',
                'activation_key',
                generated_key.id,
                f'Key aplicada na adega {company.name}.',
                new_values={'plan': generated_key.plan, 'renews_at': generated_key.renews_at, 'activation_key': generated_key.key},
                company_id=company.id,
                db_session=db.session,
            )
            db.session.commit()
            flash('Assinatura ativada com sucesso.', 'success')
            return redirect(url_for('main.dashboard'))
        if company_requires_activation(company):
            flash('Key correta, mas a assinatura ainda está vencida. Solicite a renovação ao suporte.', 'danger')
            return redirect(url_for('auth.subscription_activation'))

        flash('Assinatura ativada com sucesso.', 'success')
        return redirect(url_for('main.dashboard'))

    return render_template('subscription/activation.html', company=company, subscription=status)


@auth_bp.route('/assinaturas')
@login_required
def subscriptions():
    company = current_tenant_company()
    if current_user.role == 'master' and not company:
        return redirect(url_for('auth.master_dashboard'))

    subscription = subscription_status(company) if company else {}
    active_subscription = bool(company and company.subscription_valid)
    license_mode = company_uses_key_license(company)
    show_plans = request.args.get('planos') == '1' or not active_subscription

    if not can_view_finance_settings():
        return redirect(url_for(
            'auth.permission_unlock',
            permission='can_view_finance',
            next=request.full_path if request.query_string else request.path,
        ))

    return render_template(
        'subscription/plans.html',
        company=company,
        subscription=subscription,
        plans=BASIC_PRO_PLANS,
        current_plan=current_basic_pro_plan(company),
        active_subscription=active_subscription,
        show_plans=show_plans,
        license_mode=license_mode,
    )


def master_required():
    if current_user.role != 'master':
        flash('Apenas o usuário master pode acessar este painel.', 'danger')
        return False
    return True


@auth_bp.route('/master/adegas')
@login_required
def master_companies():
    if not master_required():
        return redirect(url_for('main.dashboard'))

    view_mode = request.args.get('view', 'table')
    if view_mode not in ('table', 'cards'):
        view_mode = 'table'
    companies = Company.query.filter(Company.is_system.is_(False)).order_by(Company.id.asc()).all()
    user_counts = {
        company.id: User.query.filter_by(company_id=company.id).count()
        for company in companies
    }
    subscription_statuses = {
        company.id: subscription_status(company)
        for company in companies
    }
    company_stats = {}
    for company in companies:
        tenant_db = None
        try:
            tenant_db = sessionmaker(bind=tenant_engine(company))()
            company_stats[company.id] = {
                'products': tenant_db.query(Product).count(),
                'sales': tenant_db.query(Sale).count(),
                'cash_registers': tenant_db.query(CashRegister).count(),
            }
        except SQLAlchemyError as error:
            current_app.logger.warning(
                'Não foi possível carregar estatísticas da adega %s no painel master: %s',
                company.id,
                error,
                exc_info=True,
            )
            company_stats[company.id] = {
                'products': 0,
                'sales': 0,
                'cash_registers': 0,
            }
        finally:
            if tenant_db:
                tenant_db.close()
    return render_template(
        'master/companies.html',
        master_section='companies',
        master_title='Adegas',
        master_description='Gerencie, acesse e acompanhe as adegas cadastradas.',
        companies=companies,
        user_counts=user_counts,
        company_stats=company_stats,
        subscription_statuses=subscription_statuses,
        subscription_plans=SUBSCRIPTION_PLANS,
        billing_cycles=BILLING_CYCLES,
        view_mode=view_mode,
        active_master_company_id=session.get('master_company_id'),
    )


@auth_bp.route('/master')
@login_required
def master_dashboard():
    if not master_required():
        return redirect(url_for('main.dashboard'))

    companies = Company.query.filter(Company.is_system.is_(False)).order_by(Company.id.desc()).all()
    users = User.query.filter(User.role != 'master').order_by(User.created_at.desc(), User.id.desc()).all()
    recent_error_logs = read_recent_error_logs()
    available_keys = ActivationKey.query.filter(
        ActivationKey.active.is_(True),
        ActivationKey.used_by_company_id.is_(None),
    ).count()

    return render_template(
        'master/companies.html',
        master_section='overview',
        master_title='Visão geral',
        master_description='Acompanhe a operação da plataforma em um só lugar.',
        companies=companies,
        recent_companies=companies[:5],
        total_users=len(users),
        active_companies=sum(1 for company in companies if company.active),
        active_subscriptions=sum(1 for company in companies if company.subscription_valid),
        available_keys=available_keys,
        recent_error_logs=recent_error_logs,
    )


@auth_bp.route('/master/usuarios')
@login_required
def master_users():
    if not master_required():
        return redirect(url_for('main.dashboard'))

    search = request.args.get('q', '').strip().casefold()
    users = User.query.order_by(User.company_id.asc(), User.first_name.asc(), User.username.asc()).all()
    if search:
        users = [
            user for user in users
            if search in ' '.join((
                user.full_name,
                user.username or '',
                user.email or '',
                user.cpf or '',
                user.company.name if user.company else '',
            )).casefold()
        ]

    return render_template(
        'master/companies.html',
        master_section='users',
        master_title='Usuários',
        master_description='Consulte os usuários e identifique a adega e o perfil de cada acesso.',
        users=users,
        search=search,
    )


@auth_bp.route('/master/usuarios/<int:user_id>/excluir', methods=['POST'])
@login_required
def delete_master_user(user_id):
    if not master_required():
        return redirect(url_for('main.dashboard'))

    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash('Não é possível excluir a conta master que está em uso.', 'danger')
        return redirect(url_for('auth.master_users'))

    confirmation = request.form.get('confirmation', '')
    if _normalized_deletion_confirmation(confirmation) != _normalized_deletion_confirmation(user.username):
        current_app.logger.warning(
            'Exclusão do usuário %s recusada: confirmação não confere.',
            user.id,
        )
        flash('A exclusão foi cancelada porque o usuário informado não confere.', 'danger')
        return redirect(url_for('auth.master_users'))

    if user.role == 'master' and User.query.filter_by(role='master', is_active=True).count() <= 1:
        flash('Não é possível excluir o último usuário master ativo.', 'danger')
        return redirect(url_for('auth.master_users'))

    old_values = {
        'username': user.username,
        'name': user.full_name,
        'role': user.role,
        'company_id': user.company_id,
    }
    try:
        db.session.execute(db.update(Sale).where(Sale.user_id == user.id).values(user_id=None))
        db.session.execute(
            db.update(Sale).where(Sale.cancelled_by_user_id == user.id).values(cancelled_by_user_id=None)
        )
        db.session.execute(db.update(CashRegister).where(CashRegister.user_id == user.id).values(user_id=None))
        db.session.execute(db.update(StockMovement).where(StockMovement.user_id == user.id).values(user_id=None))
        db.session.execute(db.update(Notification).where(Notification.user_id == user.id).values(user_id=None))
        db.session.execute(db.update(AuditLog).where(AuditLog.user_id == user.id).values(user_id=None))
        db.session.execute(db.delete(NotificationPreference).where(NotificationPreference.user_id == user.id))
        db.session.execute(db.delete(ApiRefreshToken).where(ApiRefreshToken.user_id == user.id))
        db.session.execute(db.delete(EmailVerificationCode).where(EmailVerificationCode.user_id == user.id))
        db.session.execute(db.delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
        db.session.execute(db.delete(EmailChangeRequest).where(EmailChangeRequest.user_id == user.id))
        record_audit_event(
            'user_deleted',
            'user',
            user.id,
            f'Usuário {user.username} excluído pelo painel master.',
            old_values=old_values,
            company_id=user.company_id,
            db_session=db.session,
        )
        db.session.delete(user)
        db.session.commit()
    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.error('Falha ao excluir usuário %s: %s', user_id, error, exc_info=True)
        flash('Não foi possível excluir este usuário porque ainda existem vínculos protegidos.', 'danger')
        return redirect(url_for('auth.master_users'))

    flash('Usuário excluído do banco de dados com sucesso.', 'success')
    return redirect(url_for('auth.master_users'))


@auth_bp.route('/master/assinaturas')
@login_required
def master_subscriptions():
    if not master_required():
        return redirect(url_for('main.dashboard'))

    companies = Company.query.filter(Company.is_system.is_(False)).order_by(Company.name.asc()).all()
    search = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()
    plan_filter = request.args.get('plan', '').strip()
    company_filter = request.args.get('company_id', '').strip()
    expiry_filter = request.args.get('expiry', '').strip()
    sort = request.args.get('sort', 'created_desc').strip()
    try:
        page = max(int(request.args.get('page', '1')), 1)
    except ValueError:
        page = 1

    query = ActivationKey.query
    today = date.today()
    if search:
        pattern = f'%{search}%'
        matching_company_ids = [
            company.id for company in companies if search.casefold() in company.name.casefold()
        ]
        search_clauses = [
            ActivationKey.key.ilike(pattern),
            ActivationKey.display_name.ilike(pattern),
            ActivationKey.plan.ilike(pattern),
        ]
        if matching_company_ids:
            search_clauses.extend((
                ActivationKey.assigned_company_id.in_(matching_company_ids),
                ActivationKey.used_by_company_id.in_(matching_company_ids),
            ))
        query = query.filter(or_(*search_clauses))
    if plan_filter in MASTER_KEY_PLANS:
        query = query.filter(ActivationKey.plan == plan_filter)
    if company_filter.isdigit():
        company_id = int(company_filter)
        query = query.filter(or_(
            ActivationKey.assigned_company_id == company_id,
            ActivationKey.used_by_company_id == company_id,
        ))
    if status_filter == 'available':
        query = query.filter(ActivationKey.active.is_(True), ActivationKey.used_by_company_id.is_(None), ActivationKey.renews_at >= today)
    elif status_filter == 'used':
        query = query.filter(ActivationKey.active.is_(True), ActivationKey.used_by_company_id.is_not(None))
    elif status_filter == 'expired':
        query = query.filter(ActivationKey.active.is_(True), ActivationKey.renews_at < today)
    elif status_filter == 'revoked':
        query = query.filter(ActivationKey.active.is_(False))
    if expiry_filter == '7':
        query = query.filter(ActivationKey.renews_at.between(today, today + timedelta(days=7)))
    elif expiry_filter == '30':
        query = query.filter(ActivationKey.renews_at.between(today, today + timedelta(days=30)))
    elif expiry_filter == 'expired':
        query = query.filter(ActivationKey.renews_at < today)

    ordering = {
        'created_asc': (ActivationKey.created_at.asc(), ActivationKey.id.asc()),
        'expiry_asc': (ActivationKey.renews_at.asc(), ActivationKey.id.asc()),
        'expiry_desc': (ActivationKey.renews_at.desc(), ActivationKey.id.desc()),
        'plan': (ActivationKey.plan.asc(), ActivationKey.created_at.desc()),
    }.get(sort, (ActivationKey.created_at.desc(), ActivationKey.id.desc()))
    per_page = 20
    total_keys = query.count()
    total_pages = max((total_keys + per_page - 1) // per_page, 1)
    page = min(page, total_pages)
    activation_keys = query.order_by(*ordering).offset((page - 1) * per_page).limit(per_page).all()

    all_keys = ActivationKey.query.all()
    active_keys = [key for key in all_keys if key.active and key.renews_at >= today]
    linked_company_ids = {
        key.used_by_company_id or key.assigned_company_id
        for key in active_keys if key.used_by_company_id or key.assigned_company_id
    }
    upcoming_dates = [key.renews_at for key in active_keys if key.renews_at]
    plan_counts = {}
    for activation_key in active_keys:
        plan_counts[activation_key.plan] = plan_counts.get(activation_key.plan, 0) + 1
    main_plan = max(plan_counts, key=plan_counts.get) if plan_counts else '-'
    next_expiry = min(upcoming_dates) if upcoming_dates else None

    return render_template(
        'master/companies.html',
        master_section='subscriptions',
        master_title='Assinaturas',
        master_description='Gerencie assinaturas, licenças e keys de acesso do sistema.',
        companies=companies,
        activation_keys=activation_keys,
        activation_key_statuses={
            activation_key.id: activation_key_status(activation_key)
            for activation_key in activation_keys
        },
        subscription_plans=SUBSCRIPTION_PLANS,
        master_key_plans=MASTER_KEY_PLANS,
        billing_cycles=BILLING_CYCLES,
        key_payment_cycles=KEY_PAYMENT_CYCLES,
        key_presets=KEY_PRESETS,
        subscription_summary={
            'active': len(active_keys),
            'total': len(all_keys),
            'main_plan': main_plan,
            'next_expiry': next_expiry,
            'next_expiry_days': (next_expiry - today).days if next_expiry else None,
            'linked_companies': len(linked_company_ids),
        },
        filters={'q': search, 'status': status_filter, 'plan': plan_filter, 'company_id': company_filter, 'expiry': expiry_filter, 'sort': sort},
        page=page,
        total_pages=total_pages,
        total_keys=total_keys,
    )


@auth_bp.route('/master/logs')
@login_required
def master_logs():
    if not master_required():
        return redirect(url_for('main.dashboard'))

    return render_template(
        'master/companies.html',
        master_section='logs',
        master_title='Logs',
        master_description='Investigue falhas e avisos registrados pela aplicação.',
        recent_error_logs=read_recent_error_logs(),
    )


@auth_bp.route('/master/logs/limpar', methods=['POST'])
@login_required
def clear_master_logs():
    if not master_required():
        return redirect(url_for('main.dashboard'))

    clear_error_log_file()
    record_audit_event(
        'logs_cleared',
        'logs',
        None,
        'Logs de erro e segurança foram limpos pelo painel master.',
        company_id=current_user.company_id,
        db_session=db.session,
    )
    db.session.commit()
    flash('Logs limpos com sucesso.', 'success')
    return redirect(url_for('auth.master_logs'))


@auth_bp.route('/master/assinaturas/keys/gerar', methods=['POST'])
@login_required
@limiter.limit(
    configured_limit('RATELIMIT_ADMIN', '30 per hour'),
    key_func=authenticated_identity_key,
)
def generate_master_activation_key():
    if not master_required():
        return redirect(url_for('main.dashboard'))

    plan = request.form.get('plan', 'Basic').strip()
    if plan not in MASTER_KEY_PLANS:
        flash('Plano inválido para geração de key.', 'danger')
        return redirect(url_for('auth.master_subscriptions'))

    billing_cycle, renews_at = renewal_date_from_request()
    if billing_cycle not in KEY_PAYMENT_CYCLES:
        billing_cycle = 'monthly'

    display_name = request.form.get('display_name', '').strip()[:160]
    assigned_company_id = request.form.get('company_id', '').strip()
    assigned_company = db.session.get(Company, int(assigned_company_id)) if assigned_company_id.isdigit() else None
    if assigned_company and assigned_company.is_system:
        assigned_company = None

    if renews_at < date.today():
        flash('A data de vencimento da key não pode estar no passado.', 'danger')
        return redirect(url_for('auth.master_subscriptions'))

    try:
        quantity = min(max(int(request.form.get('quantity', '1')), 1), 50)
    except ValueError:
        quantity = 1

    generated_keys = []
    for _ in range(quantity):
        activation_key = ActivationKey(
            key=generate_unique_activation_key(),
            plan=plan,
            display_name=display_name,
            payment_cycle=billing_cycle,
            renews_at=renews_at,
            active=True,
            assigned_company_id=assigned_company.id if assigned_company else None,
            created_by_user_id=current_user.id,
        )
        db.session.add(activation_key)
        generated_keys.append(activation_key)

    for activation_key in generated_keys:
        record_audit_event(
            'activation_key_generated',
            'activation_key',
            None,
            f'Key {activation_key.plan} gerada pelo painel master.',
            new_values={'plan': activation_key.plan, 'renews_at': activation_key.renews_at, 'activation_key': activation_key.key, 'assigned_company_id': activation_key.assigned_company_id, 'payment_cycle': activation_key.payment_cycle},
            company_id=activation_key.assigned_company_id or current_user.company_id,
            db_session=db.session,
        )
    db.session.commit()
    if len(generated_keys) == 1:
        label = 'Key vinculada gerada' if assigned_company else 'Key avulsa gerada'
        flash(f'{label}: {generated_keys[0].key}', 'success')
    else:
        flash(f'{len(generated_keys)} keys avulsas geradas: {", ".join(key.key for key in generated_keys)}', 'success')
    return redirect(url_for('auth.master_subscriptions'))


@auth_bp.route('/master/assinaturas/renovar', methods=['POST'])
@login_required
def renew_master_subscription():
    if not master_required():
        return redirect(url_for('main.dashboard'))

    company_id = request.form.get('company_id', '').strip()
    try:
        linked_company_id = int(company_id)
    except ValueError:
        linked_company_id = 0

    company = db.session.get(Company, linked_company_id)
    if not company or company.is_system:
        flash('Selecione uma adega para renovar a assinatura.', 'danger')
        return redirect(url_for('auth.master_subscriptions'))

    plan = request.form.get('plan', 'Basic').strip()
    if plan not in SUBSCRIPTION_PLANS:
        flash('Plano inválido para assinatura.', 'danger')
        return redirect(url_for('auth.master_subscriptions'))

    billing_cycle, renews_at = renewal_date_from_request(default_cycle=company.billing_cycle or 'monthly')
    preset_days = request.form.get('preset_days', '').strip()
    if preset_days and not request.form.get('renews_at', '').strip():
        try:
            days = max(int(preset_days), 1)
        except ValueError:
            days = 0
        if days:
            base_date = company.subscription_renews_at if company.subscription_renews_at and company.subscription_renews_at >= date.today() else date.today()
            renews_at = base_date + timedelta(days=days)
    if renews_at < date.today():
        flash('A data de renovação não pode estar no passado.', 'danger')
        return redirect(url_for('auth.master_subscriptions'))

    apply_subscription_to_company(company, plan, billing_cycle, renews_at)
    record_audit_event(
        'subscription_updated',
        'company',
        company.id,
        f'Assinatura da adega {company.name} renovada.',
        new_values={'plan': plan, 'billing_cycle': billing_cycle, 'renews_at': renews_at},
        company_id=company.id,
        db_session=db.session,
    )
    db.session.commit()
    flash(f'Assinatura da adega {company.name} renovada até {renews_at.strftime("%d/%m/%Y")}.', 'success')
    return redirect(url_for('auth.master_subscriptions'))


@auth_bp.route('/master/assinaturas/keys/<int:key_id>/cancelar', methods=['POST'])
@login_required
def cancel_master_activation_key(key_id):
    if not master_required():
        return redirect(url_for('main.dashboard'))

    activation_key = db.get_or_404(ActivationKey, key_id)
    record_audit_event(
        'activation_key_revoked',
        'activation_key',
        activation_key.id,
        'Key revogada pelo painel master.',
        old_values={'activation_key': activation_key.key, 'plan': activation_key.plan, 'renews_at': activation_key.renews_at},
        company_id=current_user.company_id,
        db_session=db.session,
    )
    activation_key.active = False
    activation_key.revoked_at = datetime.now(timezone.utc)
    if activation_key.company:
        activation_key.company.subscription_renews_at = date.today() - timedelta(days=1)
    db.session.commit()
    flash('Key revogada com sucesso. O histórico foi preservado.', 'success')
    return redirect(url_for('auth.master_subscriptions'))


@auth_bp.route('/master/assinaturas/keys/historico/limpar', methods=['POST'])
@login_required
def clear_master_activation_key_history():
    if not master_required():
        return redirect(url_for('main.dashboard'))

    confirmation = request.form.get('confirmation', '')
    if _normalized_deletion_confirmation(confirmation) != 'limpar historico':
        flash('A limpeza foi cancelada porque a confirmação não confere.', 'danger')
        return redirect(url_for('auth.master_subscriptions'))

    historical_keys = ActivationKey.query.filter(
        ActivationKey.used_by_company_id.is_(None),
        or_(ActivationKey.active.is_(False), ActivationKey.renews_at < date.today()),
    ).all()
    if not historical_keys:
        flash('Não há keys revogadas ou vencidas disponíveis para limpar.', 'info')
        return redirect(url_for('auth.master_subscriptions'))

    removed_ids = [activation_key.id for activation_key in historical_keys]
    record_audit_event(
        'activation_key_history_cleared', 'activation_key', None,
        f'Histórico de {len(removed_ids)} keys foi limpo pelo painel master.',
        old_values={'activation_key_ids': removed_ids, 'count': len(removed_ids)},
        company_id=current_user.company_id, db_session=db.session,
    )
    for activation_key in historical_keys:
        db.session.delete(activation_key)
    db.session.commit()
    flash(f'Histórico limpo: {len(removed_ids)} key(s) removida(s). Keys utilizadas foram preservadas.', 'success')
    return redirect(url_for('auth.master_subscriptions'))


@auth_bp.route('/master/assinaturas/keys/<int:key_id>/renovar', methods=['POST'])
@login_required
def renew_master_activation_key(key_id):
    if not master_required():
        return redirect(url_for('main.dashboard'))

    activation_key = db.get_or_404(ActivationKey, key_id)
    try:
        days = max(int(request.form.get('preset_days', '30')), 1)
    except ValueError:
        days = 30
    if days not in {1, 3, 7, 30, 90, 180, 365}:
        flash('Período de renovação inválido.', 'danger')
        return redirect(url_for('auth.master_subscriptions'))

    old_expiry = activation_key.renews_at
    base_date = old_expiry if old_expiry and old_expiry >= date.today() else date.today()
    activation_key.renews_at = base_date + timedelta(days=days)
    activation_key.active = True
    activation_key.revoked_at = None
    if activation_key.used_by_company_id:
        company = activation_key.company
        company.subscription_renews_at = activation_key.renews_at
        company.active = True
    record_audit_event(
        'activation_key_renewed', 'activation_key', activation_key.id,
        'Key renovada pelo painel master.',
        old_values={'renews_at': old_expiry},
        new_values={'renews_at': activation_key.renews_at, 'days': days},
        company_id=activation_key.used_by_company_id or activation_key.assigned_company_id or current_user.company_id,
        db_session=db.session,
    )
    db.session.commit()
    flash(f'Key renovada até {activation_key.renews_at.strftime("%d/%m/%Y")}.', 'success')
    return redirect(url_for('auth.master_subscriptions'))


@auth_bp.route('/master/assinaturas/keys/<int:key_id>/editar', methods=['POST'])
@login_required
def edit_master_activation_key(key_id):
    if not master_required():
        return redirect(url_for('main.dashboard'))

    activation_key = db.get_or_404(ActivationKey, key_id)
    plan = request.form.get('plan', '').strip()
    payment_cycle = request.form.get('payment_cycle', '').strip()
    company_id = request.form.get('company_id', '').strip()
    if plan not in MASTER_KEY_PLANS or payment_cycle not in KEY_PAYMENT_CYCLES:
        flash('Plano ou pagamento inválido.', 'danger')
        return redirect(url_for('auth.master_subscriptions'))
    assigned_company = db.session.get(Company, int(company_id)) if company_id.isdigit() else None
    if assigned_company and assigned_company.is_system:
        assigned_company = None
    old_values = {'plan': activation_key.plan, 'payment_cycle': activation_key.payment_cycle, 'assigned_company_id': activation_key.assigned_company_id}
    activation_key.plan = plan
    activation_key.payment_cycle = payment_cycle
    activation_key.assigned_company_id = assigned_company.id if assigned_company else None
    activation_key.display_name = request.form.get('display_name', '').strip()[:160]
    record_audit_event(
        'activation_key_updated', 'activation_key', activation_key.id,
        'Key atualizada pelo painel master.', old_values=old_values,
        new_values={'plan': plan, 'payment_cycle': payment_cycle, 'assigned_company_id': activation_key.assigned_company_id},
        company_id=activation_key.assigned_company_id or current_user.company_id, db_session=db.session,
    )
    db.session.commit()
    flash('Key atualizada com sucesso.', 'success')
    return redirect(url_for('auth.master_subscriptions'))


@auth_bp.route('/master/adegas/<int:company_id>/editar', methods=['POST'])
@login_required
def edit_company(company_id):
    if not master_required():
        return redirect(url_for('main.dashboard'))

    company = db.get_or_404(Company, company_id)
    if company.is_system:
        flash('O Painel Master é um contexto do sistema e não pode ser editado como adega.', 'danger')
        return redirect(url_for('auth.master_companies'))
    old_values = {
        'name': company.name,
        'active': company.active,
        'subscription_plan': company.subscription_plan,
        'billing_cycle': company.billing_cycle,
        'subscription_started_at': company.subscription_started_at,
        'subscription_renews_at': company.subscription_renews_at,
        'activation_key': company.activation_key,
    }
    name = request.form.get('name', '').strip()
    if not name:
        flash('Informe o nome da adega.', 'danger')
        return redirect(url_for('auth.master_companies'))

    company.name = name
    company.active = request.form.get('active') == 'on'
    if company.id == current_user.company_id:
        company.active = True

    plan = request.form.get('subscription_plan', '').strip()
    billing_cycle = request.form.get('billing_cycle', '').strip()
    started_at = parse_date_field(request.form.get('subscription_started_at'))
    renews_at = parse_date_field(request.form.get('subscription_renews_at'))

    if plan in SUBSCRIPTION_PLANS:
        company.subscription_plan = plan
    if billing_cycle in BILLING_CYCLES:
        company.billing_cycle = billing_cycle
    if started_at:
        company.subscription_started_at = started_at
    if renews_at:
        company.subscription_renews_at = renews_at

    if not company.subscription_renews_at:
        days = 365 if company.billing_cycle == 'annual' else 30
        company.subscription_renews_at = date.today() + timedelta(days=days)

    activation_key = request.form.get('activation_key', '').strip().upper()
    if request.form.get('generate_activation_key') == 'on':
        generated_record = ActivationKey(
            key=generate_unique_activation_key(),
            plan=company.subscription_plan if company.subscription_plan in MASTER_KEY_PLANS else 'Basic',
            renews_at=company.subscription_renews_at or date.today() + timedelta(days=365 if company.billing_cycle == 'annual' else 30),
            active=True,
        )
        db.session.add(generated_record)
        apply_activation_key_to_company(generated_record, company)
        company.billing_cycle = billing_cycle if billing_cycle in BILLING_CYCLES else company.billing_cycle
    elif not activation_key:
        if company.activation_key:
            company.activation_key = ''
            company.activation_key_updated_at = None
            company.subscription_started_at = None
            company.subscription_renews_at = None
    elif activation_key != (company.activation_key or ''):
        existing_key = ActivationKey.query.filter_by(key=activation_key).first()
        if existing_key:
            if not existing_key.active:
                flash('Esta key está cancelada.', 'danger')
                return redirect(url_for('auth.master_companies', view=request.form.get('view_mode', 'table')))
            if existing_key.used_by_company_id and existing_key.used_by_company_id != company.id:
                flash('Esta key já está vinculada a outra adega.', 'danger')
                return redirect(url_for('auth.master_companies', view=request.form.get('view_mode', 'table')))
            if existing_key.renews_at and existing_key.renews_at < date.today():
                flash('Esta key está vencida.', 'danger')
                return redirect(url_for('auth.master_companies', view=request.form.get('view_mode', 'table')))
            apply_activation_key_to_company(existing_key, company)
        else:
            company.activation_key = activation_key
            company.activation_key_updated_at = datetime.now(timezone.utc)
    if activation_key != (company.activation_key or ''):
        company.activation_key_updated_at = company.activation_key_updated_at or datetime.now(timezone.utc)

    record_audit_event(
        'company_updated',
        'company',
        company.id,
        f'Adega {company.name} atualizada pelo painel master.',
        old_values=old_values,
        new_values={
            'name': company.name,
            'active': company.active,
            'subscription_plan': company.subscription_plan,
            'billing_cycle': company.billing_cycle,
            'subscription_started_at': company.subscription_started_at,
            'subscription_renews_at': company.subscription_renews_at,
            'activation_key': company.activation_key,
        },
        company_id=company.id,
        db_session=db.session,
    )
    db.session.commit()
    flash('Adega atualizada com sucesso.', 'success')
    return redirect(url_for('auth.master_companies', view=request.form.get('view_mode', 'table')))


@auth_bp.route('/master/adegas/<int:company_id>/acessar', methods=['POST'])
@login_required
def access_company(company_id):
    if not master_required():
        return redirect(url_for('main.dashboard'))

    company = db.get_or_404(Company, company_id)
    if company.is_system:
        flash('O Painel Master não é uma adega para acesso operacional.', 'danger')
        return redirect(url_for('auth.master_companies'))
    tenant_engine(company)
    session['master_company_id'] = company.id
    record_audit_event(
        'company_accessed_by_master',
        'company',
        company.id,
        f'Master acessou a adega {company.name}.',
        company_id=company.id,
        db_session=db.session,
    )
    db.session.commit()
    flash(f'Master conectado em {company.name}.', 'success')
    return redirect(url_for('main.dashboard'))


@auth_bp.route('/master/adegas/sair-acesso', methods=['POST'])
@login_required
def leave_company_access():
    if not master_required():
        return redirect(url_for('main.dashboard'))

    company_id = session.pop('master_company_id', None)
    record_audit_event(
        'company_access_ended',
        'company',
        company_id,
        'Master encerrou o acesso a uma adega.',
        company_id=company_id,
        db_session=db.session,
    )
    db.session.commit()
    flash('Você voltou para o painel master.', 'info')
    return redirect(url_for('auth.master_companies'))


@auth_bp.route('/master/adegas/<int:company_id>/alternar-status', methods=['POST'])
@login_required
def toggle_company_status(company_id):
    if not master_required():
        return redirect(url_for('main.dashboard'))

    company = db.get_or_404(Company, company_id)
    if company.is_system:
        flash('O contexto do Painel Master não pode ser alterado como adega.', 'danger')
        return redirect(url_for('auth.master_companies'))
    if company.id == current_user.company_id:
        flash('Não é possível inativar a adega do usuário master.', 'danger')
        return redirect(url_for('auth.master_companies'))

    old_active = company.active
    company.active = not company.active
    record_audit_event(
        'company_activated' if company.active else 'company_deactivated',
        'company',
        company.id,
        f'Adega {company.name} {"ativada" if company.active else "inativada"}.',
        old_values={'active': old_active},
        new_values={'active': company.active},
        company_id=company.id,
        db_session=db.session,
    )
    db.session.commit()
    flash('Status da adega atualizado com sucesso.', 'success')
    return redirect(url_for('auth.master_companies'))


@auth_bp.route('/master/adegas/<int:company_id>/excluir', methods=['POST'])
@login_required
def delete_company(company_id):
    if not master_required():
        return redirect(url_for('main.dashboard'))

    company = db.get_or_404(Company, company_id)
    if company.is_system:
        flash('O contexto do Painel Master não pode ser excluído como adega.', 'danger')
        return redirect(url_for('auth.master_companies'))
    if company.id == current_user.company_id:
        flash('Não é possível excluir a adega do usuário master.', 'danger')
        return redirect(url_for('auth.master_companies'))

    confirmation = request.form.get('confirmation', '')
    if _normalized_deletion_confirmation(confirmation) != _normalized_deletion_confirmation(company.name):
        current_app.logger.warning(
            'Exclusão da adega %s recusada: confirmação não confere.',
            company.id,
        )
        flash('A exclusão foi cancelada porque o nome da adega informado não confere.', 'danger')
        return redirect(url_for('auth.master_companies'))

    database_name = company.database_path
    try:
        ActivationKey.query.filter_by(used_by_company_id=company.id).update(
            {'used_by_company_id': None, 'used_at': None},
            synchronize_session=False,
        )
        user_ids = [
            user_id
            for (user_id,) in db.session.query(User.id).filter_by(company_id=company.id).all()
        ]
        cash_register_ids = [
            cash_register_id
            for (cash_register_id,) in db.session.query(CashRegister.id).filter_by(company_id=company.id).all()
        ]
        sale_query = db.session.query(Sale.id).filter(Sale.company_id == company.id)
        if user_ids:
            sale_query = sale_query.union(db.session.query(Sale.id).filter(Sale.user_id.in_(user_ids)))
        if cash_register_ids:
            sale_query = sale_query.union(db.session.query(Sale.id).filter(Sale.cash_register_id.in_(cash_register_ids)))
        sale_ids = [sale_id for (sale_id,) in sale_query.all()]

        db.session.execute(db.delete(ApiSaleRequest).where(ApiSaleRequest.company_id == company.id))
        db.session.execute(db.delete(NotificationPreference).where(NotificationPreference.company_id == company.id))
        db.session.execute(db.delete(Notification).where(Notification.company_id == company.id))
        if user_ids:
            db.session.execute(db.delete(EmailVerificationCode).where(EmailVerificationCode.user_id.in_(user_ids)))
            db.session.execute(db.delete(PasswordResetToken).where(PasswordResetToken.user_id.in_(user_ids)))
            db.session.execute(db.delete(EmailChangeRequest).where(EmailChangeRequest.user_id.in_(user_ids)))
            db.session.execute(db.delete(ApiRefreshToken).where(ApiRefreshToken.user_id.in_(user_ids)))
            db.session.execute(db.update(AuditLog).where(AuditLog.user_id.in_(user_ids)).values(user_id=None))
        if sale_ids:
            db.session.execute(db.delete(Payment).where(Payment.sale_id.in_(sale_ids)))
            db.session.execute(db.delete(SaleItem).where(SaleItem.sale_id.in_(sale_ids)))
            db.session.execute(db.delete(Sale).where(Sale.id.in_(sale_ids)))
        db.session.execute(db.update(AuditLog).where(AuditLog.company_id == company.id).values(company_id=None))
        db.session.execute(db.delete(StockMovement).where(StockMovement.company_id == company.id))
        if cash_register_ids or user_ids:
            cash_filter = CashRegister.company_id == company.id
            if user_ids:
                cash_filter = cash_filter | CashRegister.user_id.in_(user_ids)
            db.session.execute(db.delete(CashRegister).where(cash_filter))
        db.session.execute(db.delete(Payable).where(Payable.company_id == company.id))
        db.session.execute(db.delete(EmailAlertDelivery).where(EmailAlertDelivery.company_id == company.id))
        db.session.execute(db.delete(EmailAlertSetting).where(EmailAlertSetting.company_id == company.id))
        db.session.execute(
            db.update(Product)
            .where(Product.company_id == company.id)
            .values(kit_component_product_id=None)
        )
        db.session.execute(db.delete(Product).where(Product.company_id == company.id))
        db.session.execute(db.delete(Category).where(Category.company_id == company.id))
        if user_ids:
            User.query.filter(User.id.in_(user_ids)).delete(synchronize_session=False)
        record_audit_event(
            'company_deleted',
            'company',
            company.id,
            f'Adega {company.name} excluída pelo painel master.',
            old_values={'name': company.name, 'database_path': database_name},
            company_id=None,
            db_session=db.session,
        )
        db.session.delete(company)
        db.session.commit()
    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.error('Falha ao excluir adega %s: %s', company_id, error, exc_info=True)
        flash('Não foi possível excluir esta adega porque ainda existem vínculos no banco central.', 'danger')
        return redirect(url_for('auth.master_companies'))

    if database_name:
        try:
            drop_mysql_database(database_name)
        except Exception as error:
            current_app.logger.error('Falha ao excluir banco da adega %s: %s', database_name, error, exc_info=True)
            flash('Adega removida do painel, mas não foi possível apagar o banco de dados dela automaticamente.', 'warning')
            return redirect(url_for('auth.master_companies'))

    flash('Adega excluída com sucesso.', 'success')
    return redirect(url_for('auth.master_companies'))


@auth_bp.route('/configuracoes', methods=['GET', 'POST'])
@login_required
@limiter.limit(
    configured_limit('RATELIMIT_BACKUP', '3 per hour'),
    key_func=authenticated_identity_key,
    methods=['POST'],
    exempt_when=lambda: request.form.get('form_type') != 'manual_backup',
)
def settings():
    settings_company = current_tenant_company()
    if request.method == 'POST':
        form_type = request.form.get('form_type')

        if form_type == 'profile':
            current_user.first_name = request.form.get('first_name', '').strip()
            current_user.last_name = request.form.get('last_name', '').strip()
            current_user.phone = request.form.get('phone', '').strip()
            db.session.commit()
            flash('Dados do usuário atualizados com sucesso.', 'success')
            return redirect(url_for('auth.settings'))

        if form_type == 'email':
            email = request.form.get('email', '').strip()
            if not email or not valid_email(email):
                flash('Informe um e-mail válido.', 'danger')
                return redirect(url_for('auth.settings'))
            if email == (current_user.email or ''):
                flash('Este já é o e-mail cadastrado.', 'info')
                return redirect(url_for('auth.settings'))
            if not current_user.email:
                current_user.email = email
                current_user.email_verified = True
                current_user.email_verified_at = utc_now()
                db.session.commit()
                flash('Email atualizado com sucesso.', 'success')
                return redirect(url_for('auth.settings'))

            if not current_user.email_verified:
                current_user.email = email
                current_user.email_verified = False
                current_user.email_verified_at = None
                db.session.commit()
                remember_verification_user(current_user)
                sent, message = create_email_verification_code(current_user, force=True)
                flash(message, 'success' if sent else 'warning')
                flash('Confirme o novo e-mail para concluir a alteração.', 'info')
                return redirect(url_for('auth.verify_email'))

            try:
                request_email_change(current_user, email)
            except EmailAuthenticationError as error:
                current_app.logger.error('Falha de autenticação SMTP ao solicitar troca de email para user_id=%s: %s', current_user.id, error, exc_info=True)
                flash('Gmail recusou o envio. Confira a configuração de e-mail do sistema.', 'danger')
                return redirect(url_for('auth.settings'))
            except Exception as error:
                current_app.logger.error('Falha ao solicitar troca de email para user_id=%s: %s', current_user.id, error, exc_info=True)
                flash('Não foi possível enviar a confirmação para o e-mail antigo agora.', 'danger')
                return redirect(url_for('auth.settings'))

            flash('Enviamos um link de confirmação para o e-mail antigo.', 'success')
            return redirect(url_for('auth.settings'))

        if form_type == 'email_alerts':
            if not can_manage_company_users() and not authorize_permission_override('can_manage_settings'):
                flash('Informe a senha de um usuário autorizado para alterar alertas.', 'danger')
                return redirect(url_for('auth.settings'))
            if not settings_company:
                flash('Nenhuma adega selecionada para configurar alertas.', 'danger')
                return redirect(url_for('auth.settings'))

            if request.form.get('email_alert_action') == 'test':
                recipients = []
                for alert_type in EMAIL_ALERT_TYPES:
                    recipients.extend(parse_recipients(request.form.get(f'alert_recipients_{alert_type}', '')))
                recipients = list(dict.fromkeys(recipients))
                invalid_recipient = next((recipient for recipient in recipients if not valid_email(recipient)), None)
                if invalid_recipient:
                    flash(f'E-mail inválido: {invalid_recipient}', 'danger')
                    return redirect(url_for('auth.settings'))
                if not recipients:
                    flash('Adicione pelo menos um destinatário antes de testar o envio.', 'danger')
                    return redirect(url_for('auth.settings'))
                try:
                    sent_count = send_alert_email(
                        settings_company,
                        recipients,
                        'Teste de alertas por e-mail',
                        'Este é um envio de teste solicitado nas configurações do SkyGest.',
                    )
                except EmailAuthenticationError as error:
                    current_app.logger.error('Falha de autenticação SMTP no teste de alertas: %s', error, exc_info=True)
                    flash('O servidor de e-mail recusou a autenticação. Revise a configuração SMTP.', 'danger')
                except Exception as error:
                    current_app.logger.error('Falha no teste de alertas por e-mail: %s', error, exc_info=True)
                    flash('Não foi possível enviar o teste. Verifique a configuração SMTP e tente novamente.', 'danger')
                else:
                    flash(f'E-mail de teste enviado para {sent_count} destinatário(s).', 'success')
                return redirect(url_for('auth.settings'))

            existing_settings = alert_settings_for_company(settings_company)
            for alert_type in EMAIL_ALERT_TYPES:
                setting = existing_settings.get(alert_type)
                if not setting:
                    setting = EmailAlertSetting(company_id=settings_company.id, alert_type=alert_type)
                    db.session.add(setting)
                recipients = parse_recipients(request.form.get(f'alert_recipients_{alert_type}', ''))
                invalid_recipients = [recipient for recipient in recipients if not valid_email(recipient)]
                if invalid_recipients:
                    flash(f'E-mail inválido em {EMAIL_ALERT_TYPES[alert_type]["label"]}: {invalid_recipients[0]}', 'danger')
                    return redirect(url_for('auth.settings'))
                setting.enabled = request.form.get(f'alert_enabled_{alert_type}') == 'on'
                setting.recipients = ', '.join(recipients)

            db.session.commit()
            flash('Alertas por e-mail atualizados com sucesso.', 'success')
            return redirect(url_for('auth.settings'))

        if form_type == 'password':
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')

            if not current_user.check_password(current_password):
                flash('Senha atual incorreta.', 'danger')
                return redirect(url_for('auth.settings'))
            password_error = password_first_error(new_password, username=current_user.username, email=current_user.email)
            if password_error:
                flash(password_error, 'danger')
                return redirect(url_for('auth.settings'))
            if new_password != confirm_password:
                flash('A confirmação da senha não confere.', 'danger')
                return redirect(url_for('auth.settings'))

            current_user.set_password(new_password)
            db.session.commit()
            flash('Senha alterada com sucesso.', 'success')
            return redirect(url_for('auth.settings'))

        if form_type == 'card_fees':
            if current_user.role not in ('admin', 'master') and not authorize_role_override('admin', 'master'):
                flash('Informe a senha de um admin para alterar as taxas da maquininha.', 'danger')
                return redirect(url_for('auth.settings'))

            company = current_user.company
            if current_user.role == 'master':
                company = settings_company
            if company:
                company.pix_fee_enabled = request.form.get('pix_fee_enabled') == 'on'
                company.debit_fee_enabled = request.form.get('debit_fee_enabled') == 'on'
                company.credit_fee_enabled = request.form.get('credit_fee_enabled') == 'on'
                company.card_fee_enabled = company.pix_fee_enabled or company.debit_fee_enabled or company.credit_fee_enabled
                company.pix_fee_percent = parse_percent(request.form.get('pix_fee_percent'))
                company.debit_fee_percent = parse_percent(request.form.get('debit_fee_percent'))
                company.credit_fee_percent = parse_percent(request.form.get('credit_fee_percent'))
                db.session.commit()
                flash('Taxas da maquininha atualizadas com sucesso.', 'success')
            return redirect(url_for('auth.settings'))

        if form_type == 'inventory_settings':
            if current_user.role not in ('admin', 'master') and not authorize_role_override('admin', 'master'):
                flash('Informe a senha de um admin para alterar as regras de estoque.', 'danger')
                return redirect(url_for('auth.settings'))
            if settings_company:
                settings_company.allow_negative_stock = request.form.get('allow_negative_stock') == 'on'
                db.session.commit()
                flash('Regras de estoque atualizadas com sucesso.', 'success')
            return redirect(url_for('auth.settings'))

        if form_type == 'backup_settings':
            if not can_manage_company_users() and not authorize_permission_override('can_manage_settings'):
                flash('Informe a senha de um usuário autorizado para configurar backups.', 'danger')
                return redirect(url_for('auth.settings'))

            frequency = request.form.get('backup_frequency', 'manual')
            if frequency not in BACKUP_FREQUENCIES:
                frequency = 'manual'
            if settings_company:
                settings_company.backup_frequency = frequency
                db.session.commit()
                flash('Configuração de backup salva com sucesso.', 'success')
            return redirect(url_for('auth.settings'))

        if form_type == 'manual_backup':
            if not can_manage_company_users() and not authorize_permission_override('can_manage_settings'):
                flash('Informe a senha de um usuário autorizado para gerar backup.', 'danger')
                return redirect(url_for('auth.settings'))

            try:
                backup_path = create_company_backup(settings_company, reason='manual')
                flash(f'Backup gerado com sucesso: {backup_path.name}', 'success')
            except Exception:
                flash('Não foi possível gerar o backup agora. Verifique os logs.', 'danger')
            return redirect(url_for('auth.settings'))

        if form_type == 'master_generate_key':
            if current_user.role != 'master':
                flash('Apenas o master do sistema pode gerar keys.', 'danger')
                return redirect(url_for('auth.settings'))

            plan = request.form.get('key_plan', 'Basic')
            renews_at = parse_date_field(request.form.get('key_renews_at'))
            if plan not in MASTER_KEY_PLANS:
                plan = 'Basic'
            if not renews_at:
                flash('Informe a data de validade da key.', 'danger')
                return redirect(url_for('auth.settings'))

            try:
                quantity = min(max(int(request.form.get('key_quantity', '1')), 1), 50)
            except ValueError:
                quantity = 1

            generated_keys = []
            for _ in range(quantity):
                key_record = ActivationKey(
                    key=generate_unique_activation_key(),
                    plan=plan,
                    renews_at=renews_at,
                    active=True,
                )
                db.session.add(key_record)
                generated_keys.append(key_record)
            db.session.commit()
            if len(generated_keys) == 1:
                flash(f'Key avulsa gerada: {generated_keys[0].key}', 'success')
            else:
                flash(f'{len(generated_keys)} keys avulsas geradas: {", ".join(key.key for key in generated_keys)}', 'success')
            return redirect(url_for('auth.settings'))

        if form_type == 'hire_user':
            if not can_manage_company_users() and not authorize_permission_override('can_manage_settings'):
                flash('Informe a senha de um usuário autorizado para contratar usuários.', 'danger')
                return redirect(url_for('auth.settings'))

            username = request.form.get('hire_username', '').strip()
            first_name = request.form.get('hire_first_name', '').strip()
            last_name = request.form.get('hire_last_name', '').strip()
            cpf = request.form.get('hire_cpf', '').strip()
            email = request.form.get('hire_email', '').strip()
            password = request.form.get('hire_password', '')
            role = request.form.get('hire_role', 'operator')
            if role not in EMPLOYEE_ROLES:
                role = 'operator'

            if not username:
                flash('Informe o login do novo usuário.', 'danger')
                return redirect(url_for('auth.settings'))
            password_error = password_first_error(password, username=username, email=email)
            if password_error:
                flash(password_error, 'danger')
                return redirect(url_for('auth.settings'))
            if User.query.filter_by(username=username).first():
                flash('Já existe um usuário com este login.', 'danger')
                return redirect(url_for('auth.settings'))
            if email and not valid_email(email):
                flash('Informe um e-mail válido para o funcionário.', 'danger')
                return redirect(url_for('auth.settings'))
            if company_cpf_exists(settings_company.id, cpf):
                flash('Já existe um funcionário com este CPF nesta adega.', 'danger')
                return redirect(url_for('auth.settings'))
            user = User(
                username=username,
                first_name=first_name,
                last_name=last_name,
                cpf=cpf,
                email=email,
                role=role,
                company_id=settings_company.id,
                is_active=True,
            )
            apply_employee_permissions(user, request.form)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash('Usuário contratado com sucesso.', 'success')
            return redirect(url_for('auth.settings'))

        if form_type == 'update_employee':
            if not can_manage_company_users() and not authorize_permission_override('can_manage_settings'):
                flash('Informe a senha de um usuário autorizado para alterar funcionários.', 'danger')
                return redirect(url_for('auth.settings'))

            employee_id = request.form.get('employee_id')
            employee = User.query.filter_by(id=employee_id, company_id=settings_company.id).first()
            if not employee:
                flash('Funcionário não encontrado.', 'danger')
                return redirect(url_for('auth.settings'))
            if employee.id == current_user.id and employee.role == 'admin' and request.form.get('is_active') != 'on':
                flash('Você não pode inativar o próprio admin da adega.', 'danger')
                return redirect(url_for('auth.settings'))

            employee.is_active = request.form.get('is_active') == 'on'
            employee.first_name = request.form.get('employee_first_name', '').strip()
            employee.last_name = request.form.get('employee_last_name', '').strip()
            employee_email = request.form.get('employee_email', '').strip()
            if employee_email and not valid_email(employee_email):
                flash('Informe um e-mail válido para o funcionário.', 'danger')
                return redirect(url_for('auth.settings'))
            if employee_email != (employee.email or ''):
                employee.email = employee_email
            employee_cpf = request.form.get('employee_cpf', '').strip()
            if company_cpf_exists(settings_company.id, employee_cpf, employee.id):
                flash('Já existe um funcionário com este CPF nesta adega.', 'danger')
                return redirect(url_for('auth.settings'))
            employee.cpf = employee_cpf
            role = request.form.get('employee_role', employee.role)
            if employee.id == current_user.id and employee.role == 'admin':
                role = 'admin'
            employee.role = role if role in EMPLOYEE_ROLES else employee.role
            apply_employee_permissions(employee, request.form)
            db.session.commit()
            flash('Permissões do funcionário atualizadas.', 'success')
            return redirect(url_for('auth.settings'))

    can_view_admin_tabs = can_view_admin_settings()
    can_view_finance_tab = can_view_finance_settings()
    company_users = User.query.filter_by(company_id=settings_company.id).order_by(User.username.asc()).all() if settings_company and can_view_admin_tabs else []
    key_records = ActivationKey.query.filter(
        ActivationKey.active.is_(True)
    ).order_by(ActivationKey.created_at.desc()).limit(20).all() if current_user.role == 'master' else []
    email_alert_settings = alert_settings_for_company(settings_company) if settings_company and can_view_admin_tabs else {}
    return render_template(
        'settings/index.html',
        company_users=company_users,
        settings_company=settings_company,
        employee_permissions=EMPLOYEE_PERMISSIONS,
        permission_labels=PERMISSION_LABELS,
        employee_roles=EMPLOYEE_ROLES,
        can_manage_employees=can_manage_company_users(),
        can_view_admin_tabs=can_view_admin_tabs,
        can_view_finance_tab=can_view_finance_tab,
        backup_frequencies=BACKUP_FREQUENCIES,
        backup_frequency_label=backup_frequency_label,
        can_import_products=can_import_products_settings(),
        can_export_data=can_export_data_settings(),
        key_records=key_records,
        key_plans=MASTER_KEY_PLANS,
        key_presets=KEY_PRESETS,
        default_key_renews_at=date.today() + timedelta(days=30),
        email_alert_types=EMAIL_ALERT_TYPES,
        email_alert_settings=email_alert_settings,
    )


@auth_bp.route('/configuracoes/importacao/modelo')
@login_required
def import_template_download():
    if not can_import_products_settings():
        flash('Apenas o dono da adega pode baixar o modelo de importação.', 'danger')
        return redirect(url_for('auth.settings'))

    template_path = Path(current_app.root_path) / 'static' / 'files' / 'modelo_importacao.xlsx'
    if not template_path.exists():
        flash('Modelo de importação não encontrado.', 'danger')
        return redirect(url_for('auth.settings'))

    return send_file(
        io.BytesIO(template_path.read_bytes()),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='modelo_importacao_produtos.xlsx',
    )
