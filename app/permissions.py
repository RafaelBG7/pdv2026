from functools import wraps

from flask import flash, redirect, url_for
from flask_login import current_user


PERMISSION_LABELS = {
    'can_view_products': 'Ver produtos',
    'can_manage_products': 'Gerenciar produtos',
    'can_manage_categories': 'Categorias',
    'can_manage_sales': 'Vendas',
    'can_manage_cash_register': 'Caixa',
    'can_view_reports': 'Relatórios',
    'can_manage_payables': 'Contas a pagar',
    'can_manage_settings': 'Configurações',
}


def permission_required(permission):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if current_user.role == 'master':
                return view(*args, **kwargs)
            if current_user.has_permission(permission):
                return view(*args, **kwargs)

            flash(f'Seu usuário não tem permissão para acessar {PERMISSION_LABELS.get(permission, "esta área")}.', 'danger')
            return redirect(url_for('main.dashboard'))

        return wrapped

    return decorator
