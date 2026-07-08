from datetime import date, datetime, timedelta, timezone
import io
import json
from pathlib import Path
import re
import secrets
import string
import time

from flask import Blueprint, current_app, redirect, render_template, request, send_file, session, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash

from app.backup import BACKUP_FREQUENCIES, backup_frequency_label, create_company_backup
from app.extensions import db
from app.models import ActivationKey, CashRegister, Category, Company, EmailAlertDelivery, EmailAlertSetting, EmailChangeRequest, EmailVerificationCode, PasswordResetToken, Payable, Payment, Product, Sale, SaleItem, User
from app.permissions import (
    PERMISSION_LABELS,
    authorize_permission_override,
    authorize_role_override,
    grant_permission_view_override,
    has_permission_view_override,
    user_can_override_permission,
)
from app.services.alert_service import EMAIL_ALERT_TYPES, alert_settings_for_company, parse_recipients
from app.services.email_service import EmailAuthenticationError, send_email_change_confirmation, send_password_reset_email, send_verification_code_email
from app.tenant import current_tenant_company, drop_mysql_database, tenant_database_identifier, tenant_engine


auth_bp = Blueprint('auth', __name__)
SUBSCRIPTION_PLANS = ('Basic', 'Pro', 'Essencial', 'Profissional', 'Premium')
MASTER_KEY_PLANS = ('Basic', 'Pro')
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
)
BILLING_CYCLES = {
    'monthly': 'Mensal',
    'annual': 'Anual',
}
KEY_PRESETS = (
    ('1d', '1 dia', 1),
    ('3d', '3 dias', 3),
    ('7d', '7 dias', 7),
    ('1m', '1 mês', 30),
    ('3m', '3 meses', 90),
    ('1y', '1 ano', 365),
)
LOGIN_ATTEMPTS = {}
LOGIN_ATTEMPT_LIMIT = 5
LOGIN_BLOCK_SECONDS = 15 * 60
VERIFICATION_CODE_TTL_MINUTES = 15
VERIFICATION_ATTEMPT_LIMIT = 5
VERIFICATION_RESEND_SECONDS = 60
VERIFICATION_RESEND_HOURLY_LIMIT = 3
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
    'can_manage_cash_register',
    'can_view_reports',
    'can_manage_payables',
    'can_manage_settings',
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
        'can_manage_cash_register': True,
        'can_view_reports': False,
        'can_manage_payables': False,
        'can_manage_settings': False,
    },
    'manager': {
        'can_view_products': True,
        'can_manage_products': True,
        'can_manage_categories': True,
        'can_manage_sales': True,
        'can_manage_cash_register': True,
        'can_view_reports': True,
        'can_manage_payables': True,
        'can_manage_settings': True,
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


def login_attempt_key(username):
    remote_addr = request.headers.get('X-Forwarded-For', request.remote_addr) or 'local'
    return f'{remote_addr.split(",")[0].strip()}:{(username or "").lower()}'


def login_is_blocked(username):
    attempt = LOGIN_ATTEMPTS.get(login_attempt_key(username))
    if not attempt:
        return False
    blocked_until = attempt.get('blocked_until') or 0
    if blocked_until <= time.time():
        if blocked_until:
            LOGIN_ATTEMPTS.pop(login_attempt_key(username), None)
        return False
    return True


def register_login_failure(username):
    key = login_attempt_key(username)
    attempt = LOGIN_ATTEMPTS.setdefault(key, {'count': 0, 'blocked_until': 0})
    attempt['count'] += 1
    if attempt['count'] >= LOGIN_ATTEMPT_LIMIT:
        attempt['blocked_until'] = time.time() + LOGIN_BLOCK_SECONDS


def clear_login_failures(username):
    LOGIN_ATTEMPTS.pop(login_attempt_key(username), None)


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


def available_activation_key(value):
    key = (value or '').strip().upper()
    if not key:
        return None
    activation_key = ActivationKey.query.filter_by(key=key, active=True, used_by_company_id=None).first()
    if not activation_key:
        return None
    if activation_key.renews_at and activation_key.renews_at < date.today():
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
        renews_at = date.today() + timedelta(days=365 if billing_cycle == 'annual' else 30)

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
            'label': 'Cancelada',
            'state': 'danger',
            'available': False,
        }
    if activation_key.used_by_company_id:
        return {
            'label': 'Usada',
            'state': 'ok',
            'available': False,
        }
    if activation_key.renews_at and activation_key.renews_at < today:
        return {
            'label': 'Vencida',
            'state': 'danger',
            'available': False,
        }
    return {
        'label': 'Disponível',
        'state': 'warning',
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
    if company.subscription_plan in ('Pro', 'Premium', 'Profissional'):
        return 'Pro'
    return 'Basic'


def login_form_values():
    return {
        'username': request.form.get('username', '').strip(),
    }


def register_form_values():
    return {
        'username': request.form.get('username', '').strip(),
        'company_name': request.form.get('company_name', '').strip(),
        'email': request.form.get('email', '').strip(),
    }


def render_auth_form(auth_tab='login', form_values=None, field_errors=None):
    return render_template(
        'login.html',
        auth_tab=auth_tab,
        form_values=form_values or {},
        field_errors=field_errors or {},
    )


@auth_bp.route('/login', methods=['GET', 'POST'])
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
            if password_too_short(password):
                flash(f'A senha deve ter pelo menos {password_min_length()} caracteres.', 'danger')
                return render_auth_form('register', form_values, {'password': f'Use pelo menos {password_min_length()} caracteres.'})
            if password != confirm_password:
                flash('A confirmação da senha não confere.', 'danger')
                return render_auth_form('register', form_values, {'confirm_password': 'A confirmação não confere com a senha.'})
            if User.query.filter_by(username=username).first():
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
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
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

        if login_is_blocked(username):
            flash('Muitas tentativas de login. Aguarde alguns minutos e tente novamente.', 'danger')
            return render_auth_form('login', login_form_values(), {'username': 'Muitas tentativas para este acesso.'})

        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()

        if user and user.check_password(password):
            clear_login_failures(username)
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
            login_user(user)
            flash('Login realizado com sucesso.', 'success')
            if user.role == 'master':
                return redirect(url_for('auth.master_dashboard'))
            if company_requires_activation(user.company):
                flash('A assinatura desta adega está bloqueada.', 'warning')
                if company_uses_key_license(user.company):
                    return redirect(url_for('auth.subscription_activation'))
                return redirect(url_for('auth.subscriptions'))
            return redirect(url_for('main.dashboard'))

        register_login_failure(username)
        if user:
            flash('Senha incorreta.', 'danger')
            return render_auth_form('login', login_form_values(), {'password': 'Senha incorreta.'})

        flash('Usuário ou e-mail não encontrado.', 'danger')
        return render_auth_form('login', login_form_values(), {'username': 'Usuário ou e-mail não encontrado.'})

    return render_auth_form('login')


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
        db.session.commit()
        clear_verification_user()
        login_user(user)
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
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if not valid_email(email):
            flash('Informe um e-mail válido.', 'danger')
            return render_template('forgot_password.html')

        user = User.query.filter_by(email=email).first()
        if user and user.is_active and user.email_verified:
            PasswordResetToken.query.filter_by(user_id=user.id, used=False).update({'used': True})
            token = secrets.token_urlsafe(32)
            reset_record = PasswordResetToken(
                user_id=user.id,
                token_hash=generate_password_hash(token, method='scrypt'),
                expires_at=utc_now() + timedelta(minutes=PASSWORD_RESET_TTL_MINUTES),
                used=False,
            )
            db.session.add(reset_record)
            db.session.commit()
            reset_url = public_url_for('auth.reset_password', token=token)
            try:
                if current_app.config.get('MAIL_SUPPRESS_SEND'):
                    current_app.config['TEST_LAST_PASSWORD_RESET_TOKEN'] = token
                    current_app.config['TEST_LAST_PASSWORD_RESET_URL'] = reset_url
                send_password_reset_email(user, reset_url)
                current_app.logger.info('Email de recuperação enviado para user_id=%s', user.id)
            except EmailAuthenticationError as error:
                current_app.logger.error('Falha de autenticação SMTP na recuperação de senha para %s: %s', email, error, exc_info=True)
                flash('Gmail recusou o envio. Confira se MAIL_SMTP_LOGIN é o e-mail correto e se MAIL_SMTP_PASSWORD é uma senha de app válida.', 'danger')
                return render_template('forgot_password.html')
            except Exception as error:
                current_app.logger.error('Falha ao enviar recuperação de senha para %s: %s', email, error, exc_info=True)
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
        if password_too_short(password):
            flash(f'A senha deve ter pelo menos {password_min_length()} caracteres.', 'danger')
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


@auth_bp.route('/logout')
@login_required
def logout():
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
def subscription_activation():
    if current_user.role == 'master':
        return redirect(url_for('auth.master_dashboard'))

    company = current_user.company
    status = subscription_status(company) if company else {}

    if request.method == 'POST':
        activation_key = request.form.get('activation_key', '').strip().upper()
        expected_key = (company.activation_key or '').strip().upper() if company else ''

        if not expected_key:
            generated_key = available_activation_key(activation_key)
            if not generated_key:
                flash('Key de ativação inválida ou já utilizada.', 'danger')
                return redirect(url_for('auth.subscription_activation'))
            apply_activation_key_to_company(generated_key, company)
            db.session.commit()
            flash('Assinatura ativada com sucesso.', 'success')
            return redirect(url_for('main.dashboard'))
        if activation_key != expected_key:
            generated_key = available_activation_key(activation_key)
            if not generated_key:
                flash('Key de ativação inválida.', 'danger')
                return redirect(url_for('auth.subscription_activation'))
            apply_activation_key_to_company(generated_key, company)
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
    companies = Company.query.order_by(Company.id.asc()).all()
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

    companies = Company.query.order_by(Company.id.desc()).all()
    users = User.query.order_by(User.created_at.desc(), User.id.desc()).all()
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


@auth_bp.route('/master/assinaturas')
@login_required
def master_subscriptions():
    if not master_required():
        return redirect(url_for('main.dashboard'))

    companies = Company.query.order_by(Company.name.asc()).all()
    activation_keys = ActivationKey.query.filter(
        ActivationKey.active.is_(True)
    ).order_by(ActivationKey.created_at.desc(), ActivationKey.id.desc()).limit(80).all()

    return render_template(
        'master/companies.html',
        master_section='subscriptions',
        master_title='Assinaturas',
        master_description='Gere keys, renove planos e acompanhe os vencimentos.',
        companies=companies,
        activation_keys=activation_keys,
        activation_key_statuses={
            activation_key.id: activation_key_status(activation_key)
            for activation_key in activation_keys
        },
        subscription_plans=SUBSCRIPTION_PLANS,
        master_key_plans=MASTER_KEY_PLANS,
        billing_cycles=BILLING_CYCLES,
        key_presets=KEY_PRESETS,
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
    flash('Logs limpos com sucesso.', 'success')
    return redirect(url_for('auth.master_logs'))


@auth_bp.route('/master/assinaturas/keys/gerar', methods=['POST'])
@login_required
def generate_master_activation_key():
    if not master_required():
        return redirect(url_for('main.dashboard'))

    plan = request.form.get('plan', 'Basic').strip()
    if plan not in MASTER_KEY_PLANS:
        flash('Plano inválido para geração de key.', 'danger')
        return redirect(url_for('auth.master_subscriptions'))

    billing_cycle, renews_at = renewal_date_from_request()

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
            renews_at=renews_at,
            active=True,
        )
        db.session.add(activation_key)
        generated_keys.append(activation_key)

    db.session.commit()
    if len(generated_keys) == 1:
        flash(f'Key avulsa gerada: {generated_keys[0].key}', 'success')
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
    if not company:
        flash('Selecione uma adega para renovar a assinatura.', 'danger')
        return redirect(url_for('auth.master_subscriptions'))

    plan = request.form.get('plan', 'Basic').strip()
    if plan not in SUBSCRIPTION_PLANS:
        flash('Plano inválido para assinatura.', 'danger')
        return redirect(url_for('auth.master_subscriptions'))

    billing_cycle, renews_at = renewal_date_from_request(default_cycle=company.billing_cycle or 'monthly')
    if renews_at < date.today():
        flash('A data de renovação não pode estar no passado.', 'danger')
        return redirect(url_for('auth.master_subscriptions'))

    apply_subscription_to_company(company, plan, billing_cycle, renews_at)
    db.session.commit()
    flash(f'Assinatura da adega {company.name} renovada até {renews_at.strftime("%d/%m/%Y")}.', 'success')
    return redirect(url_for('auth.master_subscriptions'))


@auth_bp.route('/master/assinaturas/keys/<int:key_id>/cancelar', methods=['POST'])
@login_required
def cancel_master_activation_key(key_id):
    if not master_required():
        return redirect(url_for('main.dashboard'))

    activation_key = db.get_or_404(ActivationKey, key_id)
    if activation_key.used_by_company_id:
        flash('Não é possível remover uma key já usada por uma adega.', 'danger')
        return redirect(url_for('auth.master_subscriptions'))

    db.session.delete(activation_key)
    db.session.commit()
    flash('Key removida da lista com sucesso.', 'success')
    return redirect(url_for('auth.master_subscriptions'))


@auth_bp.route('/master/adegas/<int:company_id>/editar', methods=['POST'])
@login_required
def edit_company(company_id):
    if not master_required():
        return redirect(url_for('main.dashboard'))

    company = db.get_or_404(Company, company_id)
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

    db.session.commit()
    flash('Adega atualizada com sucesso.', 'success')
    return redirect(url_for('auth.master_companies', view=request.form.get('view_mode', 'table')))


@auth_bp.route('/master/adegas/<int:company_id>/acessar')
@login_required
def access_company(company_id):
    if not master_required():
        return redirect(url_for('main.dashboard'))

    company = db.get_or_404(Company, company_id)
    tenant_engine(company)
    session['master_company_id'] = company.id
    flash(f'Master conectado em {company.name}.', 'success')
    return redirect(url_for('main.dashboard'))


@auth_bp.route('/master/adegas/sair-acesso')
@login_required
def leave_company_access():
    if not master_required():
        return redirect(url_for('main.dashboard'))

    session.pop('master_company_id', None)
    flash('Você voltou para o painel master.', 'info')
    return redirect(url_for('auth.master_companies'))


@auth_bp.route('/master/adegas/<int:company_id>/alternar-status', methods=['POST'])
@login_required
def toggle_company_status(company_id):
    if not master_required():
        return redirect(url_for('main.dashboard'))

    company = db.get_or_404(Company, company_id)
    if company.id == current_user.company_id:
        flash('Não é possível inativar a adega do usuário master.', 'danger')
        return redirect(url_for('auth.master_companies'))

    company.active = not company.active
    db.session.commit()
    flash('Status da adega atualizado com sucesso.', 'success')
    return redirect(url_for('auth.master_companies'))


@auth_bp.route('/master/adegas/<int:company_id>/excluir', methods=['POST'])
@login_required
def delete_company(company_id):
    if not master_required():
        return redirect(url_for('main.dashboard'))

    company = db.get_or_404(Company, company_id)
    if company.id == current_user.company_id:
        flash('Não é possível excluir a adega do usuário master.', 'danger')
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

        if user_ids:
            db.session.execute(db.delete(EmailVerificationCode).where(EmailVerificationCode.user_id.in_(user_ids)))
            db.session.execute(db.delete(PasswordResetToken).where(PasswordResetToken.user_id.in_(user_ids)))
            db.session.execute(db.delete(EmailChangeRequest).where(EmailChangeRequest.user_id.in_(user_ids)))
        if sale_ids:
            db.session.execute(db.delete(Payment).where(Payment.sale_id.in_(sale_ids)))
            db.session.execute(db.delete(SaleItem).where(SaleItem.sale_id.in_(sale_ids)))
            db.session.execute(db.delete(Sale).where(Sale.id.in_(sale_ids)))
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
            if password_too_short(new_password):
                flash(f'A nova senha deve ter pelo menos {password_min_length()} caracteres.', 'danger')
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
            if password_too_short(password):
                flash(f'A senha inicial deve ter pelo menos {password_min_length()} caracteres.', 'danger')
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
