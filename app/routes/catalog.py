import csv
import io
import re
import zipfile
from xml.etree import ElementTree

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Category, Product
from app.permissions import authorize_permission_override, permission_required
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
    if isinstance(value, (int, float)):
        return max(float(value), 0.0)
    value = (value or '0').strip()
    if ',' in value:
        value = value.replace('.', '').replace(',', '.')
    try:
        return max(float(value), 0.0)
    except ValueError:
        return 0.0


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


def import_products_from_rows(rows):
    tenant_db = tenant_session()
    company_id = current_tenant_company().id
    created = 0
    updated = 0
    skipped = 0

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
        else:
            product = Product(name=product_name, company_id=company_id, active=True, stock_quantity=0)
            tenant_db.add(product)
            created += 1

        product.company_id = company_id
        product.name = product_name
        product.category_id = category.id if category else None
        product.cost_price = cost_price
        product.sale_price = sale_price
        product.stock_quantity = stock_quantity
        product.min_stock_quantity = min_stock_quantity
        product.active = True

    tenant_db.commit()
    return created, updated, skipped


def populate_product(product):
    barcode = request.form.get('barcode', '').strip()
    category_id = request.form.get('category_id') or None
    kit_component_product_id = request.form.get('kit_component_product_id') or None

    product.name = request.form.get('name', '').strip()
    product.company_id = current_tenant_company().id
    product.barcode = barcode or None
    product.category_id = int(category_id) if category_id else None
    product.cost_price = parse_money(request.form.get('cost_price'))
    product.sale_price = parse_money(request.form.get('sale_price'))
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

    query = tenant_query(Product)
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

    products = query.order_by(sort_options.get(sort, Product.name.asc())).all()
    categories = current_company_categories_query().order_by(Category.name.asc()).all()
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
    return render_template(
        'catalog/products.html',
        products=products,
        product_suggestions=products,
        categories=categories,
        kit_products=kit_products,
        filters=filters,
        can_import_products=can_import_products(),
        import_company=current_tenant_company(),
    )


@catalog_bp.route('/produtos/importar', methods=['POST'])
@login_required
@permission_required('can_manage_products')
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
        created, updated, skipped = import_products_from_rows(rows)
    except (ValueError, KeyError, zipfile.BadZipFile, ElementTree.ParseError) as error:
        flash(str(error) or 'Não foi possível ler a planilha.', 'danger')
        return import_redirect_target()
    except IntegrityError:
        tenant_session().rollback()
        flash('A planilha possui dados duplicados ou inválidos.', 'danger')
        return import_redirect_target()

    flash(
        f'Importação concluída: {created} produto(s) criado(s), {updated} atualizado(s), {skipped} linha(s) ignorada(s).',
        'success',
    )
    return import_redirect_target()


@catalog_bp.route('/produtos/novo', methods=['GET', 'POST'])
@login_required
@permission_required('can_manage_products')
def new_product():
    product = Product(active=True)
    categories = current_company_categories_query().order_by(Category.name.asc()).all()
    kit_products = tenant_query(Product).filter_by(active=True).order_by(Product.name.asc()).all()

    if request.method == 'POST':
        populate_product(product)
        if not product.name:
            flash('Informe o nome do produto.', 'danger')
            return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)
        if product_barcode_exists(product.barcode):
            flash('Já existe um produto com este código de barras.', 'danger')
            return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)
        if product.is_kit and (not product.kit_component_product_id or product.kit_component_quantity <= 0):
            flash('Informe o produto base e a quantidade do kit.', 'danger')
            return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)
        if product.id and product.kit_component_product_id == product.id:
            flash('O produto base do kit não pode ser o próprio kit.', 'danger')
            return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)

        tenant_db = tenant_session()
        tenant_db.add(product)
        try:
            tenant_db.commit()
        except IntegrityError:
            tenant_db.rollback()
            flash('Já existe um produto com este código de barras.', 'danger')
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
    kit_products = tenant_query(Product).filter(Product.id != product.id, Product.active.is_(True)).order_by(Product.name.asc()).all()

    if request.method == 'POST':
        populate_product(product)
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

        try:
            tenant_session().commit()
        except IntegrityError:
            tenant_session().rollback()
            flash('Já existe um produto com este código de barras.', 'danger')
            return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)

        flash('Produto atualizado com sucesso.', 'success')
        return redirect(url_for('catalog.products'))

    return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)


@catalog_bp.route('/produtos/<int:product_id>/atualizar', methods=['POST'])
@login_required
@permission_required('can_manage_products')
def quick_update_product(product_id):
    product = tenant_get_or_404(Product, product_id)
    product.company_id = current_tenant_company().id
    product.name = request.form.get('name', '').strip()
    product.barcode = request.form.get('barcode', '').strip() or None
    category_id = request.form.get('category_id') or None
    product.category_id = int(category_id) if category_id else None
    product.cost_price = parse_money(request.form.get('cost_price'))
    product.sale_price = parse_money(request.form.get('sale_price'))
    product.stock_quantity = parse_int(request.form.get('stock_quantity'))
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
        tenant_session().commit()
    except IntegrityError:
        tenant_session().rollback()
        flash('Já existe um produto com este código de barras.', 'danger')
        return redirect(url_for('catalog.products', status='all'))

    flash('Produto atualizado com sucesso.', 'success')
    return redirect(url_for('catalog.products', status='all'))


@catalog_bp.route('/produtos/<int:product_id>/notificacao-estoque')
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
    product.active = not product.active
    tenant_session().commit()

    status = 'ativado' if product.active else 'desativado'
    flash(f'Produto {status} com sucesso.', 'success')
    return redirect(url_for('catalog.products', status='all'))


@catalog_bp.route('/produtos/<int:product_id>/excluir', methods=['POST'])
@login_required
@permission_required('can_manage_products')
def delete_product(product_id):
    product = tenant_get_or_404(Product, product_id)
    tenant_db = tenant_session()
    tenant_db.delete(product)
    tenant_db.commit()

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
    filters = {
        'search': search,
        'usage': usage,
        'sort': sort,
    }

    return render_template(
        'catalog/categories.html',
        categories=categories,
        category_suggestions=category_suggestions,
        filters=filters,
    )


@catalog_bp.route('/categorias/<int:category_id>/atualizar', methods=['POST'])
@login_required
@permission_required('can_manage_categories')
def update_category(category_id):
    category = tenant_get_or_404(Category, category_id)
    category.name = request.form.get('name', '').strip()
    category.company_id = current_tenant_company().id

    if not category.name:
        flash('Informe o nome da categoria.', 'danger')
        return redirect(url_for('catalog.categories'))
    if category_name_exists(category.name, category.id):
        flash('Já existe uma categoria com este nome.', 'danger')
        return redirect(url_for('catalog.categories'))

    try:
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
    tenant_db.delete(category)
    tenant_db.commit()
    flash('Categoria excluída com sucesso.', 'success')
    return redirect(url_for('catalog.categories'))
