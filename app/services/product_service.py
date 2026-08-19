from dataclasses import dataclass
from decimal import Decimal

from app.models import Category, Product, SaleItem
from app.services.audit_service import changed_values, record_audit_event
from app.services.stock_service import StockMovementError, adjust_stock


class ProductOperationError(ValueError):
    def __init__(self, message, code, status_code=422, field=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.field = field


@dataclass(frozen=True)
class ProductInput:
    name: str
    barcode: str
    category_id: int | None
    cost_price: Decimal
    sale_price: Decimal
    stock_quantity: int
    min_stock_quantity: int
    active: bool
    stock_reason: str = ''
    is_kit: bool = False
    kit_component_product_id: int | None = None
    kit_component_quantity: int = 0


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


def create_product(db_session, company, user, product_input):
    category, kit_component = validate_product_input(db_session, company.id, product_input)
    product = Product(
        name=product_input.name,
        barcode=product_input.barcode or None,
        category_id=category.id if category else None,
        company_id=company.id,
        cost_price=float(product_input.cost_price),
        sale_price=float(product_input.sale_price),
        stock_quantity=0,
        min_stock_quantity=product_input.min_stock_quantity,
        active=product_input.active,
        is_kit=product_input.is_kit,
        kit_component_product_id=kit_component.id if kit_component else None,
        kit_component_quantity=product_input.kit_component_quantity if kit_component else 0,
    )
    product.category = category
    db_session.add(product)
    db_session.flush()

    if product_input.stock_quantity != 0:
        try:
            adjust_stock(
                db_session,
                product,
                product_input.stock_quantity,
                source_type='product_creation',
                user_id=user.id,
                unit_cost=product_input.cost_price,
                reason=product_input.stock_reason or 'Estoque inicial informado no cadastro nativo',
                allow_negative_stock=bool(company.allow_negative_stock),
            )
        except StockMovementError as error:
            raise ProductOperationError(
                str(error),
                'invalid_stock_adjustment',
                422,
                'stock_quantity',
            ) from error

    record_audit_event(
        'product_created',
        'product',
        product.id,
        f'Produto {product.name} cadastrado pelo aplicativo Windows.',
        new_values=product_audit_values(product),
        company_id=company.id,
        user=user,
        db_session=db_session,
    )
    db_session.flush()
    return product


def update_product(db_session, company, user, product_id, product_input):
    query = db_session.query(Product).filter(
        Product.id == product_id,
        Product.company_id == company.id,
    )
    bind = db_session.get_bind()
    if bind is not None and bind.dialect.name.startswith('mysql'):
        query = query.with_for_update()
    product = query.first()
    if product is None:
        raise ProductOperationError(
            'Produto não encontrado nesta adega.',
            'product_not_found',
            404,
        )

    category, kit_component = validate_product_input(
        db_session,
        company.id,
        product_input,
        product_id=product.id,
    )
    old_values = product_audit_values(product)
    previous_stock = int(product.stock_quantity or 0)

    product.name = product_input.name
    product.barcode = product_input.barcode or None
    product.category_id = category.id if category else None
    product.category = category
    product.cost_price = float(product_input.cost_price)
    product.sale_price = float(product_input.sale_price)
    product.min_stock_quantity = product_input.min_stock_quantity
    product.active = product_input.active
    product.is_kit = product_input.is_kit
    product.kit_component_product_id = kit_component.id if kit_component else None
    product.kit_component = kit_component
    product.kit_component_quantity = product_input.kit_component_quantity if kit_component else 0
    db_session.flush()

    if product_input.stock_quantity != previous_stock:
        try:
            adjust_stock(
                db_session,
                product,
                product_input.stock_quantity,
                source_type='product_edit',
                user_id=user.id,
                unit_cost=product_input.cost_price,
                reason=product_input.stock_reason or 'Ajuste registrado pela edição nativa do produto',
                allow_negative_stock=bool(company.allow_negative_stock),
            )
        except StockMovementError as error:
            raise ProductOperationError(
                str(error),
                'invalid_stock_adjustment',
                422,
                'stock_quantity',
            ) from error

    new_values = product_audit_values(product)
    old_diff, new_diff = changed_values(old_values, new_values)
    if old_diff or new_diff:
        record_audit_event(
            'product_updated',
            'product',
            product.id,
            f'Produto {product.name} atualizado pelo aplicativo Windows.',
            old_values=old_diff,
            new_values=new_diff,
            company_id=company.id,
            user=user,
            db_session=db_session,
        )
    db_session.flush()
    return product


def delete_product(db_session, company, user, product_id):
    product = db_session.query(Product).filter(
        Product.id == product_id,
        Product.company_id == company.id,
    ).first()
    if product is None:
        raise ProductOperationError(
            'Produto não encontrado nesta adega.',
            'product_not_found',
            404,
        )

    dependent_kit = db_session.query(Product.id).filter(
        Product.company_id == company.id,
        Product.kit_component_product_id == product.id,
    ).first()
    if dependent_kit is not None:
        raise ProductOperationError(
            'Este produto é base de um kit e não pode ser excluído.',
            'product_used_by_kit',
            409,
        )

    sale_item = db_session.query(SaleItem.id).filter(
        SaleItem.product_id == product.id,
    ).first()
    if sale_item is not None:
        raise ProductOperationError(
            'Este produto possui vendas registradas. Inative-o para preservar o histórico.',
            'product_has_sales',
            409,
        )

    old_values = product_audit_values(product)
    record_audit_event(
        'product_deleted',
        'product',
        product.id,
        f'Produto {product.name} excluído.',
        old_values=old_values,
        company_id=company.id,
        user=user,
        db_session=db_session,
    )
    deleted_id = product.id
    db_session.delete(product)
    db_session.flush()
    return deleted_id


def validate_product_input(db_session, company_id, product_input, product_id=None):
    if not product_input.name:
        raise ProductOperationError(
            'Informe o nome do produto.',
            'product_name_required',
            422,
            'name',
        )

    duplicate_query = db_session.query(Product.id).filter(
        Product.company_id == company_id,
        Product.barcode == product_input.barcode,
    )
    if product_id is not None:
        duplicate_query = duplicate_query.filter(Product.id != product_id)
    if product_input.barcode and duplicate_query.first() is not None:
        raise ProductOperationError(
            'Já existe um produto com este código de barras nesta adega.',
            'barcode_already_exists',
            409,
            'barcode',
        )

    category = None
    if product_input.category_id is not None:
        category = db_session.query(Category).filter(
            Category.id == product_input.category_id,
            Category.company_id == company_id,
        ).first()
        if category is None:
            raise ProductOperationError(
                'A categoria informada não pertence a esta adega.',
                'category_not_found',
                422,
                'category_id',
            )

    kit_component = None
    if product_input.is_kit:
        if product_input.kit_component_product_id is None or product_input.kit_component_quantity < 1:
            raise ProductOperationError(
                'Informe o produto base e a quantidade consumida pelo kit.',
                'kit_component_required',
                422,
                'kit_component_product_id',
            )
        if product_id is not None and product_input.kit_component_product_id == product_id:
            raise ProductOperationError(
                'O produto base do kit não pode ser o próprio kit.',
                'kit_component_self_reference',
                422,
                'kit_component_product_id',
            )
        kit_component = db_session.query(Product).filter(
            Product.id == product_input.kit_component_product_id,
            Product.company_id == company_id,
            Product.active.is_(True),
        ).first()
        if kit_component is None:
            raise ProductOperationError(
                'O produto base informado não pertence a esta adega ou está inativo.',
                'kit_component_not_found',
                422,
                'kit_component_product_id',
            )

    return category, kit_component
