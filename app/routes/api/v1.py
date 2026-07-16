from contextlib import contextmanager
from functools import wraps

from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy import and_, func, or_
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
from app.tenant import tenant_engine


api_v1_bp = Blueprint('api_v1', __name__, url_prefix='/api/v1')


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
