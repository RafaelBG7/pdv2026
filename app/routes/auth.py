from datetime import date, datetime, timedelta, timezone
import secrets
import string

from flask import Blueprint, redirect, render_template, request, session, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import CashRegister, Company, Product, Sale, User
from app.permissions import PERMISSION_LABELS
from app.tenant import current_tenant_company, drop_mysql_database, tenant_database_identifier, tenant_engine


auth_bp = Blueprint('auth', __name__)
SUBSCRIPTION_PLANS = ('Essencial', 'Profissional', 'Premium')
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


def generate_activation_key():
    alphabet = string.ascii_uppercase + string.digits
    groups = [
        ''.join(secrets.choice(alphabet) for _ in range(4))
        for _ in range(4)
    ]
    return '-'.join(groups)


def can_manage_company_users():
    return current_user.role in ('admin', 'master') or current_user.has_permission('can_manage_settings')


def can_view_admin_settings():
    return current_user.role in ('admin', 'master') or current_user.has_permission('can_manage_settings')


def apply_employee_permissions(user, form):
    if user.role == 'admin':
        for permission in EMPLOYEE_PERMISSIONS:
            setattr(user, permission, True)
        return

    for permission in EMPLOYEE_PERMISSIONS:
        setattr(user, permission, form.get(permission) == 'on')
    if user.can_manage_products:
        user.can_view_products = True


def subscription_status(company):
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
    if not company:
        return True
    if not company.active:
        return True
    if not company.subscription_renews_at:
        return True
    return company.subscription_renews_at < date.today()


def current_basic_pro_plan(company):
    if not company:
        return None
    if company.subscription_plan in ('Pro', 'Premium', 'Profissional'):
        return 'Pro'
    return 'Basic'


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'master':
            return redirect(url_for('auth.master_companies'))
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        form_type = request.form.get('form_type', 'login')
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if form_type == 'register':
            email = request.form.get('email', '').strip()
            company_name = request.form.get('company_name', '').strip() or username
            confirm_password = request.form.get('confirm_password', '')

            if not username:
                flash('Informe o usuário para cadastro.', 'danger')
                return render_template('login.html', auth_tab='register')
            if len(password) < 3:
                flash('A senha deve ter pelo menos 3 caracteres.', 'danger')
                return render_template('login.html', auth_tab='register')
            if password != confirm_password:
                flash('A confirmação da senha não confere.', 'danger')
                return render_template('login.html', auth_tab='register')
            if User.query.filter_by(username=username).first():
                flash('Já existe um usuário com este login.', 'danger')
                return render_template('login.html', auth_tab='register')

            company = Company(name=company_name)
            company.activation_key = generate_activation_key()
            company.activation_key_updated_at = datetime.now(timezone.utc)
            db.session.add(company)
            db.session.flush()
            tenant_database_identifier(company)
            user = User(username=username, email=email, role='admin', company_id=company.id, is_active=True)
            user.set_password(password)
            db.session.add(user)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash('Já existe um usuário com este login.', 'danger')
                return render_template('login.html', auth_tab='register')

            login_user(user)
            flash('Cadastro realizado com sucesso.', 'success')
            return redirect(url_for('main.dashboard'))

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            if not user.is_active:
                flash('Este usuário está inativo. Fale com o master da adega.', 'danger')
                return render_template('login.html', auth_tab='login')
            if user.role != 'master' and user.company and not user.company.active:
                flash('Esta adega está inativa. Fale com o usuário master.', 'danger')
                return render_template('login.html', auth_tab='login')
            login_user(user)
            flash('Login realizado com sucesso.', 'success')
            if user.role == 'master':
                return redirect(url_for('auth.master_companies'))
            if company_requires_activation(user.company):
                flash('A assinatura desta adega venceu. Ative com a key para continuar.', 'warning')
                return redirect(url_for('auth.subscription_activation'))
            return redirect(url_for('main.dashboard'))

        flash('Usuário ou senha inválidos.', 'danger')

    return render_template('login.html', auth_tab='login')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/assinatura', methods=['GET', 'POST'])
@login_required
def subscription_activation():
    if current_user.role == 'master':
        return redirect(url_for('auth.master_companies'))

    company = current_user.company
    status = subscription_status(company) if company else {}

    if request.method == 'POST':
        activation_key = request.form.get('activation_key', '').strip().upper()
        expected_key = (company.activation_key or '').strip().upper() if company else ''

        if not expected_key:
            flash('Esta adega ainda não possui key de ativação. Fale com o suporte.', 'danger')
            return redirect(url_for('auth.subscription_activation'))
        if activation_key != expected_key:
            flash('Key de ativação inválida.', 'danger')
            return redirect(url_for('auth.subscription_activation'))
        if company_requires_activation(company):
            flash('Key correta, mas a assinatura ainda está vencida. Solicite a renovação ao suporte.', 'danger')
            return redirect(url_for('auth.subscription_activation'))

        flash('Assinatura ativada com sucesso.', 'success')
        return redirect(url_for('main.dashboard'))

    return render_template('subscription/activation.html', company=company, subscription=status)


@auth_bp.route('/assinaturas')
@login_required
def subscriptions():
    if not can_view_admin_settings():
        flash('Seu usuário não tem permissão para ver o plano da adega.', 'danger')
        return redirect(url_for('main.dashboard'))

    company = current_tenant_company()
    if current_user.role == 'master' and not company:
        return redirect(url_for('auth.master_companies'))

    return render_template(
        'subscription/plans.html',
        company=company,
        subscription=subscription_status(company) if company else {},
        plans=BASIC_PRO_PLANS,
        current_plan=current_basic_pro_plan(company),
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
        tenant_db = sessionmaker(bind=tenant_engine(company))()
        try:
            company_stats[company.id] = {
                'products': tenant_db.query(Product).count(),
                'sales': tenant_db.query(Sale).count(),
                'cash_registers': tenant_db.query(CashRegister).count(),
            }
        finally:
            tenant_db.close()

    return render_template(
        'master/companies.html',
        companies=companies,
        user_counts=user_counts,
        company_stats=company_stats,
        subscription_statuses=subscription_statuses,
        subscription_plans=SUBSCRIPTION_PLANS,
        billing_cycles=BILLING_CYCLES,
        view_mode=view_mode,
        active_master_company_id=session.get('master_company_id'),
    )


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
    if request.form.get('generate_activation_key') == 'on' or not activation_key:
        activation_key = generate_activation_key()
    if activation_key != (company.activation_key or ''):
        company.activation_key = activation_key
        company.activation_key_updated_at = datetime.now(timezone.utc)

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
    User.query.filter_by(company_id=company.id).delete()
    db.session.delete(company)
    db.session.commit()

    if database_name:
        drop_mysql_database(database_name)

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
            current_user.email = request.form.get('email', '').strip()
            db.session.commit()
            flash('Email atualizado com sucesso.', 'success')
            return redirect(url_for('auth.settings'))

        if form_type == 'password':
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')

            if not current_user.check_password(current_password):
                flash('Senha atual incorreta.', 'danger')
                return redirect(url_for('auth.settings'))
            if len(new_password) < 3:
                flash('A nova senha deve ter pelo menos 3 caracteres.', 'danger')
                return redirect(url_for('auth.settings'))
            if new_password != confirm_password:
                flash('A confirmação da senha não confere.', 'danger')
                return redirect(url_for('auth.settings'))

            current_user.set_password(new_password)
            db.session.commit()
            flash('Senha alterada com sucesso.', 'success')
            return redirect(url_for('auth.settings'))

        if form_type == 'card_fees':
            if not can_view_admin_settings():
                flash('Apenas o usuário master pode alterar as taxas da maquininha.', 'danger')
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

        if form_type == 'hire_user':
            if not can_manage_company_users():
                flash('Apenas o usuário master pode contratar usuários.', 'danger')
                return redirect(url_for('auth.settings'))

            username = request.form.get('hire_username', '').strip()
            email = request.form.get('hire_email', '').strip()
            password = request.form.get('hire_password', '')
            role = request.form.get('hire_role', 'operator')

            if not username:
                flash('Informe o login do novo usuário.', 'danger')
                return redirect(url_for('auth.settings'))
            if len(password) < 3:
                flash('A senha inicial deve ter pelo menos 3 caracteres.', 'danger')
                return redirect(url_for('auth.settings'))
            if User.query.filter_by(username=username).first():
                flash('Já existe um usuário com este login.', 'danger')
                return redirect(url_for('auth.settings'))
            if role == 'admin' and User.query.filter_by(company_id=settings_company.id, role='admin').first():
                flash('Esta adega já possui um master da adega.', 'danger')
                return redirect(url_for('auth.settings'))

            user = User(
                username=username,
                email=email,
                role='admin' if role == 'admin' else 'operator',
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
            if not can_manage_company_users():
                flash('Apenas o usuário master pode alterar funcionários.', 'danger')
                return redirect(url_for('auth.settings'))

            employee_id = request.form.get('employee_id')
            employee = User.query.filter_by(id=employee_id, company_id=settings_company.id).first()
            if not employee:
                flash('Funcionário não encontrado.', 'danger')
                return redirect(url_for('auth.settings'))
            if employee.id == current_user.id and employee.role == 'admin' and request.form.get('is_active') != 'on':
                flash('Você não pode inativar o próprio master da adega.', 'danger')
                return redirect(url_for('auth.settings'))

            employee.is_active = request.form.get('is_active') == 'on'
            apply_employee_permissions(employee, request.form)
            db.session.commit()
            flash('Permissões do funcionário atualizadas.', 'success')
            return redirect(url_for('auth.settings'))

    can_view_admin_tabs = can_view_admin_settings()
    company_users = User.query.filter_by(company_id=settings_company.id).order_by(User.username.asc()).all() if settings_company and can_view_admin_tabs else []
    return render_template(
        'settings/index.html',
        company_users=company_users,
        settings_company=settings_company,
        employee_permissions=EMPLOYEE_PERMISSIONS,
        permission_labels=PERMISSION_LABELS,
        can_manage_employees=can_manage_company_users(),
        can_view_admin_tabs=can_view_admin_tabs,
    )
