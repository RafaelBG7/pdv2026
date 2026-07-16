from datetime import date, datetime, time, timedelta

from sqlalchemy import case, func
from sqlalchemy.orm import selectinload

from app.models import CashRegister, Payable, Payment, Product, Sale, SaleItem, User


PAYMENT_METHODS = {
    'money': 'Dinheiro',
    'pix': 'Pix',
    'debit': 'Débito',
    'credit': 'Crédito',
}


def _money(value):
    return round(float(value or 0), 2)


def _item_profit_expression():
    stored_profit = func.coalesce(SaleItem.profit_amount, 0.0)
    calculated_profit = (
        func.coalesce(SaleItem.unit_price, 0.0)
        - func.coalesce(SaleItem.unit_cost_price, 0.0)
    ) * func.coalesce(SaleItem.quantity, 0)
    return case(
        (stored_profit != 0.0, stored_profit),
        else_=calculated_profit,
    )


def _period_filters(company_id, start_at, end_at):
    return (
        Sale.company_id == company_id,
        Sale.created_at >= start_at,
        Sale.created_at < end_at,
    )


def _sales_totals(db_session, company_id, start_at, end_at):
    filters = _period_filters(company_id, start_at, end_at)
    row = db_session.query(
        func.count(Sale.id),
        func.coalesce(func.sum(Sale.final_amount), 0.0),
    ).filter(*filters).one()
    count = int(row[0] or 0)
    total = _money(row[1])
    return {
        'sales_count': count,
        'sales_total': total,
        'average_ticket': _money(total / count) if count else 0.0,
    }


def _sales_profit(db_session, company_id, start_at=None, end_at=None, cash_register_id=None):
    query = (
        db_session.query(func.coalesce(func.sum(_item_profit_expression()), 0.0))
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(Sale.company_id == company_id)
    )
    if start_at is not None:
        query = query.filter(Sale.created_at >= start_at)
    if end_at is not None:
        query = query.filter(Sale.created_at < end_at)
    if cash_register_id is not None:
        query = query.filter(Sale.cash_register_id == cash_register_id)
    return _money(query.scalar())


def _payment_totals(db_session, company_id, start_at, end_at):
    rows = (
        db_session.query(Payment.method, func.coalesce(func.sum(Payment.amount), 0.0))
        .join(Sale, Sale.id == Payment.sale_id)
        .filter(*_period_filters(company_id, start_at, end_at))
        .group_by(Payment.method)
        .all()
    )
    amounts = {method: _money(amount) for method, amount in rows}
    return [
        {
            'method': method,
            'label': label,
            'amount': amounts.get(method, 0.0),
        }
        for method, label in PAYMENT_METHODS.items()
    ]


def _top_products(db_session, company_id, start_at, end_at, include_profit):
    profit_expression = _item_profit_expression()
    rows = (
        db_session.query(
            Product.id,
            Product.name,
            func.coalesce(func.sum(SaleItem.quantity), 0),
            func.coalesce(func.sum(SaleItem.total_price), 0.0),
            func.coalesce(func.sum(profit_expression), 0.0),
        )
        .join(SaleItem, SaleItem.product_id == Product.id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(Product.company_id == company_id)
        .filter(*_period_filters(company_id, start_at, end_at))
        .group_by(Product.id, Product.name)
        .order_by(func.sum(SaleItem.quantity).desc(), func.lower(Product.name), Product.id)
        .limit(5)
        .all()
    )
    return [
        {
            'product_id': product_id,
            'name': name,
            'quantity': int(quantity or 0),
            'total': _money(total),
            'profit': _money(profit) if include_profit else None,
        }
        for product_id, name, quantity, total, profit in rows
    ]


def _low_stock(db_session, company_id):
    candidates = (
        db_session.query(Product)
        .options(selectinload(Product.kit_component))
        .filter(
            Product.company_id == company_id,
            Product.active.is_(True),
            Product.min_stock_quantity > 0,
        )
        .all()
    )
    low_stock = [
        product for product in candidates
        if int(product.effective_stock_quantity or 0) <= int(product.min_stock_quantity or 0)
    ]
    low_stock.sort(key=lambda product: (
        int(product.effective_stock_quantity or 0),
        product.name.casefold(),
        product.id,
    ))
    return len(low_stock), [
        {
            'id': product.id,
            'name': product.name,
            'stock_quantity': int(product.effective_stock_quantity or 0),
            'min_stock_quantity': int(product.min_stock_quantity or 0),
        }
        for product in low_stock[:6]
    ]


def _recent_sales(db_session, company_id):
    sales = (
        db_session.query(Sale)
        .options(selectinload(Sale.payments))
        .filter(Sale.company_id == company_id)
        .order_by(Sale.created_at.desc(), Sale.id.desc())
        .limit(6)
        .all()
    )
    user_ids = {sale.user_id for sale in sales if sale.user_id}
    users = {
        user.id: user.full_name or user.username
        for user in db_session.query(User).filter(
            User.company_id == company_id,
            User.id.in_(user_ids),
        ).all()
    } if user_ids else {}
    return [
        {
            'id': sale.id,
            'created_at': sale.created_at.isoformat() if sale.created_at else None,
            'final_amount': _money(sale.final_amount),
            'payment_status': sale.payment_status or 'pending',
            'user_name': users.get(sale.user_id, 'Usuário não identificado'),
            'payment_methods': [
                PAYMENT_METHODS.get(payment.method, payment.method)
                for payment in sale.payments
                if _money(payment.amount) > 0
            ],
        }
        for sale in sales
    ]


def _current_cash(db_session, company_id, include_reports):
    cash_register = (
        db_session.query(CashRegister)
        .filter(
            CashRegister.company_id == company_id,
            CashRegister.status == 'open',
        )
        .order_by(CashRegister.opened_at.desc(), CashRegister.id.desc())
        .first()
    )
    if cash_register is None:
        return {
            'id': None,
            'status': 'closed',
            'opened_at': None,
            'opening_amount': None,
            'sales_total': None,
            'profit': None,
        }

    cash_total = None
    cash_profit = None
    if include_reports:
        cash_total = _money(
            db_session.query(func.coalesce(func.sum(Sale.final_amount), 0.0))
            .filter(
                Sale.company_id == company_id,
                Sale.cash_register_id == cash_register.id,
            )
            .scalar()
        )
        cash_profit = _sales_profit(
            db_session,
            company_id,
            cash_register_id=cash_register.id,
        )

    return {
        'id': cash_register.id,
        'status': 'open',
        'opened_at': cash_register.opened_at.isoformat() if cash_register.opened_at else None,
        'opening_amount': _money(cash_register.opening_amount),
        'sales_total': cash_total,
        'profit': cash_profit,
    }


def _upcoming_payables(db_session, company_id, today, allowed):
    if not allowed:
        return None, []
    base_query = db_session.query(Payable).filter(
        Payable.company_id == company_id,
        Payable.paid.is_(False),
        Payable.due_date <= today + timedelta(days=3),
    )
    count = base_query.count()
    payables = (
        base_query
        .order_by(Payable.due_date.asc(), func.lower(Payable.description), Payable.id)
        .limit(6)
        .all()
    )
    return count, [
        {
            'id': payable.id,
            'description': payable.description,
            'amount': _money(payable.amount),
            'due_date': payable.due_date.isoformat() if payable.due_date else None,
            'overdue': bool(payable.due_date and payable.due_date < today),
        }
        for payable in payables
    ]


def build_dashboard_snapshot(
    db_session,
    company_id,
    *,
    can_view_reports,
    can_manage_payables,
    today=None,
):
    today = today or date.today()
    start_at = datetime.combine(today, time.min)
    end_at = datetime.combine(today + timedelta(days=1), time.min)

    totals = _sales_totals(db_session, company_id, start_at, end_at)
    profit = _sales_profit(db_session, company_id, start_at, end_at) if can_view_reports else None
    low_stock_count, low_stock_products = _low_stock(db_session, company_id)
    payable_count, upcoming_payables = _upcoming_payables(
        db_session,
        company_id,
        today,
        can_manage_payables,
    )

    return {
        'date': today.isoformat(),
        'permissions': {
            'can_view_reports': bool(can_view_reports),
            'can_manage_payables': bool(can_manage_payables),
        },
        'summary': {
            **totals,
            'profit': profit,
            'average_ticket': totals['average_ticket'] if can_view_reports else None,
            'low_stock_count': low_stock_count,
            'payables_due_count': payable_count,
        },
        'cash_register': _current_cash(db_session, company_id, can_view_reports),
        'payment_totals': (
            _payment_totals(db_session, company_id, start_at, end_at)
            if can_view_reports else []
        ),
        'top_products': _top_products(
            db_session,
            company_id,
            start_at,
            end_at,
            can_view_reports,
        ),
        'low_stock_products': low_stock_products,
        'recent_sales': _recent_sales(db_session, company_id),
        'upcoming_payables': upcoming_payables,
    }
