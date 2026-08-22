from contextlib import contextmanager
import csv
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import wraps
import io
import re
import zipfile
from xml.etree import ElementTree

from flask import Blueprint, Response, current_app, g, jsonify, request
from sqlalchemy import and_, func, or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload, sessionmaker

from app.extensions import db, limiter
from app.money import money_json, parse_money_decimal
from app.backup import BACKUP_FREQUENCIES, create_company_backup
from app.models import (
    ActivationKey,
    ApiRefreshToken,
    AuditLog,
    CashRegister,
    Category,
    Company,
    EmailAlertSetting,
    NotificationPreference,
    Payable,
    Payment,
    Product,
    Sale,
    SaleItem,
    StockMovement,
    User,
)
from app.services.alert_service import EMAIL_ALERT_TYPES, parse_recipients
from app.services.api_auth_service import (
    ApiAuthError,
    authenticate_access_token,
    authenticate_credentials,
    authenticate_credentials_for_activation,
    issue_token_pair,
    require_secure_auth_transport,
    revoke_session,
    rotate_refresh_token,
    user_identity_data,
)
from app.services.audit_service import audit_action_label, changed_values, entity_label, record_audit_event
from app.services.cash_register_service import (
    CashRegisterOperationError,
    build_cash_register_snapshot,
    close_cash_register,
    money_decimal,
    money_value,
    open_cash_register,
    timestamp_value,
)
from app.services.category_service import (
    CategoryInput,
    CategoryOperationError,
    category_product_count,
    create_category,
    delete_category,
    update_category,
)
from app.services.dashboard_service import build_dashboard_snapshot
from app.services.product_service import (
    ProductInput,
    ProductOperationError,
    create_product,
    delete_product,
    normalize_product_barcode,
    update_product,
)
from app.services.password_recovery_service import request_password_recovery
from app.security.rate_limit import (
    authenticated_identity_key,
    api_identity_key,
    configured_limit,
    login_identity_key,
    token_identity_key,
    redis_health_status,
)
from app.services.notification_service import (
    CATEGORIES as NOTIFICATION_CATEGORIES,
    SEVERITIES as NOTIFICATION_SEVERITIES,
    dismiss_notification,
    find_visible_notification,
    get_unread_count,
    get_user_notifications,
    mark_all_as_read,
    mark_as_read,
    preference_for,
    sync_operational_notifications,
)
from app.time_utils import (
    business_date_range_utc,
    business_today,
    to_business_datetime,
    utc_isoformat,
)
from app.services.sale_service import (
    PAYMENT_METHODS,
    SaleLineInput,
    SaleOperationError,
    SalePaymentInput,
    cancel_sale,
    create_sale,
    find_completed_sale_request,
    serialize_sale_result,
)
from app.services.stock_service import (
    MOVEMENT_TYPE_LABELS,
    SOURCE_TYPE_LABELS,
    StockMovementError,
    adjust_stock,
    increase_stock,
    register_stock_movement,
    stock_movement_label,
    stock_source_label,
)
from app.tenant import tenant_engine


api_v1_bp = Blueprint('api_v1', __name__, url_prefix='/api/v1')
limiter.limit(
    configured_limit('RATELIMIT_API_GENERAL', '600 per minute'),
    key_func=api_identity_key,
)(api_v1_bp)
IDEMPOTENCY_KEY_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$')
PAYABLE_CATEGORIES = ('Aluguel', 'Luz', 'Água', 'Internet', 'Fornecedor', 'Impostos', 'Outros')
PAYABLE_STATUS_LABELS = {
    'open': 'Aberta',
    'paid': 'Paga',
    'overdue': 'Vencida',
    'due_today': 'Vence hoje',
    'near_due': 'Próxima',
}
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
EMPLOYEE_PERMISSION_LABELS = {
    'can_view_products': 'Ver produtos',
    'can_manage_products': 'Gerenciar produtos',
    'can_manage_categories': 'Gerenciar categorias',
    'can_manage_sales': 'Realizar vendas',
    'can_cancel_sales': 'Cancelar vendas',
    'can_manage_cash_register': 'Abrir e fechar caixa',
    'can_view_reports': 'Ver relatórios',
    'can_manage_payables': 'Contas a pagar',
    'can_manage_settings': 'Configurações e equipe',
    'can_view_stock_movements': 'Ver estoque',
    'can_manage_stock': 'Movimentar estoque',
    'can_view_audit_logs': 'Ver auditoria',
}
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
EMAIL_PATTERN = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def api_success(data, status_code=200):
    response = jsonify({
        'success': True,
        'data': data,
        'message': None,
        'errors': [],
    })
    response.status_code = status_code
    response.headers['Cache-Control'] = 'no-store'
    return response


def api_failure(message, code, status_code, field=None):
    response = jsonify({
        'success': False,
        'data': None,
        'message': message,
        'errors': [{
            'field': field,
            'code': code,
            'message': message,
        }],
    })
    response.status_code = status_code
    response.headers['Cache-Control'] = 'no-store'
    return response


def api_auth_error_response(error):
    return api_failure(
        error.message,
        error.code,
        error.status_code,
        error.field,
    )


def available_activation_key(value):
    key = (value or '').strip().upper()
    if not key:
        return None
    activation_key = ActivationKey.query.filter_by(
        key=key,
        active=True,
        used_by_company_id=None,
    ).first()
    if not activation_key:
        return None
    if activation_key.renews_at and activation_key.renews_at < date.today():
        return None
    return activation_key


def apply_activation_key_to_company(activation_key, company):
    today = date.today()
    company.activation_key = activation_key.key
    company.activation_key_updated_at = datetime.now(timezone.utc)
    company.subscription_plan = activation_key.plan
    company.subscription_started_at = today
    company.subscription_renews_at = activation_key.renews_at
    company.billing_cycle = 'annual' if (activation_key.renews_at - today).days >= 365 else 'monthly'
    company.active = True
    activation_key.used_by_company_id = company.id
    activation_key.used_at = datetime.now(timezone.utc)


def json_object_body():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ApiAuthError(
            'Envie um objeto JSON válido.',
            'invalid_json',
            400,
        )
    return payload


def bearer_access_token():
    authorization = request.headers.get('Authorization', '')
    scheme, _, token = authorization.partition(' ')
    if scheme.casefold() != 'bearer' or not token.strip():
        raise ApiAuthError(
            'Informe um token Bearer para acessar este recurso.',
            'missing_access_token',
            401,
        )
    return token.strip()


def api_auth_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        try:
            require_secure_auth_transport()
            authenticated = authenticate_access_token(bearer_access_token())
        except ApiAuthError as error:
            return api_auth_error_response(error)
        g.api_user = authenticated.user
        g.api_session = authenticated.session
        return view(*args, **kwargs)

    return wrapped


def api_permission_required(permission):
    def decorator(view):
        @wraps(view)
        @api_auth_required
        def wrapped(*args, **kwargs):
            if not g.api_user.has_permission(permission):
                return api_failure(
                    'Você não tem permissão para acessar esta informação.',
                    'permission_denied',
                    403,
                )
            return view(*args, **kwargs)

        return wrapped

    return decorator


@contextmanager
def api_tenant_database(user):
    company = user.company
    if company is None:
        raise ApiAuthError(
            'Selecione uma adega antes de acessar o catálogo.',
            'company_context_required',
            409,
        )

    if current_app.testing:
        yield db.session
        return

    tenant_db = sessionmaker(bind=tenant_engine(company))()
    try:
        yield tenant_db
    finally:
        tenant_db.close()


def positive_integer_argument(name, default, maximum=None):
    raw_value = (request.args.get(name) or '').strip()
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError as error:
        raise ApiAuthError(
            f'O parâmetro {name} precisa ser um número inteiro.',
            'invalid_query_parameter',
            422,
            name,
        ) from error
    if value < 1:
        raise ApiAuthError(
            f'O parâmetro {name} precisa ser maior que zero.',
            'invalid_query_parameter',
            422,
            name,
        )
    return min(value, maximum) if maximum else value


def json_positive_integer(payload, name):
    raw_value = payload.get(name)
    if isinstance(raw_value, bool):
        raw_value = None
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as error:
        raise ApiAuthError(
            f'O campo {name} precisa ser um número inteiro maior que zero.',
            'invalid_integer',
            422,
            name,
        ) from error
    if value < 1:
        raise ApiAuthError(
            f'O campo {name} precisa ser maior que zero.',
            'invalid_integer',
            422,
            name,
        )
    return value


def json_money(payload, name):
    raw_value = payload.get(name)
    if isinstance(raw_value, bool) or raw_value is None:
        raise ApiAuthError(
            f'Informe o campo {name}.',
            'money_required',
            422,
            name,
        )

    text = str(raw_value).strip()
    if not text:
        raise ApiAuthError(
            f'Informe o campo {name}.',
            'money_required',
            422,
            name,
        )
    if ',' in text:
        text = text.replace('.', '').replace(',', '.')
    try:
        value = Decimal(text)
    except InvalidOperation as error:
        raise ApiAuthError(
            f'O campo {name} precisa ser um valor monetário válido.',
            'invalid_money',
            422,
            name,
        ) from error
    if not value.is_finite() or value < 0 or value > Decimal('999999999.99'):
        raise ApiAuthError(
            f'O campo {name} está fora do intervalo permitido.',
            'invalid_money',
            422,
            name,
        )
    return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def json_optional_money(payload, name, default='0.00'):
    if name not in payload or payload.get(name) in {None, ''}:
        return Decimal(default).quantize(Decimal('0.01'))
    return json_money(payload, name)


def optional_money_argument(name):
    raw_value = request.args.get(name)
    if raw_value is None or not raw_value.strip():
        return None
    text = raw_value.strip()
    if ',' in text:
        text = text.replace('.', '').replace(',', '.')
    try:
        value = Decimal(text)
    except InvalidOperation as error:
        raise ApiAuthError(
            f'O parâmetro {name} precisa ser um valor monetário válido.',
            'invalid_query_parameter',
            422,
            name,
        ) from error
    if not value.is_finite() or value < 0 or value > Decimal('999999999.99'):
        raise ApiAuthError(
            f'O parâmetro {name} está fora do intervalo permitido.',
            'invalid_query_parameter',
            422,
            name,
        )
    return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def json_text(payload, name, required=False, max_length=255):
    raw_value = payload.get(name)
    if raw_value is None:
        text = ''
    elif isinstance(raw_value, str):
        text = raw_value.strip()
    else:
        text = str(raw_value).strip()

    if required and not text:
        raise ApiAuthError(
            f'Informe o campo {name}.',
            'text_required',
            422,
            name,
        )
    if len(text) > max_length:
        raise ApiAuthError(
            f'O campo {name} excede o tamanho permitido.',
            'text_too_long',
            422,
            name,
        )
    return text


def json_optional_positive_integer(payload, name):
    raw_value = payload.get(name)
    if raw_value in {None, '', 0, '0'}:
        return None
    return json_positive_integer(payload, name)


def json_non_negative_integer(payload, name, default=0, maximum=100000000):
    raw_value = payload.get(name, default)
    if raw_value in {None, ''}:
        raw_value = default
    if isinstance(raw_value, bool):
        raw_value = None
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as error:
        raise ApiAuthError(
            f'O campo {name} precisa ser um número inteiro.',
            'invalid_integer',
            422,
            name,
        ) from error
    if value < 0 or value > maximum:
        raise ApiAuthError(
            f'O campo {name} está fora do intervalo permitido.',
            'invalid_integer',
            422,
            name,
        )
    return value


def json_integer(payload, name, default=0, minimum=-100000000, maximum=100000000):
    raw_value = payload.get(name, default)
    if raw_value in {None, ''}:
        raw_value = default
    if isinstance(raw_value, bool):
        raw_value = None
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as error:
        raise ApiAuthError(
            f'O campo {name} precisa ser um número inteiro.',
            'invalid_integer',
            422,
            name,
        ) from error
    if value < minimum or value > maximum:
        raise ApiAuthError(
            f'O campo {name} está fora do intervalo permitido.',
            'invalid_integer',
            422,
            name,
        )
    return value


def parse_report_date_argument(name):
    raw_value = (request.args.get(name) or '').strip()
    if not raw_value:
        return None
    try:
        return date.fromisoformat(raw_value)
    except ValueError as error:
        raise ApiAuthError(
            f'O parâmetro {name} precisa estar no formato AAAA-MM-DD.',
            'invalid_query_parameter',
            422,
            name,
        ) from error


def parse_optional_query_date_argument(name):
    raw_value = (request.args.get(name) or '').strip()
    if not raw_value:
        return None
    try:
        return date.fromisoformat(raw_value)
    except ValueError as error:
        raise ApiAuthError(
            f'O parâmetro {name} precisa estar no formato AAAA-MM-DD.',
            'invalid_query_parameter',
            422,
            name,
        ) from error


def json_required_date(payload, name):
    raw_value = json_text(payload, name, required=True, max_length=20)
    try:
        return date.fromisoformat(raw_value)
    except ValueError as error:
        raise ApiAuthError(
            f'O campo {name} precisa estar no formato AAAA-MM-DD.',
            'invalid_date',
            422,
            name,
        ) from error


def api_report_period_range(period, start_date=None, end_date=None):
    today = business_today()
    if period == 'weekly':
        end = end_date or today
        start = start_date or (end - timedelta(days=7))
        label = f'Últimos 7 dias: {start.strftime("%d/%m/%Y")} a {end.strftime("%d/%m/%Y")}'
    elif period == 'monthly':
        end = end_date or today
        start = start_date or (end - timedelta(days=30))
        label = f'Últimos 30 dias: {start.strftime("%d/%m/%Y")} a {end.strftime("%d/%m/%Y")}'
    elif period == 'annual':
        end = end_date or today
        start = start_date or (end - timedelta(days=365))
        label = f'Último ano: {start.strftime("%d/%m/%Y")} a {end.strftime("%d/%m/%Y")}'
    elif period == 'custom':
        start = start_date or today
        end = end_date or start
        if end < start:
            start, end = end, start
        label = f'{start.strftime("%d/%m/%Y")} a {end.strftime("%d/%m/%Y")}'
    else:
        period = 'daily'
        start = start_date or today
        end = start
        label = start.strftime('%d/%m/%Y')

    start_datetime, end_datetime = business_date_range_utc(start, end)
    return period, start, end, start_datetime, end_datetime, label


def api_sale_item_profit(item):
    if item.profit_amount is not None:
        return item.profit_amount or 0.0
    return ((item.unit_price or 0.0) - (item.unit_cost_price or 0.0)) * (item.quantity or 0)


def api_serialize_sale_receipt(sale):
    paid_amount = sum(
        (money_decimal(payment.amount) for payment in sale.payments),
        Decimal('0.00'),
    )
    final_amount = money_decimal(sale.final_amount)
    change_amount = max(paid_amount - final_amount, Decimal('0.00'))

    return {
        'id': sale.id,
        'idempotency_key': '',
        'already_processed': False,
        'created_at': timestamp_value(sale.created_at),
        'cash_register_id': sale.cash_register_id or 0,
        'payment_status': sale.payment_status or 'pending',
        'status': sale.status or 'completed',
        'is_cancelled': sale.is_cancelled,
        'cancelled_at': timestamp_value(sale.cancelled_at),
        'cancelled_by_user_id': sale.cancelled_by_user_id,
        'cancelled_by_user_name': (
            sale.cancelled_by_user.full_name or sale.cancelled_by_user.username
            if sale.cancelled_by_user else ''
        ),
        'cancellation_reason': sale.cancellation_reason or '',
        'subtotal': money_value(sale.total_amount),
        'discount_amount': money_value(sale.discount_amount),
        'final_amount': money_value(final_amount),
        'paid_amount': money_value(paid_amount),
        'change_amount': money_value(change_amount),
        'stock_warnings': [],
        'items': [
            {
                'product_id': item.product_id,
                'name': item.product.name if item.product else f'Produto #{item.product_id}',
                'quantity': item.quantity or 0,
                'unit_price': money_value(item.unit_price),
                'subtotal': money_value(item.total_price),
                'profit_amount': money_value(api_sale_item_profit(item)),
            }
            for item in sale.items
        ],
        'payments': [
            {
                'method': payment.method,
                'label': PAYMENT_METHODS.get(payment.method, payment.method or 'Pagamento'),
                'amount': money_value(payment.amount),
            }
            for payment in sale.payments
        ],
    }


def api_build_sales_report(sales):
    sales = [sale for sale in sales if not sale.is_cancelled]
    payment_totals = {method: 0.0 for method in PAYMENT_METHODS}
    product_totals = {}
    totals = {
        'sales_count': len(sales),
        'items_count': 0,
        'subtotal': 0.0,
        'discount': 0.0,
        'final': 0.0,
        'profit': 0.0,
        'average_ticket': 0.0,
    }

    for sale in sales:
        totals['subtotal'] += sale.total_amount or 0.0
        totals['discount'] += sale.discount_amount or 0.0
        totals['final'] += sale.final_amount or 0.0
        for item in sale.items:
            quantity = item.quantity or 0
            profit = api_sale_item_profit(item)
            product_name = item.product.name if item.product else 'Produto removido'
            product_id = item.product_id or 0
            totals['items_count'] += quantity
            totals['profit'] += profit
            product_data = product_totals.setdefault(product_id, {
                'product_id': product_id,
                'name': product_name,
                'quantity': 0,
                'total': 0.0,
                'profit': 0.0,
            })
            product_data['quantity'] += quantity
            product_data['total'] += item.total_price or 0.0
            product_data['profit'] += profit
        for payment in sale.payments:
            payment_totals[payment.method] = payment_totals.get(payment.method, 0.0) + (payment.amount or 0.0)

    if totals['sales_count']:
        totals['average_ticket'] = totals['final'] / totals['sales_count']

    top_products = sorted(
        product_totals.values(),
        key=lambda item: (item['total'], item['quantity'], item['name'].casefold()),
        reverse=True,
    )[:10]

    return {
        'summary': {
            key: round(value, 2) if isinstance(value, float) else value
            for key, value in totals.items()
        },
        'payment_totals': [
            {
                'method': method,
                'label': PAYMENT_METHODS.get(method, method),
                'amount': round(payment_totals.get(method, 0.0), 2),
            }
            for method in PAYMENT_METHODS
        ],
        'top_products': [
            {
                **product,
                'total': round(product['total'], 2),
                'profit': round(product['profit'], 2),
            }
            for product in top_products
        ],
    }


def api_product_report_sort_options():
    return [
        {'value': 'quantity_desc', 'label': 'Mais vendidos'},
        {'value': 'revenue_desc', 'label': 'Maior faturamento'},
        {'value': 'profit_desc', 'label': 'Maior lucro'},
        {'value': 'stock_asc', 'label': 'Menor estoque'},
        {'value': 'no_sales', 'label': 'Produtos sem venda'},
    ]


def api_build_product_report(
    tenant_db,
    company_id,
    start_datetime,
    end_datetime,
    search='',
    category_id=0,
    product_id=0,
    sort='quantity_desc',
    page=1,
    per_page=25,
):
    sale_item_totals = (
        tenant_db.query(
            SaleItem.product_id.label('product_id'),
            func.coalesce(func.sum(SaleItem.quantity), 0).label('quantity'),
            func.coalesce(func.sum(SaleItem.total_price), 0).label('revenue'),
            func.coalesce(func.sum(SaleItem.unit_cost_price * SaleItem.quantity), 0).label('cost'),
            func.coalesce(func.sum(SaleItem.profit_amount), 0).label('profit'),
        )
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(
            Sale.company_id == company_id,
            Sale.valid_filter(),
            Sale.created_at >= start_datetime,
            Sale.created_at < end_datetime,
        )
        .group_by(SaleItem.product_id)
        .subquery()
    )

    query = (
        tenant_db.query(
            Product,
            sale_item_totals.c.quantity,
            sale_item_totals.c.revenue,
            sale_item_totals.c.cost,
            sale_item_totals.c.profit,
        )
        .outerjoin(sale_item_totals, sale_item_totals.c.product_id == Product.id)
        .options(selectinload(Product.category))
        .filter(Product.company_id == company_id)
    )

    if search:
        pattern = f'%{search}%'
        query = query.filter(or_(
            Product.name.ilike(pattern),
            Product.barcode.ilike(pattern),
        ))
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if product_id:
        query = query.filter(Product.id == product_id)

    rows = []
    for product, quantity, revenue, cost, profit in query.all():
        quantity = int(quantity or 0)
        revenue = round(float(revenue or 0), 2)
        cost = round(float(cost or 0), 2)
        profit = round(float(profit or 0), 2)
        rows.append({
            'product_id': product.id,
            'product_name': product.name,
            'barcode': product.barcode or '',
            'category_id': product.category_id,
            'category_name': product.category.name if product.category else '-',
            'quantity': quantity,
            'revenue': revenue,
            'cost': cost,
            'profit': profit,
            'average_ticket': round(revenue / quantity, 2) if quantity else 0.0,
            'stock': product.effective_stock_quantity or 0,
            'active': bool(product.active),
        })

    if sort == 'revenue_desc':
        rows.sort(key=lambda item: (item['revenue'], item['quantity'], item['product_name'].casefold()), reverse=True)
    elif sort == 'profit_desc':
        rows.sort(key=lambda item: (item['profit'], item['revenue'], item['product_name'].casefold()), reverse=True)
    elif sort == 'stock_asc':
        rows.sort(key=lambda item: (item['stock'], item['product_name'].casefold()))
    elif sort == 'no_sales':
        rows = [item for item in rows if item['quantity'] == 0]
        rows.sort(key=lambda item: item['product_name'].casefold())
    else:
        sort = 'quantity_desc'
        rows.sort(key=lambda item: (item['quantity'], item['revenue'], item['product_name'].casefold()), reverse=True)

    totals = {
        'products': len(rows),
        'quantity': sum(item['quantity'] for item in rows),
        'revenue': round(sum(item['revenue'] for item in rows), 2),
        'cost': round(sum(item['cost'] for item in rows), 2),
        'profit': round(sum(item['profit'] for item in rows), 2),
    }
    if totals['quantity']:
        totals['average_ticket'] = round(totals['revenue'] / totals['quantity'], 2)
    else:
        totals['average_ticket'] = 0.0

    total_items = len(rows)
    total_pages = max(1, (total_items + per_page - 1) // per_page)
    page = min(page, total_pages)
    offset = (page - 1) * per_page
    return {
        'items': rows[offset:offset + per_page],
        'summary': totals,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total_items,
            'pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1,
        },
        'sort': sort,
        'sort_options': api_product_report_sort_options(),
    }


def api_build_sales_chart(period, start, end, sales, metric='revenue'):
    metric = metric if metric in {'revenue', 'quantity'} else 'revenue'
    buckets = []
    if period == 'daily':
        for hour in range(24):
            buckets.append({
                'key': f'{hour:02d}',
                'label': f'{hour:02d}h',
                'title': f'{hour:02d}:00 às {hour:02d}:59',
                'sales_count': 0,
                'total': 0.0,
            })
        bucket_index = {int(bucket['key']): bucket for bucket in buckets}
        for sale in sales:
            if sale.created_at:
                local_created_at = to_business_datetime(sale.created_at)
                bucket = bucket_index.get(local_created_at.hour)
                if bucket is not None:
                    bucket['sales_count'] += 1
                    bucket['total'] += sale.final_amount or 0.0
    elif period == 'annual':
        current = start.replace(day=1)
        end_month = end.replace(day=1)
        while current <= end_month:
            buckets.append({
                'key': f'{current.year}-{current.month:02d}',
                'label': current.strftime('%m/%Y'),
                'title': current.strftime('%m/%Y'),
                'sales_count': 0,
                'total': 0.0,
            })
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
        bucket_index = {bucket['key']: bucket for bucket in buckets}
        for sale in sales:
            if sale.created_at:
                local_created_at = to_business_datetime(sale.created_at)
                key = f'{local_created_at.year}-{local_created_at.month:02d}'
                if key in bucket_index:
                    bucket_index[key]['sales_count'] += 1
                    bucket_index[key]['total'] += sale.final_amount or 0.0
    else:
        current = start
        while current <= end:
            buckets.append({
                'key': current.isoformat(),
                'label': current.strftime('%d/%m'),
                'title': current.strftime('%d/%m/%Y'),
                'sales_count': 0,
                'total': 0.0,
            })
            current += timedelta(days=1)
        bucket_index = {bucket['key']: bucket for bucket in buckets}
        for sale in sales:
            if sale.created_at:
                key = to_business_datetime(sale.created_at).date().isoformat()
                if key in bucket_index:
                    bucket_index[key]['sales_count'] += 1
                    bucket_index[key]['total'] += sale.final_amount or 0.0

    active_buckets = [bucket for bucket in buckets if bucket['sales_count'] > 0]
    peak_by_quantity = max(
        active_buckets,
        key=lambda item: (item['sales_count'], item['total']),
        default=None,
    )
    peak_by_revenue = max(
        active_buckets,
        key=lambda item: (item['total'], item['sales_count']),
        default=None,
    )
    selected_peak = peak_by_quantity if metric == 'quantity' else peak_by_revenue
    max_value = max(
        (bucket['sales_count'] if metric == 'quantity' else bucket['total'] for bucket in buckets),
        default=0,
    )

    for bucket in buckets:
        value = bucket['sales_count'] if metric == 'quantity' else bucket['total']
        bucket['total'] = round(bucket['total'], 2)
        bucket['percent'] = round((value / max_value) * 100, 2) if max_value else 0
        bucket['is_peak'] = bool(selected_peak and bucket['key'] == selected_peak['key'])

    return {
        'metric': metric,
        'buckets': buckets,
        'peak': selected_peak,
        'peak_by_quantity': peak_by_quantity,
        'peak_by_revenue': peak_by_revenue,
    }


def json_bool(payload, name, default=True):
    raw_value = payload.get(name, default)
    if isinstance(raw_value, bool):
        return raw_value
    if isinstance(raw_value, str):
        normalized = raw_value.strip().casefold()
        if normalized in {'1', 'true', 'sim', 'yes', 'ativo', 'active'}:
            return True
        if normalized in {'0', 'false', 'nao', 'não', 'no', 'inativo', 'inactive'}:
            return False
    if raw_value in {0, 1}:
        return bool(raw_value)
    raise ApiAuthError(
        f'O campo {name} precisa ser verdadeiro ou falso.',
        'invalid_boolean',
        422,
        name,
    )


def product_input_from_payload(payload):
    return ProductInput(
        name=json_text(payload, 'name', required=True, max_length=180),
        barcode=json_text(payload, 'barcode', required=False, max_length=80),
        category_id=json_optional_positive_integer(payload, 'category_id'),
        cost_price=json_optional_money(payload, 'cost_price'),
        sale_price=json_money(payload, 'sale_price'),
        stock_quantity=json_integer(payload, 'stock_quantity'),
        min_stock_quantity=json_non_negative_integer(payload, 'min_stock_quantity'),
        active=json_bool(payload, 'active', default=True),
        stock_reason=json_text(payload, 'stock_reason', required=False, max_length=240),
        is_kit=json_bool(payload, 'is_kit', default=False),
        kit_component_product_id=json_optional_positive_integer(payload, 'kit_component_product_id'),
        kit_component_quantity=json_non_negative_integer(payload, 'kit_component_quantity'),
    )


def category_input_from_payload(payload):
    return CategoryInput(
        name=json_text(payload, 'name', required=True, max_length=120),
    )


def sale_idempotency_key(payload):
    header_value = (request.headers.get('Idempotency-Key') or '').strip()
    body_value = str(payload.get('idempotency_key') or '').strip()
    if header_value and body_value and header_value != body_value:
        raise ApiAuthError(
            'A chave de idempotência do cabeçalho difere da chave enviada no corpo.',
            'idempotency_key_mismatch',
            422,
            'idempotency_key',
        )

    key = header_value or body_value
    if not key:
        raise ApiAuthError(
            'Informe uma chave de idempotência para registrar a venda.',
            'idempotency_key_required',
            422,
            'idempotency_key',
        )
    if not IDEMPOTENCY_KEY_PATTERN.fullmatch(key):
        raise ApiAuthError(
            'A chave de idempotência precisa ter de 8 a 128 caracteres seguros.',
            'invalid_idempotency_key',
            422,
            'idempotency_key',
        )
    return key


def sale_line_inputs(payload):
    raw_items = payload.get('items')
    if not isinstance(raw_items, list) or not raw_items:
        raise ApiAuthError(
            'Adicione pelo menos um produto à venda.',
            'sale_items_required',
            422,
            'items',
        )
    if len(raw_items) > 200:
        raise ApiAuthError(
            'Uma venda pode conter no máximo 200 linhas de produtos.',
            'too_many_sale_items',
            422,
            'items',
        )

    items = []
    for index, raw_item in enumerate(raw_items):
        if not isinstance(raw_item, dict):
            raise ApiAuthError(
                f'O item {index + 1} precisa ser um objeto JSON.',
                'invalid_sale_item',
                422,
                'items',
            )
        product_id = json_positive_integer(raw_item, 'product_id')
        quantity = json_positive_integer(raw_item, 'quantity')
        if quantity > 100000:
            raise ApiAuthError(
                'A quantidade de um produto excede o limite permitido.',
                'invalid_quantity',
                422,
                'items',
            )
        items.append(SaleLineInput(product_id=product_id, quantity=quantity))
    return items


def sale_payment_inputs(payload):
    raw_payments = payload.get('payments')
    if not isinstance(raw_payments, list):
        raise ApiAuthError(
            'Informe as formas de pagamento da venda.',
            'payments_required',
            422,
            'payments',
        )
    if len(raw_payments) > 12:
        raise ApiAuthError(
            'A quantidade de formas de pagamento excede o limite permitido.',
            'too_many_payments',
            422,
            'payments',
        )

    aggregated = {}
    for index, raw_payment in enumerate(raw_payments):
        if not isinstance(raw_payment, dict):
            raise ApiAuthError(
                f'O pagamento {index + 1} precisa ser um objeto JSON.',
                'invalid_payment',
                422,
                'payments',
            )
        method = str(raw_payment.get('method') or '').strip().casefold()
        amount = json_money(raw_payment, 'amount')
        aggregated[method] = aggregated.get(method, Decimal('0.00')) + amount

    return [
        SalePaymentInput(method=method, amount=amount)
        for method, amount in aggregated.items()
        if amount > 0
    ]


def catalog_category_data(category, product_count):
    return {
        'id': category.id,
        'name': category.name,
        'product_count': int(product_count or 0),
    }


def catalog_product_data(product, include_cost):
    category = product.category
    payload = {
        'id': product.id,
        'name': product.name,
        'barcode': product.barcode or '',
        'category': None if category is None else {
            'id': category.id,
            'name': category.name,
        },
        'sale_price': round(float(product.sale_price or 0), 2),
        'stock_quantity': int(product.effective_stock_quantity),
        'min_stock_quantity': int(product.min_stock_quantity or 0),
        'active': bool(product.active),
        'is_kit': bool(product.is_kit),
        'kit_component': None if product.kit_component is None else {
            'id': product.kit_component.id,
            'name': product.kit_component.name,
        },
        'kit_component_quantity': int(product.kit_component_quantity or 0),
    }
    if include_cost:
        payload.update({
            'cost_price': round(float(product.cost_price or 0), 2),
            'profit_amount': round(float(product.profit_amount), 2),
            'profit_margin_percent': round(float(product.profit_margin_percent), 2),
        })
    return payload


def stock_movement_data(movement, include_cost=False):
    product = movement.product
    user = movement.user
    category = product.category if product is not None else None
    previous_stock = int(movement.previous_stock or 0)
    new_stock = int(movement.new_stock or 0)
    signed_quantity = new_stock - previous_stock
    source_label = stock_source_label(movement.source_type, movement.movement_type)
    reference = ''
    if movement.source_id:
        reference = {
            'sale': f'Venda #{movement.source_id}',
            'kit_sale': f'Venda #{movement.source_id} (kit)',
            'sale_cancellation': f'Cancelamento da venda #{movement.source_id}',
        }.get(movement.source_type, f'Referência #{movement.source_id}')

    payload = {
        'id': movement.id,
        'created_at': utc_isoformat(movement.created_at),
        'product': None if product is None else {
            'id': product.id,
            'name': product.name,
            'category': None if category is None else {
                'id': category.id,
                'name': category.name,
            },
        },
        'user': None if user is None else {
            'id': user.id,
            'username': user.username,
        },
        'movement_type': movement.movement_type or '',
        'movement_type_label': stock_movement_label(movement.movement_type),
        'source_type': movement.source_type or '',
        'source_type_label': source_label,
        'origin': movement.source_type or '',
        'origin_label': source_label,
        'source_id': movement.source_id,
        'reference': reference,
        'quantity': int(movement.quantity or 0),
        'signed_quantity': signed_quantity,
        'direction': 'in' if signed_quantity > 0 else 'out' if signed_quantity < 0 else 'none',
        'previous_stock': previous_stock,
        'new_stock': new_stock,
        'balance_consistent': previous_stock + signed_quantity == new_stock,
        'reason': movement.reason or '',
        'notes': movement.notes or '',
    }
    if include_cost:
        payload.update({
            'unit_cost': round(float(movement.unit_cost or 0), 2),
            'total_cost': round(float(movement.total_cost or 0), 2),
        })
    return payload


def stock_filter_options(labels):
    return [
        {'value': value, 'label': label}
        for value, label in labels.items()
    ]


def payable_status_value(payable, today=None):
    today = today or business_today()
    if payable.paid:
        return 'paid'
    if payable.due_date and payable.due_date < today:
        return 'overdue'
    if payable.due_date and payable.due_date == today:
        return 'due_today'
    if payable.due_date and payable.due_date <= today + timedelta(days=3):
        return 'near_due'
    return 'open'


def payable_data(payable, today=None):
    status = payable_status_value(payable, today)
    return {
        'id': payable.id,
        'description': payable.description,
        'category': payable.category or 'Outros',
        'amount': money_json(payable.amount),
        'due_date': payable.due_date.isoformat() if payable.due_date else None,
        'paid': bool(payable.paid),
        'paid_at': utc_isoformat(payable.paid_at),
        'notes': payable.notes or '',
        'created_at': utc_isoformat(payable.created_at),
        'status': status,
        'status_label': PAYABLE_STATUS_LABELS.get(status, status),
    }


def payable_filter_options():
    return [
        {'value': 'open', 'label': 'Abertas'},
        {'value': 'overdue', 'label': 'Vencidas'},
        {'value': 'due_today', 'label': 'Vencem hoje'},
        {'value': 'near_due', 'label': 'Próximas'},
        {'value': 'paid', 'label': 'Pagas'},
        {'value': 'all', 'label': 'Todas'},
    ]


def payable_snapshot(db_session, company_id, status_filter, search, category, start_date, end_date):
    today = business_today()
    query = db_session.query(Payable).filter(Payable.company_id == company_id)
    if search:
        pattern = f'%{search}%'
        query = query.filter(or_(
            Payable.description.ilike(pattern),
            Payable.category.ilike(pattern),
            Payable.notes.ilike(pattern),
        ))
    if category and category != 'all':
        query = query.filter(Payable.category == category)
    if start_date:
        query = query.filter(Payable.due_date >= start_date)
    if end_date:
        query = query.filter(Payable.due_date <= end_date)
    if status_filter == 'paid':
        query = query.filter(Payable.paid.is_(True))
    elif status_filter == 'overdue':
        query = query.filter(Payable.paid.is_(False), Payable.due_date < today)
    elif status_filter == 'due_today':
        query = query.filter(Payable.paid.is_(False), Payable.due_date == today)
    elif status_filter == 'near_due':
        query = query.filter(
            Payable.paid.is_(False),
            Payable.due_date > today,
            Payable.due_date <= today + timedelta(days=3),
        )
    elif status_filter != 'all':
        status_filter = 'open'
        query = query.filter(Payable.paid.is_(False))

    items = query.order_by(
        Payable.paid.asc(),
        Payable.due_date.asc(),
        func.lower(Payable.description).asc(),
        Payable.id.asc(),
    ).all()

    open_query = db_session.query(Payable).filter(
        Payable.company_id == company_id,
        Payable.paid.is_(False),
    )
    open_items = open_query.all()
    paid_count = int(db_session.query(Payable).filter(
        Payable.company_id == company_id,
        Payable.paid.is_(True),
    ).count() or 0)
    category_rows = db_session.query(Payable.category).filter(
        Payable.company_id == company_id,
    ).distinct().order_by(func.lower(Payable.category)).all()

    return {
        'items': [payable_data(payable, today) for payable in items],
        'summary': {
            'open_amount': money_json(sum((item.amount or 0 for item in open_items), Decimal('0.00'))),
            'overdue_amount': money_json(sum((
                item.amount or 0
                for item in open_items
                if payable_status_value(item, today) == 'overdue'
            ), Decimal('0.00'))),
            'due_soon_amount': money_json(sum((
                item.amount or 0
                for item in open_items
                if payable_status_value(item, today) in {'due_today', 'near_due'}
            ), Decimal('0.00'))),
            'open_count': len(open_items),
            'paid_count': paid_count,
        },
        'categories': [
            category_row[0]
            for category_row in category_rows
            if category_row[0]
        ],
        'status_options': payable_filter_options(),
        'selected_status': status_filter,
    }


@api_v1_bp.get('/health')
def health_check():
    return api_success({
        'status': 'ok',
        'service': 'girofy',
        'api_version': 'v1',
    })


@api_v1_bp.get('/health/dependencies')
def api_dependency_health_check():
    database_status = 'ok'
    try:
        db.session.execute(text('SELECT 1'))
    except Exception:
        database_status = 'error'
    redis_status = redis_health_status()
    healthy = database_status == 'ok' and redis_status in {'ok', 'memory', 'disabled'}
    response, status_code = api_success({
        'status': 'ok' if healthy else 'degraded',
        'dependencies': {'database': database_status, 'redis': redis_status},
    }), 200 if healthy else 503
    return response, status_code


@api_v1_bp.post('/auth/login')
@limiter.limit(
    configured_limit('RATELIMIT_LOGIN', '5 per minute;20 per hour'),
    key_func=login_identity_key,
    override_defaults=False,
)
def api_login():
    identifier = ''
    try:
        require_secure_auth_transport()
        payload = json_object_body()
        identifier = str(payload.get('identifier') or payload.get('username') or '').strip()
        password = payload.get('password')
        if not identifier:
            raise ApiAuthError(
                'Informe seu usuário ou e-mail.',
                'identifier_required',
                422,
                'identifier',
            )
        if not isinstance(password, str) or not password:
            raise ApiAuthError(
                'Informe sua senha.',
                'password_required',
                422,
                'password',
            )
        if len(identifier) > 255 or len(password) > int(current_app.config.get('PASSWORD_MAX_LENGTH', 128)):
            raise ApiAuthError(
                'Os dados de acesso excedem o tamanho permitido.',
                'credentials_too_long',
                422,
            )

        user = authenticate_credentials(identifier, password)
        token_pair, _ = issue_token_pair(user)
        record_audit_event(
            'login_success',
            'auth',
            user.id,
            f'Login no aplicativo Windows realizado por {user.username}.',
            new_values={'client': 'windows_native'},
            company_id=user.company_id,
            user=user,
            db_session=db.session,
        )
        db.session.commit()
        return api_success({
            **token_pair,
            **user_identity_data(user),
        })
    except ApiAuthError as error:
        db.session.rollback()
        if identifier and error.code in {'invalid_credentials', 'login_rate_limited'}:
            record_audit_event(
                'login_failed',
                'auth',
                None,
                f'Tentativa de login no aplicativo Windows falhou para {identifier}.',
                new_values={'identifier': identifier, 'client': 'windows_native'},
                db_session=db.session,
            )
            db.session.commit()
        return api_auth_error_response(error)


@api_v1_bp.post('/auth/password-recovery/request')
@limiter.limit(
    configured_limit('RATELIMIT_PASSWORD_RESET', '3 per 15 minutes'),
    key_func=login_identity_key,
    override_defaults=False,
)
def api_request_password_recovery():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return api_failure(
            'Envie um objeto JSON válido.',
            'invalid_json',
            400,
        )
    identifier = str(payload.get('identifier') or '').strip()
    if not identifier:
        return api_failure(
            'Informe seu usuário ou e-mail.',
            'identifier_required',
            422,
            'identifier',
        )
    if len(identifier) > 255:
        return api_failure(
            'Os dados informados excedem o tamanho permitido.',
            'identifier_too_long',
            422,
            'identifier',
        )

    try:
        request_password_recovery(identifier)
    except Exception:
        db.session.rollback()
        current_app.logger.error(
            'Falha técnica na solicitação de recuperação pela API.',
            exc_info=True,
        )

    return api_success({
        'requested': True,
    })


@api_v1_bp.post('/subscription/activate')
@limiter.limit(
    configured_limit('RATELIMIT_ACTIVATION', '5 per 15 minutes'),
    key_func=login_identity_key,
    override_defaults=False,
)
def api_activate_subscription():
    identifier = ''
    try:
        require_secure_auth_transport()
        payload = json_object_body()
        identifier = str(payload.get('identifier') or payload.get('username') or '').strip()
        password = payload.get('password')
        activation_key_value = str(payload.get('activation_key') or payload.get('key') or '').strip()

        if not identifier:
            raise ApiAuthError(
                'Informe seu usuário ou e-mail.',
                'identifier_required',
                422,
                'identifier',
            )
        if not isinstance(password, str) or not password:
            raise ApiAuthError(
                'Informe sua senha.',
                'password_required',
                422,
                'password',
            )
        if not activation_key_value:
            raise ApiAuthError(
                'Informe a key de ativação.',
                'activation_key_required',
                422,
                'activation_key',
            )
        if len(identifier) > 255 or len(password) > int(current_app.config.get('PASSWORD_MAX_LENGTH', 128)):
            raise ApiAuthError(
                'Os dados de acesso excedem o tamanho permitido.',
                'credentials_too_long',
                422,
            )

        user = authenticate_credentials_for_activation(identifier, password)
        company = user.company
        if company is None:
            raise ApiAuthError(
                'Este usuário não possui uma adega vinculada.',
                'company_context_required',
                403,
            )

        activation_key = available_activation_key(activation_key_value)
        if activation_key is None:
            raise ApiAuthError(
                'Key inválida, expirada ou já utilizada.',
                'invalid_activation_key',
                422,
                'activation_key',
            )

        apply_activation_key_to_company(activation_key, company)
        token_pair, _ = issue_token_pair(user)
        record_audit_event(
            'subscription_activated',
            'subscription',
            company.id,
            f'Assinatura ativada pelo aplicativo Windows para {company.name}.',
            new_values={
                'client': 'windows_native',
                'plan': company.subscription_plan,
                'renews_at': company.subscription_renews_at.isoformat() if company.subscription_renews_at else None,
            },
            company_id=company.id,
            user=user,
            db_session=db.session,
        )
        db.session.commit()
        return api_success({
            **token_pair,
            **user_identity_data(user),
        })
    except ApiAuthError as error:
        db.session.rollback()
        if identifier and error.code in {'invalid_credentials', 'login_rate_limited'}:
            record_audit_event(
                'login_failed',
                'auth',
                None,
                f'Tentativa de ativação no aplicativo Windows falhou para {identifier}.',
                new_values={'identifier': identifier, 'client': 'windows_native'},
                db_session=db.session,
            )
            db.session.commit()
        return api_auth_error_response(error)


@api_v1_bp.post('/auth/refresh')
@limiter.limit(
    configured_limit('RATELIMIT_REFRESH', '120 per hour'),
    key_func=token_identity_key,
    override_defaults=False,
)
def api_refresh():
    try:
        require_secure_auth_transport()
        payload = json_object_body()
        refresh_token = payload.get('refresh_token')
        if not isinstance(refresh_token, str) or not refresh_token:
            raise ApiAuthError(
                'Informe o token de atualização.',
                'refresh_token_required',
                422,
                'refresh_token',
            )
        token_pair, user = rotate_refresh_token(refresh_token)
        db.session.commit()
        return api_success({
            **token_pair,
            **user_identity_data(user),
        })
    except ApiAuthError as error:
        db.session.rollback()
        return api_auth_error_response(error)


@api_v1_bp.post('/auth/logout')
@api_auth_required
def api_logout():
    revoke_session(g.api_session)
    record_audit_event(
        'logout',
        'auth',
        g.api_user.id,
        f'Sessão do aplicativo Windows encerrada por {g.api_user.username}.',
        new_values={'client': 'windows_native'},
        company_id=g.api_user.company_id,
        user=g.api_user,
        db_session=db.session,
    )
    db.session.commit()
    return api_success({'logged_out': True})


@api_v1_bp.get('/auth/me')
@api_auth_required
def api_me():
    return api_success(user_identity_data(g.api_user))


def api_settings_payload(user):
    identity = user_identity_data(user)
    company = user.company
    return {
        **identity,
        'profile': {
            'first_name': user.first_name or '',
            'last_name': user.last_name or '',
            'full_name': user.full_name or user.username,
            'email': user.email or '',
            'phone': user.phone or '',
            'username': user.username,
            'role_label': user.role_label,
        },
        'company_settings': None if company is None else {
            'allow_negative_stock': bool(company.allow_negative_stock),
            'backup_frequency': company.backup_frequency or 'manual',
            'backup_last_at': utc_isoformat(company.backup_last_at),
            'backup_last_status': company.backup_last_status or '',
            'pix_fee_enabled': bool(company.pix_fee_enabled),
            'debit_fee_enabled': bool(company.debit_fee_enabled),
            'credit_fee_enabled': bool(company.credit_fee_enabled),
            'pix_fee_percent': float(company.pix_fee_percent or 0),
            'debit_fee_percent': float(company.debit_fee_percent or 0),
            'credit_fee_percent': float(company.credit_fee_percent or 0),
        },
    }


def normalize_digits(value):
    return re.sub(r'\D+', '', value or '')


def api_can_manage_team(user):
    return (
        user.role in ('admin', 'manager', 'master')
        or user.has_permission('can_manage_settings')
    )


def api_require_team_permission():
    if g.api_user.company_id is None:
        raise ApiAuthError(
            'Nenhuma adega está vinculada ao usuário autenticado.',
            'company_required',
            403,
        )
    if not api_can_manage_team(g.api_user):
        raise ApiAuthError(
            'Você não tem permissão para gerenciar a equipe.',
            'permission_denied',
            403,
        )


def api_require_settings_permission():
    if g.api_user.company_id is None:
        raise ApiAuthError(
            'Nenhuma adega está vinculada ao usuário autenticado.',
            'company_required',
            403,
        )
    if not api_can_manage_team(g.api_user):
        raise ApiAuthError(
            'Você não tem permissão para gerenciar as configurações da adega.',
            'permission_denied',
            403,
        )


def api_can_export_data(user):
    return user.role in ('admin', 'master') and user.company_id is not None


def api_can_import_products(user):
    return user.role in ('admin', 'manager', 'master') and user.company_id is not None


def api_require_export_permission():
    if g.api_user.company_id is None:
        raise ApiAuthError(
            'Nenhuma adega está vinculada ao usuário autenticado.',
            'company_required',
            403,
        )
    if not api_can_export_data(g.api_user):
        raise ApiAuthError(
            'Apenas administradores podem exportar dados da adega.',
            'permission_denied',
            403,
        )


def api_require_product_import_permission():
    if g.api_user.company_id is None:
        raise ApiAuthError(
            'Nenhuma adega está vinculada ao usuário autenticado.',
            'company_required',
            403,
        )
    if not api_can_import_products(g.api_user):
        raise ApiAuthError(
            'Apenas administradores e gerentes podem importar produtos.',
            'permission_denied',
            403,
        )


def format_export_datetime(value):
    return value.strftime('%d/%m/%Y %H:%M') if value else ''


def format_export_date(value):
    return value.strftime('%d/%m/%Y') if value else ''


def format_export_money(value):
    return f'{float(value or 0):.2f}'.replace('.', ',')


def api_sale_profit_amount(sale):
    return sum(api_sale_item_profit(item) for item in sale.items)


def api_cash_register_total_sold(cash_register):
    return sum(float(sale.final_amount or 0) for sale in cash_register.sales)


def api_cash_register_profit_amount(cash_register):
    return sum(api_sale_profit_amount(sale) for sale in cash_register.sales)


def api_export_products_rows(tenant_db):
    products = (
        tenant_db.query(Product)
        .options(selectinload(Product.category), selectinload(Product.kit_component))
        .filter(Product.company_id == g.api_user.company_id)
        .order_by(Product.name.asc())
        .all()
    )
    return [
        [
            product.id,
            product.name,
            product.barcode or '',
            product.category.name if product.category else '',
            format_export_money(product.cost_price),
            format_export_money(product.sale_price),
            product.stock_quantity or 0,
            product.min_stock_quantity or 0,
            'Sim' if product.active else 'Não',
            'Sim' if product.is_kit else 'Não',
            product.kit_component.name if product.kit_component else '',
            product.kit_component_quantity or 0,
            format_export_datetime(product.created_at),
        ]
        for product in products
    ]


def api_export_sales_rows(tenant_db):
    sales = (
        tenant_db.query(Sale)
        .options(selectinload(Sale.payments), selectinload(Sale.items))
        .filter(Sale.company_id == g.api_user.company_id)
        .order_by(Sale.created_at.desc())
        .all()
    )
    rows = []
    for sale in sales:
        payments = ', '.join(
            f'{PAYMENT_METHODS.get(payment.method, payment.method)}: {format_export_money(payment.amount)}'
            for payment in sale.payments
        )
        rows.append([
            sale.id,
            format_export_datetime(sale.created_at),
            format_export_money(sale.total_amount),
            format_export_money(sale.discount_amount),
            format_export_money(sale.final_amount),
            format_export_money(api_sale_profit_amount(sale)),
            sale.payment_status or '',
            payments,
            sale.cash_register_id or '',
        ])
    return rows


def api_export_cash_register_rows(tenant_db):
    cash_registers = (
        tenant_db.query(CashRegister)
        .options(selectinload(CashRegister.sales).selectinload(Sale.items))
        .filter(CashRegister.company_id == g.api_user.company_id)
        .order_by(CashRegister.opened_at.desc())
        .all()
    )
    return [
        [
            cash_register.id,
            format_export_datetime(cash_register.opened_at),
            format_export_datetime(cash_register.closed_at),
            cash_register.status or '',
            format_export_money(cash_register.opening_amount),
            format_export_money(cash_register.closing_amount),
            format_export_money(api_cash_register_total_sold(cash_register)),
            format_export_money(api_cash_register_profit_amount(cash_register)),
            len(cash_register.sales),
        ]
        for cash_register in cash_registers
    ]


def api_export_payables_rows(tenant_db):
    payables = (
        tenant_db.query(Payable)
        .filter(Payable.company_id == g.api_user.company_id)
        .order_by(Payable.due_date.desc(), Payable.description.asc())
        .all()
    )
    today = date.today()
    return [
        [
            payable.id,
            payable.description,
            payable.category or '',
            format_export_money(payable.amount),
            format_export_date(payable.due_date),
            PAYABLE_STATUS_LABELS.get(payable_status_value(payable, today), 'Aberta'),
            'Sim' if payable.paid else 'Não',
            format_export_datetime(payable.paid_at),
            payable.notes or '',
        ]
        for payable in payables
    ]


API_EXPORT_DEFINITIONS = {
    'produtos': {
        'label': 'Produtos',
        'filename': 'girofy_produtos',
        'headers': [
            'ID',
            'Nome',
            'Código de barras',
            'Categoria',
            'Custo',
            'Venda',
            'Estoque',
            'Estoque mínimo',
            'Ativo',
            'Kit',
            'Produto base do kit',
            'Quantidade do kit',
            'Criado em',
        ],
        'rows': api_export_products_rows,
    },
    'vendas': {
        'label': 'Vendas',
        'filename': 'girofy_vendas',
        'headers': [
            'ID',
            'Data',
            'Total bruto',
            'Desconto',
            'Total final',
            'Lucro',
            'Status',
            'Pagamentos',
            'Caixa',
        ],
        'rows': api_export_sales_rows,
    },
    'caixas': {
        'label': 'Caixas',
        'filename': 'girofy_caixas',
        'headers': [
            'ID',
            'Abertura',
            'Fechamento',
            'Status',
            'Valor inicial',
            'Valor final',
            'Total vendido',
            'Lucro',
            'Vendas',
        ],
        'rows': api_export_cash_register_rows,
    },
    'contas': {
        'label': 'Contas a pagar',
        'filename': 'girofy_contas_a_pagar',
        'headers': [
            'ID',
            'Descrição',
            'Categoria',
            'Valor',
            'Vencimento',
            'Status',
            'Paga',
            'Pago em',
            'Observações',
        ],
        'rows': api_export_payables_rows,
    },
}


def api_csv_export_response(export_type, headers, rows):
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(headers)
    writer.writerows(rows)
    csv_body = '\ufeff' + output.getvalue()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'{API_EXPORT_DEFINITIONS[export_type]["filename"]}_{timestamp}.csv'
    response = Response(csv_body, mimetype='text/csv; charset=utf-8')
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.headers['Cache-Control'] = 'no-store'
    return response


def api_import_parse_money(value):
    if isinstance(value, (int, float, Decimal)):
        return max(float(value), 0.0)
    value = str(value or '0').strip()
    if ',' in value:
        value = value.replace('.', '').replace(',', '.')
    try:
        return max(float(value), 0.0)
    except ValueError:
        return 0.0


def api_import_parse_int(value):
    try:
        return max(int(float(str(value or 0).replace(',', '.'))), 0)
    except ValueError:
        return 0


def api_import_normalize_header(value):
    value = str(value or '').strip().lower()
    replacements = {
        'ç': 'c',
        'ã': 'a',
        'á': 'a',
        'à': 'a',
        'â': 'a',
        'é': 'e',
        'ê': 'e',
        'í': 'i',
        'ó': 'o',
        'ô': 'o',
        'õ': 'o',
        'ú': 'u',
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    return re.sub(r'[^a-z0-9]+', '_', value).strip('_')


def api_import_column(row, *names):
    normalized = {api_import_normalize_header(key): value for key, value in row.items()}
    for name in names:
        key = api_import_normalize_header(name)
        if key in normalized:
            return normalized[key]
    return ''


def api_read_csv_import_rows(file_storage):
    content = file_storage.read().decode('utf-8-sig')
    sample = content[:2048]
    delimiter = ';' if sample.count(';') > sample.count(',') else ','
    return list(csv.DictReader(io.StringIO(content), delimiter=delimiter))


def api_xlsx_column_index(cell_reference):
    letters = ''.join(char for char in cell_reference if char.isalpha())
    index = 0
    for letter in letters:
        index = index * 26 + (ord(letter.upper()) - ord('A') + 1)
    return index - 1


def api_read_xlsx_import_rows(file_storage):
    data = file_storage.read()
    with zipfile.ZipFile(io.BytesIO(data)) as workbook:
        shared_strings = []
        if 'xl/sharedStrings.xml' in workbook.namelist():
            shared_root = ElementTree.fromstring(workbook.read('xl/sharedStrings.xml'))
            for item in shared_root.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si'):
                text_parts = [
                    text_node.text or ''
                    for text_node in item.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')
                ]
                shared_strings.append(''.join(text_parts))

        sheet_name = 'xl/worksheets/sheet1.xml'
        if sheet_name not in workbook.namelist():
            raise ValueError('A planilha precisa ter uma primeira aba válida.')

        sheet_root = ElementTree.fromstring(workbook.read(sheet_name))
        table_rows = []
        for sheet_row in sheet_root.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row'):
            values = []
            for cell in sheet_row.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c'):
                reference = cell.attrib.get('r', '')
                index = api_xlsx_column_index(reference)
                while len(values) <= index:
                    values.append('')

                value_node = cell.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v')
                inline_node = cell.find(
                    '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}is/'
                    '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t'
                )
                value = ''
                if inline_node is not None:
                    value = inline_node.text or ''
                elif value_node is not None:
                    value = value_node.text or ''
                    if cell.attrib.get('t') == 's' and value.isdigit():
                        value = shared_strings[int(value)] if int(value) < len(shared_strings) else ''
                values[index] = value
            if any(str(value).strip() for value in values):
                table_rows.append(values)

    if not table_rows:
        return []

    headers = [str(header).strip() for header in table_rows[0]]
    rows = []
    for values in table_rows[1:]:
        row = {}
        for index, header in enumerate(headers):
            row[header] = values[index] if index < len(values) else ''
        rows.append(row)
    return rows


def api_read_product_import_rows(file_storage):
    filename = (file_storage.filename or '').lower()
    if filename.endswith('.csv'):
        return api_read_csv_import_rows(file_storage)
    if filename.endswith('.xlsx'):
        return api_read_xlsx_import_rows(file_storage)
    raise ValueError('Formato inválido. Envie uma planilha CSV ou XLSX.')


def api_find_or_create_import_category(name, tenant_db, company_id):
    name = str(name or '').strip()
    if not name:
        return None

    category = tenant_db.query(Category).filter(
        Category.company_id == company_id,
        func.lower(Category.name) == name.lower(),
    ).first()
    if category:
        return category

    category = Category(name=name, company_id=company_id)
    tenant_db.add(category)
    tenant_db.flush()
    return category


def api_product_import_audit_values(product):
    return {
        'name': product.name,
        'barcode': product.barcode,
        'category_id': product.category_id,
        'cost_price': product.cost_price,
        'sale_price': product.sale_price,
        'stock_quantity': product.stock_quantity,
        'min_stock_quantity': product.min_stock_quantity,
        'active': product.active,
    }


def api_find_import_product(tenant_db, company_id, product_name, barcode):
    if barcode:
        product = tenant_db.query(Product).filter(
            Product.company_id == company_id,
            Product.barcode == barcode,
        ).first()
        if product:
            return product

    return tenant_db.query(Product).filter(
        Product.company_id == company_id,
        func.lower(Product.name) == product_name.lower(),
    ).first()


def api_import_products_from_rows(rows, tenant_db, user):
    company_id = user.company_id
    created = 0
    updated = 0
    skipped = 0
    movements = 0

    for row in rows:
        product_name = str(api_import_column(row, 'produto', 'nome', 'nome_produto', 'product', 'name') or '').strip()
        if not product_name:
            skipped += 1
            continue

        barcode = str(api_import_column(row, 'codigo de barras', 'codigo_barras', 'barcode', 'ean', 'sku') or '').strip() or None
        category_name = api_import_column(row, 'categoria', 'category')
        cost_price = api_import_parse_money(api_import_column(
            row,
            'valor de custo',
            'custo',
            'preco de custo',
            'preco_custo',
            'cost_price',
            'cost',
        ))
        sale_price = api_import_parse_money(api_import_column(
            row,
            'valor de venda',
            'venda',
            'preco de venda',
            'preco_venda',
            'sale_price',
            'price',
        ))
        stock_quantity = api_import_parse_int(api_import_column(
            row,
            'estoque atual',
            'estoque_atual',
            'estoque',
            'stock_quantity',
            'stock',
        ))
        min_stock_quantity = api_import_parse_int(api_import_column(
            row,
            'estoque minimo',
            'estoque_minimo',
            'min_stock_quantity',
            'min_stock',
        ))
        category = api_find_or_create_import_category(category_name, tenant_db, company_id)

        product = api_find_import_product(tenant_db, company_id, product_name, barcode)
        if product:
            updated += 1
            old_values = api_product_import_audit_values(product)
            previous_stock = int(product.stock_quantity or 0)
        else:
            product = Product(name=product_name, company_id=company_id, active=True, stock_quantity=0)
            tenant_db.add(product)
            tenant_db.flush()
            created += 1
            old_values = {}
            previous_stock = 0

        product.company_id = company_id
        product.name = product_name
        product.barcode = barcode
        product.category_id = category.id if category else None
        product.cost_price = cost_price
        product.sale_price = sale_price
        product.min_stock_quantity = min_stock_quantity
        product.active = True
        tenant_db.flush()

        if previous_stock == 0 and int(product.stock_quantity or 0) == 0 and stock_quantity > 0 and not old_values:
            register_stock_movement(
                tenant_db,
                product,
                'import',
                'spreadsheet_import',
                stock_quantity,
                stock_quantity,
                user_id=user.id,
                unit_cost=cost_price,
                reason='Estoque importado pelo aplicativo Windows',
            )
            movements += 1
        elif stock_quantity != previous_stock:
            adjust_stock(
                tenant_db,
                product,
                stock_quantity,
                source_type='spreadsheet_import',
                user_id=user.id,
                unit_cost=cost_price,
                reason='Estoque ajustado por importação no aplicativo Windows',
                allow_negative_stock=user.company.allow_negative_stock,
            )
            movements += 1

        new_values = api_product_import_audit_values(product)
        old_diff, new_diff = changed_values(old_values, new_values)
        record_audit_event(
            'product_created' if not old_values else 'product_updated',
            'product',
            product.id,
            f'Produto {product.name} {"criado" if not old_values else "atualizado"} por importação no aplicativo Windows.',
            old_values=old_diff,
            new_values=new_diff,
            company_id=company_id,
            user=user,
            db_session=tenant_db,
        )

    tenant_db.commit()
    return {
        'created': created,
        'updated': updated,
        'skipped': skipped,
        'movements': movements,
        'total_rows': len(rows),
    }


def api_role_options():
    return [
        {
            'value': role,
            'label': data['label'],
            'description': data['description'],
            'default_permissions': ROLE_PERMISSION_DEFAULTS[role],
        }
        for role, data in EMPLOYEE_ROLES.items()
    ]


def api_permission_options():
    return [
        {
            'value': permission,
            'label': EMPLOYEE_PERMISSION_LABELS[permission],
        }
        for permission in EMPLOYEE_PERMISSIONS
    ]


def api_employee_data(user):
    permissions = {
        permission: bool(getattr(user, permission, False))
        for permission in EMPLOYEE_PERMISSIONS
    }
    return {
        'id': user.id,
        'username': user.username,
        'first_name': user.first_name or '',
        'last_name': user.last_name or '',
        'full_name': user.full_name or user.username,
        'cpf': user.cpf or '',
        'email': user.email or '',
        'phone': user.phone or '',
        'role': user.role,
        'role_label': user.role_label,
        'is_active': bool(user.is_active),
        'is_current_user': user.id == g.api_user.id,
        'permissions': permissions,
        'created_at': utc_isoformat(user.created_at),
    }


def company_cpf_exists_api(company_id, cpf, user_id=None):
    cpf_digits = normalize_digits(cpf)
    if not cpf_digits:
        return False
    query = User.query.filter_by(company_id=company_id)
    if user_id:
        query = query.filter(User.id != user_id)
    return any(normalize_digits(user.cpf) == cpf_digits for user in query.all())


def apply_role_permissions_api(user, role):
    defaults = ROLE_PERMISSION_DEFAULTS.get(role, ROLE_PERMISSION_DEFAULTS['operator'])
    for permission in EMPLOYEE_PERMISSIONS:
        setattr(user, permission, bool(defaults.get(permission, False)))


def json_employee_role(payload, name='role'):
    role = json_text(payload, name, required=False, max_length=30) or 'operator'
    if role not in EMPLOYEE_ROLES:
        raise ApiAuthError(
            'Perfil de funcionário inválido.',
            'invalid_employee_role',
            422,
            name,
        )
    return role


def validate_employee_email(email):
    if email and not EMAIL_PATTERN.match(email):
        raise ApiAuthError(
            'Informe um e-mail válido para o funcionário.',
            'invalid_email',
            422,
            'email',
        )


@api_v1_bp.get('/settings/account')
@api_auth_required
def api_settings_account():
    return api_success(api_settings_payload(g.api_user))


def api_json_fee_percent(payload, name):
    value = json_optional_money(payload, name)
    if value > Decimal('100.00'):
        raise ApiAuthError(
            f'O campo {name} deve ser menor ou igual a 100%.',
            'invalid_percent',
            422,
            name,
        )
    return float(value)


@api_v1_bp.put('/settings/company')
@api_auth_required
def api_update_company_settings():
    try:
        api_require_settings_permission()
        payload = json_object_body()
        company = g.api_user.company

        old_values = {
            'allow_negative_stock': bool(company.allow_negative_stock),
            'pix_fee_enabled': bool(company.pix_fee_enabled),
            'pix_fee_percent': float(company.pix_fee_percent or 0),
            'debit_fee_enabled': bool(company.debit_fee_enabled),
            'debit_fee_percent': float(company.debit_fee_percent or 0),
            'credit_fee_enabled': bool(company.credit_fee_enabled),
            'credit_fee_percent': float(company.credit_fee_percent or 0),
        }

        company.allow_negative_stock = json_bool(payload, 'allow_negative_stock', default=company.allow_negative_stock)
        company.pix_fee_enabled = json_bool(payload, 'pix_fee_enabled', default=company.pix_fee_enabled)
        company.debit_fee_enabled = json_bool(payload, 'debit_fee_enabled', default=company.debit_fee_enabled)
        company.credit_fee_enabled = json_bool(payload, 'credit_fee_enabled', default=company.credit_fee_enabled)
        company.pix_fee_percent = api_json_fee_percent(payload, 'pix_fee_percent')
        company.debit_fee_percent = api_json_fee_percent(payload, 'debit_fee_percent')
        company.credit_fee_percent = api_json_fee_percent(payload, 'credit_fee_percent')
        company.card_fee_enabled = (
            company.pix_fee_enabled
            or company.debit_fee_enabled
            or company.credit_fee_enabled
        )

        new_values = {
            'allow_negative_stock': bool(company.allow_negative_stock),
            'pix_fee_enabled': bool(company.pix_fee_enabled),
            'pix_fee_percent': float(company.pix_fee_percent or 0),
            'debit_fee_enabled': bool(company.debit_fee_enabled),
            'debit_fee_percent': float(company.debit_fee_percent or 0),
            'credit_fee_enabled': bool(company.credit_fee_enabled),
            'credit_fee_percent': float(company.credit_fee_percent or 0),
            'client': 'windows_native',
        }
        record_audit_event(
            'company_settings_updated',
            'company',
            company.id,
            'Regras operacionais e taxas da adega atualizadas pelo aplicativo Windows.',
            old_values=old_values,
            new_values=new_values,
            company_id=company.id,
            user=g.api_user,
            db_session=db.session,
        )
        db.session.commit()
        return api_success(api_settings_payload(g.api_user))
    except ApiAuthError as error:
        db.session.rollback()
        return api_auth_error_response(error)


@api_v1_bp.put('/settings/profile')
@api_auth_required
def api_update_profile():
    try:
        payload = json_object_body()
        first_name = str(payload.get('first_name') or '').strip()
        last_name = str(payload.get('last_name') or '').strip()
        phone = str(payload.get('phone') or '').strip()

        if len(first_name) > 120:
            raise ApiAuthError('O nome deve ter no máximo 120 caracteres.', 'first_name_too_long', 422, 'first_name')
        if len(last_name) > 120:
            raise ApiAuthError('O sobrenome deve ter no máximo 120 caracteres.', 'last_name_too_long', 422, 'last_name')
        if len(phone) > 40:
            raise ApiAuthError('O telefone deve ter no máximo 40 caracteres.', 'phone_too_long', 422, 'phone')

        old_values = {
            'first_name': g.api_user.first_name or '',
            'last_name': g.api_user.last_name or '',
            'phone': g.api_user.phone or '',
        }
        g.api_user.first_name = first_name
        g.api_user.last_name = last_name
        g.api_user.phone = phone
        new_values = {
            'first_name': g.api_user.first_name or '',
            'last_name': g.api_user.last_name or '',
            'phone': g.api_user.phone or '',
        }
        record_audit_event(
            'profile_updated',
            'user',
            g.api_user.id,
            f'Perfil do usuário {g.api_user.username} atualizado pelo aplicativo Windows.',
            old_values=old_values,
            new_values=new_values,
            company_id=g.api_user.company_id,
            user=g.api_user,
            db_session=db.session,
        )
        db.session.commit()
        return api_success(api_settings_payload(g.api_user))
    except ApiAuthError as error:
        db.session.rollback()
        return api_auth_error_response(error)


@api_v1_bp.put('/settings/password')
@api_auth_required
def api_update_password():
    try:
        payload = json_object_body()
        current_password = payload.get('current_password')
        new_password = payload.get('new_password')
        confirm_password = payload.get('confirm_password')

        if not isinstance(current_password, str) or not current_password:
            raise ApiAuthError('Informe a senha atual.', 'current_password_required', 422, 'current_password')
        if not g.api_user.check_password(current_password):
            raise ApiAuthError('A senha atual está incorreta.', 'current_password_invalid', 422, 'current_password')
        if not isinstance(new_password, str) or len(new_password) < 6:
            raise ApiAuthError('A nova senha deve ter pelo menos 6 caracteres.', 'new_password_too_short', 422, 'new_password')
        if len(new_password) > int(current_app.config.get('PASSWORD_MAX_LENGTH', 128)):
            raise ApiAuthError('A nova senha excede o tamanho permitido.', 'new_password_too_long', 422, 'new_password')
        if new_password != confirm_password:
            raise ApiAuthError('A confirmação da senha não confere.', 'password_confirmation_mismatch', 422, 'confirm_password')

        g.api_user.set_password(new_password)
        revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
        ApiRefreshToken.query.filter_by(user_id=g.api_user.id, revoked_at=None).update({
            ApiRefreshToken.revoked_at: revoked_at,
        })
        record_audit_event(
            'password_changed',
            'user',
            g.api_user.id,
            f'Senha do usuário {g.api_user.username} alterada pelo aplicativo Windows.',
            new_values={'client': 'windows_native', 'sessions_revoked': True},
            company_id=g.api_user.company_id,
            user=g.api_user,
            db_session=db.session,
        )
        db.session.commit()
        return api_success({'password_changed': True, 'requires_login': True})
    except ApiAuthError as error:
        db.session.rollback()
        return api_auth_error_response(error)


@api_v1_bp.put('/settings/backup')
@api_auth_required
def api_update_backup_settings():
    try:
        api_require_settings_permission()
        payload = json_object_body()
        frequency = json_text(payload, 'backup_frequency', max_length=20) or 'manual'
        if frequency not in BACKUP_FREQUENCIES:
            raise ApiAuthError(
                'Frequência de backup inválida.',
                'invalid_backup_frequency',
                422,
                'backup_frequency',
            )

        company = g.api_user.company
        old_values = {
            'backup_frequency': company.backup_frequency or 'manual',
        }
        company.backup_frequency = frequency
        record_audit_event(
            'backup_settings_updated',
            'company',
            company.id,
            f'Frequência de backup alterada pelo aplicativo Windows para {BACKUP_FREQUENCIES[frequency]}.',
            old_values=old_values,
            new_values={'backup_frequency': frequency, 'client': 'windows_native'},
            company_id=company.id,
            user=g.api_user,
            db_session=db.session,
        )
        db.session.commit()
        return api_success(api_settings_payload(g.api_user))
    except ApiAuthError as error:
        db.session.rollback()
        return api_auth_error_response(error)


@api_v1_bp.post('/settings/backup/run')
@api_auth_required
@limiter.limit(
    configured_limit('RATELIMIT_BACKUP', '3 per hour'),
    key_func=authenticated_identity_key,
    override_defaults=False,
)
def api_run_manual_backup():
    try:
        api_require_settings_permission()
        company = g.api_user.company
        backup_path = create_company_backup(company, reason='windows_manual')
        record_audit_event(
            'backup_created',
            'company',
            company.id,
            f'Backup manual gerado pelo aplicativo Windows: {backup_path.name}.',
            new_values={
                'file_name': backup_path.name,
                'client': 'windows_native',
            },
            company_id=company.id,
            user=g.api_user,
            db_session=db.session,
        )
        db.session.commit()
        return api_success({
            **api_settings_payload(g.api_user),
            'backup': {
                'file_name': backup_path.name,
                'status': company.backup_last_status or 'success',
                'generated_at': utc_isoformat(company.backup_last_at),
            },
        })
    except ApiAuthError as error:
        db.session.rollback()
        return api_auth_error_response(error)
    except Exception:
        db.session.rollback()
        return api_failure(
            'Não foi possível gerar o backup agora. Verifique os logs do servidor.',
            'backup_failed',
            500,
        )


@api_v1_bp.get('/settings/export/<export_type>')
@api_auth_required
@limiter.limit(
    configured_limit('RATELIMIT_EXPORT', '20 per hour'),
    key_func=authenticated_identity_key,
    override_defaults=False,
)
def api_export_settings_data(export_type):
    try:
        api_require_export_permission()
        normalized_export_type = (export_type or '').strip().lower()
        export_definition = API_EXPORT_DEFINITIONS.get(normalized_export_type)
        if export_definition is None:
            raise ApiAuthError(
                'Tipo de exportação inválido.',
                'invalid_export_type',
                422,
                'export_type',
            )

        with api_tenant_database(g.api_user) as tenant_db:
            rows = export_definition['rows'](tenant_db)

        record_audit_event(
            'data_exported',
            'export',
            None,
            f'Exportação de {export_definition["label"]} realizada pelo aplicativo Windows.',
            new_values={
                'export_type': normalized_export_type,
                'rows': len(rows),
                'client': 'windows_native',
            },
            company_id=g.api_user.company_id,
            user=g.api_user,
            db_session=db.session,
        )
        db.session.commit()
        return api_csv_export_response(normalized_export_type, export_definition['headers'], rows)
    except ApiAuthError as error:
        db.session.rollback()
        return api_auth_error_response(error)


@api_v1_bp.post('/settings/import/products')
@api_auth_required
@limiter.limit(
    configured_limit('RATELIMIT_IMPORT', '5 per hour'),
    key_func=authenticated_identity_key,
    override_defaults=False,
)
def api_import_settings_products():
    try:
        api_require_product_import_permission()
        file_storage = request.files.get('spreadsheet') or request.files.get('file')
        if not file_storage or not file_storage.filename:
            raise ApiAuthError(
                'Envie uma planilha CSV ou XLSX para importar.',
                'file_required',
                422,
                'spreadsheet',
            )

        rows = api_read_product_import_rows(file_storage)
        with api_tenant_database(g.api_user) as tenant_db:
            summary = api_import_products_from_rows(rows, tenant_db, g.api_user)

        record_audit_event(
            'products_imported',
            'product',
            None,
            (
                'Importação pelo aplicativo Windows concluída: '
                f'{summary["created"]} criado(s), {summary["updated"]} atualizado(s), '
                f'{summary["skipped"]} ignorado(s), {summary["movements"]} movimentação(ões).'
            ),
            new_values={
                **summary,
                'client': 'windows_native',
                'file_name': file_storage.filename,
            },
            company_id=g.api_user.company_id,
            user=g.api_user,
            db_session=db.session,
        )
        db.session.commit()
        return api_success(summary)
    except ApiAuthError as error:
        db.session.rollback()
        return api_auth_error_response(error)
    except (ValueError, UnicodeDecodeError, zipfile.BadZipFile, ElementTree.ParseError) as error:
        db.session.rollback()
        return api_failure(
            str(error) or 'Não foi possível ler a planilha.',
            'invalid_import_file',
            422,
            'spreadsheet',
        )
    except (IntegrityError, StockMovementError):
        db.session.rollback()
        current_app.logger.exception('Failed to import products from Windows client.')
        return api_failure(
            'A planilha possui dados duplicados ou inválidos.',
            'invalid_import_data',
            422,
            'spreadsheet',
        )
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Unexpected product import failure from Windows client.')
        return api_failure(
            'Não foi possível importar a planilha agora. Verifique os logs do servidor.',
            'import_failed',
            500,
            'spreadsheet',
        )


@api_v1_bp.get('/settings/team')
@api_auth_required
def api_settings_team():
    try:
        api_require_team_permission()
        search = (request.args.get('search') or '').strip()
        query = User.query.filter_by(company_id=g.api_user.company_id)
        if search:
            pattern = f'%{search}%'
            query = query.filter(or_(
                User.username.ilike(pattern),
                User.first_name.ilike(pattern),
                User.last_name.ilike(pattern),
                User.email.ilike(pattern),
                User.cpf.ilike(pattern),
            ))
        users = query.order_by(User.username.asc(), User.id.asc()).all()
        return api_success({
            'employees': [api_employee_data(user) for user in users],
            'roles': api_role_options(),
            'permissions': api_permission_options(),
        })
    except ApiAuthError as error:
        return api_auth_error_response(error)


@api_v1_bp.post('/settings/team')
@api_auth_required
def api_create_employee():
    try:
        api_require_team_permission()
        payload = json_object_body()
        username = json_text(payload, 'username', required=True, max_length=80)
        password = payload.get('password')
        first_name = json_text(payload, 'first_name', max_length=120)
        last_name = json_text(payload, 'last_name', max_length=120)
        cpf = json_text(payload, 'cpf', max_length=20)
        email = json_text(payload, 'email', max_length=255)
        phone = json_text(payload, 'phone', max_length=40)
        role = json_employee_role(payload)

        if not isinstance(password, str) or len(password) < 6:
            raise ApiAuthError(
                'A senha do funcionário deve ter pelo menos 6 caracteres.',
                'password_too_short',
                422,
                'password',
            )
        if User.query.filter(func.lower(User.username) == username.casefold()).first():
            raise ApiAuthError(
                'Já existe um usuário com este login.',
                'username_exists',
                409,
                'username',
            )
        validate_employee_email(email)
        if company_cpf_exists_api(g.api_user.company_id, cpf):
            raise ApiAuthError(
                'Já existe um funcionário com este CPF nesta adega.',
                'cpf_exists',
                409,
                'cpf',
            )

        employee = User(
            username=username,
            first_name=first_name,
            last_name=last_name,
            cpf=cpf,
            email=email,
            phone=phone,
            role=role,
            company_id=g.api_user.company_id,
            is_active=True,
            email_verified=True,
            email_verified_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        apply_role_permissions_api(employee, role)
        employee.set_password(password)
        db.session.add(employee)
        db.session.flush()
        record_audit_event(
            'employee_created',
            'user',
            employee.id,
            f'Funcionário {employee.username} contratado pelo aplicativo Windows.',
            new_values=api_employee_data(employee),
            company_id=g.api_user.company_id,
            user=g.api_user,
            db_session=db.session,
        )
        db.session.commit()
        return api_success(api_employee_data(employee), 201)
    except ApiAuthError as error:
        db.session.rollback()
        return api_auth_error_response(error)


@api_v1_bp.put('/settings/team/<int:user_id>')
@api_auth_required
def api_update_employee(user_id):
    try:
        api_require_team_permission()
        payload = json_object_body()
        employee = User.query.filter_by(id=user_id, company_id=g.api_user.company_id).first()
        if not employee:
            raise ApiAuthError(
                'Funcionário não encontrado.',
                'employee_not_found',
                404,
            )

        old_values = api_employee_data(employee)
        first_name = json_text(payload, 'first_name', max_length=120)
        last_name = json_text(payload, 'last_name', max_length=120)
        cpf = json_text(payload, 'cpf', max_length=20)
        email = json_text(payload, 'email', max_length=255)
        phone = json_text(payload, 'phone', max_length=40)
        role = json_employee_role(payload)
        is_active = bool(payload.get('is_active', True))

        validate_employee_email(email)
        if company_cpf_exists_api(g.api_user.company_id, cpf, employee.id):
            raise ApiAuthError(
                'Já existe um funcionário com este CPF nesta adega.',
                'cpf_exists',
                409,
                'cpf',
            )
        if employee.id == g.api_user.id and employee.role == 'admin':
            role = 'admin'
            is_active = True

        employee.first_name = first_name
        employee.last_name = last_name
        employee.cpf = cpf
        employee.email = email
        employee.phone = phone
        employee.role = role
        employee.is_active = is_active
        apply_role_permissions_api(employee, role)
        record_audit_event(
            'employee_updated',
            'user',
            employee.id,
            f'Funcionário {employee.username} atualizado pelo aplicativo Windows.',
            old_values=old_values,
            new_values=api_employee_data(employee),
            company_id=g.api_user.company_id,
            user=g.api_user,
            db_session=db.session,
        )
        db.session.commit()
        return api_success(api_employee_data(employee))
    except ApiAuthError as error:
        db.session.rollback()
        return api_auth_error_response(error)


@api_v1_bp.get('/dashboard/summary')
@api_auth_required
def api_dashboard_summary():
    try:
        with api_tenant_database(g.api_user) as tenant_db:
            snapshot = build_dashboard_snapshot(
                tenant_db,
                g.api_user.company_id,
                can_view_reports=g.api_user.has_permission('can_view_reports'),
                can_manage_payables=g.api_user.has_permission('can_manage_payables'),
            )
        return api_success(snapshot)
    except ApiAuthError as error:
        return api_auth_error_response(error)


@api_v1_bp.get('/reports/summary')
@api_permission_required('can_view_reports')
def api_reports_summary():
    try:
        requested_period = (request.args.get('period') or 'daily').strip().casefold()
        chart_metric = (request.args.get('chart_metric') or 'revenue').strip().casefold()
        start_arg = parse_report_date_argument('start_date')
        end_arg = parse_report_date_argument('end_date')
        period, start, end, start_datetime, end_datetime, label = api_report_period_range(
            requested_period,
            start_arg,
            end_arg,
        )

        with api_tenant_database(g.api_user) as tenant_db:
            sales = (
                tenant_db.query(Sale)
                .options(
                    selectinload(Sale.payments),
                    selectinload(Sale.items).selectinload(SaleItem.product),
                )
                .filter(
                    Sale.company_id == g.api_user.company_id,
                    Sale.valid_filter(),
                    Sale.created_at >= start_datetime,
                    Sale.created_at < end_datetime,
                )
                .order_by(Sale.created_at.asc(), Sale.id.asc())
                .all()
            )

        report = api_build_sales_report(sales)
        chart = api_build_sales_chart(period, start, end, sales, chart_metric)
        return api_success({
            'period': period,
            'period_label': label,
            'start_date': start.isoformat(),
            'end_date': end.isoformat(),
            'chart_metric': chart['metric'],
            **report,
            'chart': chart,
        })
    except ApiAuthError as error:
        return api_auth_error_response(error)


@api_v1_bp.get('/reports/products')
@api_permission_required('can_view_reports')
def api_reports_products():
    try:
        requested_period = (request.args.get('period') or 'daily').strip().casefold()
        start_arg = parse_report_date_argument('start_date')
        end_arg = parse_report_date_argument('end_date')
        period, start, end, start_datetime, end_datetime, label = api_report_period_range(
            requested_period,
            start_arg,
            end_arg,
        )
        search = (request.args.get('q') or '').strip()[:180]
        sort = (request.args.get('sort') or 'quantity_desc').strip()[:40]
        page = positive_integer_argument('page', 1, maximum=100000)
        per_page = positive_integer_argument('per_page', 25, maximum=100)
        category_id = 0
        product_id = 0
        if (request.args.get('category_id') or '').strip():
            category_id = positive_integer_argument('category_id', 1, maximum=100000000)
        if (request.args.get('product_id') or '').strip():
            product_id = positive_integer_argument('product_id', 1, maximum=100000000)

        with api_tenant_database(g.api_user) as tenant_db:
            report = api_build_product_report(
                tenant_db,
                g.api_user.company_id,
                start_datetime,
                end_datetime,
                search=search,
                category_id=category_id,
                product_id=product_id,
                sort=sort,
                page=page,
                per_page=per_page,
            )

        return api_success({
            'period': period,
            'period_label': label,
            'start_date': start.isoformat(),
            'end_date': end.isoformat(),
            'search': search,
            'category_id': category_id,
            'product_id': product_id,
            **report,
        })
    except ApiAuthError as error:
        return api_auth_error_response(error)


def audit_log_data(log):
    return {
        'id': log.id,
        'created_at': utc_isoformat(log.created_at),
        'user_id': log.user_id,
        'user_name': log.user_name or 'Sistema',
        'user_role': log.user_role or '',
        'action': log.action,
        'action_label': audit_action_label(log.action),
        'entity_type': log.entity_type,
        'entity_label': entity_label(log.entity_type),
        'entity_id': log.entity_id,
        'description': log.description or '',
        'old_values': log.old_values or '',
        'new_values': log.new_values or '',
        'ip_address': log.ip_address or '',
        'user_agent': log.user_agent or '',
        'request_id': log.request_id or '',
        'route': log.route or '',
        'http_method': log.http_method or '',
    }


def audit_filter_options(values, label_factory=None):
    options = []
    for value in values:
        if not value:
            continue
        options.append({
            'value': value,
            'label': label_factory(value) if label_factory else value,
        })
    return options


def audit_user_options(users):
    return [
        {
            'id': user.id,
            'username': user.username,
            'label': user.username,
        }
        for user in users
    ]


@api_v1_bp.get('/audit/logs')
@api_permission_required('can_view_audit_logs')
def api_audit_logs():
    try:
        page = positive_integer_argument('page', 1, maximum=100000)
        per_page = positive_integer_argument('per_page', 30, maximum=100)
        search = (request.args.get('q') or '').strip()[:180]
        user_id = 0
        if (request.args.get('user_id') or '').strip():
            user_id = positive_integer_argument('user_id', 1, maximum=100000000)
        action = (request.args.get('action') or 'all').strip()[:80]
        entity_type = (request.args.get('entity_type') or 'all').strip()[:80]
        http_method = (request.args.get('http_method') or 'all').strip().upper()[:10]
        start_date = parse_optional_query_date_argument('start_date')
        end_date = parse_optional_query_date_argument('end_date')
        if start_date and end_date and end_date < start_date:
            start_date, end_date = end_date, start_date

        with api_tenant_database(g.api_user) as tenant_db:
            base_query = tenant_db.query(AuditLog).filter(AuditLog.company_id == g.api_user.company_id)
            if search:
                pattern = f'%{search}%'
                base_query = base_query.filter(or_(
                    AuditLog.description.ilike(pattern),
                    AuditLog.user_name.ilike(pattern),
                    AuditLog.action.ilike(pattern),
                    AuditLog.entity_type.ilike(pattern),
                    AuditLog.request_id.ilike(pattern),
                    AuditLog.route.ilike(pattern),
                ))
            if user_id > 0:
                base_query = base_query.filter(AuditLog.user_id == user_id)
            if action != 'all':
                base_query = base_query.filter(AuditLog.action == action)
            if entity_type != 'all':
                base_query = base_query.filter(AuditLog.entity_type == entity_type)
            if http_method != 'ALL':
                base_query = base_query.filter(AuditLog.http_method == http_method)
            if start_date:
                base_query = base_query.filter(AuditLog.created_at >= datetime.combine(start_date, time.min))
            if end_date:
                base_query = base_query.filter(AuditLog.created_at <= datetime.combine(end_date, time.max))

            total = base_query.count()
            total_pages = max((total + per_page - 1) // per_page, 1) if total else 0
            if total_pages and page > total_pages:
                page = total_pages

            logs = (
                base_query
                .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
                .offset((page - 1) * per_page)
                .limit(per_page)
                .all()
            )
            users_count = (
                base_query
                .with_entities(AuditLog.user_id)
                .filter(AuditLog.user_id.isnot(None))
                .distinct()
                .count()
            )
            actions_count = (
                base_query
                .with_entities(AuditLog.action)
                .distinct()
                .count()
            )
            actions = [
                value for (value,) in (
                    tenant_db.query(AuditLog.action)
                    .filter(AuditLog.company_id == g.api_user.company_id)
                    .distinct()
                    .order_by(AuditLog.action.asc())
                    .all()
                )
            ]
            entities = [
                value for (value,) in (
                    tenant_db.query(AuditLog.entity_type)
                    .filter(AuditLog.company_id == g.api_user.company_id)
                    .distinct()
                    .order_by(AuditLog.entity_type.asc())
                    .all()
                )
            ]
            methods = [
                value for (value,) in (
                    tenant_db.query(AuditLog.http_method)
                    .filter(AuditLog.company_id == g.api_user.company_id)
                    .distinct()
                    .order_by(AuditLog.http_method.asc())
                    .all()
                )
            ]
            users = (
                tenant_db.query(User)
                .filter(User.company_id == g.api_user.company_id)
                .order_by(User.username.asc())
                .all()
            )

        return api_success({
            'items': [audit_log_data(log) for log in logs],
            'pagination': {
                'page': page if total else 0,
                'per_page': per_page,
                'total': total,
                'total_pages': total_pages,
            },
            'summary': {
                'count': total,
                'users': users_count,
                'actions': actions_count,
            },
            'users': audit_user_options(users),
            'action_options': audit_filter_options(actions, audit_action_label),
            'entity_options': audit_filter_options(entities, entity_label),
            'method_options': audit_filter_options(methods),
        })
    except ApiAuthError as error:
        return api_auth_error_response(error)


def api_tenant_payable_or_error(tenant_db, payable_id):
    payable = (
        tenant_db.query(Payable)
        .filter(
            Payable.id == payable_id,
            Payable.company_id == g.api_user.company_id,
        )
        .first()
    )
    if payable is None:
        raise ApiAuthError(
            'Conta a pagar não encontrada.',
            'payable_not_found',
            404,
            'payable_id',
        )
    return payable


@api_v1_bp.get('/payables')
@api_permission_required('can_manage_payables')
def api_payables():
    try:
        status_filter = (request.args.get('status') or 'open').strip().casefold()
        if status_filter not in {'open', 'paid', 'all', 'overdue', 'due_today', 'near_due'}:
            raise ApiAuthError(
                'Status de conta a pagar inválido.',
                'invalid_query_parameter',
                422,
                'status',
            )
        search = (request.args.get('q') or '').strip()[:160]
        category = (request.args.get('category') or 'all').strip()
        start_date = parse_optional_query_date_argument('start_date')
        end_date = parse_optional_query_date_argument('end_date')
        if start_date and end_date and end_date < start_date:
            raise ApiAuthError(
                'A data final não pode ser anterior à data inicial.',
                'invalid_date_range',
                422,
                'end_date',
            )

        with api_tenant_database(g.api_user) as tenant_db:
            snapshot = payable_snapshot(
                tenant_db,
                g.api_user.company_id,
                status_filter,
                search,
                category,
                start_date,
                end_date,
            )
        return api_success(snapshot)
    except ApiAuthError as error:
        return api_auth_error_response(error)


@api_v1_bp.post('/payables')
@api_permission_required('can_manage_payables')
def api_create_payable():
    try:
        payload = json_object_body()
        description = json_text(payload, 'description', required=True, max_length=180)
        category = json_text(payload, 'category', required=False, max_length=80) or 'Outros'
        if category not in PAYABLE_CATEGORIES:
            category = 'Outros'
        try:
            amount = parse_money_decimal(payload.get('amount'), positive=True)
        except ValueError as error:
            raise ApiAuthError(
                'O valor da conta precisa ser monetário, maior que zero e estar no intervalo permitido.',
                'invalid_money',
                422,
                'amount',
            ) from error
        due_date = json_required_date(payload, 'due_date')
        notes = json_text(payload, 'notes', required=False, max_length=2000)

        with api_tenant_database(g.api_user) as tenant_db:
            try:
                payable = Payable(
                    company_id=g.api_user.company_id,
                    description=description,
                    category=category,
                    amount=amount,
                    due_date=due_date,
                    notes=notes,
                )
                tenant_db.add(payable)
                tenant_db.flush()
                record_audit_event(
                    'payable_created',
                    'payable',
                    payable.id,
                    f'Conta "{description}" cadastrada pelo aplicativo Windows.',
                    new_values={
                        'description': description,
                        'category': category,
                        'amount': money_json(amount),
                        'due_date': due_date.isoformat(),
                    },
                    company_id=g.api_user.company_id,
                    user=g.api_user,
                    db_session=tenant_db,
                )
                tenant_db.commit()
                response_data = payable_data(payable)
            except Exception:
                tenant_db.rollback()
                raise
        return api_success(response_data, 201)
    except ApiAuthError as error:
        return api_auth_error_response(error)
    except IntegrityError:
        current_app.logger.exception('Falha de integridade ao cadastrar conta a pagar.')
        return api_failure(
            'Não foi possível cadastrar a conta. Atualize os dados e tente novamente.',
            'payable_integrity_error',
            409,
        )


@api_v1_bp.post('/payables/<int:payable_id>/pay')
@api_permission_required('can_manage_payables')
def api_pay_payable(payable_id):
    try:
        with api_tenant_database(g.api_user) as tenant_db:
            try:
                payable = api_tenant_payable_or_error(tenant_db, payable_id)
                if not payable.paid:
                    payable.paid = True
                    payable.paid_at = datetime.now(timezone.utc)
                    record_audit_event(
                        'payable_paid',
                        'payable',
                        payable.id,
                        f'Conta "{payable.description}" marcada como paga pelo aplicativo Windows.',
                        new_values={
                            'paid': True,
                            'paid_at': payable.paid_at.isoformat(),
                        },
                        company_id=g.api_user.company_id,
                        user=g.api_user,
                        db_session=tenant_db,
                    )
                    sync_operational_notifications(tenant_db, g.api_user.company_id)
                    tenant_db.commit()
                response_data = payable_data(payable)
            except Exception:
                tenant_db.rollback()
                raise
        return api_success(response_data)
    except ApiAuthError as error:
        return api_auth_error_response(error)


@api_v1_bp.post('/payables/<int:payable_id>/reopen')
@api_permission_required('can_manage_payables')
def api_reopen_payable(payable_id):
    try:
        with api_tenant_database(g.api_user) as tenant_db:
            try:
                payable = api_tenant_payable_or_error(tenant_db, payable_id)
                if payable.paid:
                    previous_paid_at = payable.paid_at.isoformat() if payable.paid_at else None
                    payable.paid = False
                    payable.paid_at = None
                    record_audit_event(
                        'payable_reopened',
                        'payable',
                        payable.id,
                        f'Conta "{payable.description}" reaberta pelo aplicativo Windows.',
                        old_values={'paid': True, 'paid_at': previous_paid_at},
                        new_values={'paid': False, 'paid_at': None},
                        company_id=g.api_user.company_id,
                        user=g.api_user,
                        db_session=tenant_db,
                    )
                    sync_operational_notifications(tenant_db, g.api_user.company_id)
                    tenant_db.commit()
                response_data = payable_data(payable)
            except Exception:
                tenant_db.rollback()
                raise
        return api_success(response_data)
    except ApiAuthError as error:
        return api_auth_error_response(error)


@api_v1_bp.get('/cash-registers/summary')
@api_permission_required('can_manage_cash_register')
def api_cash_register_summary():
    try:
        with api_tenant_database(g.api_user) as tenant_db:
            snapshot = build_cash_register_snapshot(
                tenant_db,
                g.api_user.company_id,
                can_view_financials=g.api_user.has_permission('can_view_reports'),
            )
        return api_success(snapshot)
    except ApiAuthError as error:
        return api_auth_error_response(error)


def api_cash_register_detail_data(tenant_db, cash_register, can_view_financials):
    snapshot = build_cash_register_snapshot(
        tenant_db,
        g.api_user.company_id,
        can_view_financials=can_view_financials,
        recent_limit=50,
    )
    cash_register_record = snapshot['current_register']
    if cash_register_record is None or cash_register_record['id'] != cash_register.id:
        cash_register_record = next(
            (
                item
                for item in snapshot['recent_registers']
                if item['id'] == cash_register.id
            ),
            None,
        )

    sales = sorted(
        cash_register.sales,
        key=lambda sale: (sale.created_at or datetime.min, sale.id or 0),
    )
    user_ids = {sale.user_id for sale in sales if sale.user_id}
    if cash_register.user_id:
        user_ids.add(cash_register.user_id)
    users = {
        user.id: user.full_name or user.username
        for user in tenant_db.query(User).filter(
            User.company_id == g.api_user.company_id,
            User.id.in_(user_ids),
        ).all()
    } if user_ids else {}

    if cash_register_record is None:
        sales_total = sum((money_decimal(sale.final_amount) for sale in sales), Decimal('0.00'))
        opening_amount = money_decimal(cash_register.opening_amount)
        closing_amount = money_decimal(cash_register.closing_amount)
        expected_amount = opening_amount + sales_total
        payment_totals = {}
        for sale in sales:
            for payment in sale.payments:
                payment_totals[payment.method] = (
                    payment_totals.get(payment.method, Decimal('0.00'))
                    + money_decimal(payment.amount)
                )
        cash_register_record = {
            'id': cash_register.id,
            'status': cash_register.status,
            'opened_at': timestamp_value(cash_register.opened_at),
            'closed_at': timestamp_value(cash_register.closed_at),
            'responsible_user': users.get(cash_register.user_id, 'Usuário não identificado'),
            'sales_count': len(sales),
            'opening_amount': money_value(opening_amount) if can_view_financials else None,
            'closing_amount': (
                money_value(closing_amount)
                if can_view_financials and cash_register.status == 'closed'
                else None
            ),
            'sales_total': money_value(sales_total) if can_view_financials else None,
            'expected_amount': money_value(expected_amount) if can_view_financials else None,
            'difference': (
                money_value(closing_amount - expected_amount)
                if can_view_financials and cash_register.status == 'closed'
                else None
            ),
            'payment_totals': [
                {
                    'method': method,
                    'label': label,
                    'amount': money_value(payment_totals.get(method, Decimal('0.00'))),
                }
                for method, label in PAYMENT_METHODS.items()
            ] if can_view_financials else [],
        }

    def sale_payment_data(payment):
        return {
            'method': payment.method,
            'label': PAYMENT_METHODS.get(payment.method, payment.method or 'Pagamento'),
            'amount': float(payment.amount or 0) if can_view_financials else None,
        }

    def sale_item_data(item):
        product_name = item.product.name if item.product else f'Produto #{item.product_id}'
        return {
            'product_id': item.product_id,
            'product_name': product_name,
            'quantity': int(item.quantity or 0),
            'unit_price': float(item.unit_price or 0) if can_view_financials else None,
            'total_price': float(item.total_price or 0) if can_view_financials else None,
        }

    timeline = []
    running_balance = money_decimal(cash_register.opening_amount)
    for sale in sales:
        sale_datetime = sale.created_at
        local_sale_datetime = to_business_datetime(sale_datetime)
        payments = [sale_payment_data(payment) for payment in sale.payments]
        payment_labels = [payment['label'] for payment in payments]
        balance_before_sale = running_balance
        running_balance += money_decimal(sale.final_amount)
        timeline.append({
            'id': sale.id,
            'number': f'#{sale.id}',
            'created_at': utc_isoformat(sale_datetime),
            'date': local_sale_datetime.strftime('%d/%m/%Y') if local_sale_datetime else '',
            'time': local_sale_datetime.strftime('%H:%M') if local_sale_datetime else '',
            'seller': users.get(sale.user_id, 'Usuário não identificado'),
            'payment_status': sale.payment_status,
            'status': sale.status or 'completed',
            'is_cancelled': sale.is_cancelled,
            'cancelled_at': timestamp_value(sale.cancelled_at),
            'cancelled_by_user_id': sale.cancelled_by_user_id,
            'cancellation_reason': sale.cancellation_reason or '',
            'payments_text': ', '.join(payment_labels) if payment_labels else 'Sem pagamento',
            'total_amount': float(sale.total_amount or 0) if can_view_financials else None,
            'discount_amount': float(sale.discount_amount or 0) if can_view_financials else None,
            'final_amount': float(sale.final_amount or 0) if can_view_financials else None,
            'balance_before_sale': (
                money_value(balance_before_sale) if can_view_financials else None
            ),
            'balance_after_sale': (
                money_value(running_balance) if can_view_financials else None
            ),
            'payments': payments,
            'items': [sale_item_data(item) for item in sale.items],
        })

    return {
        'permissions': snapshot['permissions'],
        'cash_register': cash_register_record,
        'timeline': timeline,
    }


@api_v1_bp.get('/cash-registers/<int:cash_register_id>')
@api_permission_required('can_manage_cash_register')
def api_cash_register_detail(cash_register_id):
    try:
        can_view_financials = g.api_user.has_permission('can_view_reports')
        with api_tenant_database(g.api_user) as tenant_db:
            cash_register = (
                tenant_db.query(CashRegister)
                .options(
                    selectinload(CashRegister.sales).selectinload(Sale.items).selectinload(SaleItem.product),
                    selectinload(CashRegister.sales).selectinload(Sale.payments),
                )
                .filter(
                    CashRegister.id == cash_register_id,
                    CashRegister.company_id == g.api_user.company_id,
                )
                .first()
            )
            if cash_register is None:
                raise ApiAuthError(
                    'Caixa não encontrado.',
                    'cash_register_not_found',
                    404,
                    'cash_register_id',
                )
            data = api_cash_register_detail_data(
                tenant_db,
                cash_register,
                can_view_financials,
            )
        return api_success(data)
    except ApiAuthError as error:
        return api_auth_error_response(error)


@api_v1_bp.post('/cash-registers/open')
@api_permission_required('can_manage_cash_register')
def api_open_cash_register():
    try:
        payload = json_object_body()
        opening_amount = json_money(payload, 'opening_amount')
        with api_tenant_database(g.api_user) as tenant_db:
            try:
                open_cash_register(
                    tenant_db,
                    g.api_user.company_id,
                    g.api_user,
                    opening_amount,
                )
                tenant_db.commit()
                snapshot = build_cash_register_snapshot(
                    tenant_db,
                    g.api_user.company_id,
                    can_view_financials=g.api_user.has_permission('can_view_reports'),
                )
            except Exception:
                tenant_db.rollback()
                raise
        return api_success(snapshot, 201)
    except ApiAuthError as error:
        return api_auth_error_response(error)
    except CashRegisterOperationError as error:
        return api_failure(
            error.message,
            error.code,
            error.status_code,
            error.field,
        )


@api_v1_bp.post('/cash-registers/close')
@api_permission_required('can_manage_cash_register')
def api_close_cash_register():
    try:
        payload = json_object_body()
        cash_register_id = json_positive_integer(payload, 'cash_register_id')
        closing_amount = json_money(payload, 'closing_amount')
        can_view_financials = g.api_user.has_permission('can_view_reports')
        with api_tenant_database(g.api_user) as tenant_db:
            try:
                close_cash_register(
                    tenant_db,
                    g.api_user.company_id,
                    g.api_user,
                    cash_register_id,
                    closing_amount,
                    can_view_financials,
                    datetime.now(timezone.utc),
                )
                tenant_db.commit()
                snapshot = build_cash_register_snapshot(
                    tenant_db,
                    g.api_user.company_id,
                    can_view_financials=can_view_financials,
                )
            except Exception:
                tenant_db.rollback()
                raise
        return api_success(snapshot)
    except ApiAuthError as error:
        return api_auth_error_response(error)
    except CashRegisterOperationError as error:
        return api_failure(
            error.message,
            error.code,
            error.status_code,
            error.field,
        )


@api_v1_bp.post('/sales')
@api_permission_required('can_manage_sales')
def api_create_sale():
    try:
        payload = json_object_body()
        idempotency_key = sale_idempotency_key(payload)
        item_inputs = sale_line_inputs(payload)
        payment_inputs = sale_payment_inputs(payload)
        discount_amount = json_optional_money(payload, 'discount_amount')

        with api_tenant_database(g.api_user) as tenant_db:
            try:
                result = create_sale(
                    tenant_db,
                    g.api_user.company,
                    g.api_user,
                    item_inputs,
                    payment_inputs,
                    discount_amount,
                    idempotency_key,
                )
                was_already_processed = result.already_processed
                stock_warnings = result.stock_warnings
                tenant_db.commit()
            except IntegrityError:
                tenant_db.rollback()
                result = find_completed_sale_request(
                    tenant_db,
                    g.api_user.company_id,
                    idempotency_key,
                )
                if result is None:
                    raise SaleOperationError(
                        'Outra tentativa desta venda ainda está sendo processada. Tente novamente.',
                        'sale_request_conflict',
                        409,
                    )
                was_already_processed = True
                stock_warnings = result.stock_warnings
            except Exception:
                tenant_db.rollback()
                raise

            persisted_result = find_completed_sale_request(
                tenant_db,
                g.api_user.company_id,
                idempotency_key,
            )
            if persisted_result is None:
                raise SaleOperationError(
                    'A venda não pôde ser confirmada após a gravação.',
                    'sale_confirmation_failed',
                    500,
                )
            persisted_result.already_processed = was_already_processed
            persisted_result.stock_warnings = stock_warnings
            response_data = serialize_sale_result(persisted_result)

        return api_success(response_data, 200 if was_already_processed else 201)
    except ApiAuthError as error:
        return api_auth_error_response(error)
    except SaleOperationError as error:
        return api_failure(
            error.message,
            error.code,
            error.status_code,
            error.field,
        )


@api_v1_bp.get('/sales/<int:sale_id>')
@api_permission_required('can_manage_sales')
def api_sale_detail(sale_id):
    try:
        company_id = g.api_user.company_id
        with api_tenant_database(g.api_user) as tenant_db:
            sale = (
                tenant_db.query(Sale)
                .options(
                    selectinload(Sale.items).selectinload(SaleItem.product),
                    selectinload(Sale.payments),
                )
                .filter(
                    Sale.company_id == company_id,
                    Sale.id == sale_id,
                )
                .first()
            )
            if sale is None:
                return api_failure(
                    'Venda não encontrada.',
                    'sale_not_found',
                    404,
                )
            response_data = api_serialize_sale_receipt(sale)

        return api_success(response_data)
    except ApiAuthError as error:
        return api_auth_error_response(error)


@api_v1_bp.post('/sales/<int:sale_id>/cancel')
@api_permission_required('can_cancel_sales')
def api_cancel_sale(sale_id):
    try:
        payload = json_object_body()
        reason = json_text(payload, 'reason', required=True, max_length=500)
        with api_tenant_database(g.api_user) as tenant_db:
            try:
                result = cancel_sale(
                    tenant_db,
                    g.api_user.company,
                    g.api_user,
                    sale_id,
                    reason,
                )
                tenant_db.commit()
                response_data = api_serialize_sale_receipt(result.sale)
                response_data['stock_movements'] = [
                    {
                        'id': movement.id,
                        'product_id': movement.product_id,
                        'quantity': movement.quantity,
                        'previous_stock': movement.previous_stock,
                        'new_stock': movement.new_stock,
                    }
                    for movement in result.stock_movements
                ]
                response_data['cash_register_was_closed'] = result.cash_register_was_closed
            except Exception:
                tenant_db.rollback()
                raise
        return api_success(response_data)
    except ApiAuthError as error:
        return api_auth_error_response(error)
    except SaleOperationError as error:
        return api_failure(error.message, error.code, error.status_code, error.field)


@api_v1_bp.get('/sales/today')
@api_permission_required('can_manage_sales')
def api_today_sales():
    try:
        company_id = g.api_user.company_id
        page = positive_integer_argument('page', 1, maximum=100000)
        per_page = positive_integer_argument('per_page', 30, maximum=100)
        with api_tenant_database(g.api_user) as tenant_db:
            open_cash_register = (
                tenant_db.query(CashRegister)
                .filter(
                    CashRegister.company_id == company_id,
                    CashRegister.status == 'open',
                )
                .order_by(CashRegister.opened_at.desc(), CashRegister.id.desc())
                .first()
            )

            sales_query = (
                tenant_db.query(Sale)
                .options(selectinload(Sale.payments))
                .filter(Sale.company_id == company_id)
            )

            if open_cash_register:
                sales_query = sales_query.filter(
                    Sale.cash_register_id == open_cash_register.id,
                )
            else:
                today = datetime.now().date()
                start_at = datetime.combine(today, time.min)
                end_at = start_at + timedelta(days=1)
                sales_query = sales_query.filter(
                    Sale.created_at >= start_at,
                    Sale.created_at < end_at,
                )

            total = sales_query.count()
            sales = (
                sales_query
                .order_by(Sale.created_at.desc(), Sale.id.desc())
                .offset((page - 1) * per_page)
                .limit(per_page)
                .all()
            )
            user_ids = {sale.user_id for sale in sales if sale.user_id}
            users = {}
            if user_ids:
                users = {
                    user.id: user
                    for user in tenant_db.query(User).filter(User.id.in_(user_ids)).all()
                }

            cash_register_id = open_cash_register.id if open_cash_register else None
            sales_data = [
                {
                    'id': sale.id,
                    'created_at': timestamp_value(sale.created_at),
                    'final_amount': money_value(sale.final_amount),
                    'payment_status': sale.payment_status or 'pending',
                    'status': sale.status or 'completed',
                    'is_cancelled': sale.is_cancelled,
                    'user_name': (
                        users.get(sale.user_id).username
                        if sale.user_id in users
                        else 'Sistema'
                    ),
                    'payment_methods': [
                        PAYMENT_METHODS.get(payment.method, payment.method or 'Pagamento')
                        for payment in sale.payments
                    ],
                }
                for sale in sales
            ]

        return api_success({
            'cash_register_id': cash_register_id,
            'sales': sales_data,
            'page': page,
            'per_page': per_page,
            'total': total,
            'has_more': page * per_page < total,
        })
    except ApiAuthError as error:
        return api_auth_error_response(error)


@api_v1_bp.get('/catalog/categories')
@api_permission_required('can_view_products')
def api_catalog_categories():
    try:
        company_id = g.api_user.company_id
        search = (request.args.get('q') or '').strip()
        if len(search) > 120:
            raise ApiAuthError(
                'A busca de categoria excede o tamanho permitido.',
                'query_too_long',
                422,
                'q',
            )

        with api_tenant_database(g.api_user) as tenant_db:
            query = (
                tenant_db.query(Category, func.count(Product.id))
                .outerjoin(
                    Product,
                    and_(
                        Product.category_id == Category.id,
                        Product.company_id == company_id,
                    ),
                )
                .filter(Category.company_id == company_id)
            )
            if search:
                query = query.filter(Category.name.ilike(f'%{search}%'))
            categories = (
                query
                .group_by(Category.id, Category.name, Category.company_id, Category.created_at)
                .order_by(func.lower(Category.name), Category.id)
                .all()
            )

        return api_success({
            'items': [
                catalog_category_data(category, product_count)
                for category, product_count in categories
            ],
            'total': len(categories),
        })
    except ApiAuthError as error:
        return api_auth_error_response(error)


@api_v1_bp.post('/catalog/categories')
@api_permission_required('can_manage_categories')
def api_create_catalog_category():
    try:
        payload = json_object_body()
        category_input = category_input_from_payload(payload)
        with api_tenant_database(g.api_user) as tenant_db:
            try:
                category = create_category(
                    tenant_db,
                    g.api_user.company,
                    g.api_user,
                    category_input,
                )
                tenant_db.commit()
                response_data = catalog_category_data(category, 0)
            except Exception:
                tenant_db.rollback()
                raise

        return api_success(response_data, 201)
    except ApiAuthError as error:
        return api_auth_error_response(error)
    except CategoryOperationError as error:
        return api_failure(
            error.message,
            error.code,
            error.status_code,
            error.field,
        )
    except IntegrityError:
        return api_failure(
            'Já existe uma categoria com este nome nesta adega.',
            'category_already_exists',
            409,
            'name',
        )


@api_v1_bp.put('/catalog/categories/<int:category_id>')
@api_permission_required('can_manage_categories')
def api_update_catalog_category(category_id):
    try:
        payload = json_object_body()
        category_input = category_input_from_payload(payload)
        with api_tenant_database(g.api_user) as tenant_db:
            try:
                category = update_category(
                    tenant_db,
                    g.api_user.company,
                    g.api_user,
                    category_id,
                    category_input,
                )
                product_count = category_product_count(
                    tenant_db,
                    g.api_user.company_id,
                    category.id,
                )
                tenant_db.commit()
                response_data = catalog_category_data(category, product_count)
            except Exception:
                tenant_db.rollback()
                raise

        return api_success(response_data)
    except ApiAuthError as error:
        return api_auth_error_response(error)
    except CategoryOperationError as error:
        return api_failure(
            error.message,
            error.code,
            error.status_code,
            error.field,
        )
    except IntegrityError:
        return api_failure(
            'Já existe uma categoria com este nome nesta adega.',
            'category_already_exists',
            409,
            'name',
        )


@api_v1_bp.delete('/catalog/categories/<int:category_id>')
@api_permission_required('can_manage_categories')
def api_delete_catalog_category(category_id):
    try:
        with api_tenant_database(g.api_user) as tenant_db:
            try:
                deleted_category_id = delete_category(
                    tenant_db,
                    g.api_user.company,
                    g.api_user,
                    category_id,
                )
                tenant_db.commit()
            except Exception:
                tenant_db.rollback()
                raise

        return api_success({
            'id': deleted_category_id,
            'deleted': True,
        })
    except ApiAuthError as error:
        return api_auth_error_response(error)
    except CategoryOperationError as error:
        return api_failure(
            error.message,
            error.code,
            error.status_code,
            error.field,
        )


@api_v1_bp.get('/catalog/products')
@api_permission_required('can_view_products')
def api_catalog_products():
    try:
        page = positive_integer_argument('page', 1)
        per_page = positive_integer_argument('per_page', 30, maximum=100)
        search = (request.args.get('q') or '').strip()
        if len(search) > 120:
            raise ApiAuthError(
                'A busca de produto excede o tamanho permitido.',
                'query_too_long',
                422,
                'q',
            )
        barcode = normalize_product_barcode(request.args.get('barcode'))
        if 'barcode' in request.args and not barcode:
            raise ApiAuthError(
                'Informe o código de barras para a busca exata.',
                'invalid_query_parameter',
                422,
                'barcode',
            )
        if len(barcode) > 80:
            raise ApiAuthError(
                'O código de barras excede o tamanho permitido.',
                'query_too_long',
                422,
                'barcode',
            )

        category_id = None
        if (request.args.get('category_id') or '').strip():
            category_id = positive_integer_argument('category_id', 1)

        active_filter = (request.args.get('active') or 'all').strip().casefold()
        if active_filter not in {'all', 'active', 'inactive'}:
            raise ApiAuthError(
                'O filtro de status informado é inválido.',
                'invalid_query_parameter',
                422,
                'active',
            )

        stock_filter = (request.args.get('stock') or 'all').strip().casefold()
        if stock_filter not in {'all', 'available', 'low', 'out'}:
            raise ApiAuthError(
                'O filtro de estoque informado é inválido.',
                'invalid_query_parameter',
                422,
                'stock',
            )
        min_price = optional_money_argument('min_price')
        max_price = optional_money_argument('max_price')
        if min_price is not None and max_price is not None and min_price > max_price:
            raise ApiAuthError(
                'O preço mínimo não pode ser maior que o preço máximo.',
                'invalid_query_parameter',
                422,
                'min_price',
            )

        sort = (request.args.get('sort') or 'name').strip().casefold()
        company_id = g.api_user.company_id
        include_cost = g.api_user.has_permission('can_manage_products')

        with api_tenant_database(g.api_user) as tenant_db:
            query = (
                tenant_db.query(Product)
                .options(
                    selectinload(Product.category),
                    selectinload(Product.kit_component),
                )
                .filter(Product.company_id == company_id)
            )
            if search:
                pattern = f'%{search}%'
                query = query.filter(or_(
                    Product.name.ilike(pattern),
                    Product.barcode.ilike(pattern),
                ))
            if barcode:
                query = query.filter(Product.barcode == barcode)
            if category_id is not None:
                query = query.filter(Product.category_id == category_id)
            if active_filter == 'active':
                query = query.filter(Product.active.is_(True))
            elif active_filter == 'inactive':
                query = query.filter(Product.active.is_(False))

            if stock_filter == 'available':
                query = query.filter(Product.stock_quantity > 0)
            elif stock_filter == 'out':
                query = query.filter(Product.stock_quantity <= 0)
            elif stock_filter == 'low':
                query = query.filter(
                    Product.min_stock_quantity > 0,
                    Product.stock_quantity >= 0,
                    Product.stock_quantity <= Product.min_stock_quantity,
                )
            if min_price is not None:
                query = query.filter(Product.sale_price >= min_price)
            if max_price is not None:
                query = query.filter(Product.sale_price <= max_price)

            ordering = {
                'name': (func.lower(Product.name), Product.id),
                'name_desc': (func.lower(Product.name).desc(), Product.id.desc()),
                'price': (Product.sale_price, func.lower(Product.name), Product.id),
                'price_desc': (Product.sale_price.desc(), func.lower(Product.name), Product.id),
                'stock': (Product.stock_quantity, func.lower(Product.name), Product.id),
                'stock_desc': (Product.stock_quantity.desc(), func.lower(Product.name), Product.id),
                'created_desc': (Product.created_at.desc(), Product.id.desc()),
                'created_asc': (Product.created_at, Product.id),
            }
            if sort not in ordering:
                raise ApiAuthError(
                    'A ordenação informada é inválida.',
                    'invalid_query_parameter',
                    422,
                    'sort',
                )

            total = query.order_by(None).count()
            products = (
                query
                .order_by(*ordering[sort])
                .offset((page - 1) * per_page)
                .limit(per_page)
                .all()
            )

        return api_success({
            'items': [catalog_product_data(product, include_cost) for product in products],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page,
            },
        })
    except ApiAuthError as error:
        return api_auth_error_response(error)


@api_v1_bp.post('/catalog/products')
@api_permission_required('can_manage_products')
def api_create_catalog_product():
    try:
        payload = json_object_body()
        product_input = product_input_from_payload(payload)
        with api_tenant_database(g.api_user) as tenant_db:
            try:
                product = create_product(
                    tenant_db,
                    g.api_user.company,
                    g.api_user,
                    product_input,
                )
                tenant_db.commit()
                response_data = catalog_product_data(product, include_cost=True)
            except IntegrityError:
                tenant_db.rollback()
                raise ProductOperationError(
                    'Não foi possível cadastrar o produto por conflito de dados.',
                    'product_conflict',
                    409,
                )
            except Exception:
                tenant_db.rollback()
                raise
        return api_success(response_data, 201)
    except ApiAuthError as error:
        return api_auth_error_response(error)
    except ProductOperationError as error:
        return api_failure(
            error.message,
            error.code,
            error.status_code,
            error.field,
        )


@api_v1_bp.put('/catalog/products/<int:product_id>')
@api_permission_required('can_manage_products')
def api_update_catalog_product(product_id):
    try:
        payload = json_object_body()
        product_input = product_input_from_payload(payload)
        with api_tenant_database(g.api_user) as tenant_db:
            try:
                product = update_product(
                    tenant_db,
                    g.api_user.company,
                    g.api_user,
                    product_id,
                    product_input,
                )
                tenant_db.commit()
                response_data = catalog_product_data(product, include_cost=True)
            except IntegrityError:
                tenant_db.rollback()
                raise ProductOperationError(
                    'Não foi possível atualizar o produto por conflito de dados.',
                    'product_conflict',
                    409,
                )
            except Exception:
                tenant_db.rollback()
                raise
        return api_success(response_data)
    except ApiAuthError as error:
        return api_auth_error_response(error)
    except ProductOperationError as error:
        return api_failure(
            error.message,
            error.code,
            error.status_code,
            error.field,
        )


@api_v1_bp.delete('/catalog/products/<int:product_id>')
@api_permission_required('can_manage_products')
def api_delete_catalog_product(product_id):
    try:
        with api_tenant_database(g.api_user) as tenant_db:
            try:
                deleted_product_id = delete_product(
                    tenant_db,
                    g.api_user.company,
                    g.api_user,
                    product_id,
                )
                tenant_db.commit()
            except Exception:
                tenant_db.rollback()
                raise

        return api_success({
            'id': deleted_product_id,
            'deleted': True,
        })
    except ApiAuthError as error:
        return api_auth_error_response(error)
    except ProductOperationError as error:
        return api_failure(
            error.message,
            error.code,
            error.status_code,
            error.field,
        )


@api_v1_bp.get('/stock/movements')
@api_permission_required('can_view_stock_movements')
def api_stock_movements():
    try:
        page = positive_integer_argument('page', 1)
        per_page = positive_integer_argument('per_page', 25, maximum=100)
        search = (request.args.get('q') or '').strip()[:120]
        category_id = request.args.get('category_id', '').strip()
        user_id = request.args.get('user_id', '').strip()
        movement_type = (request.args.get('movement_type') or 'all').strip()
        source_type = (request.args.get('source_type') or 'all').strip()
        start_date = parse_optional_query_date_argument('start_date')
        end_date = parse_optional_query_date_argument('end_date')
        if start_date and end_date and start_date > end_date:
            raise ApiAuthError(
                'A data inicial não pode ser posterior à data final.',
                'invalid_date_range',
                422,
                'start_date',
            )

        if movement_type != 'all' and movement_type not in MOVEMENT_TYPE_LABELS:
            raise ApiAuthError(
                'Tipo de movimentação inválido.',
                'invalid_query_parameter',
                422,
                'movement_type',
            )
        if source_type != 'all' and source_type not in SOURCE_TYPE_LABELS:
            raise ApiAuthError(
                'Origem de movimentação inválida.',
                'invalid_query_parameter',
                422,
                'source_type',
            )

        parsed_category_id = None
        if category_id:
            try:
                parsed_category_id = int(category_id)
            except ValueError as error:
                raise ApiAuthError(
                    'A categoria precisa ser um número inteiro.',
                    'invalid_query_parameter',
                    422,
                    'category_id',
                ) from error
            if parsed_category_id < 1:
                raise ApiAuthError(
                    'A categoria precisa ser maior que zero.',
                    'invalid_query_parameter',
                    422,
                    'category_id',
                )

        parsed_user_id = None
        if user_id:
            try:
                parsed_user_id = int(user_id)
            except ValueError as error:
                raise ApiAuthError(
                    'O responsável precisa ser um número inteiro.',
                    'invalid_query_parameter',
                    422,
                    'user_id',
                ) from error
            if parsed_user_id < 1:
                raise ApiAuthError(
                    'O responsável precisa ser maior que zero.',
                    'invalid_query_parameter',
                    422,
                    'user_id',
                )

        with api_tenant_database(g.api_user) as tenant_db:
            query = tenant_db.query(StockMovement).options(
                selectinload(StockMovement.product).selectinload(Product.category),
                selectinload(StockMovement.user),
            ).filter(StockMovement.company_id == g.api_user.company_id)

            summary_query = tenant_db.query(StockMovement).filter(
                StockMovement.company_id == g.api_user.company_id,
            )

            if search or parsed_category_id:
                query = query.join(Product, StockMovement.product_id == Product.id)
                summary_query = summary_query.join(Product, StockMovement.product_id == Product.id)
            if search:
                pattern = f'%{search}%'
                query = query.filter(or_(
                    Product.name.ilike(pattern),
                    StockMovement.reason.ilike(pattern),
                    StockMovement.notes.ilike(pattern),
                ))
                summary_query = summary_query.filter(or_(
                    Product.name.ilike(pattern),
                    StockMovement.reason.ilike(pattern),
                    StockMovement.notes.ilike(pattern),
                ))
            if parsed_category_id:
                query = query.filter(Product.category_id == parsed_category_id)
                summary_query = summary_query.filter(Product.category_id == parsed_category_id)
            if movement_type != 'all':
                query = query.filter(StockMovement.movement_type == movement_type)
                summary_query = summary_query.filter(StockMovement.movement_type == movement_type)
            if source_type != 'all':
                query = query.filter(StockMovement.source_type == source_type)
                summary_query = summary_query.filter(StockMovement.source_type == source_type)
            if parsed_user_id:
                query = query.filter(StockMovement.user_id == parsed_user_id)
                summary_query = summary_query.filter(StockMovement.user_id == parsed_user_id)
            if start_date:
                start_utc, _ = business_date_range_utc(start_date, start_date)
                query = query.filter(StockMovement.created_at >= start_utc)
                summary_query = summary_query.filter(StockMovement.created_at >= start_utc)
            if end_date:
                _, end_utc = business_date_range_utc(end_date, end_date)
                query = query.filter(StockMovement.created_at < end_utc)
                summary_query = summary_query.filter(StockMovement.created_at < end_utc)

            total = query.count()
            movements = query.order_by(
                StockMovement.created_at.desc(),
                StockMovement.id.desc(),
            ).offset((page - 1) * per_page).limit(per_page).all()
            total_pages = (total + per_page - 1) // per_page if total else 0

            entries = {'entry', 'adjustment_in', 'return', 'initial_stock', 'import'}
            exits = {'sale', 'adjustment_out'}
            summary = {
                'entries_quantity': int(summary_query.filter(
                    StockMovement.movement_type.in_(entries),
                ).with_entities(func.coalesce(func.sum(StockMovement.quantity), 0)).scalar() or 0),
                'exits_quantity': int(summary_query.filter(
                    StockMovement.movement_type.in_(exits),
                ).with_entities(func.coalesce(func.sum(StockMovement.quantity), 0)).scalar() or 0),
                'movement_count': int(summary_query.count() or 0),
                'product_count': int(summary_query.with_entities(
                    func.count(func.distinct(StockMovement.product_id)),
                ).scalar() or 0),
            }
            responsible_users = (
                tenant_db.query(User.id, User.username)
                .join(StockMovement, StockMovement.user_id == User.id)
                .filter(StockMovement.company_id == g.api_user.company_id)
                .distinct()
                .order_by(User.username.asc(), User.id.asc())
                .all()
            )
            include_cost = g.api_user.has_permission('can_view_reports')

        return api_success({
            'items': [stock_movement_data(movement, include_cost=include_cost) for movement in movements],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': total_pages,
            },
            'summary': summary,
            'movement_types': stock_filter_options(MOVEMENT_TYPE_LABELS),
            'source_types': stock_filter_options(SOURCE_TYPE_LABELS),
            'responsible_users': [
                {'value': str(user_id), 'label': username}
                for user_id, username in responsible_users
            ],
            'costs_visible': include_cost,
        })
    except ApiAuthError as error:
        return api_auth_error_response(error)


@api_v1_bp.post('/stock/entries')
@api_permission_required('can_manage_stock')
def api_create_stock_entry():
    try:
        payload = json_object_body()
        product_id = json_positive_integer(payload, 'product_id')
        quantity = json_positive_integer(payload, 'quantity')
        unit_cost = json_optional_money(payload, 'unit_cost')
        reason = json_text(payload, 'reason', required=False, max_length=180)
        notes = json_text(payload, 'notes', required=False, max_length=1000)
        update_cost = json_bool(payload, 'update_cost', default=False)

        with api_tenant_database(g.api_user) as tenant_db:
            product = tenant_db.query(Product).filter(
                Product.id == product_id,
                Product.company_id == g.api_user.company_id,
            ).first()
            if product is None:
                raise ApiAuthError(
                    'Produto não encontrado nesta adega.',
                    'product_not_found',
                    404,
                    'product_id',
                )
            try:
                if update_cost:
                    product.cost_price = float(unit_cost)
                movement = increase_stock(
                    tenant_db,
                    product,
                    quantity,
                    movement_type='entry',
                    source_type='manual',
                    user_id=g.api_user.id,
                    unit_cost=unit_cost,
                    reason=reason or 'Entrada manual de estoque',
                    notes=notes,
                )
                tenant_db.commit()
                response_data = stock_movement_data(
                    movement,
                    include_cost=g.api_user.has_permission('can_view_reports'),
                )
            except StockMovementError:
                tenant_db.rollback()
                raise
            except Exception:
                tenant_db.rollback()
                raise
        return api_success(response_data, 201)
    except ApiAuthError as error:
        return api_auth_error_response(error)
    except StockMovementError as error:
        return api_failure(str(error), 'stock_movement_error', 422)


@api_v1_bp.post('/stock/adjustments')
@api_permission_required('can_manage_stock')
def api_create_stock_adjustment():
    try:
        payload = json_object_body()
        product_id = json_positive_integer(payload, 'product_id')
        adjustment_mode = json_text(payload, 'adjustment_mode', required=False, max_length=20) or 'target'
        reason = json_text(payload, 'reason', required=True, max_length=180)
        notes = json_text(payload, 'notes', required=False, max_length=1000)

        with api_tenant_database(g.api_user) as tenant_db:
            product = tenant_db.query(Product).filter(
                Product.id == product_id,
                Product.company_id == g.api_user.company_id,
            ).first()
            if product is None:
                raise ApiAuthError(
                    'Produto não encontrado nesta adega.',
                    'product_not_found',
                    404,
                    'product_id',
                )

            if adjustment_mode == 'target':
                new_stock = json_integer(payload, 'target_stock')
            elif adjustment_mode == 'delta':
                direction = json_text(payload, 'direction', required=True, max_length=10)
                quantity = json_positive_integer(payload, 'quantity')
                if direction not in {'in', 'out'}:
                    raise ApiAuthError(
                        'A direção do ajuste precisa ser in ou out.',
                        'invalid_adjustment_direction',
                        422,
                        'direction',
                    )
                current_stock = int(product.stock_quantity or 0)
                new_stock = current_stock + quantity if direction == 'in' else current_stock - quantity
            else:
                raise ApiAuthError(
                    'Modo de ajuste inválido.',
                    'invalid_adjustment_mode',
                    422,
                    'adjustment_mode',
                )

            try:
                movement = adjust_stock(
                    tenant_db,
                    product,
                    new_stock,
                    source_type='manual',
                    user_id=g.api_user.id,
                    reason=reason,
                    notes=notes,
                    allow_negative_stock=bool(getattr(g.api_user.company, 'allow_negative_stock', False)),
                )
                tenant_db.commit()
                if movement is None:
                    return api_success({
                        'changed': False,
                        'message': 'O estoque já estava neste valor.',
                    })
                response_data = {
                    'changed': True,
                    'movement': stock_movement_data(
                        movement,
                        include_cost=g.api_user.has_permission('can_view_reports'),
                    ),
                }
            except StockMovementError:
                tenant_db.rollback()
                raise
            except Exception:
                tenant_db.rollback()
                raise
        return api_success(response_data, 201)
    except ApiAuthError as error:
        return api_auth_error_response(error)
    except StockMovementError as error:
        return api_failure(str(error), 'stock_movement_error', 422)


def notification_preference_data(preference):
    return {
        'notification_type': preference.notification_type,
        'in_app_enabled': bool(preference.in_app_enabled),
        'email_enabled': bool(preference.email_enabled),
        'desktop_enabled': bool(preference.desktop_enabled),
        'minimum_severity': preference.minimum_severity,
        'email_recipients': preference.email_recipients or '',
        'quiet_hours_start': preference.quiet_hours_start or '',
        'quiet_hours_end': preference.quiet_hours_end or '',
        'daily_digest_enabled': bool(preference.daily_digest_enabled),
        'daily_digest_time': preference.daily_digest_time or '08:00',
    }


def email_alert_setting_data(setting):
    metadata = EMAIL_ALERT_TYPES[setting.alert_type]
    return {
        'alert_type': setting.alert_type,
        'label': metadata['label'],
        'description': metadata['description'],
        'enabled': bool(setting.enabled),
        'recipients': setting.recipient_list,
    }


@api_v1_bp.get('/notifications/email-alert-settings')
@api_auth_required
def api_email_alert_settings():
    if not g.api_user.has_permission('can_manage_settings'):
        return api_failure('Você não tem permissão para configurar alertas por e-mail.', 'permission_denied', 403)
    with api_tenant_database(g.api_user) as tenant_db:
        company = tenant_db.get(Company, g.api_user.company_id)
        existing = {
            item.alert_type: item
            for item in tenant_db.query(EmailAlertSetting).filter_by(company_id=g.api_user.company_id).all()
        }
        default_recipients = ', '.join(
            user.email for user in tenant_db.query(User).filter_by(company_id=g.api_user.company_id).all()
            if user.is_active and user.email and user.email_verified and user.role in ('admin', 'master')
        )
        for alert_type, metadata in EMAIL_ALERT_TYPES.items():
            if alert_type not in existing:
                setting = EmailAlertSetting(
                    company_id=g.api_user.company_id,
                    alert_type=alert_type,
                    enabled=metadata['default_enabled'],
                    recipients=default_recipients,
                )
                tenant_db.add(setting)
                existing[alert_type] = setting
        tenant_db.commit()
        items = [email_alert_setting_data(existing[key]) for key in EMAIL_ALERT_TYPES]
    return api_success({
        'company_name': company.name if company else '',
        'smtp_configured': bool(current_app.config.get('MAIL_SMTP_SERVER')),
        'items': items,
    })


@api_v1_bp.put('/notifications/email-alert-settings')
@api_auth_required
def api_update_email_alert_settings():
    if not g.api_user.has_permission('can_manage_settings'):
        return api_failure('Você não tem permissão para configurar alertas por e-mail.', 'permission_denied', 403)
    try:
        payload = json_object_body()
        raw_items = payload.get('items')
        if not isinstance(raw_items, list):
            raise ApiAuthError('Informe a lista de alertas.', 'invalid_payload', 422, 'items')
        received = {}
        for index, item in enumerate(raw_items):
            if not isinstance(item, dict):
                raise ApiAuthError('Alerta inválido.', 'invalid_payload', 422, f'items[{index}]')
            alert_type = str(item.get('alert_type') or '').strip()
            if alert_type not in EMAIL_ALERT_TYPES or alert_type in received:
                raise ApiAuthError('Tipo de alerta inválido ou duplicado.', 'invalid_alert_type', 422, f'items[{index}].alert_type')
            raw_recipients = item.get('recipients')
            recipients = (
                [str(value).strip() for value in raw_recipients if str(value).strip()]
                if isinstance(raw_recipients, list)
                else parse_recipients(raw_recipients)
            )
            invalid = next((email for email in recipients if not EMAIL_PATTERN.match(email)), None)
            if invalid:
                raise ApiAuthError('Informe apenas e-mails válidos.', 'invalid_email', 422, f'items[{index}].recipients')
            received[alert_type] = (bool(item.get('enabled')), recipients)
        if set(received) != set(EMAIL_ALERT_TYPES):
            raise ApiAuthError('Envie todos os tipos de alerta.', 'incomplete_alert_settings', 422, 'items')

        with api_tenant_database(g.api_user) as tenant_db:
            company = tenant_db.get(Company, g.api_user.company_id)
            existing = {
                item.alert_type: item
                for item in tenant_db.query(EmailAlertSetting).filter_by(company_id=g.api_user.company_id).all()
            }
            for alert_type, (enabled, recipients) in received.items():
                setting = existing.get(alert_type)
                if setting is None:
                    setting = EmailAlertSetting(company_id=g.api_user.company_id, alert_type=alert_type)
                    tenant_db.add(setting)
                    existing[alert_type] = setting
                setting.enabled = enabled
                setting.recipients = ', '.join(dict.fromkeys(recipients))
            record_audit_event(
                'email_alert_settings_updated', 'email_alert_setting', None,
                'Alertas por e-mail atualizados pelo aplicativo Windows.',
                company_id=g.api_user.company_id, db_session=tenant_db,
            )
            tenant_db.commit()
            items = [email_alert_setting_data(existing[key]) for key in EMAIL_ALERT_TYPES]
        return api_success({
            'company_name': company.name if company else '',
            'smtp_configured': bool(current_app.config.get('MAIL_SMTP_SERVER')),
            'items': items,
        })
    except ApiAuthError as error:
        return api_auth_error_response(error)


@api_v1_bp.get('/notifications')
@api_auth_required
def api_notifications():
    try:
        page = positive_integer_argument('page', 1)
        page_size = positive_integer_argument('page_size', 20, maximum=100)
        category = (request.args.get('category') or '').strip()
        severity = (request.args.get('severity') or '').strip()
        raw_is_read = (request.args.get('is_read') or '').strip().lower()
        if category and category not in NOTIFICATION_CATEGORIES:
            raise ApiAuthError('Categoria de notificação inválida.', 'invalid_query_parameter', 422, 'category')
        if severity and severity not in NOTIFICATION_SEVERITIES:
            raise ApiAuthError('Severidade de notificação inválida.', 'invalid_query_parameter', 422, 'severity')
        if raw_is_read not in {'', 'true', 'false', '1', '0'}:
            raise ApiAuthError('O parâmetro is_read precisa ser true ou false.', 'invalid_query_parameter', 422, 'is_read')
        is_read = None if not raw_is_read else raw_is_read in {'true', '1'}
        date_from = parse_optional_query_date_argument('date_from')
        date_to = parse_optional_query_date_argument('date_to')
        start_at = datetime.combine(date_from, time.min) if date_from else None
        end_at = datetime.combine(date_to, time.max) if date_to else None

        with api_tenant_database(g.api_user) as tenant_db:
            sync_operational_notifications(tenant_db, g.api_user.company_id)
            data = get_user_notifications(
                tenant_db,
                g.api_user.company_id,
                g.api_user.id,
                page=page,
                page_size=page_size,
                category=category or None,
                severity=severity or None,
                is_read=is_read,
                date_from=start_at,
                date_to=end_at,
                search=(request.args.get('search') or '').strip(),
            )
            tenant_db.commit()
        return api_success(data)
    except ApiAuthError as error:
        return api_auth_error_response(error)


@api_v1_bp.get('/notifications/unread-count')
@api_auth_required
def api_notifications_unread_count():
    with api_tenant_database(g.api_user) as tenant_db:
        sync_operational_notifications(tenant_db, g.api_user.company_id)
        count = get_unread_count(tenant_db, g.api_user.company_id, g.api_user.id)
        tenant_db.commit()
    return api_success({'unread_count': count})


@api_v1_bp.put('/notifications/<int:notification_id>/read')
@api_auth_required
def api_notification_read(notification_id):
    with api_tenant_database(g.api_user) as tenant_db:
        notification = find_visible_notification(
            tenant_db, g.api_user.company_id, g.api_user.id, notification_id,
        )
        if notification is None:
            return api_failure('Notificação não encontrada.', 'notification_not_found', 404)
        mark_as_read(tenant_db, notification)
        tenant_db.commit()
        from app.services.notification_service import notification_data
        data = notification_data(notification)
    return api_success(data)


@api_v1_bp.put('/notifications/read-all')
@api_auth_required
def api_notifications_read_all():
    with api_tenant_database(g.api_user) as tenant_db:
        changed = mark_all_as_read(tenant_db, g.api_user.company_id, g.api_user.id)
        record_audit_event(
            'notifications_read_all', 'notification', None,
            f'{changed} notificações marcadas como lidas.',
            company_id=g.api_user.company_id, db_session=tenant_db,
        )
        tenant_db.commit()
    return api_success({'changed': changed, 'unread_count': 0})


@api_v1_bp.put('/notifications/<int:notification_id>/dismiss')
@api_auth_required
def api_notification_dismiss(notification_id):
    with api_tenant_database(g.api_user) as tenant_db:
        notification = find_visible_notification(
            tenant_db, g.api_user.company_id, g.api_user.id, notification_id,
        )
        if notification is None:
            return api_failure('Notificação não encontrada.', 'notification_not_found', 404)
        dismiss_notification(tenant_db, notification)
        tenant_db.commit()
    return api_success({'id': notification_id, 'dismissed': True})


@api_v1_bp.get('/notifications/preferences')
@api_auth_required
def api_notification_preferences():
    with api_tenant_database(g.api_user) as tenant_db:
        preference = preference_for(
            tenant_db, g.api_user.company_id, g.api_user.id, '*', create=True,
        )
        tenant_db.commit()
        data = notification_preference_data(preference)
    data['can_manage_recipients'] = g.api_user.has_permission('can_manage_settings')
    return api_success(data)


@api_v1_bp.put('/notifications/preferences')
@api_auth_required
def api_update_notification_preferences():
    try:
        payload = json_object_body()
        minimum_severity = json_text(payload, 'minimum_severity', max_length=20) or 'info'
        if minimum_severity not in NOTIFICATION_SEVERITIES:
            raise ApiAuthError('Severidade mínima inválida.', 'invalid_severity', 422, 'minimum_severity')
        recipients = json_text(payload, 'email_recipients', max_length=1000)
        if recipients and not g.api_user.has_permission('can_manage_settings'):
            raise ApiAuthError(
                'Você não tem permissão para alterar destinatários.',
                'permission_denied', 403, 'email_recipients',
            )
        recipient_values = [item.strip() for item in recipients.replace(';', ',').split(',') if item.strip()]
        if any(not EMAIL_PATTERN.match(item) for item in recipient_values):
            raise ApiAuthError('Informe apenas e-mails válidos.', 'invalid_email', 422, 'email_recipients')
        quiet_hours_start = json_text(payload, 'quiet_hours_start', max_length=5)
        quiet_hours_end = json_text(payload, 'quiet_hours_end', max_length=5)
        daily_digest_time = json_text(payload, 'daily_digest_time', max_length=5) or '08:00'
        if bool(quiet_hours_start) != bool(quiet_hours_end):
            raise ApiAuthError(
                'Informe os dois horários do período de silêncio ou deixe ambos vazios.',
                'invalid_quiet_hours', 422, 'quiet_hours_start',
            )
        for field, value in (
            ('quiet_hours_start', quiet_hours_start),
            ('quiet_hours_end', quiet_hours_end),
            ('daily_digest_time', daily_digest_time),
        ):
            if value:
                try:
                    datetime.strptime(value, '%H:%M')
                except ValueError as error:
                    raise ApiAuthError(
                        'Informe o horário no formato HH:mm.',
                        'invalid_time', 422, field,
                    ) from error

        with api_tenant_database(g.api_user) as tenant_db:
            preference = preference_for(
                tenant_db, g.api_user.company_id, g.api_user.id, '*', create=True,
            )
            preference.in_app_enabled = json_bool(payload, 'in_app_enabled', True)
            preference.email_enabled = json_bool(payload, 'email_enabled', False)
            preference.desktop_enabled = json_bool(payload, 'desktop_enabled', True)
            preference.minimum_severity = minimum_severity
            if g.api_user.has_permission('can_manage_settings'):
                preference.email_recipients = ', '.join(recipient_values)
            preference.quiet_hours_start = quiet_hours_start
            preference.quiet_hours_end = quiet_hours_end
            preference.daily_digest_enabled = json_bool(payload, 'daily_digest_enabled', False)
            preference.daily_digest_time = daily_digest_time
            record_audit_event(
                'notification_preferences_updated', 'notification_preference', preference.id,
                'Preferências de notificações atualizadas.',
                new_values=notification_preference_data(preference),
                company_id=g.api_user.company_id, db_session=tenant_db,
            )
            tenant_db.commit()
            data = notification_preference_data(preference)
        data['can_manage_recipients'] = g.api_user.has_permission('can_manage_settings')
        return api_success(data)
    except ApiAuthError as error:
        return api_auth_error_response(error)
