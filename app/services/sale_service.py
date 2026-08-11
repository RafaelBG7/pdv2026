from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import selectinload

from app.models import (
    ApiSaleRequest,
    CashRegister,
    Payment,
    Product,
    Sale,
    SaleItem,
    StockMovement,
)
from app.services.audit_service import record_audit_event
from app.services.stock_service import StockMovementError, decrease_stock, increase_stock


PAYMENT_METHODS = {
    'money': 'Dinheiro',
    'pix': 'Pix',
    'debit': 'Débito',
    'credit': 'Crédito',
}
MONEY_QUANTUM = Decimal('0.01')


class SaleOperationError(Exception):
    def __init__(self, message, code, status_code=422, field=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.field = field


@dataclass(frozen=True)
class SaleLineInput:
    product_id: int
    quantity: int


@dataclass(frozen=True)
class SalePaymentInput:
    method: str
    amount: Decimal


@dataclass
class SaleCreationResult:
    sale: Sale
    idempotency_key: str
    already_processed: bool = False
    stock_warnings: tuple[str, ...] = ()


@dataclass
class SaleCancellationResult:
    sale: Sale
    stock_movements: tuple[StockMovement, ...]
    cash_register_was_closed: bool


def money_decimal(value):
    return Decimal(str(value or 0)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def money_value(value):
    return float(money_decimal(value))


def timestamp_value(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def stock_source_for_product(product):
    if not product.is_kit:
        return product, 1
    if not product.kit_component or int(product.kit_component_quantity or 0) <= 0:
        return None, 0
    return product.kit_component, int(product.kit_component_quantity)


def card_fee_total(company, payments, final_amount, paid_amount):
    if final_amount <= 0 or paid_amount <= 0:
        return Decimal('0.00')

    payment_scale = min(final_amount / paid_amount, Decimal('1.00'))
    fee_total = Decimal('0.00')
    for payment in payments:
        effective_amount = payment.amount * payment_scale
        if payment.method == 'pix' and company.pix_fee_enabled:
            fee_total += effective_amount * money_decimal(company.pix_fee_percent) / Decimal('100')
        elif payment.method == 'debit' and company.debit_fee_enabled:
            fee_total += effective_amount * money_decimal(company.debit_fee_percent) / Decimal('100')
        elif payment.method == 'credit' and company.credit_fee_enabled:
            fee_total += effective_amount * money_decimal(company.credit_fee_percent) / Decimal('100')
    return fee_total.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def find_sale_request(db_session, company_id, idempotency_key):
    return (
        db_session.query(ApiSaleRequest)
        .options(
            selectinload(ApiSaleRequest.sale).selectinload(Sale.items).selectinload(SaleItem.product),
            selectinload(ApiSaleRequest.sale).selectinload(Sale.payments),
        )
        .filter(
            ApiSaleRequest.company_id == company_id,
            ApiSaleRequest.idempotency_key == idempotency_key,
        )
        .first()
    )


def find_completed_sale_request(db_session, company_id, idempotency_key):
    sale_request = find_sale_request(db_session, company_id, idempotency_key)
    if sale_request is None or sale_request.sale is None:
        return None
    return SaleCreationResult(
        sale=sale_request.sale,
        idempotency_key=idempotency_key,
        already_processed=True,
    )


def create_sale(
    db_session,
    company,
    user,
    item_inputs,
    payment_inputs,
    discount_amount,
    idempotency_key,
):
    existing = find_completed_sale_request(db_session, company.id, idempotency_key)
    if existing is not None:
        return existing

    sale_request = ApiSaleRequest(
        company_id=company.id,
        idempotency_key=idempotency_key,
    )
    db_session.add(sale_request)
    db_session.flush()

    cash_register = (
        db_session.query(CashRegister)
        .filter(
            CashRegister.company_id == company.id,
            CashRegister.status == 'open',
        )
        .order_by(CashRegister.opened_at.desc(), CashRegister.id.desc())
        .with_for_update()
        .first()
    )
    if cash_register is None:
        raise SaleOperationError(
            'Abra o caixa antes de registrar uma venda.',
            'cash_register_required',
            409,
        )

    aggregated_items = {}
    for item in item_inputs:
        if item.quantity <= 0:
            raise SaleOperationError(
                'A quantidade precisa ser maior que zero.',
                'invalid_quantity',
                422,
                'items',
            )
        aggregated_items[item.product_id] = aggregated_items.get(item.product_id, 0) + item.quantity

    if not aggregated_items:
        raise SaleOperationError(
            'Adicione pelo menos um produto à venda.',
            'sale_items_required',
            422,
            'items',
        )

    products = (
        db_session.query(Product)
        .options(selectinload(Product.kit_component))
        .filter(
            Product.company_id == company.id,
            Product.id.in_(aggregated_items),
        )
        .order_by(Product.id)
        .all()
    )
    products_by_id = {product.id: product for product in products}
    selected_items = []
    stock_requirements = {}
    subtotal = Decimal('0.00')

    for product_id, quantity in aggregated_items.items():
        product = products_by_id.get(product_id)
        if product is None:
            raise SaleOperationError(
                f'O produto #{product_id} não pertence a esta adega.',
                'product_not_found',
                404,
                'items',
            )
        if not product.active:
            raise SaleOperationError(
                f'O produto {product.name} está inativo.',
                'product_inactive',
                409,
                'items',
            )

        stock_product, units_per_sale = stock_source_for_product(product)
        if stock_product is None or stock_product.company_id != company.id:
            raise SaleOperationError(
                f'Configure o kit do produto {product.name} antes de vender.',
                'kit_not_configured',
                409,
                'items',
            )

        required_quantity = units_per_sale * quantity
        stock_requirements[stock_product.id] = (
            stock_requirements.get(stock_product.id, 0) + required_quantity
        )
        line_total = (money_decimal(product.sale_price) * quantity).quantize(
            MONEY_QUANTUM,
            rounding=ROUND_HALF_UP,
        )
        selected_items.append((product, stock_product, required_quantity, quantity, line_total))
        subtotal += line_total

    stock_products = {
        product.id: product
        for product in db_session.query(Product).filter(
            Product.company_id == company.id,
            Product.id.in_(stock_requirements),
        ).order_by(Product.id).with_for_update().all()
    }
    stock_warnings = []
    for stock_product_id, required_quantity in stock_requirements.items():
        stock_product = stock_products.get(stock_product_id)
        if stock_product is None:
            raise SaleOperationError(
                'O produto usado para baixa de estoque não foi encontrado.',
                'stock_product_not_found',
                409,
                'items',
            )
        resulting_stock = int(stock_product.stock_quantity or 0) - required_quantity
        if resulting_stock < 0 and not company.allow_negative_stock:
            raise SaleOperationError(
                f'Estoque insuficiente para {stock_product.name}.',
                'insufficient_stock',
                409,
                'items',
            )
        if resulting_stock < 0:
            stock_warnings.append(f'{stock_product.name}: {resulting_stock} un.')

    subtotal = subtotal.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    discount = money_decimal(discount_amount)
    if discount > subtotal:
        raise SaleOperationError(
            'O desconto não pode ser maior que o subtotal.',
            'discount_exceeds_subtotal',
            422,
            'discount_amount',
        )
    final_amount = (subtotal - discount).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)

    normalized_payments = []
    paid_amount = Decimal('0.00')
    for payment in payment_inputs:
        if payment.method not in PAYMENT_METHODS:
            raise SaleOperationError(
                'A forma de pagamento informada é inválida.',
                'invalid_payment_method',
                422,
                'payments',
            )
        amount = money_decimal(payment.amount)
        if amount <= 0:
            continue
        normalized_payments.append(SalePaymentInput(payment.method, amount))
        paid_amount += amount

    paid_amount = paid_amount.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    if paid_amount < final_amount:
        missing = final_amount - paid_amount
        raise SaleOperationError(
            f'Falta pagar R$ {str(missing).replace(".", ",")}.',
            'payment_insufficient',
            422,
            'payments',
        )

    machine_fee = card_fee_total(company, normalized_payments, final_amount, paid_amount)
    sale = Sale(
        total_amount=money_value(subtotal),
        discount_amount=money_value(discount),
        final_amount=money_value(final_amount),
        payment_status='paid',
        user_id=user.id,
        company_id=company.id,
        cash_register_id=cash_register.id,
    )
    db_session.add(sale)
    db_session.flush()

    try:
        for product, stock_product, required_quantity, quantity, line_total in selected_items:
            decrease_stock(
                db_session,
                stock_product,
                required_quantity,
                movement_type='sale',
                source_type='sale',
                user_id=user.id,
                source_id=sale.id,
                unit_cost=stock_product.cost_price,
                reason=f'Baixa da venda #{sale.id}',
                notes=f'Produto vendido: {product.name}',
                allow_negative_stock=company.allow_negative_stock,
            )
            unit_cost = money_decimal(product.cost_price)
            item_fee = (
                machine_fee * (line_total / subtotal)
                if subtotal > 0
                else Decimal('0.00')
            )
            profit = ((money_decimal(product.sale_price) - unit_cost) * quantity) - item_fee
            db_session.add(SaleItem(
                sale_id=sale.id,
                product_id=product.id,
                quantity=quantity,
                unit_price=money_value(product.sale_price),
                unit_cost_price=money_value(unit_cost),
                total_price=money_value(line_total),
                profit_amount=money_value(profit),
            ))
    except StockMovementError as error:
        raise SaleOperationError(str(error), 'stock_movement_failed', 409, 'items') from error

    for payment in normalized_payments:
        db_session.add(Payment(
            sale_id=sale.id,
            method=payment.method,
            amount=money_value(payment.amount),
        ))

    sale_request.sale_id = sale.id
    audit_log = record_audit_event(
        'sale_completed',
        'sale',
        sale.id,
        f'Venda #{sale.id} concluída pelo aplicativo Windows.',
        new_values={
            'sale_id': sale.id,
            'subtotal': money_value(subtotal),
            'discount': money_value(discount),
            'final_amount': money_value(final_amount),
            'paid_amount': money_value(paid_amount),
            'cash_register_id': cash_register.id,
            'idempotency_key': idempotency_key,
            'client': 'windows_native',
            'payments': {
                payment.method: money_value(payment.amount)
                for payment in normalized_payments
            },
            'items': [
                {
                    'product_id': product.id,
                    'name': product.name,
                    'quantity': quantity,
                    'total': money_value(line_total),
                }
                for product, _, _, quantity, line_total in selected_items
            ],
        },
        company_id=company.id,
        user=user,
        db_session=db_session,
    )
    if audit_log is None:
        raise SaleOperationError(
            'Não foi possível registrar a auditoria. O cancelamento foi interrompido.',
            'sale_cancellation_audit_failed',
            500,
        )
    db_session.flush()
    return SaleCreationResult(
        sale=sale,
        idempotency_key=idempotency_key,
        stock_warnings=tuple(stock_warnings),
    )


def cancel_sale(db_session, company, user, sale_id, reason):
    cancellation_reason = (reason or '').strip()
    if not cancellation_reason:
        raise SaleOperationError(
            'Informe o motivo do cancelamento.',
            'cancellation_reason_required',
            422,
            'reason',
        )
    if len(cancellation_reason) > 500:
        raise SaleOperationError(
            'O motivo do cancelamento deve ter no máximo 500 caracteres.',
            'cancellation_reason_too_long',
            422,
            'reason',
        )

    sale_query = (
        db_session.query(Sale)
        .options(
            selectinload(Sale.items).selectinload(SaleItem.product),
            selectinload(Sale.payments),
        )
        .filter(
            Sale.id == sale_id,
            Sale.company_id == company.id,
        )
    )
    bind = db_session.get_bind()
    if bind is not None and bind.dialect.name.startswith('mysql'):
        sale_query = sale_query.with_for_update()
    sale = sale_query.first()
    if sale is None:
        raise SaleOperationError(
            'Venda não encontrada nesta adega.',
            'sale_not_found',
            404,
        )
    if sale.is_cancelled:
        raise SaleOperationError(
            'Esta venda já foi cancelada.',
            'sale_already_cancelled',
            409,
        )

    existing_cancellations = db_session.query(StockMovement.id).filter(
        StockMovement.company_id == company.id,
        StockMovement.source_type == 'sale_cancellation',
        StockMovement.source_id == sale.id,
        StockMovement.movement_type == 'cancellation',
    ).first()
    if existing_cancellations is not None:
        raise SaleOperationError(
            'Esta venda já possui devolução de estoque registrada.',
            'sale_cancellation_stock_already_returned',
            409,
        )

    original_movements = (
        db_session.query(StockMovement)
        .filter(
            StockMovement.company_id == company.id,
            StockMovement.source_type == 'sale',
            StockMovement.source_id == sale.id,
            StockMovement.movement_type == 'sale',
        )
        .order_by(StockMovement.product_id.asc(), StockMovement.id.asc())
        .all()
    )
    if sale.items and not original_movements:
        raise SaleOperationError(
            'A movimentação original desta venda não foi encontrada. O cancelamento foi interrompido para proteger o estoque.',
            'sale_stock_movements_missing',
            409,
        )

    quantities_by_product = {}
    for movement in original_movements:
        if movement.product_id is None:
            raise SaleOperationError(
                'Um produto da movimentação original não está mais disponível.',
                'sale_stock_product_missing',
                409,
            )
        quantities_by_product[movement.product_id] = (
            quantities_by_product.get(movement.product_id, 0) + int(movement.quantity or 0)
        )

    products = {
        product.id: product
        for product in db_session.query(Product).filter(
            Product.company_id == company.id,
            Product.id.in_(quantities_by_product),
        ).order_by(Product.id).all()
    } if quantities_by_product else {}
    if len(products) != len(quantities_by_product):
        raise SaleOperationError(
            'Um produto consumido pela venda não foi encontrado. O estoque não foi alterado.',
            'sale_stock_product_missing',
            409,
        )

    returned_movements = []
    try:
        for product_id, quantity in quantities_by_product.items():
            product = products[product_id]
            returned_movements.append(increase_stock(
                db_session,
                product,
                quantity,
                movement_type='cancellation',
                source_type='sale_cancellation',
                user_id=user.id,
                source_id=sale.id,
                unit_cost=product.cost_price,
                reason=f'Cancelamento da venda #{sale.id}',
                notes=cancellation_reason,
            ))
    except StockMovementError as error:
        raise SaleOperationError(
            str(error),
            'sale_cancellation_stock_failed',
            409,
        ) from error

    cancelled_at = datetime.now(timezone.utc)
    previous_status = sale.status or 'completed'
    sale.status = 'cancelled'
    sale.cancelled_at = cancelled_at
    sale.cancelled_by_user_id = user.id
    sale.cancellation_reason = cancellation_reason
    cash_register_was_closed = bool(
        sale.cash_register is not None and sale.cash_register.status == 'closed'
    )
    record_audit_event(
        'sale_cancelled',
        'sale',
        sale.id,
        f'Venda #{sale.id} cancelada.',
        old_values={
            'status': previous_status,
            'final_amount': money_value(sale.final_amount),
            'cash_register_id': sale.cash_register_id,
        },
        new_values={
            'status': sale.status,
            'cancelled_at': cancelled_at,
            'cancelled_by_user_id': user.id,
            'cancellation_reason': cancellation_reason,
            'cash_register_status': sale.cash_register.status if sale.cash_register else '',
            'stock_movements': [movement.id for movement in returned_movements],
        },
        company_id=company.id,
        user=user,
        db_session=db_session,
    )
    db_session.flush()
    return SaleCancellationResult(
        sale=sale,
        stock_movements=tuple(returned_movements),
        cash_register_was_closed=cash_register_was_closed,
    )


def serialize_sale_result(result):
    sale = result.sale
    paid_amount = sum((money_decimal(payment.amount) for payment in sale.payments), Decimal('0.00'))
    final_amount = money_decimal(sale.final_amount)
    change_amount = max(paid_amount - final_amount, Decimal('0.00'))
    return {
        'id': sale.id,
        'idempotency_key': result.idempotency_key,
        'already_processed': result.already_processed,
        'created_at': timestamp_value(sale.created_at),
        'cash_register_id': sale.cash_register_id,
        'payment_status': sale.payment_status,
        'status': sale.status or 'completed',
        'is_cancelled': sale.is_cancelled,
        'cancelled_at': timestamp_value(sale.cancelled_at),
        'cancelled_by_user_id': sale.cancelled_by_user_id,
        'cancellation_reason': sale.cancellation_reason or '',
        'subtotal': money_value(sale.total_amount),
        'discount_amount': money_value(sale.discount_amount),
        'final_amount': money_value(final_amount),
        'paid_amount': money_value(paid_amount),
        'change_amount': money_value(change_amount),
        'stock_warnings': list(result.stock_warnings),
        'items': [
            {
                'product_id': item.product_id,
                'name': item.product.name if item.product else f'Produto #{item.product_id}',
                'quantity': int(item.quantity or 0),
                'unit_price': money_value(item.unit_price),
                'subtotal': money_value(item.total_price),
            }
            for item in sale.items
        ],
        'payments': [
            {
                'method': payment.method,
                'label': PAYMENT_METHODS.get(payment.method, payment.method),
                'amount': money_value(payment.amount),
            }
            for payment in sale.payments
        ],
    }
