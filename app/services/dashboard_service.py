from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import case, func
from sqlalchemy.orm import selectinload

from app.models import Category, CashRegister, Payable, Payment, Product, Sale, SaleItem, User
from app.money import money_decimal
from app.time_utils import (
    business_date_range_utc,
    business_today,
    to_business_datetime,
    utc_isoformat,
)


PAYMENT_METHODS = {
    'money': 'Dinheiro',
    'pix': 'Pix',
    'debit': 'Débito',
    'credit': 'Crédito',
}

DASHBOARD_PERIODS = {
    'today': 'Hoje',
    '7d': 'Últimos 7 dias',
    '30d': 'Últimos 30 dias',
    'month': 'Este mês',
    'previous_month': 'Mês anterior',
    '3m': 'Últimos 3 meses',
    '6m': 'Últimos 6 meses',
    'year': 'Este ano',
    'custom': 'Personalizado',
}


def _shift_month(value, months):
    absolute = value.year * 12 + value.month - 1 + months
    year, zero_based_month = divmod(absolute, 12)
    month = zero_based_month + 1
    return value.replace(year=year, month=month, day=min(value.day, monthrange(year, month)[1]))


def resolve_dashboard_period(period='today', start_date=None, end_date=None, today=None):
    today = today or business_today()
    period = (period or 'today').strip().casefold()
    if period not in DASHBOARD_PERIODS:
        period = 'today'

    if period == 'custom':
        if not start_date or not end_date:
            raise ValueError('Informe as datas inicial e final do período personalizado.')
        if start_date > end_date:
            raise ValueError('A data inicial não pode ser posterior à data final.')
        start, end = start_date, end_date
    elif period == 'today':
        start = end = today
    elif period == '7d':
        start, end = today - timedelta(days=6), today
    elif period == '30d':
        start, end = today - timedelta(days=29), today
    elif period == 'month':
        start, end = today.replace(day=1), today
    elif period == 'previous_month':
        previous = _shift_month(today.replace(day=1), -1)
        start = previous
        end = previous.replace(day=monthrange(previous.year, previous.month)[1])
    elif period in {'3m', '6m'}:
        months = 3 if period == '3m' else 6
        start, end = _shift_month(today, -(months - 1)).replace(day=1), today
    else:
        start, end = today.replace(month=1, day=1), today

    duration = (end - start).days + 1
    previous_end = start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=duration - 1)
    return {
        'key': period,
        'label': DASHBOARD_PERIODS[period],
        'start_date': start,
        'end_date': end,
        'previous_start_date': previous_start,
        'previous_end_date': previous_end,
    }


def _change_percent(current, previous):
    previous_value = money_decimal(previous)
    if previous_value == 0:
        return None
    current_value = money_decimal(current)
    return float(
        (((current_value - previous_value) / abs(previous_value)) * Decimal('100'))
        .quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
    )


def _money(value):
    return money_decimal(value)


def _item_profit_expression():
    stored_profit = func.coalesce(SaleItem.profit_amount, Decimal('0.00'))
    calculated_profit = (
        func.coalesce(SaleItem.unit_price, Decimal('0.00'))
        - func.coalesce(SaleItem.unit_cost_price, Decimal('0.00'))
    ) * func.coalesce(SaleItem.quantity, 0)
    return case(
        (stored_profit != Decimal('0.00'), stored_profit),
        else_=calculated_profit,
    )


def _period_filters(company_id, start_at, end_at):
    return (
        Sale.company_id == company_id,
        Sale.valid_filter(),
        Sale.created_at >= start_at,
        Sale.created_at < end_at,
    )


def _sales_totals(db_session, company_id, start_at, end_at):
    filters = _period_filters(company_id, start_at, end_at)
    row = db_session.query(
        func.count(Sale.id),
        func.coalesce(func.sum(Sale.final_amount), Decimal('0.00')),
    ).filter(*filters).one()
    count = int(row[0] or 0)
    total = _money(row[1])
    return {
        'sales_count': count,
        'sales_total': total,
        'average_ticket': _money(total / count) if count else Decimal('0.00'),
    }


def _sales_profit(db_session, company_id, start_at=None, end_at=None, cash_register_id=None):
    query = (
        db_session.query(func.coalesce(func.sum(_item_profit_expression()), Decimal('0.00')))
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(Sale.company_id == company_id, Sale.valid_filter())
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
        db_session.query(Payment.method, func.coalesce(func.sum(Payment.amount), Decimal('0.00')))
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
            'amount': amounts.get(method, Decimal('0.00')),
        }
        for method, label in PAYMENT_METHODS.items()
    ]


def _top_products(db_session, company_id, start_at, end_at, include_profit):
    profit_expression = _item_profit_expression()
    rows = (
        db_session.query(
            Product.id,
            Product.name,
            Category.name,
            func.coalesce(func.sum(SaleItem.quantity), 0),
            func.coalesce(func.sum(SaleItem.total_price), Decimal('0.00')),
            func.coalesce(func.sum(profit_expression), Decimal('0.00')),
        )
        .join(SaleItem, SaleItem.product_id == Product.id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .outerjoin(Category, Category.id == Product.category_id)
        .filter(Product.company_id == company_id)
        .filter(*_period_filters(company_id, start_at, end_at))
        .group_by(Product.id, Product.name, Category.name)
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
            'category': category_name or 'Sem categoria',
        }
        for product_id, name, category_name, quantity, total, profit in rows
    ]


def _category_sales(db_session, company_id, start_at, end_at):
    rows = (
        db_session.query(
            Category.name,
            func.coalesce(func.sum(SaleItem.total_price), Decimal('0.00')),
        )
        .select_from(Product)
        .join(SaleItem, SaleItem.product_id == Product.id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .outerjoin(Category, Category.id == Product.category_id)
        .filter(Product.company_id == company_id)
        .filter(*_period_filters(company_id, start_at, end_at))
        .group_by(Category.name)
        .order_by(func.sum(SaleItem.total_price).desc())
        .all()
    )
    total = sum((money_decimal(amount) for _, amount in rows), Decimal('0.00'))
    result = []
    for category_name, amount in rows:
        value = _money(amount)
        result.append({
            'category': category_name or 'Sem categoria',
            'total': value,
            'percent': float(((value / total) * Decimal('100')).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)) if total else 0.0,
        })
    return result


def _revenue_series(db_session, company_id, start_at, end_at, start_date, end_date):
    rows = (
        db_session.query(Sale.created_at, Sale.final_amount)
        .filter(*_period_filters(company_id, start_at, end_at))
        .order_by(Sale.created_at.asc())
        .all()
    )
    duration = (end_date - start_date).days + 1
    if duration == 1:
        buckets = {hour: Decimal('0.00') for hour in range(24)}
        for created_at, amount in rows:
            local = to_business_datetime(created_at)
            buckets[local.hour] += money_decimal(amount)
        points = [{'label': f'{hour:02d}h', 'total': _money(value)} for hour, value in buckets.items()]
        granularity = 'hour'
    elif duration <= 93:
        buckets = {start_date + timedelta(days=offset): Decimal('0.00') for offset in range(duration)}
        for created_at, amount in rows:
            local_date = to_business_datetime(created_at).date()
            if local_date in buckets:
                buckets[local_date] += money_decimal(amount)
        points = [{'label': day.strftime('%d/%m'), 'total': _money(value)} for day, value in buckets.items()]
        granularity = 'day'
    else:
        cursor = start_date.replace(day=1)
        buckets = {}
        while cursor <= end_date:
            buckets[(cursor.year, cursor.month)] = Decimal('0.00')
            cursor = _shift_month(cursor, 1)
        for created_at, amount in rows:
            local = to_business_datetime(created_at)
            key = (local.year, local.month)
            if key in buckets:
                buckets[key] += money_decimal(amount)
        points = [
            {'label': date(year, month, 1).strftime('%m/%Y'), 'total': _money(value)}
            for (year, month), value in buckets.items()
        ]
        granularity = 'month'
    maximum = max((point['total'] for point in points), default=Decimal('0.00'))
    for point in points:
        point['ratio'] = float((point['total'] / maximum).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)) if maximum else 0.0
    return {'granularity': granularity, 'points': points}


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


def _recent_sales(db_session, company_id, start_at=None, end_at=None):
    sales = (
        db_session.query(Sale)
        .options(selectinload(Sale.payments))
        .filter(Sale.company_id == company_id, Sale.valid_filter())
        .filter(Sale.created_at >= start_at, Sale.created_at < end_at)
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
            'created_at': utc_isoformat(sale.created_at),
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
            db_session.query(func.coalesce(func.sum(Sale.final_amount), Decimal('0.00')))
            .filter(
                Sale.company_id == company_id,
                Sale.cash_register_id == cash_register.id,
                Sale.valid_filter(),
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
        'opened_at': utc_isoformat(cash_register.opened_at),
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
    period='today',
    start_date=None,
    end_date=None,
):
    today = today or business_today()
    selected = resolve_dashboard_period(period, start_date, end_date, today)
    start_at, end_at = business_date_range_utc(selected['start_date'], selected['end_date'])
    previous_start_at, previous_end_at = business_date_range_utc(
        selected['previous_start_date'], selected['previous_end_date'])

    totals = _sales_totals(db_session, company_id, start_at, end_at)
    previous_totals = _sales_totals(db_session, company_id, previous_start_at, previous_end_at)
    profit = _sales_profit(db_session, company_id, start_at, end_at) if can_view_reports else None
    previous_profit = (
        _sales_profit(db_session, company_id, previous_start_at, previous_end_at)
        if can_view_reports else None
    )
    low_stock_count, low_stock_products = _low_stock(db_session, company_id)
    payable_count, upcoming_payables = _upcoming_payables(
        db_session,
        company_id,
        today,
        can_manage_payables,
    )

    return {
        'date': today.isoformat(),
        'period': {
            'key': selected['key'],
            'label': selected['label'],
            'start_date': selected['start_date'].isoformat(),
            'end_date': selected['end_date'].isoformat(),
            'previous_start_date': selected['previous_start_date'].isoformat(),
            'previous_end_date': selected['previous_end_date'].isoformat(),
        },
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
            'sales_total_change': _change_percent(totals['sales_total'], previous_totals['sales_total']),
            'sales_count_change': _change_percent(totals['sales_count'], previous_totals['sales_count']),
            'profit_change': _change_percent(profit, previous_profit) if can_view_reports else None,
            'customers': None,
            'customers_change': None,
            'customers_available': False,
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
        'revenue_series': (
            _revenue_series(
                db_session, company_id, start_at, end_at,
                selected['start_date'], selected['end_date'])
            if can_view_reports else {'granularity': 'day', 'points': []}
        ),
        'category_sales': (
            _category_sales(db_session, company_id, start_at, end_at)
            if can_view_reports else []
        ),
        'low_stock_products': low_stock_products,
        'recent_sales': _recent_sales(db_session, company_id, start_at, end_at),
        'upcoming_payables': upcoming_payables,
    }
