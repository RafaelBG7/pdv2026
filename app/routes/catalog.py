from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.extensions import db
from app.models import Category, Product


catalog_bp = Blueprint('catalog', __name__, url_prefix='/catalogo')


def parse_money(value):
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


def populate_product(product):
    barcode = request.form.get('barcode', '').strip()
    category_id = request.form.get('category_id') or None
    kit_component_product_id = request.form.get('kit_component_product_id') or None

    product.name = request.form.get('name', '').strip()
    product.barcode = barcode or None
    product.category_id = int(category_id) if category_id else None
    product.cost_price = parse_money(request.form.get('cost_price'))
    product.sale_price = parse_money(request.form.get('sale_price'))
    product.stock_quantity = parse_int(request.form.get('stock_quantity'))
    product.active = request.form.get('active') == 'on'
    product.is_kit = request.form.get('is_kit') == 'on'
    product.kit_component_product_id = int(kit_component_product_id) if kit_component_product_id else None
    product.kit_component_quantity = parse_int(request.form.get('kit_component_quantity'))

    if not product.is_kit:
        product.kit_component_product_id = None
        product.kit_component_quantity = 0


@catalog_bp.route('/produtos')
@login_required
def products():
    search = request.args.get('q', '').strip()
    status = request.args.get('status', 'active')
    category_id = request.args.get('category_id', '').strip()
    stock = request.args.get('stock', 'all')
    min_price = parse_optional_money(request.args.get('min_price'))
    max_price = parse_optional_money(request.args.get('max_price'))
    sort = request.args.get('sort', 'name_asc')

    query = Product.query
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
        query = query.filter(Product.stock_quantity > 0, Product.stock_quantity <= 5)

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
    categories = Category.query.order_by(Category.name.asc()).all()
    kit_products = Product.query.filter_by(active=True).order_by(Product.name.asc()).all()
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
    )


@catalog_bp.route('/produtos/novo', methods=['GET', 'POST'])
@login_required
def new_product():
    product = Product(active=True)
    categories = Category.query.order_by(Category.name.asc()).all()
    kit_products = Product.query.filter_by(active=True).order_by(Product.name.asc()).all()

    if request.method == 'POST':
        populate_product(product)
        if not product.name:
            flash('Informe o nome do produto.', 'danger')
            return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)
        if product.is_kit and (not product.kit_component_product_id or product.kit_component_quantity <= 0):
            flash('Informe o produto base e a quantidade do kit.', 'danger')
            return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)
        if product.id and product.kit_component_product_id == product.id:
            flash('O produto base do kit não pode ser o próprio kit.', 'danger')
            return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)

        db.session.add(product)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash('Já existe um produto com este código de barras.', 'danger')
            return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)

        flash('Produto cadastrado com sucesso.', 'success')
        return redirect(url_for('catalog.products'))

    return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)


@catalog_bp.route('/produtos/<int:product_id>/editar', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    product = db.get_or_404(Product, product_id)
    categories = Category.query.order_by(Category.name.asc()).all()
    kit_products = Product.query.filter(Product.id != product.id, Product.active.is_(True)).order_by(Product.name.asc()).all()

    if request.method == 'POST':
        populate_product(product)
        if not product.name:
            flash('Informe o nome do produto.', 'danger')
            return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)
        if product.is_kit and (not product.kit_component_product_id or product.kit_component_quantity <= 0):
            flash('Informe o produto base e a quantidade do kit.', 'danger')
            return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)
        if product.id and product.kit_component_product_id == product.id:
            flash('O produto base do kit não pode ser o próprio kit.', 'danger')
            return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash('Já existe um produto com este código de barras.', 'danger')
            return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)

        flash('Produto atualizado com sucesso.', 'success')
        return redirect(url_for('catalog.products'))

    return render_template('catalog/product_form.html', product=product, categories=categories, kit_products=kit_products)


@catalog_bp.route('/produtos/<int:product_id>/atualizar', methods=['POST'])
@login_required
def quick_update_product(product_id):
    product = db.get_or_404(Product, product_id)
    product.name = request.form.get('name', '').strip()
    product.barcode = request.form.get('barcode', '').strip() or None
    category_id = request.form.get('category_id') or None
    product.category_id = int(category_id) if category_id else None
    product.cost_price = parse_money(request.form.get('cost_price'))
    product.sale_price = parse_money(request.form.get('sale_price'))
    product.stock_quantity = parse_int(request.form.get('stock_quantity'))
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
    if product.is_kit and (not product.kit_component_product_id or product.kit_component_quantity <= 0):
        flash('Informe o produto base e a quantidade do kit.', 'danger')
        return redirect(url_for('catalog.products', status='all'))
    if product.id and product.kit_component_product_id == product.id:
        flash('O produto base do kit não pode ser o próprio kit.', 'danger')
        return redirect(url_for('catalog.products', status='all'))

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash('Já existe um produto com este código de barras.', 'danger')
        return redirect(url_for('catalog.products', status='all'))

    flash('Produto atualizado com sucesso.', 'success')
    return redirect(url_for('catalog.products', status='all'))


@catalog_bp.route('/produtos/<int:product_id>/alternar-status', methods=['POST'])
@login_required
def toggle_product(product_id):
    product = db.get_or_404(Product, product_id)
    product.active = not product.active
    db.session.commit()

    status = 'ativado' if product.active else 'desativado'
    flash(f'Produto {status} com sucesso.', 'success')
    return redirect(url_for('catalog.products', status='all'))


@catalog_bp.route('/produtos/<int:product_id>/excluir', methods=['POST'])
@login_required
def delete_product(product_id):
    product = db.get_or_404(Product, product_id)
    db.session.delete(product)
    db.session.commit()

    flash('Produto excluído com sucesso.', 'success')
    return redirect(url_for('catalog.products', status='all'))


@catalog_bp.route('/categorias', methods=['GET', 'POST'])
@login_required
def categories():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Informe o nome da categoria.', 'danger')
        else:
            category = Category(name=name)
            db.session.add(category)
            try:
                db.session.commit()
                flash('Categoria cadastrada com sucesso.', 'success')
            except IntegrityError:
                db.session.rollback()
                flash('Já existe uma categoria com este nome.', 'danger')

        return redirect(url_for('catalog.categories'))

    search = request.args.get('q', '').strip()
    usage = request.args.get('usage', 'all')
    sort = request.args.get('sort', 'name_asc')

    product_count = func.count(Product.id).label('product_count')
    query = (
        db.session.query(Category, product_count)
        .outerjoin(Product, Product.category_id == Category.id)
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
def update_category(category_id):
    category = db.get_or_404(Category, category_id)
    category.name = request.form.get('name', '').strip()

    if not category.name:
        flash('Informe o nome da categoria.', 'danger')
        return redirect(url_for('catalog.categories'))

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash('Já existe uma categoria com este nome.', 'danger')
        return redirect(url_for('catalog.categories'))

    flash('Categoria atualizada com sucesso.', 'success')
    return redirect(url_for('catalog.categories'))


@catalog_bp.route('/categorias/<int:category_id>/excluir', methods=['POST'])
@login_required
def delete_category(category_id):
    category = db.get_or_404(Category, category_id)
    if Product.query.filter_by(category_id=category.id).first():
        flash('Não é possível excluir uma categoria com produtos vinculados.', 'danger')
        return redirect(url_for('catalog.categories'))

    db.session.delete(category)
    db.session.commit()
    flash('Categoria excluída com sucesso.', 'success')
    return redirect(url_for('catalog.categories'))
