import csv
import io
import re
import zipfile
from xml.etree import ElementTree

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.extensions import limiter
from app.security.rate_limit import authenticated_identity_key, configured_limit
from app.models import Category, Product
from app.money import money_json, parse_money_decimal
from app.permissions import authorize_permission_override, permission_required
from app.services.audit_service import changed_values, record_audit_event
from app.services.product_service import ProductOperationError, delete_product as delete_product_service
from app.services.stock_service import StockMovementError, adjust_stock, increase_stock, register_stock_movement
from app.tenant import current_tenant_company, tenant_session


catalog_bp = Blueprint('catalog', __name__, url_prefix='/catalogo')


def tenant_query(model):
    company = current_tenant_company()
    return tenant_session().query(model).filter(model.company_id == company.id)


def tenant_get_or_404(model, record_id):
    record = tenant_query(model).filter_by(id=record_id).first()
    if not record:
        abort(404)
    return record


def product_barcode_exists(barcode, product_id=None):
    if not barcode:
        return False
    query = tenant_query(Product).filter(Product.barcode == barcode)
    if product_id:
        query = query.filter(Product.id != product_id)
    return query.first() is not None


def kit_component_is_valid(component_id, product_id=None):
    if not component_id:
        return False
    query = tenant_query(Product).filter(Product.id == component_id, Product.active.is_(True))
    if product_id:
        query = query.filter(Product.id != product_id)
    return query.first() is not None


def category_name_exists(name, category_id=None):
    query = tenant_session().query(Category).filter(
        Category.company_id == current_tenant_company().id,
        func.lower(Category.name) == name.lower(),
    )
    if category_id:
        query = query.filter(Category.id != category_id)
    return query.first() is not None


def is_duplicate_error(error):
    message = str(getattr(error, 'orig', error)).lower()
    return 'duplicate' in message or 'unique' in message or '1062' in message


def current_company_categories_query():
    return tenant_session().query(Category).filter(Category.company_id == current_tenant_company().id)


def can_import_products():
    return current_user.role in ('admin', 'manager', 'master')


def import_redirect_target():
    target = request.form.get('return_to')
    if target == 'settings':
        return redirect(url_for('auth.settings'))
    return redirect(url_for('catalog.products', status='all'))


def parse_money(value):
    try:
        return parse_money_decimal(value if value not in (None, '') else '0')
    except ValueError:
        return parse_money_decimal('0')


def parse_optional_money(value):
    value = (value or '').strip()
    if not value:
        return None
    return parse_money(value)


def parse_int(value):
    try:
        return max(int(value or 0), 0)
    except ValueError:
        return 0


def normalize_header(value):
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


def import_column(row, *names):
    normalized = {normalize_header(key): value for key, value in row.items()}
    for name in names:
        key = normalize_header(name)
        if key in normalized:
            return normalized[key]
    return ''


def read_csv_rows(file_storage):
    content = file_storage.read().decode('utf-8-sig')
    sample = content[:2048]
    delimiter = ';' if sample.count(';') > sample.count(',') else ','
    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    return list(reader)


def xlsx_column_index(cell_reference):
    letters = ''.join(char for char in cell_reference if char.isalpha())
    index = 0
    for letter in letters:
        index = index * 26 + (ord(letter.upper()) - ord('A') + 1)
    return index - 1


def read_xlsx_rows(file_storage):
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
        sheet_root = ElementTree.fromstring(workbook.read(sheet_name))
        table_rows = []
        for sheet_row in sheet_root.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row'):
            values = []
            for cell in sheet_row.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c'):
                reference = cell.attrib.get('r', '')
                index = xlsx_column_index(reference)
                while len(values) <= index:
                    values.append('')

                value_node = cell.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v')
                inline_node = cell.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}is/{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')
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


def read_import_rows(file_storage):
    filename = (file_storage.filename or '').lower()
    if filename.endswith('.csv'):
        return read_csv_rows(file_storage)
    if filename.endswith('.xlsx'):
        return read_xlsx_rows(file_storage)
    raise ValueError('Formato inválido. Envie uma planilha CSV ou XLSX.')


def find_or_create_category(name, tenant_db, company_id):
    name = str(name or '').strip()
    if not name:
        return None

    category = tenant_session().query(Category).filter(
        Category.company_id == company_id,
        func.lower(Category.name) == name.lower(),
    ).first()
    if category:
        return category

    category = Category(name=name, company_id=company_id)
    tenant_db.add(category)
    tenant_db.flush()
    return category


def product_audit_values(product):
    return {
        'name': product.name,
        'barcode': product.barcode,
        'category_id': product.category_id,
        'cost_price': product.cost_price,
        'sale_price': product.sale_price,
        'stock_quantity': product.stock_quantity,
        'min_stock_quantity': product.min_stock_quantity,
        'active': product.active,
        'is_kit': product.is_kit,
        'kit_component_product_id': product.kit_component_product_id,
        'kit_component_quantity': product.kit_component_quantity,
    }


def import_products_from_rows(rows):
    tenant_db = tenant_session()
    company_id = current_tenant_company().id
    created = 0
    updated = 0
    skipped = 0
    movements = 0

    for row in rows:
        product_name = str(import_column(row, 'produto', 'nome', 'nome_produto', 'product', 'name') or '').strip()
        if not product_name:
            skipped += 1
            continue

        category_name = import_column(row, 'categoria', 'category')
        cost_price = parse_money(import_column(row, 'valor de custo', 'custo', 'preco de custo', 'preco_custo', 'cost_price', 'cost'))
        sale_price = parse_money(import_column(row, 'valor de venda', 'venda', 'preco de venda', 'preco_venda', 'sale_price', 'price'))
        stock_quantity = parse_int(import_column(row, 'estoque atual', 'estoque_atual', 'estoque', 'stock_quantity', 'stock'))
        min_stock_quantity = parse_int(import_column(row, 'estoque minimo', 'estoque_minimo', 'min_stock_quantity', 'min_stock'))
        category = find_or_create_category(category_name, tenant_db, company_id)

        product = tenant_query(Product).filter(func.lower(Product.name) == product_name.lower()).first()
        if product:
            updated += 1
            old_values = product_audit_values(product)
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
        product.category_id = category.id if category else None
        product.cost_price = cost_price
        product.sale_price = sale_price
        product.min_stock_quantity = min_stock_quantity
        product.active = True
        tenant_db.flush()

        if previous_stock == 0 and product.stock_quantity == 0 and stock_quantity > 0 and not old_values:
            register_stock_movement(
                tenant_db,
                product,
                'import',
                'spreadsheet_import',
                stock_quantity,
                stock_quantity,
                user_id=current_user.id,
                unit_cost=cost_price,
                reason='Estoque importado na criação do produto',
            )
            movements += 1
        elif stock_quantity != previous_stock:
            adjust_stock(
                tenant_db,
                product,
                stock_quantity,
                source_type='spreadsheet_import',
                user_id=current_user.id,
                unit_cost=cost_price,
                reason='Estoque ajustado por importação de planilha',
                allow_negative_stock=current_tenant_company().allow_negative_stock,
            )
            movements += 1

        new_values = product_audit_values(product)
        old_diff, new_diff = changed_values(old_values, new_values)
        record_audit_event(
            'product_created' if not old_values else 'product_updated',
            'product',
            product.id,
            f'Produto {product.name} {"criado" if not old_values else "atualizado"} por importação.',
            old_values=old_diff,
            new_values=new_diff,
            company_id=company_id,
            db_session=tenant_db,
        )

    tenant_db.commit()
    record_audit_event(
        'products_imported',
        'product',
        None,
        f'Importação concluída: {created} criado(s), {updated} atualizado(s), {skipped} ignorado(s), {movements} movimentação(ões).',
        new_values={
            'created': created,
            'updated': updated,
            'skipped': skipped,
            'movements': movements,
        },
        company_id=company_id,
    )
    db.session.commit()
    return created, updated, skipped, movements


def populate_product(product, include_stock=True):
    barcode = request.form.get('barcode', '').strip()
    category_id = request.form.get('category_id') or None
    kit_component_product_id = request.form.get('kit_component_product_id') or None

    product.name = request.form.get('name', '').strip()
    product.company_id = current_tenant_company().id
    product.barcode = barcode or None
    product.category_id = int(category_id) if category_id else None
    product.cost_price = parse_money(request.form.get('cost_price'))
    product.sale_price = parse_money(request.form.get('sale_price'))
    if include_stock:
        product.stock_quantity = parse_int(request.form.get('stock_quantity'))
    product.min_stock_quantity = parse_int(request.form.get('min_stock_quantity'))
    product.active = request.form.get('active') == 'on'
    product.is_kit = request.form.get('is_kit') == 'on'
    product.kit_component_product_id = int(kit_component_product_id) if kit_component_product_id else None
    product.kit_component_quantity = parse_int(request.form.get('kit_component_quantity'))

    if not product.is_kit:
        product.kit_component_product_id = None
        product.kit_component_quantity = 0


@catalog_bp.route('/produtos')
@login_required
@permission_required('can_view_products')
def products():
    search = request.args.get('q', '').strip()
    status = request.args.get('status', 'active')
    category_id = request.args.get('category_id', '').strip()
    stock = request.args.get('stock', 'all')
    min_price = parse_optional_money(request.args.get('min_price'))
    max_price = parse_optional_money(request.args.get('max_price'))
    sort = request.args.get('sort', 'name_asc')
    page = request.args.get('page', 1, type=int) or 1
    page = max(page, 1)
    per_page = 20

    query = tenant_query(Product).options(
        joinedload(Product.category),
        joinedload(Product.kit_component),
    )
    if search:
        term = f'%{search}%'
        query = query.filter((Product.name.ilike(term)) | (Product.barcode.ilike(term)))
    if status == 'active':
        query = query.filter_by(active=True)
    elif status == 'inactive':
        query = query.filter_by(active=False)

    if category_id.isdigit():
        query = query.filter_by(category_id=int(category_id))

    if stock == 'available':
        query = query.filter(Product.stock_quantity > 0)
    elif stock == 'out':
        query = query.filter(Product.stock_quantity <= 0)
    elif stock == 'low':
        query = query.filter(Product.min_stock_quantity > 0, Product.stock_quantity >= 0, Product.stock_quantity <= Product.min_stock_quantity)

    if min_price is not None:
        query = query.filter(Product.sale_price >= min_price)
    if max_price is not None:
        query = query.filter(Product.sale_price <= max_price)

    sort_options = {
        'name_asc': Product.name.asc(),
        'name_desc': Product.name.desc(),
        'price_asc': Product.sale_price.asc(),
        'price_desc': Product.sale_price.desc(),
        'stock_asc': Product.stock_quantity.asc(),
        'stock_desc': Product.stock_quantity.desc(),
        'created_desc': Product.created_at.desc(),
    }

    ordered_query = query.order_by(sort_options.get(sort, Product.name.asc()))
    total_products = query.order_by(None).count()
    total_pages = max((total_products + per_page - 1) // per_page, 1)
    page = min(page, total_pages)
    products = ordered_query.offset((page - 1) * per_page).limit(per_page).all()
    product_suggestions = ordered_query.all()
    categories = current_company_categories_query().order_by(Category.name.asc()).all()
    category_counts = dict(
        tenant_session().query(Product.category_id, func.count(Product.id)).filter(
            Product.company_id == current_tenant_company().id,
            Product.category_id.is_not(None),
        ).group_by(Product.category_id).all()
    )
    kit_products = tenant_query(Product).filter_by(active=True).order_by(Product.name.asc()).all()
    filters = {
        'search': search,
        'status': status,
        'category_id': category_id,
        'stock': stock,
        'min_price': request.args.get('min_price', '').strip(),
        'max_price': request.args.get('max_price', '').strip(),
        'sort': sort,
    }
    pagination_query = {key: value for key, value in request.args.items() if key != 'page'}
    return render_template(
        'catalog/products.html',
        products=products,
        product_suggestions=product_suggestions,
        categories=categories,
        category_counts=category_counts,
        kit_products=kit_products,
        filters=filters,
        page=page,
        per_page=per_page,
        total_products=total_products,
        total_pages=total_pages,
        pagination_query=pagination_query,
        can_import_products=can_import_products(),
        import_company=current_tenant_company(),
    )


@catalog_bp.route('/produtos/importar', methods=['POST'])
@login_required
@permission_required('can_manage_products')
@limiter.limit(
    configured_limit('RATELIMIT_IMPORT', '5 per hour'),
    key_func=authenticated_identity_key,
)
def import_products():
    if not can_import_products() and not authorize_permission_override('can_manage_products'):
        flash('Apenas o dono da adega pode importar planilhas.', 'danger')
        return import_redirect_target()

    file_storage = request.files.get('spreadsheet')
    if not file_storage or not file_storage.filename:
        flash('Envie uma planilha para importar.', 'danger')
        return import_redirect_target()

    try:
        rows = read_import_rows(file_storage)
        created, updated, skipped, movements = import_products_from_rows(rows)
    except (ValueError, KeyError, zipfile.BadZipFile, ElementTree.ParseError) as error:
        flash(str(error) or 'Não foi possível ler a planilha.', 'danger')
        return import_redirect_target()
    except IntegrityError:
        tenant_session().rollback()
        flash('A planilha possui dados duplicados ou inválidos.', 'danger')
        return import_redirect_target()

    flash(
        f'Importação concluída: {created} produto(s) criado(s), {updated} atualizado(s), {skipped} linha(s) ignorada(s). {movements} movimentação(ões) de estoque.',
        'success',
    )
    return import_redirect_target()


@catalog_bp.route('/produtos/sugestoes-kit')
@login_required
@permission_required('can_manage_products')
def kit_product_suggestions():
    search = request.args.get('q', '').strip()[:120]
    exclude_id = request.args.get('exclude_id', type=int)
    if len(search) < 2:
        return jsonify({'items': []})

    pattern = f'%{search}%'
    query = tenant_query(Product).filter(
        Product.active.is_(True),
        or_(Product.name.ilike(pattern), Product.barcode.ilike(pattern)),
    )
    if exclude_id:
        query = query.filter(Product.id != exclude_id)

    products = query.order_by(Product.name.asc()).limit(12).all()
    return jsonify({
        'items': [
            {
                'id': product.id,
                'value': product.name,
                'title': product.name,
                'barcode': product.barcode or '',
                'stock': int(product.effective_stock_quantity or 0),
                'sale_price': money_json(product.sale_price),
                'meta': (
                    f"Código: {product.barcode or 'sem código'} · "
                    f"Estoque: {int(product.effective_stock_quantity or 0)} un. · "
                    f"R$ {format(product.sale_price or 0, '.2f').replace('.', ',')}"
                ),
            }
            for product in products
        ],
    })


@catalog_bp.route('/produtos/novo', methods=['GET', 'POST'])
@login_required
@permission_required('can_manage_products')
def new_product():
    product = Product(active=True)
    categories = current_company_categories_query().order_by(Category.name.asc()).all()
    kit_products = []

    if request.method == 'POST':
        initial_stock = parse_int(request.form.get('stock_quantity'))
        populate_product(product, include_stock=False)
        product.stock_quantity = 0
        if not product.name:
            flash('Informe o nome do produto.', 'danger')
            return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)
        if product_barcode_exists(product.barcode):
            flash('Já existe um produto com este código de barras.', 'danger')
            return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)
        if product.is_kit and (not product.kit_component_product_id or product.kit_component_quantity <= 0):
            flash('Informe o produto base e a quantidade do kit.', 'danger')
            return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)
        if product.is_kit and not kit_component_is_valid(product.kit_component_product_id):
            flash('Selecione um produto base válido e ativo para o kit.', 'danger')
            return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)
        if product.id and product.kit_component_product_id == product.id:
            flash('O produto base do kit não pode ser o próprio kit.', 'danger')
            return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)

        tenant_db = tenant_session()
        tenant_db.add(product)
        try:
            tenant_db.flush()
            if initial_stock > 0:
                register_stock_movement(
                    tenant_db,
                    product,
                    'initial_stock',
                    'product_creation',
                    initial_stock,
                    initial_stock,
                    user_id=current_user.id,
                    unit_cost=product.cost_price,
                    reason=request.form.get('stock_reason', '').strip() or 'Estoque inicial informado no cadastro',
                )
            record_audit_event(
                'product_created',
                'product',
                product.id,
                f'Produto {product.name} cadastrado.',
                new_values=product_audit_values(product),
                company_id=current_tenant_company().id,
                db_session=tenant_db,
            )
            tenant_db.commit()
        except IntegrityError:
            tenant_db.rollback()
            flash('Já existe um produto com este código de barras.', 'danger')
            return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)
        except StockMovementError as error:
            tenant_db.rollback()
            flash(str(error), 'danger')
            return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)

        flash('Produto cadastrado com sucesso.', 'success')
        return redirect(url_for('catalog.products'))

    return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)


@catalog_bp.route('/produtos/<int:product_id>/editar', methods=['GET', 'POST'])
@login_required
@permission_required('can_manage_products')
def edit_product(product_id):
    product = tenant_get_or_404(Product, product_id)
    categories = current_company_categories_query().order_by(Category.name.asc()).all()
    kit_products = []

    if request.method == 'POST':
        tenant_db = tenant_session()
        old_values = product_audit_values(product)
        previous_stock = int(product.stock_quantity or 0)
        requested_stock = parse_int(request.form.get('stock_quantity'))
        populate_product(product, include_stock=False)
        if not product.name:
            flash('Informe o nome do produto.', 'danger')
            return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)
        if product_barcode_exists(product.barcode, product.id):
            flash('Já existe um produto com este código de barras.', 'danger')
            return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)
        if product.is_kit and (not product.kit_component_product_id or product.kit_component_quantity <= 0):
            flash('Informe o produto base e a quantidade do kit.', 'danger')
            return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)
        if product.id and product.kit_component_product_id == product.id:
            flash('O produto base do kit não pode ser o próprio kit.', 'danger')
            return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)
        if product.is_kit and not kit_component_is_valid(product.kit_component_product_id, product.id):
            flash('Selecione um produto base válido e ativo para o kit.', 'danger')
            return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)

        try:
            tenant_db.flush()
            if requested_stock != previous_stock:
                adjust_stock(
                    tenant_db,
                    product,
                    requested_stock,
                    source_type='product_edit',
                    user_id=current_user.id,
                    unit_cost=product.cost_price,
                    reason=request.form.get('stock_reason', '').strip() or 'Ajuste registrado pela edição do produto',
                    allow_negative_stock=current_tenant_company().allow_negative_stock,
                )
            new_values = product_audit_values(product)
            old_diff, new_diff = changed_values(old_values, new_values)
            if old_diff or new_diff:
                record_audit_event(
                    'product_updated',
                    'product',
                    product.id,
                    f'Produto {product.name} atualizado.',
                    old_values=old_diff,
                    new_values=new_diff,
                    company_id=current_tenant_company().id,
                    db_session=tenant_db,
                )
            tenant_db.commit()
        except IntegrityError:
            tenant_db.rollback()
            flash('Já existe um produto com este código de barras.', 'danger')
            return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)
        except StockMovementError as error:
            tenant_db.rollback()
            flash(str(error), 'danger')
            return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)

        flash('Produto atualizado com sucesso.', 'success')
        return redirect(url_for('catalog.products'))

    return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)


@catalog_bp.route('/produtos/<int:product_id>/atualizar', methods=['POST'])
@login_required
@permission_required('can_manage_products')
def quick_update_product(product_id):
    product = tenant_get_or_404(Product, product_id)
    tenant_db = tenant_session()
    old_values = product_audit_values(product)
    previous_stock = int(product.stock_quantity or 0)
    requested_stock = parse_int(request.form.get('stock_quantity'))
    product.company_id = current_tenant_company().id
    product.name = request.form.get('name', '').strip()
    product.barcode = request.form.get('barcode', '').strip() or None
    category_id = request.form.get('category_id') or None
    product.category_id = int(category_id) if category_id else None
    product.cost_price = parse_money(request.form.get('cost_price'))
    product.sale_price = parse_money(request.form.get('sale_price'))
    product.min_stock_quantity = parse_int(request.form.get('min_stock_quantity'))
    product.is_kit = request.form.get('is_kit') == 'on'
    kit_component_product_id = request.form.get('kit_component_product_id') or None
    product.kit_component_product_id = int(kit_component_product_id) if kit_component_product_id else None
    product.kit_component_quantity = parse_int(request.form.get('kit_component_quantity'))

    if not product.is_kit:
        product.kit_component_product_id = None
        product.kit_component_quantity = 0

    if not product.name:
        flash('Informe o nome do produto.', 'danger')
        return redirect(url_for('catalog.products', status='all'))
    if product_barcode_exists(product.barcode, product.id):
        flash('Já existe um produto com este código de barras.', 'danger')
        return redirect(url_for('catalog.products', status='all'))
    if product.is_kit and (not product.kit_component_product_id or product.kit_component_quantity <= 0):
        flash('Informe o produto base e a quantidade do kit.', 'danger')
        return redirect(url_for('catalog.products', status='all'))
    if product.id and product.kit_component_product_id == product.id:
        flash('O produto base do kit não pode ser o próprio kit.', 'danger')
        return redirect(url_for('catalog.products', status='all'))

    try:
        tenant_db.flush()
        if requested_stock != previous_stock:
            adjust_stock(
                tenant_db,
                product,
                requested_stock,
                source_type='product_edit',
                user_id=current_user.id,
                unit_cost=product.cost_price,
                reason=request.form.get('stock_reason', '').strip() or 'Ajuste registrado pela atualização rápida',
                allow_negative_stock=current_tenant_company().allow_negative_stock,
            )
        new_values = product_audit_values(product)
        old_diff, new_diff = changed_values(old_values, new_values)
        if old_diff or new_diff:
            record_audit_event(
                'product_updated',
                'product',
                product.id,
                f'Produto {product.name} atualizado.',
                old_values=old_diff,
                new_values=new_diff,
                company_id=current_tenant_company().id,
                db_session=tenant_db,
            )
        tenant_db.commit()
    except IntegrityError:
        tenant_db.rollback()
        flash('Já existe um produto com este código de barras.', 'danger')
        return redirect(url_for('catalog.products', status='all'))
    except StockMovementError as error:
        tenant_db.rollback()
        flash(str(error), 'danger')
        return redirect(url_for('catalog.products', status='all'))

    flash('Produto atualizado com sucesso.', 'success')
    return redirect(url_for('catalog.products', status='all'))


@catalog_bp.route('/produtos/<int:product_id>/notificacao-estoque', methods=['POST'])
@login_required
@permission_required('can_view_products')
def dismiss_low_stock_notification(product_id):
    product = tenant_get_or_404(Product, product_id)
    stock_quantity = product.effective_stock_quantity or 0
    min_stock_quantity = product.min_stock_quantity or 0
    alert_type = 'product_out_of_stock' if stock_quantity <= 0 else 'product_low_stock'
    notification_key = f'{alert_type}:{product.id}:{stock_quantity}:{min_stock_quantity}'
    dismissed_notifications = set(session.get('dismissed_low_stock_notifications', []))
    dismissed_notifications.add(notification_key)
    session['dismissed_low_stock_notifications'] = sorted(dismissed_notifications)
    session.modified = True

    return redirect(url_for('catalog.products', status='active', q=product.name))


@catalog_bp.route('/produtos/<int:product_id>/alternar-status', methods=['POST'])
@login_required
@permission_required('can_manage_products')
def toggle_product(product_id):
    product = tenant_get_or_404(Product, product_id)
    old_active = product.active
    product.active = not product.active
    record_audit_event(
        'product_activated' if product.active else 'product_deactivated',
        'product',
        product.id,
        f'Produto {product.name} {"ativado" if product.active else "inativado"}.',
        old_values={'active': old_active},
        new_values={'active': product.active},
        company_id=current_tenant_company().id,
        db_session=tenant_session(),
    )
    tenant_session().commit()

    status = 'ativado' if product.active else 'desativado'
    flash(f'Produto {status} com sucesso.', 'success')
    return redirect(url_for('catalog.products', status='all'))


@catalog_bp.route('/produtos/<int:product_id>/excluir', methods=['POST'])
@login_required
@permission_required('can_manage_products')
def delete_product(product_id):
    tenant_db = tenant_session()
    try:
        delete_product_service(
            tenant_db,
            current_tenant_company(),
            current_user,
            product_id,
        )
        tenant_db.commit()
    except ProductOperationError as error:
        tenant_db.rollback()
        flash(error.message, 'danger')
        return redirect(url_for('catalog.products', status='all'))

    flash('Produto excluído com sucesso.', 'success')
    return redirect(url_for('catalog.products', status='all'))


@catalog_bp.route('/categorias', methods=['GET', 'POST'])
@login_required
@permission_required('can_manage_categories')
def categories():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Informe o nome da categoria.', 'danger')
        else:
            if category_name_exists(name):
                flash('Já existe uma categoria com este nome.', 'danger')
                return redirect(url_for('catalog.categories'))
            category = Category(name=name, company_id=current_tenant_company().id)
            tenant_db = tenant_session()
            tenant_db.add(category)
            try:
                tenant_db.flush()
                record_audit_event(
                    'category_created',
                    'category',
                    category.id,
                    f'Categoria {category.name} cadastrada.',
                    new_values={'name': category.name},
                    company_id=current_tenant_company().id,
                    db_session=tenant_db,
                )
                tenant_db.commit()
                flash('Categoria cadastrada com sucesso.', 'success')
            except IntegrityError as error:
                tenant_db.rollback()
                if is_duplicate_error(error):
                    flash('Já existe uma categoria com este nome.', 'danger')
                else:
                    flash('Não foi possível cadastrar a categoria. Tente novamente.', 'danger')

        return redirect(url_for('catalog.categories'))

    search = request.args.get('q', '').strip()
    usage = request.args.get('usage', 'all')
    sort = request.args.get('sort', 'name_asc')

    product_count = func.count(Product.id).label('product_count')
    query = (
        tenant_session().query(Category, product_count)
        .outerjoin(Product, (Product.category_id == Category.id) & (Product.company_id == current_tenant_company().id))
        .filter(Category.company_id == current_tenant_company().id)
        .group_by(Category.id)
    )

    if search:
        query = query.filter(Category.name.ilike(f'%{search}%'))

    if usage == 'with_products':
        query = query.having(product_count > 0)
    elif usage == 'empty':
        query = query.having(product_count == 0)

    sort_options = {
        'name_asc': Category.name.asc(),
        'name_desc': Category.name.desc(),
        'products_desc': product_count.desc(),
        'products_asc': product_count.asc(),
        'created_desc': Category.created_at.desc(),
    }
    categories = query.order_by(sort_options.get(sort, Category.name.asc())).all()
    category_suggestions = [category for category, _product_count in categories]
    category_counts = {category.id: count for category, count in categories}
    filters = {
        'search': search,
        'usage': usage,
        'sort': sort,
    }

    return render_template(
        'catalog/categories.html',
        categories=categories,
        category_suggestions=category_suggestions,
        category_counts=category_counts,
        filters=filters,
    )


@catalog_bp.route('/categorias/<int:category_id>/atualizar', methods=['POST'])
@login_required
@permission_required('can_manage_categories')
def update_category(category_id):
    category = tenant_get_or_404(Category, category_id)
    old_name = category.name
    category.name = request.form.get('name', '').strip()
    category.company_id = current_tenant_company().id

    if not category.name:
        flash('Informe o nome da categoria.', 'danger')
        return redirect(url_for('catalog.categories'))
    if category_name_exists(category.name, category.id):
        flash('Já existe uma categoria com este nome.', 'danger')
        return redirect(url_for('catalog.categories'))

    try:
        record_audit_event(
            'category_updated',
            'category',
            category.id,
            f'Categoria {category.name} atualizada.',
            old_values={'name': old_name},
            new_values={'name': category.name},
            company_id=current_tenant_company().id,
            db_session=tenant_session(),
        )
        tenant_session().commit()
    except IntegrityError as error:
        tenant_session().rollback()
        if is_duplicate_error(error):
            flash('Já existe uma categoria com este nome.', 'danger')
        else:
            flash('Não foi possível atualizar a categoria. Tente novamente.', 'danger')
        return redirect(url_for('catalog.categories'))

    flash('Categoria atualizada com sucesso.', 'success')
    return redirect(url_for('catalog.categories'))


@catalog_bp.route('/categorias/<int:category_id>/excluir', methods=['POST'])
@login_required
@permission_required('can_manage_categories')
def delete_category(category_id):
    category = tenant_get_or_404(Category, category_id)
    if tenant_query(Product).filter_by(category_id=category.id).first():
        flash('Não é possível excluir uma categoria com produtos vinculados.', 'danger')
        return redirect(url_for('catalog.categories'))

    tenant_db = tenant_session()
    record_audit_event(
        'category_deleted',
        'category',
        category.id,
        f'Categoria {category.name} excluída.',
        old_values={'name': category.name},
        company_id=current_tenant_company().id,
        db_session=tenant_db,
    )
    tenant_db.delete(category)
    tenant_db.commit()
    flash('Categoria excluída com sucesso.', 'success')
    return redirect(url_for('catalog.categories'))
