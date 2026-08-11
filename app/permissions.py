from functools import wraps

from flask import flash, g, redirect, request, session, url_for
from flask_login import current_user


PERMISSION_LABELS = {
    'can_view_products': 'Ver produtos',
    'can_manage_products': 'Gerenciar produtos',
    'can_manage_categories': 'Categorias',
    'can_manage_sales': 'Vendas',
    'can_cancel_sales': 'Cancelar vendas',
    'can_manage_cash_register': 'Caixa',
    'can_view_reports': 'Relatórios',
    'can_manage_payables': 'Contas a pagar',
    'can_manage_settings': 'Configurações',
    'can_view_finance': 'Financeiro',
    'can_export_data': 'Exportação',
    'can_view_stock_movements': 'Ver movimentações de estoque',
    'can_manage_stock': 'Gerenciar estoque',
    'can_view_audit_logs': 'Auditoria',
}

def user_can_override_permission(user, permission):
    if not user or not user.is_active:
        return False
    if user.role == 'master':
        return True
    if current_user.is_authenticated and user.company_id != current_user.company_id:
        return False
    if permission in ('can_view_finance', 'can_export_data'):
        return user.role == 'admin'
    return user.has_permission(permission)


def authorize_permission_override(permission):
    username = (request.form.get('_permission_override_username') or '').strip()
    password = request.form.get('_permission_override_password') or ''
    if not username or not password:
        return False

    from app.models import User

    authorizer = User.query.filter_by(username=username).first()
    if not authorizer or not authorizer.check_password(password):
        return False
    return user_can_override_permission(authorizer, permission)


def authorize_role_override(*roles):
    username = (request.form.get('_permission_override_username') or '').strip()
    password = request.form.get('_permission_override_password') or ''
    if not username or not password:
        return False

    from app.models import User

    authorizer = User.query.filter_by(username=username).first()
    if not authorizer or not authorizer.is_active or not authorizer.check_password(password):
        return False
    if authorizer.role == 'master':
        return True
    if current_user.is_authenticated and authorizer.company_id != current_user.company_id:
        return False
    return authorizer.role in roles


def needs_permission_override(permission):
    if not current_user.is_authenticated:
        return False
    if current_user.role == 'master':
        return False
    return not current_user.has_permission(permission)


def permission_view_overrides():
    return set(session.get('permission_view_overrides', []))


def has_permission_view_override(permission):
    return permission in permission_view_overrides()


def grant_permission_view_override(permission):
    overrides = permission_view_overrides()
    overrides.add(permission)
    session['permission_view_overrides'] = sorted(overrides)
    session.modified = True


def permission_required(permission):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            g.required_permission = permission
            g.needs_permission_override = needs_permission_override(permission)

            if current_user.role == 'master':
                return view(*args, **kwargs)
            if current_user.has_permission(permission):
                return view(*args, **kwargs)
            if request.method in ('GET', 'HEAD', 'OPTIONS') and has_permission_view_override(permission):
                return view(*args, **kwargs)
            if request.method in ('GET', 'HEAD', 'OPTIONS'):
                return redirect(url_for(
                    'auth.permission_unlock',
                    permission=permission,
                    next=request.full_path if request.query_string else request.path,
                ))
            if authorize_permission_override(permission):
                g.permission_override_authorized = True
                return view(*args, **kwargs)

            flash(
                f'Informe a senha de um usuário autorizado para realizar: {PERMISSION_LABELS.get(permission, "esta ação")}.',
                'danger',
            )
            return redirect(request.referrer or url_for('main.dashboard'))

        return wrapped

    return decorator
