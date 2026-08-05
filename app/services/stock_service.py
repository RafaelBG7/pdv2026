from decimal import Decimal, ROUND_HALF_UP

from app.models import Product, StockMovement
from app.services.audit_service import record_audit_event


MOVEMENT_TYPE_LABELS = {
    'entry': 'Entrada manual',
    'sale': 'Venda',
    'adjustment_in': 'Ajuste de entrada',
    'adjustment_out': 'Ajuste de saída',
    'return': 'Devolução',
    'cancellation': 'Cancelamento',
    'initial_stock': 'Estoque inicial',
    'import': 'Importação',
}

SOURCE_TYPE_LABELS = {
    'manual': 'Manual',
    'sale': 'Venda',
    'product_creation': 'Cadastro de produto',
    'product_edit': 'Edição de produto',
    'spreadsheet_import': 'Importação de planilha',
    'sale_cancellation': 'Cancelamento de venda',
    'system': 'Sistema',
}


class StockMovementError(ValueError):
    pass


def decimal_money(value):
    try:
        return Decimal(str(value or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except Exception as error:
        raise StockMovementError('Valor monetário inválido.') from error


def stock_movement_label(movement_type):
    return MOVEMENT_TYPE_LABELS.get(movement_type, movement_type)


def stock_source_label(source_type):
    return SOURCE_TYPE_LABELS.get(source_type, source_type)


def audit_action_for_movement(movement_type):
    if movement_type == 'sale':
        return 'stock_sale'
    if movement_type == 'import':
        return 'stock_import'
    if movement_type == 'return':
        return 'stock_return'
    if movement_type == 'entry':
        return 'stock_entry'
    return 'stock_adjustment'


def lock_product(db_session, product):
    if not product or not product.id:
        return product
    bind = db_session.get_bind()
    dialect_name = bind.dialect.name if bind is not None else ''
    query = db_session.query(Product).filter(
        Product.id == product.id,
        Product.company_id == product.company_id,
    )
    if dialect_name.startswith('mysql'):
        query = query.with_for_update()
    locked = query.first()
    if not locked:
        raise StockMovementError('Produto não encontrado para movimentação de estoque.')
    return locked


def register_stock_movement(
    db_session,
    product,
    movement_type,
    source_type,
    quantity,
    new_stock,
    user_id=None,
    source_id=None,
    unit_cost=None,
    reason='',
    notes='',
    audit=True,
):
    quantity = int(quantity or 0)
    if quantity <= 0:
        raise StockMovementError('A quantidade da movimentação precisa ser maior que zero.')

    product = lock_product(db_session, product)
    previous_stock = int(product.stock_quantity or 0)
    new_stock = int(new_stock)
    unit_cost_value = decimal_money(unit_cost if unit_cost is not None else product.cost_price)
    total_cost_value = (unit_cost_value * Decimal(quantity)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    product.stock_quantity = new_stock
    movement = StockMovement(
        company_id=product.company_id,
        product_id=product.id,
        user_id=user_id,
        movement_type=movement_type,
        source_type=source_type,
        source_id=source_id,
        quantity=quantity,
        previous_stock=previous_stock,
        new_stock=new_stock,
        unit_cost=unit_cost_value,
        total_cost=total_cost_value,
        reason=reason or stock_movement_label(movement_type),
        notes=notes or '',
    )
    db_session.add(movement)
    db_session.flush()

    from app.services.notification_service import create_notification, resolve_notification
    stock_notification_keys = {
        'negative': f'product_negative_stock:{product.company_id}:{product.id}',
        'out': f'product_out_of_stock:{product.company_id}:{product.id}',
        'low': f'product_low_stock:{product.company_id}:{product.id}',
    }
    if new_stock < 0:
        create_notification(
            db_session,
            company_id=product.company_id,
            user_id=None,
            notification_type='product_negative_stock',
            category='stock',
            severity='critical',
            title=f'Estoque negativo - {product.name}',
            message=f'O produto {product.name} ficou com {new_stock} unidade(s) em estoque.',
            deduplication_key=stock_notification_keys['negative'],
            entity_type='product',
            entity_id=product.id,
            action_url='/estoque/movimentacoes',
            metadata={'stock_quantity': new_stock, 'movement_id': movement.id},
        )
    else:
        resolve_notification(db_session, product.company_id, stock_notification_keys['negative'])

    if new_stock == 0:
        create_notification(
            db_session,
            company_id=product.company_id,
            user_id=None,
            notification_type='product_out_of_stock',
            category='stock',
            severity='critical',
            title=f'Produto sem estoque - {product.name}',
            message=f'O produto {product.name} chegou a zero unidade em estoque.',
            deduplication_key=stock_notification_keys['out'],
            entity_type='product',
            entity_id=product.id,
            action_url='/catalogo/produtos',
            metadata={'stock_quantity': new_stock, 'movement_id': movement.id},
        )
    else:
        resolve_notification(db_session, product.company_id, stock_notification_keys['out'])

    minimum_stock = int(product.min_stock_quantity or 0)
    if 0 < new_stock <= minimum_stock:
        create_notification(
            db_session,
            company_id=product.company_id,
            user_id=None,
            notification_type='product_low_stock',
            category='stock',
            severity='warning',
            title=f'Estoque baixo - {product.name}',
            message=f'{product.name} possui {new_stock} unidade(s); mínimo configurado: {minimum_stock}.',
            deduplication_key=stock_notification_keys['low'],
            entity_type='product',
            entity_id=product.id,
            action_url='/catalogo/produtos',
            metadata={'stock_quantity': new_stock, 'minimum_stock': minimum_stock, 'movement_id': movement.id},
            email_requested=False,
        )
    else:
        resolve_notification(db_session, product.company_id, stock_notification_keys['low'])

    if movement_type in {'adjustment_in', 'adjustment_out'} and quantity >= 50:
        create_notification(
            db_session,
            company_id=product.company_id,
            notification_type='large_manual_stock_adjustment',
            category='stock',
            severity='warning',
            title=f'Grande ajuste de estoque - {product.name}',
            message=f'Foi realizado um ajuste manual de {quantity} unidade(s) em {product.name}.',
            deduplication_key=f'large_stock_adjustment:{product.company_id}:{movement.id}',
            user_id=user_id,
            entity_type='stock_movement',
            entity_id=movement.id,
            action_url='/estoque/movimentacoes',
            metadata={'quantity': quantity, 'previous_stock': previous_stock, 'new_stock': new_stock},
            email_requested=False,
        )

    if audit:
        record_audit_event(
            audit_action_for_movement(movement_type),
            'stock_movement',
            movement.id,
            f'{stock_movement_label(movement_type)} de {quantity} un. em {product.name}.',
            old_values={'stock_quantity': previous_stock},
            new_values={
                'stock_quantity': new_stock,
                'movement_id': movement.id,
                'product_id': product.id,
                'quantity': quantity,
                'source_type': source_type,
            },
            company_id=product.company_id,
            db_session=db_session,
        )
    return movement


def increase_stock(
    db_session,
    product,
    quantity,
    movement_type='entry',
    source_type='manual',
    user_id=None,
    source_id=None,
    unit_cost=None,
    reason='',
    notes='',
):
    product = lock_product(db_session, product)
    new_stock = int(product.stock_quantity or 0) + int(quantity or 0)
    return register_stock_movement(
        db_session,
        product,
        movement_type,
        source_type,
        quantity,
        new_stock,
        user_id=user_id,
        source_id=source_id,
        unit_cost=unit_cost,
        reason=reason,
        notes=notes,
    )


def decrease_stock(
    db_session,
    product,
    quantity,
    movement_type='adjustment_out',
    source_type='manual',
    user_id=None,
    source_id=None,
    unit_cost=None,
    reason='',
    notes='',
    allow_negative_stock=False,
):
    product = lock_product(db_session, product)
    quantity = int(quantity or 0)
    new_stock = int(product.stock_quantity or 0) - quantity
    if new_stock < 0 and not allow_negative_stock:
        raise StockMovementError(f'Estoque insuficiente para {product.name}.')
    return register_stock_movement(
        db_session,
        product,
        movement_type,
        source_type,
        quantity,
        new_stock,
        user_id=user_id,
        source_id=source_id,
        unit_cost=unit_cost,
        reason=reason,
        notes=notes,
    )


def adjust_stock(
    db_session,
    product,
    new_stock,
    source_type='manual',
    user_id=None,
    source_id=None,
    unit_cost=None,
    reason='',
    notes='',
    allow_negative_stock=False,
):
    product = lock_product(db_session, product)
    previous_stock = int(product.stock_quantity or 0)
    new_stock = int(new_stock)
    if new_stock < 0 and not allow_negative_stock:
        raise StockMovementError('O estoque resultante não pode ficar negativo.')
    difference = new_stock - previous_stock
    if difference == 0:
        return None
    if difference > 0:
        return register_stock_movement(
            db_session,
            product,
            'adjustment_in',
            source_type,
            difference,
            new_stock,
            user_id=user_id,
            source_id=source_id,
            unit_cost=unit_cost,
            reason=reason or 'Ajuste positivo de estoque',
            notes=notes,
        )
    return register_stock_movement(
        db_session,
        product,
        'adjustment_out',
        source_type,
        abs(difference),
        new_stock,
        user_id=user_id,
        source_id=source_id,
        unit_cost=unit_cost,
        reason=reason or 'Ajuste negativo de estoque',
        notes=notes,
    )
