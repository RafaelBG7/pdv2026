from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import wraps
import re

from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload, sessionmaker

from app.extensions import db
from app.models import Category, Product
from app.services.api_auth_service import (
    ApiAuthError,
    authenticate_access_token,
    authenticate_credentials,
    issue_token_pair,
    require_secure_auth_transport,
    revoke_session,
    rotate_refresh_token,
    user_identity_data,
)
from app.services.audit_service import record_audit_event
from app.services.cash_register_service import (
    CashRegisterOperationError,
    build_cash_register_snapshot,
    close_cash_register,
    open_cash_register,
)
from app.services.dashboard_service import build_dashboard_snapshot
from app.services.sale_service import (
    SaleLineInput,
    SaleOperationError,
    SalePaymentInput,
    create_sale,
    find_completed_sale_request,
    serialize_sale_result,
)
from app.tenant import tenant_engine


api_v1_bp = Blueprint('api_v1', __name__, url_prefix='/api/v1')
IDEMPOTENCY_KEY_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$')


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
    }
    if include_cost:
        payload.update({
            'cost_price': round(float(product.cost_price or 0), 2),
            'profit_amount': round(float(product.profit_amount), 2),
            'profit_margin_percent': round(float(product.profit_margin_percent), 2),
        })
    return payload


@api_v1_bp.get('/health')
def health_check():
    return api_success({
        'status': 'ok',
        'service': 'girofy',
        'api_version': 'v1',
    })


@api_v1_bp.post('/auth/login')
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


@api_v1_bp.post('/auth/refresh')
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
            if category_id is not None:
                query = query.filter(Product.category_id == category_id)
            if active_filter == 'active':
                query = query.filter(Product.active.is_(True))
            elif active_filter == 'inactive':
                query = query.filter(Product.active.is_(False))

            ordering = {
                'name': (func.lower(Product.name), Product.id),
                'name_desc': (func.lower(Product.name).desc(), Product.id.desc()),
                'price': (Product.sale_price, func.lower(Product.name), Product.id),
                'price_desc': (Product.sale_price.desc(), func.lower(Product.name), Product.id),
                'stock': (Product.stock_quantity, func.lower(Product.name), Product.id),
                'stock_desc': (Product.stock_quantity.desc(), func.lower(Product.name), Product.id),
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
