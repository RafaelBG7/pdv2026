import csv
import io
from datetime import date, datetime, time, timedelta, timezone

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import AuditLog, CashRegister, Category, Company, Payable, Payment, Product, Sale, SaleItem, StockMovement, User
from app.permissions import authorize_role_override, has_permission_view_override, permission_required
from app.services.audit_service import audit_action_label, entity_label, record_audit_event
from app.services.stock_service import (
    MOVEMENT_TYPE_LABELS,
    SOURCE_TYPE_LABELS,
    StockMovementError,
    adjust_stock,
    increase_stock,
    stock_movement_label,
    stock_source_label,
    decrease_stock,
)
from app.tenant import current_tenant_company, tenant_session

main_bp = Blueprint('main', __name__)
PAYMENT_METHODS = {
    'money': 'Dinheiro',
    'pix': 'Pix',
    'debit': 'Débito',
    'credit': 'Crédito',
}
PAYABLE_CATEGORIES = ('Aluguel', 'Luz', 'Água', 'Internet', 'Fornecedor', 'Impostos', 'Outros')
EXPORT_TYPES = ('produtos', 'vendas', 'caixas', 'contas')


def parse_money(value):
    value = (value or '0').strip()
    if ',' in value:
        value = value.replace('.', '').replace(',', '.')
    try:
        return max(float(value), 0.0)
    except ValueError:
        return 0.0


def format_brl(value):
    return f'R$ {value:.2f}'.replace('.', ',')


def payable_status(payable):
    if payable.paid:
        return 'paid'
    today = date.today()
    if payable.due_date < today:
        return 'overdue'
    if payable.due_date == today:
        return 'due_today'
    if payable.due_date <= today + timedelta(days=3):
        return 'near_due'
    return 'pending'


def payable_status_label(payable):
    status = payable_status(payable)
    labels = {
        'paid': 'Pago',
        'overdue': 'Vencida',
        'due_today': 'Vence hoje',
        'near_due': 'Próxima',
        'pending': 'Pendente',
    }
    return labels.get(status, 'Pendente')


def can_export_data():
    return current_user.role in ('admin', 'master') and current_tenant_company() is not None


def can_view_cash_financials():
    return current_user.has_permission('can_view_reports') or has_permission_view_override('can_view_reports')


def csv_response(filename, headers, rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=';')
    writer.writerow(headers)
    writer.writerows(rows)
    content = '\ufeff' + buffer.getvalue()
    return Response(
        content,
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


def export_products_rows():
    products = tenant_query(Product).order_by(Product.name.asc()).all()
    return [
        [
            product.id,
            product.name,
            product.barcode or '',
            product.category.name if product.category else '',
            f'{product.cost_price or 0:.2f}',
            f'{product.sale_price or 0:.2f}',
            product.stock_quantity or 0,
            product.effective_stock_quantity or 0,
            product.min_stock_quantity or 0,
            'Sim' if product.active else 'Não',
            'Sim' if product.is_kit else 'Não',
            product.kit_component.name if product.is_kit and product.kit_component else '',
            product.kit_component_quantity or 0,
        ]
        for product in products
    ]


def export_sales_rows():
    sales = tenant_query(Sale).order_by(Sale.created_at.desc()).all()
    rows = []
    for sale in sales:
        payments = ', '.join(
            f'{PAYMENT_METHODS.get(payment.method, payment.method)}: {payment.amount or 0:.2f}'
            for payment in sale.payments
        )
        rows.append([
            sale.id,
            sale.created_at.strftime('%d/%m/%Y %H:%M') if sale.created_at else '',
            f'{sale.total_amount or 0:.2f}',
            f'{sale.discount_amount or 0:.2f}',
            f'{sale.final_amount or 0:.2f}',
            f'{sale_profit(sale):.2f}',
            sale.payment_status,
            payments,
            sale.cash_register_id or '',
        ])
    return rows


def export_cash_register_rows():
    cash_registers = tenant_query(CashRegister).order_by(CashRegister.opened_at.desc()).all()
    return [
        [
            cash_register.id,
            cash_register.opened_at.strftime('%d/%m/%Y %H:%M') if cash_register.opened_at else '',
            cash_register.closed_at.strftime('%d/%m/%Y %H:%M') if cash_register.closed_at else '',
            cash_register.status,
            f'{cash_register.opening_amount or 0:.2f}',
            f'{cash_register.closing_amount or 0:.2f}',
            f'{cash_register_total_sold(cash_register):.2f}',
            f'{cash_register_profit(cash_register):.2f}',
            len(cash_register.sales),
        ]
        for cash_register in cash_registers
    ]


def export_payables_rows():
    payables = tenant_query(Payable).order_by(Payable.due_date.desc(), Payable.description.asc()).all()
    return [
        [
            payable.id,
            payable.description,
            payable.category or '',
            f'{payable.amount or 0:.2f}',
            payable.due_date.strftime('%d/%m/%Y') if payable.due_date else '',
            payable_status_label(payable),
            'Sim' if payable.paid else 'Não',
            payable.paid_at.strftime('%d/%m/%Y %H:%M') if payable.paid_at else '',
            payable.notes or '',
        ]
        for payable in payables
    ]


def card_fee_total(company, payments, final_amount, paid_amount):
    if not company or final_amount <= 0 or paid_amount <= 0:
        return 0.0

    payment_scale = min(final_amount / paid_amount, 1.0)
    fee_total = 0.0
    for method, amount in payments:
        effective_amount = (amount or 0.0) * payment_scale
        if method == 'pix' and company.pix_fee_enabled:
            fee_total += effective_amount * ((company.pix_fee_percent or 0.0) / 100)
        elif method == 'debit' and company.debit_fee_enabled:
            fee_total += effective_amount * ((company.debit_fee_percent or 0.0) / 100)
        elif method == 'credit' and company.credit_fee_enabled:
            fee_total += effective_amount * ((company.credit_fee_percent or 0.0) / 100)

    return round(fee_total, 2)


def parse_quantity(value):
    try:
        return max(int(value or 0), 0)
    except ValueError:
        return 0


def parse_signed_quantity(value):
    try:
        return int(value or 0)
    except ValueError:
        return 0


def parse_date(value):
    try:
        return datetime.strptime(value or '', '%Y-%m-%d').date()
    except ValueError:
        return None


def sale_form_state():
    product_ids = request.form.getlist('product_id[]')
    quantities = request.form.getlist('quantity[]')
    items = []

    for product_id, quantity in zip(product_ids, quantities):
        items.append({
            'product_id': product_id,
            'quantity': quantity or '1',
        })

    return {
        'items': items or [{'product_id': '', 'quantity': '1'}],
        'discount_amount': request.form.get('discount_amount', ''),
        'show_payment_step': True,
        'payments': {
            method: request.form.get(f'payment_{method}', '')
            for method in PAYMENT_METHODS
        },
    }


def open_cash_register():
    return tenant_session().query(CashRegister).filter_by(company_id=current_tenant_company().id, status='open').order_by(CashRegister.opened_at.desc()).first()


def tenant_query(model):
    company = current_tenant_company()
    return tenant_session().query(model).filter(model.company_id == company.id)


def tenant_get_or_404(model, record_id):
    record = tenant_query(model).filter_by(id=record_id).first()
    if not record:
        abort(404)
    return record


def product_name_map(product_ids):
    if not product_ids:
        return {}
    return {
        product.id: product.name
        for product in tenant_session().query(Product).filter(Product.id.in_(product_ids)).all()
    }


def user_name_map(user_ids, session=None):
    user_ids = {user_id for user_id in user_ids if user_id}
    if not user_ids:
        return {}
    session = session or tenant_session()
    return {
        user.id: user.full_name or user.username
        for user in session.query(User).filter(User.id.in_(user_ids)).all()
    }


def audit_json_lines(value):
    if not value:
        return []
    import json

    try:
        data = json.loads(value)
    except (TypeError, ValueError):
        return [str(value)]
    if isinstance(data, dict):
        return [f'{key}: {data[key]}' for key in sorted(data)]
    if isinstance(data, list):
        return [str(item) for item in data]
    return [str(data)]


def apply_date_filters(query, model, start_value, end_value):
    start_date = parse_date(start_value)
    end_date = parse_date(end_value)
    if start_date:
        query = query.filter(model.created_at >= datetime.combine(start_date, time.min))
    if end_date:
        query = query.filter(model.created_at < datetime.combine(end_date + timedelta(days=1), time.min))
    return query


def tenant_actor_user_id():
    company = current_tenant_company()
    if not company or not current_user.is_authenticated:
        return None
    if current_user.company_id != company.id:
        return None
    return current_user.id


def stock_source_for_product(product):
    if product.is_kit:
        if not product.kit_component or product.kit_component_quantity <= 0:
            return None, 0
        return product.kit_component, product.kit_component_quantity
    return product, 1


def sale_item_profit(item):
    if item.profit_amount not in (None, 0):
        return item.profit_amount or 0.0

    cost_price = item.unit_cost_price
    if (cost_price is None or cost_price == 0) and item.product:
        cost_price = item.product.cost_price

    return ((item.unit_price or 0.0) - (cost_price or 0.0)) * (item.quantity or 0)


def sale_profit(sale):
    gross_profit = sum(sale_item_profit(item) for item in sale.items)
    return round(gross_profit - (sale.discount_amount or 0.0), 2)


def cash_register_profit(cash_register):
    if not cash_register:
        return 0.0
    return round(sum(sale_profit(sale) for sale in cash_register.sales), 2)


def cash_register_total_sold(cash_register):
    if not cash_register:
        return 0.0
    return round(sum(sale.final_amount or 0.0 for sale in cash_register.sales), 2)


def cash_register_expected_amount(cash_register):
    if not cash_register:
        return 0.0
    return round((cash_register.opening_amount or 0.0) + cash_register_total_sold(cash_register), 2)


def payment_summary_text(sale):
    summary = [
        f'{PAYMENT_METHODS.get(payment.method, payment.method)} {format_brl(payment.amount or 0.0)}'
        for payment in sale.payments
        if payment.amount and payment.amount > 0
    ]
    return ' · '.join(summary) if summary else '-'


def build_sale_timeline(sales):
    ordered_sales = sorted(sales, key=lambda sale: sale.created_at or datetime.min)
    user_ids = {sale.user_id for sale in ordered_sales if sale.user_id}
    users = {
        user.id: user.full_name or user.username
        for user in tenant_session().query(User).filter(User.id.in_(user_ids)).all()
    } if user_ids else {}

    timeline = []
    for sale in ordered_sales:
        timeline.append({
            'sale': sale,
            'time': sale.created_at.strftime('%H:%M') if sale.created_at else '-',
            'date': sale.created_at.strftime('%d/%m/%Y') if sale.created_at else '-',
            'user': users.get(sale.user_id, 'Usuário não identificado'),
            'payments_text': payment_summary_text(sale),
        })
    return timeline


def build_cash_register_snapshot(cash_register):
    sales = list(cash_register.sales) if cash_register else []
    totals, payment_totals, _ = build_sales_report(sales)
    return {
        'totals': totals,
        'payment_totals': payment_totals,
        'timeline': build_sale_timeline(sales),
    }


def report_period_range(period, start_date=None, end_date=None):
    today = date.today()

    if period == 'weekly':
        end = end_date or today
        start = start_date or (end - timedelta(days=7))
        label = f'Últimos 7 dias: {start.strftime("%d/%m/%Y")} a {end.strftime("%d/%m/%Y")}'
    elif period == 'monthly':
        end = end_date or today
        start = start_date or (end - timedelta(days=30))
        label = f'Últimos 30 dias: {start.strftime("%d/%m/%Y")} a {end.strftime("%d/%m/%Y")}'
    elif period == 'annual':
        end = end_date or today
        start = start_date or (end - timedelta(days=365))
        label = f'Último ano: {start.strftime("%d/%m/%Y")} a {end.strftime("%d/%m/%Y")}'
    elif period == 'custom':
        start = start_date or today
        end = end_date or start
        if end < start:
            start, end = end, start
        label = f'{start.strftime("%d/%m/%Y")} a {end.strftime("%d/%m/%Y")}'
    else:
        period = 'daily'
        start = start_date or today
        end = start
        label = start.strftime('%d/%m/%Y')

    start_datetime = datetime.combine(start, time.min)
    end_datetime = datetime.combine(end + timedelta(days=1), time.min)
    return period, start, end, start_datetime, end_datetime, label


def build_sales_report(sales):
    payment_totals = {method: 0.0 for method in PAYMENT_METHODS}
    product_totals = {}
    totals = {
        'sales_count': len(sales),
        'items_count': 0,
        'subtotal': 0.0,
        'discount': 0.0,
        'final': 0.0,
        'profit': 0.0,
        'average_ticket': 0.0,
    }

    for sale in sales:
        totals['subtotal'] += sale.total_amount or 0.0
        totals['discount'] += sale.discount_amount or 0.0
        totals['final'] += sale.final_amount or 0.0
        totals['profit'] += sale_profit(sale)

        for payment in sale.payments:
            payment_totals[payment.method] = payment_totals.get(payment.method, 0.0) + (payment.amount or 0.0)

        for item in sale.items:
            totals['items_count'] += item.quantity or 0
            product_name = item.product.name if item.product else 'Produto removido'
            product_data = product_totals.setdefault(product_name, {
                'name': product_name,
                'quantity': 0,
                'total': 0.0,
                'profit': 0.0,
            })
            product_data['quantity'] += item.quantity or 0
            product_data['total'] += item.total_price or 0.0
            product_data['profit'] += sale_item_profit(item)

    if totals['sales_count']:
        totals['average_ticket'] = totals['final'] / totals['sales_count']

    for key in ('subtotal', 'discount', 'final', 'profit', 'average_ticket'):
        totals[key] = round(totals[key], 2)

    payment_totals = {
        method: round(amount, 2)
        for method, amount in payment_totals.items()
        if amount > 0
    }
    top_products = sorted(product_totals.values(), key=lambda item: item['total'], reverse=True)
    for product in top_products:
        product['total'] = round(product['total'], 2)
        product['profit'] = round(product['profit'], 2)

    return totals, payment_totals, top_products


def build_sales_chart(period, start, end, sales):
    buckets = []

    if period == 'annual':
        current = start.replace(day=1)
        end_month = end.replace(day=1)
        while current <= end_month:
            buckets.append({
                'key': (current.year, current.month),
                'label': current.strftime('%m/%Y'),
                'total': 0.0,
            })
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)

        bucket_index = {bucket['key']: bucket for bucket in buckets}
        for sale in sales:
            if sale.created_at:
                sale_date = sale.created_at.date()
                key = (sale_date.year, sale_date.month)
                if key in bucket_index:
                    bucket_index[key]['total'] += sale.final_amount or 0.0
    else:
        current = start
        while current <= end:
            buckets.append({
                'key': current,
                'label': current.strftime('%d/%m'),
                'title': current.strftime('%d/%m/%Y'),
                'total': 0.0,
            })
            current += timedelta(days=1)

        bucket_index = {bucket['key']: bucket for bucket in buckets}
        for sale in sales:
            if sale.created_at:
                sale_date = sale.created_at.date()
                if sale_date in bucket_index:
                    bucket_index[sale_date]['total'] += sale.final_amount or 0.0

    max_total = max((bucket['total'] for bucket in buckets), default=0.0)
    for bucket in buckets:
        bucket['total'] = round(bucket['total'], 2)
        bucket['percent'] = round((bucket['total'] / max_total) * 100, 2) if max_total else 0
        bucket['title'] = bucket.get('title', bucket['label'])

    return buckets


def build_daily_sales_activity(start_datetime, end_datetime, metric='revenue'):
    """Aggregate daily sales in SQL and return a stable 24-hour chart structure."""
    metric = metric if metric in ('revenue', 'quantity') else 'revenue'
    hour_expression = func.extract('hour', Sale.created_at)
    rows = tenant_query(Sale).with_entities(
        hour_expression.label('sale_hour'),
        func.count(Sale.id).label('sales_count'),
        func.coalesce(func.sum(Sale.final_amount), 0).label('revenue'),
    ).filter(
        Sale.created_at >= start_datetime,
        Sale.created_at < end_datetime,
    ).group_by(hour_expression).all()

    aggregated = {
        int(row.sale_hour): {
            'sales_count': int(row.sales_count or 0),
            'total': round(float(row.revenue or 0), 2),
        }
        for row in rows
        if row.sale_hour is not None
    }
    buckets = []
    for hour in range(24):
        values = aggregated.get(hour, {'sales_count': 0, 'total': 0.0})
        buckets.append({
            'hour': hour,
            'label': f'{hour:02d}h',
            'title': f'{hour:02d}:00 às {hour:02d}:59',
            'sales_count': values['sales_count'],
            'total': values['total'],
        })

    active_buckets = [bucket for bucket in buckets if bucket['sales_count'] > 0]
    peak_by_quantity = max(
        active_buckets,
        key=lambda item: (item['sales_count'], item['total'], -item['hour']),
        default=None,
    )
    peak_by_revenue = max(
        active_buckets,
        key=lambda item: (item['total'], item['sales_count'], -item['hour']),
        default=None,
    )
    selected_peak = peak_by_quantity if metric == 'quantity' else peak_by_revenue
    max_value = max(
        (bucket['sales_count'] if metric == 'quantity' else bucket['total'] for bucket in buckets),
        default=0,
    )

    for bucket in buckets:
        value = bucket['sales_count'] if metric == 'quantity' else bucket['total']
        bucket['percent'] = round((value / max_value) * 100, 2) if max_value else 0
        bucket['is_peak'] = bool(selected_peak and bucket['hour'] == selected_peak['hour'])

    return {
        'buckets': buckets,
        'metric': metric,
        'peak': peak_by_quantity,
        'peak_by_quantity': peak_by_quantity,
        'peak_by_revenue': peak_by_revenue,
    }


def cash_register_peak_hours(cash_register):
    hours = {}
    if not cash_register:
        return []

    for sale in cash_register.sales:
        if not sale.created_at:
            continue
        hour = sale.created_at.hour
        data = hours.setdefault(hour, {
            'hour': hour,
            'label': f'{hour:02d}:00 - {hour:02d}:59',
            'sales_count': 0,
            'total': 0.0,
        })
        data['sales_count'] += 1
        data['total'] += sale.final_amount or 0.0

    peak_hours = sorted(
        hours.values(),
        key=lambda item: (item['sales_count'], item['total']),
        reverse=True,
    )
    for item in peak_hours:
        item['total'] = round(item['total'], 2)

    return peak_hours


def build_product_report(start_datetime, end_datetime, category_id='', product_id='', sort='quantity_desc'):
    company = current_tenant_company()
    tenant_db = tenant_session()
    sale_item_query = (
        tenant_db.query(
            SaleItem.product_id.label('product_id'),
            func.coalesce(func.sum(SaleItem.quantity), 0).label('quantity'),
            func.coalesce(func.sum(SaleItem.total_price), 0).label('revenue'),
            func.coalesce(func.sum(SaleItem.unit_cost_price * SaleItem.quantity), 0).label('cost'),
            func.coalesce(func.sum(SaleItem.profit_amount), 0).label('profit'),
        )
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(Sale.company_id == company.id)
    )
    if start_datetime and end_datetime:
        sale_item_query = sale_item_query.filter(
            Sale.created_at >= start_datetime,
            Sale.created_at < end_datetime,
        )
    sale_item_totals = sale_item_query.group_by(SaleItem.product_id).subquery()

    query = (
        tenant_db.query(
            Product,
            sale_item_totals.c.quantity,
            sale_item_totals.c.revenue,
            sale_item_totals.c.cost,
            sale_item_totals.c.profit,
        )
        .outerjoin(sale_item_totals, sale_item_totals.c.product_id == Product.id)
        .options(selectinload(Product.category))
        .filter(Product.company_id == company.id)
    )

    if category_id and str(category_id).isdigit():
        query = query.filter(Product.category_id == int(category_id))
    if product_id and str(product_id).isdigit():
        query = query.filter(Product.id == int(product_id))

    rows = []
    for product, quantity, revenue, cost, profit in query.all():
        quantity = int(quantity or 0)
        revenue = round(float(revenue or 0), 2)
        cost = round(float(cost or 0), 2)
        profit = round(float(profit or 0), 2)
        rows.append({
            'product': product,
            'category': product.category.name if product.category else '-',
            'quantity': quantity,
            'revenue': revenue,
            'cost': cost,
            'profit': profit,
            'average_ticket': round(revenue / quantity, 2) if quantity else 0.0,
            'stock': product.effective_stock_quantity or 0,
        })

    if sort == 'revenue_desc':
        rows.sort(key=lambda item: (item['revenue'], item['quantity'], item['product'].name.lower()), reverse=True)
    elif sort == 'profit_desc':
        rows.sort(key=lambda item: (item['profit'], item['revenue'], item['product'].name.lower()), reverse=True)
    elif sort == 'stock_asc':
        rows.sort(key=lambda item: (item['stock'], item['product'].name.lower()))
    elif sort == 'no_sales':
        rows = [item for item in rows if item['quantity'] == 0]
        rows.sort(key=lambda item: item['product'].name.lower())
    else:
        sort = 'quantity_desc'
        rows.sort(key=lambda item: (item['quantity'], item['revenue'], item['product'].name.lower()), reverse=True)

    totals = {
        'quantity': sum(item['quantity'] for item in rows),
        'revenue': round(sum(item['revenue'] for item in rows), 2),
        'cost': round(sum(item['cost'] for item in rows), 2),
        'profit': round(sum(item['profit'] for item in rows), 2),
        'products': len(rows),
    }
    return rows, totals, sort


@main_bp.route('/')
@main_bp.route('/dashboard')
@login_required
def dashboard():
    today = date.today()
    company = current_tenant_company()
    tenant_db = tenant_session()
    current_cash_register = open_cash_register()

    sales = tenant_db.query(Sale).filter_by(company_id=company.id).order_by(Sale.created_at.desc()).all()
    today_sales = [
        sale for sale in sales
        if sale.created_at and sale.created_at.date() == today
    ]
    today_totals, today_payment_totals, today_top_products = build_sales_report(today_sales)

    low_stock_products = tenant_db.query(Product).filter(
        Product.company_id == company.id,
        Product.active.is_(True),
        Product.min_stock_quantity > 0,
    ).order_by(Product.name.asc()).all()
    low_stock_products = [
        product for product in low_stock_products
        if (product.effective_stock_quantity or 0) <= (product.min_stock_quantity or 0)
    ]
    low_stock_products.sort(key=lambda product: ((product.effective_stock_quantity or 0), product.name.lower()))

    upcoming_payables = tenant_db.query(Payable).filter(
        Payable.company_id == company.id,
        Payable.paid.is_(False),
        Payable.due_date <= today + timedelta(days=3),
    ).order_by(Payable.due_date.asc(), Payable.description.asc()).limit(6).all()

    dashboard_summary = {
        'sales_total': today_totals['final'],
        'sales_count': today_totals['sales_count'],
        'profit': today_totals['profit'],
        'average_ticket': today_totals['average_ticket'],
        'cash_status': 'Aberto' if current_cash_register else 'Fechado',
        'cash_total': cash_register_total_sold(current_cash_register),
        'cash_profit': cash_register_profit(current_cash_register),
        'low_stock_count': len(low_stock_products),
        'payables_due_count': len(upcoming_payables),
    }

    return render_template(
        'dashboard.html',
        open_cash_register=current_cash_register,
        dashboard_summary=dashboard_summary,
        payment_methods=PAYMENT_METHODS,
        today_payment_totals=today_payment_totals,
        top_products=today_top_products[:5],
        low_stock_products=low_stock_products[:6],
        upcoming_payables=upcoming_payables,
        payable_status_label=payable_status_label,
    )


@main_bp.route('/vendas')
@login_required
@permission_required('can_manage_sales')
def sales():
    today = date.today()
    start_of_day = datetime.combine(today, time.min)
    end_of_day = datetime.combine(today, time.max)
    sales = tenant_query(Sale).options(
        selectinload(Sale.payments),
    ).filter(
        Sale.created_at >= start_of_day,
        Sale.created_at <= end_of_day,
    ).order_by(Sale.created_at.desc()).all()
    user_ids = {sale.user_id for sale in sales if sale.user_id}
    sale_users = {
        user.id: user.full_name or user.username
        for user in tenant_session().query(User).filter(User.id.in_(user_ids)).all()
    } if user_ids else {}

    def unique_options(values):
        seen = set()
        options = []
        for value, label in values:
            key = str(value or '').strip()
            if not key or key in seen:
                continue
            seen.add(key)
            options.append({'value': key, 'label': label})
        return options

    sales_filter_options = {
        'users': unique_options((sale_users.get(sale.user_id, 'Usuário não identificado'), sale_users.get(sale.user_id, 'Usuário não identificado')) for sale in sales),
        'statuses': unique_options(
            (
                sale.payment_status or '',
                'Pago' if sale.payment_status == 'paid' else sale.payment_status or 'Pendente',
            )
            for sale in sales
        ),
    }

    return render_template(
        'sales/index.html',
        sales=sales,
        sale_users=sale_users,
        sales_filter_options=sales_filter_options,
        payment_methods=PAYMENT_METHODS,
        open_cash_register=open_cash_register(),
    )


@main_bp.route('/estoque/movimentacoes')
@login_required
@permission_required('can_view_stock_movements')
def stock_movements():
    page = max(request.args.get('page', 1, type=int) or 1, 1)
    per_page = 20
    product_search = request.args.get('produto', '').strip()
    category_id = request.args.get('categoria', '').strip()
    movement_type = request.args.get('tipo', '').strip()
    source_type = request.args.get('origem', '').strip()
    user_id = request.args.get('usuario', '').strip()

    query = tenant_query(StockMovement).order_by(StockMovement.created_at.desc())
    if product_search:
        matching_products = tenant_query(Product).filter(Product.name.ilike(f'%{product_search}%')).with_entities(Product.id)
        query = query.filter(StockMovement.product_id.in_(matching_products))
    if category_id.isdigit():
        product_ids = tenant_query(Product).filter(Product.category_id == int(category_id)).with_entities(Product.id)
        query = query.filter(StockMovement.product_id.in_(product_ids))
    if movement_type:
        query = query.filter(StockMovement.movement_type == movement_type)
    if source_type:
        query = query.filter(StockMovement.source_type == source_type)
    if user_id.isdigit():
        query = query.filter(StockMovement.user_id == int(user_id))
    query = apply_date_filters(query, StockMovement, request.args.get('data_inicio'), request.args.get('data_fim'))

    total_movements = query.order_by(None).count()
    total_pages = max((total_movements + per_page - 1) // per_page, 1)
    page = min(page, total_pages)
    movements = query.offset((page - 1) * per_page).limit(per_page).all()
    product_ids = {movement.product_id for movement in movements}
    user_ids = {movement.user_id for movement in movements if movement.user_id}
    products_by_id = product_name_map(product_ids)
    users_by_id = user_name_map(user_ids)
    all_categories = tenant_session().query(Category).filter_by(company_id=current_tenant_company().id).order_by(Category.name.asc()).all()
    all_users = tenant_session().query(User).filter_by(company_id=current_tenant_company().id).order_by(User.username.asc()).all()

    filtered_movements = query.all()
    summary = {
        'entries': sum(item.quantity or 0 for item in filtered_movements if item.new_stock >= item.previous_stock),
        'exits': sum(item.quantity or 0 for item in filtered_movements if item.new_stock < item.previous_stock),
        'count': total_movements,
        'products': len({item.product_id for item in filtered_movements}),
    }
    filters = {
        'produto': product_search,
        'categoria': category_id,
        'tipo': movement_type,
        'origem': source_type,
        'usuario': user_id,
        'data_inicio': request.args.get('data_inicio', '').strip(),
        'data_fim': request.args.get('data_fim', '').strip(),
    }
    pagination_query = {key: value for key, value in request.args.items() if key != 'page'}
    return render_template(
        'stock/movements.html',
        movements=movements,
        products_by_id=products_by_id,
        users_by_id=users_by_id,
        categories=all_categories,
        users=all_users,
        movement_type_labels=MOVEMENT_TYPE_LABELS,
        source_type_labels=SOURCE_TYPE_LABELS,
        stock_movement_label=stock_movement_label,
        stock_source_label=stock_source_label,
        summary=summary,
        filters=filters,
        page=page,
        total_pages=total_pages,
        pagination_query=pagination_query,
    )


@main_bp.route('/estoque/entrada', methods=['GET', 'POST'])
@login_required
@permission_required('can_manage_stock')
def stock_entry():
    products = tenant_query(Product).filter_by(active=True).order_by(Product.name.asc()).all()
    if request.method == 'POST':
        product_id = request.form.get('product_id', '').strip()
        quantity = parse_quantity(request.form.get('quantity'))
        unit_cost = parse_money(request.form.get('unit_cost'))
        reason = request.form.get('reason', '').strip() or 'Entrada manual de estoque'
        notes = request.form.get('notes', '').strip()
        update_cost = request.form.get('update_cost') == 'on'
        product = tenant_query(Product).filter_by(id=int(product_id)).first() if product_id.isdigit() else None

        if not product:
            flash('Selecione um produto válido.', 'danger')
        elif quantity <= 0:
            flash('Informe uma quantidade maior que zero.', 'danger')
        else:
            tenant_db = tenant_session()
            try:
                if update_cost:
                    old_cost = product.cost_price
                    product.cost_price = unit_cost
                    record_audit_event(
                        'product_updated',
                        'product',
                        product.id,
                        f'Custo do produto {product.name} atualizado na entrada de estoque.',
                        old_values={'cost_price': old_cost},
                        new_values={'cost_price': product.cost_price},
                        company_id=current_tenant_company().id,
                        db_session=tenant_db,
                    )
                movement = increase_stock(
                    tenant_db,
                    product,
                    quantity,
                    movement_type='entry',
                    source_type='manual',
                    user_id=tenant_actor_user_id(),
                    unit_cost=unit_cost,
                    reason=reason,
                    notes=notes,
                )
                tenant_db.commit()
                flash(f'Entrada registrada. Novo estoque: {movement.new_stock} un.', 'success')
                return redirect(url_for('main.stock_movements'))
            except StockMovementError as error:
                tenant_db.rollback()
                flash(str(error), 'danger')

    return render_template('stock/form.html', mode='entry', products=products)


@main_bp.route('/estoque/ajuste', methods=['GET', 'POST'])
@login_required
@permission_required('can_manage_stock')
def stock_adjustment():
    products = tenant_query(Product).filter_by(active=True).order_by(Product.name.asc()).all()
    if request.method == 'POST':
        product_id = request.form.get('product_id', '').strip()
        adjustment_mode = request.form.get('adjustment_mode', 'target')
        direction = request.form.get('direction', 'in')
        quantity = parse_quantity(request.form.get('quantity'))
        target_stock = parse_signed_quantity(request.form.get('target_stock'))
        reason = request.form.get('reason', '').strip()
        notes = request.form.get('notes', '').strip()
        product = tenant_query(Product).filter_by(id=int(product_id)).first() if product_id.isdigit() else None

        if not product:
            flash('Selecione um produto válido.', 'danger')
        elif not reason:
            flash('Informe o motivo do ajuste.', 'danger')
        elif adjustment_mode == 'delta' and quantity <= 0:
            flash('Informe uma quantidade maior que zero.', 'danger')
        else:
            current_stock = int(product.stock_quantity or 0)
            new_stock = target_stock if adjustment_mode == 'target' else (
                current_stock + quantity if direction == 'in' else current_stock - quantity
            )
            tenant_db = tenant_session()
            try:
                movement = adjust_stock(
                    tenant_db,
                    product,
                    new_stock,
                    source_type='manual',
                    user_id=tenant_actor_user_id(),
                    unit_cost=product.cost_price,
                    reason=reason,
                    notes=notes,
                    allow_negative_stock=current_tenant_company().allow_negative_stock,
                )
                if not movement:
                    flash('O estoque informado é igual ao saldo atual. Nenhuma movimentação foi criada.', 'info')
                    return redirect(url_for('main.stock_adjustment'))
                tenant_db.commit()
                flash(f'Ajuste registrado. Novo estoque: {movement.new_stock} un.', 'success')
                return redirect(url_for('main.stock_movements'))
            except StockMovementError as error:
                tenant_db.rollback()
                flash(str(error), 'danger')

    return render_template('stock/form.html', mode='adjustment', products=products)


@main_bp.route('/auditoria')
@login_required
@permission_required('can_view_audit_logs')
def audit_logs():
    company = current_tenant_company()
    page = max(request.args.get('page', 1, type=int) or 1, 1)
    per_page = 20
    query = tenant_session().query(AuditLog).filter(AuditLog.company_id == company.id)
    search = request.args.get('q', '').strip()
    if search:
        term = f'%{search}%'
        query = query.filter((AuditLog.description.ilike(term)) | (AuditLog.user_name.ilike(term)) | (AuditLog.action.ilike(term)))
    if request.args.get('usuario', '').strip().isdigit():
        query = query.filter(AuditLog.user_id == int(request.args.get('usuario')))
    if request.args.get('acao', '').strip():
        query = query.filter(AuditLog.action == request.args.get('acao').strip())
    if request.args.get('entidade', '').strip():
        query = query.filter(AuditLog.entity_type == request.args.get('entidade').strip())
    if request.args.get('metodo', '').strip():
        query = query.filter(AuditLog.http_method == request.args.get('metodo').strip())
    query = apply_date_filters(query, AuditLog, request.args.get('data_inicio'), request.args.get('data_fim'))
    query = query.order_by(AuditLog.created_at.desc())

    total_logs = query.order_by(None).count()
    total_pages = max((total_logs + per_page - 1) // per_page, 1)
    page = min(page, total_pages)
    logs = query.offset((page - 1) * per_page).limit(per_page).all()
    users = tenant_session().query(User).filter_by(company_id=company.id).order_by(User.username.asc()).all()
    available_actions = [
        action for (action,) in tenant_session().query(AuditLog.action).filter_by(company_id=company.id).distinct().order_by(AuditLog.action.asc()).all()
    ]
    available_entities = [
        entity for (entity,) in tenant_session().query(AuditLog.entity_type).filter_by(company_id=company.id).distinct().order_by(AuditLog.entity_type.asc()).all()
    ]
    summary = {
        'count': total_logs,
        'users': len({log.user_id for log in query.all() if log.user_id}),
        'actions': len(available_actions),
    }
    filters = {
        'q': search,
        'usuario': request.args.get('usuario', '').strip(),
        'acao': request.args.get('acao', '').strip(),
        'entidade': request.args.get('entidade', '').strip(),
        'metodo': request.args.get('metodo', '').strip(),
        'data_inicio': request.args.get('data_inicio', '').strip(),
        'data_fim': request.args.get('data_fim', '').strip(),
    }
    pagination_query = {key: value for key, value in request.args.items() if key != 'page'}
    return render_template(
        'audit/index.html',
        logs=logs,
        users=users,
        available_actions=available_actions,
        available_entities=available_entities,
        audit_action_label=audit_action_label,
        entity_label=entity_label,
        audit_json_lines=audit_json_lines,
        summary=summary,
        filters=filters,
        page=page,
        total_pages=total_pages,
        pagination_query=pagination_query,
        master_view=False,
    )


@main_bp.route('/master/auditoria')
@login_required
def master_audit_logs():
    if current_user.role != 'master':
        abort(403)
    page = max(request.args.get('page', 1, type=int) or 1, 1)
    per_page = 20
    query = db.session.query(AuditLog)
    if request.args.get('adega', '').strip().isdigit():
        query = query.filter(AuditLog.company_id == int(request.args.get('adega')))
    if request.args.get('usuario', '').strip().isdigit():
        query = query.filter(AuditLog.user_id == int(request.args.get('usuario')))
    if request.args.get('acao', '').strip():
        query = query.filter(AuditLog.action == request.args.get('acao').strip())
    query = apply_date_filters(query, AuditLog, request.args.get('data_inicio'), request.args.get('data_fim'))
    query = query.order_by(AuditLog.created_at.desc())

    total_logs = query.order_by(None).count()
    total_pages = max((total_logs + per_page - 1) // per_page, 1)
    page = min(page, total_pages)
    logs = query.offset((page - 1) * per_page).limit(per_page).all()
    companies = db.session.query(Company).order_by(Company.name.asc()).all()
    users = db.session.query(User).order_by(User.username.asc()).all()
    available_actions = [action for (action,) in db.session.query(AuditLog.action).distinct().order_by(AuditLog.action.asc()).all()]
    filters = {
        'adega': request.args.get('adega', '').strip(),
        'usuario': request.args.get('usuario', '').strip(),
        'acao': request.args.get('acao', '').strip(),
        'data_inicio': request.args.get('data_inicio', '').strip(),
        'data_fim': request.args.get('data_fim', '').strip(),
    }
    return render_template(
        'audit/master.html',
        logs=logs,
        companies=companies,
        users=users,
        available_actions=available_actions,
        audit_action_label=audit_action_label,
        entity_label=entity_label,
        audit_json_lines=audit_json_lines,
        filters=filters,
        page=page,
        total_pages=total_pages,
        pagination_query={key: value for key, value in request.args.items() if key != 'page'},
    )


@main_bp.route('/exportacoes/<export_type>', methods=['GET', 'POST'])
@login_required
def export_data(export_type):
    if not can_export_data() and not (request.method == 'POST' and authorize_role_override('admin', 'master')):
        flash('Informe a senha de um admin para exportar dados.', 'danger')
        return redirect(request.referrer or url_for('main.dashboard'))
    if export_type not in EXPORT_TYPES:
        abort(404)

    today_label = date.today().strftime('%Y-%m-%d')
    record_audit_event(
        'data_exported',
        'export',
        None,
        f'Exportação de {export_type} realizada.',
        new_values={'export_type': export_type},
        company_id=current_tenant_company().id,
        db_session=tenant_session(),
    )
    tenant_session().commit()
    if export_type == 'produtos':
        return csv_response(
            f'produtos-{today_label}.csv',
            ['id', 'produto', 'codigo', 'categoria', 'custo', 'venda', 'estoque', 'estoque_disponivel', 'estoque_minimo', 'ativo', 'kit', 'produto_base', 'quantidade_base'],
            export_products_rows(),
        )
    if export_type == 'vendas':
        return csv_response(
            f'vendas-{today_label}.csv',
            ['id', 'data', 'subtotal', 'desconto', 'total', 'lucro', 'status', 'pagamentos', 'caixa_id'],
            export_sales_rows(),
        )
    if export_type == 'caixas':
        return csv_response(
            f'caixas-{today_label}.csv',
            ['id', 'abertura', 'fechamento', 'status', 'valor_inicial', 'valor_fechamento', 'total_vendido', 'lucro', 'vendas'],
            export_cash_register_rows(),
        )
    return csv_response(
        f'contas-{today_label}.csv',
        ['id', 'descricao', 'categoria', 'valor', 'vencimento', 'status', 'pago', 'pago_em', 'observacoes'],
        export_payables_rows(),
    )


@main_bp.route('/contas-a-pagar', methods=['GET', 'POST'])
@login_required
@permission_required('can_manage_payables')
def payables():
    if request.method == 'POST':
        description = request.form.get('description', '').strip()
        category = request.form.get('category', 'Outros').strip() or 'Outros'
        amount = parse_money(request.form.get('amount'))
        due_date = parse_date(request.form.get('due_date'))
        notes = request.form.get('notes', '').strip()

        if not description:
            flash('Informe a descrição da conta.', 'danger')
        elif not due_date:
            flash('Informe uma data de vencimento válida.', 'danger')
        else:
            tenant_db = tenant_session()
            payable = Payable(
                company_id=current_tenant_company().id,
                description=description,
                category=category if category in PAYABLE_CATEGORIES else 'Outros',
                amount=amount,
                due_date=due_date,
                notes=notes,
            )
            tenant_db.add(payable)
            tenant_db.flush()
            record_audit_event(
                'payable_created',
                'payable',
                payable.id,
                f'Conta {payable.description} cadastrada.',
                new_values={
                    'description': payable.description,
                    'category': payable.category,
                    'amount': payable.amount,
                    'due_date': payable.due_date,
                },
                company_id=current_tenant_company().id,
                db_session=tenant_db,
            )
            tenant_db.commit()
            flash('Conta a pagar cadastrada com sucesso.', 'success')
            return redirect(url_for('main.payables'))

    status_filter = request.args.get('status', 'open')
    query = tenant_query(Payable)
    if status_filter == 'paid':
        query = query.filter_by(paid=True)
    elif status_filter == 'all':
        pass
    else:
        status_filter = 'open'
        query = query.filter_by(paid=False)

    payables_list = query.order_by(Payable.paid.asc(), Payable.due_date.asc(), Payable.description.asc()).all()
    open_payables = tenant_query(Payable).filter_by(paid=False).all()
    totals = {
        'open': round(sum(item.amount or 0.0 for item in open_payables), 2),
        'overdue': round(sum(item.amount or 0.0 for item in open_payables if payable_status(item) == 'overdue'), 2),
        'due_soon': round(sum(item.amount or 0.0 for item in open_payables if payable_status(item) in ('due_today', 'near_due')), 2),
    }

    return render_template(
        'payables/index.html',
        payables=payables_list,
        categories=PAYABLE_CATEGORIES,
        status_filter=status_filter,
        payable_status=payable_status,
        payable_status_label=payable_status_label,
        totals=totals,
        today=date.today(),
    )


@main_bp.route('/contas-a-pagar/<int:payable_id>/pagar', methods=['POST'])
@login_required
@permission_required('can_manage_payables')
def pay_payable(payable_id):
    payable = tenant_get_or_404(Payable, payable_id)
    old_values = {'paid': payable.paid, 'paid_at': payable.paid_at}
    payable.paid = True
    payable.paid_at = datetime.now(timezone.utc)
    record_audit_event(
        'payable_paid',
        'payable',
        payable.id,
        f'Conta {payable.description} marcada como paga.',
        old_values=old_values,
        new_values={'paid': payable.paid, 'paid_at': payable.paid_at},
        company_id=current_tenant_company().id,
        db_session=tenant_session(),
    )
    tenant_session().commit()
    flash('Conta marcada como paga.', 'success')
    return redirect(url_for('main.payables'))


@main_bp.route('/contas-a-pagar/<int:payable_id>/reabrir', methods=['POST'])
@login_required
@permission_required('can_manage_payables')
def reopen_payable(payable_id):
    payable = tenant_get_or_404(Payable, payable_id)
    old_values = {'paid': payable.paid, 'paid_at': payable.paid_at}
    payable.paid = False
    payable.paid_at = None
    record_audit_event(
        'payable_reopened',
        'payable',
        payable.id,
        f'Conta {payable.description} reaberta.',
        old_values=old_values,
        new_values={'paid': payable.paid, 'paid_at': payable.paid_at},
        company_id=current_tenant_company().id,
        db_session=tenant_session(),
    )
    tenant_session().commit()
    flash('Conta reaberta.', 'info')
    return redirect(url_for('main.payables', status='all'))


@main_bp.route('/relatorios')
@login_required
@permission_required('can_view_reports')
def reports():
    report_view = request.args.get('view', 'summary')
    if report_view not in ('summary', 'products'):
        report_view = 'summary'
    selected_period = request.args.get('period', 'daily')
    chart_metric = request.args.get('chart_metric', 'revenue')
    if chart_metric not in ('revenue', 'quantity'):
        chart_metric = 'revenue'
    start_date = parse_date(request.args.get('start_date'))
    end_date = parse_date(request.args.get('end_date'))
    period, start, end, start_datetime, end_datetime, label = report_period_range(
        selected_period,
        start_date=start_date,
        end_date=end_date,
    )
    sales = tenant_query(Sale).options(
        selectinload(Sale.payments),
        selectinload(Sale.items).selectinload(SaleItem.product),
    ).filter(
        Sale.created_at >= start_datetime,
        Sale.created_at < end_datetime,
    ).order_by(Sale.created_at.desc()).all()
    totals, payment_totals, top_products = build_sales_report(sales)
    daily_activity = build_daily_sales_activity(start_datetime, end_datetime, chart_metric) if period == 'daily' else None
    chart_data = daily_activity['buckets'] if daily_activity else build_sales_chart(period, start, end, sales)
    product_start_arg = request.args.get('product_start_date', '').strip()
    product_end_arg = request.args.get('product_end_date', '').strip()
    product_has_date_filter = bool(product_start_arg or product_end_arg)
    product_start = parse_date(product_start_arg) if product_start_arg else None
    product_end = parse_date(product_end_arg) if product_end_arg else None
    if product_has_date_filter:
        product_start = product_start or start
        product_end = product_end or end
    if product_start and product_end and product_end < product_start:
        product_start, product_end = product_end, product_start
    product_start_datetime = datetime.combine(product_start, time.min) if product_start else None
    product_end_datetime = datetime.combine(product_end + timedelta(days=1), time.min) if product_end else None
    product_category_id = request.args.get('product_category_id', '').strip()
    product_id = request.args.get('product_id', '').strip()
    product_sort = request.args.get('product_sort', 'quantity_desc')
    product_report, product_report_totals, product_sort = build_product_report(
        product_start_datetime,
        product_end_datetime,
        category_id=product_category_id,
        product_id=product_id,
        sort=product_sort,
    )
    categories = tenant_session().query(Category).filter_by(company_id=current_tenant_company().id).order_by(Category.name.asc()).all()
    products = tenant_query(Product).order_by(Product.name.asc()).all()

    return render_template(
        'reports/index.html',
        report_view=report_view,
        period=period,
        period_label=label,
        start_date=start,
        end_date=end,
        sales=sales,
        totals=totals,
        chart_data=chart_data,
        chart_metric=chart_metric,
        daily_activity=daily_activity,
        payment_totals=payment_totals,
        top_products=top_products,
        product_report=product_report,
        product_report_totals=product_report_totals,
        product_start_date=product_start,
        product_end_date=product_end,
        product_has_date_filter=product_has_date_filter,
        product_category_id=product_category_id,
        product_id=product_id,
        product_sort=product_sort,
        categories=categories,
        products=products,
        payment_methods=PAYMENT_METHODS,
        sale_profit=sale_profit,
    )


@main_bp.route('/vendas/nova', methods=['GET', 'POST'])
@login_required
@permission_required('can_manage_sales')
def new_sale():
    cash_register = open_cash_register()
    if not cash_register:
        flash('Abra o caixa antes de registrar uma venda.', 'warning')
        return redirect(url_for('main.cash_register'))

    company = current_tenant_company()
    products = tenant_query(Product).filter_by(active=True).order_by(Product.name.asc()).all()
    form_state = {
        'items': [{'product_id': '', 'quantity': '1'}],
        'discount_amount': '',
        'show_payment_step': False,
        'payments': {},
    }

    if request.method == 'POST':
        form_state = sale_form_state()
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        selected_items = []
        stock_requirements = {}
        stock_warnings = []
        total_amount = 0.0

        for product_id, quantity_value in zip(product_ids, quantities):
            quantity = parse_quantity(quantity_value)
            if not product_id or quantity <= 0:
                continue

            try:
                product_id_int = int(product_id)
            except (TypeError, ValueError):
                flash('Selecione um produto válido para finalizar a venda.', 'danger')
                return render_template(
                    'sales/form.html',
                    products=products,
                    payment_methods=PAYMENT_METHODS,
                    form_state=form_state,
                )

            product = tenant_query(Product).filter_by(id=product_id_int).first()
            if not product or not product.active:
                continue

            stock_product, units_per_sale = stock_source_for_product(product)
            if not stock_product:
                flash(f'Configure o kit do produto {product.name} antes de vender.', 'danger')
                return render_template(
                    'sales/form.html',
                    products=products,
                    payment_methods=PAYMENT_METHODS,
                    form_state=form_state,
                )

            stock_requirements[stock_product.id] = stock_requirements.get(stock_product.id, 0) + (units_per_sale * quantity)
            line_total = round(product.sale_price * quantity, 2)
            selected_items.append((product, quantity, line_total))
            total_amount += line_total

        for stock_product_id, required_quantity in stock_requirements.items():
            stock_product = tenant_query(Product).filter_by(id=stock_product_id).first()
            if not stock_product:
                continue
            if (stock_product.stock_quantity or 0) < required_quantity:
                if not company.allow_negative_stock:
                    flash(f'Estoque insuficiente para {stock_product.name}.', 'danger')
                    return render_template(
                        'sales/form.html',
                        products=products,
                        payment_methods=PAYMENT_METHODS,
                        form_state=form_state,
                    )
                resulting_stock = (stock_product.stock_quantity or 0) - required_quantity
                stock_warnings.append(f'{stock_product.name}: {resulting_stock} un.')

        if not selected_items:
            flash('Adicione pelo menos um produto à venda.', 'danger')
            return render_template(
                'sales/form.html',
                products=products,
                payment_methods=PAYMENT_METHODS,
                form_state=form_state,
            )

        payments = []
        paid_amount = 0.0
        for method in PAYMENT_METHODS:
            amount = parse_money(request.form.get(f'payment_{method}'))
            if amount > 0:
                payments.append((method, amount))
                paid_amount += amount

        total_amount = round(total_amount, 2)
        requested_discount = parse_money(request.form.get('discount_amount'))
        if requested_discount > total_amount:
            flash(f'O desconto não pode ser maior que o subtotal de {format_brl(total_amount)}.', 'danger')
            return render_template(
                'sales/form.html',
                products=products,
                payment_methods=PAYMENT_METHODS,
                form_state=form_state,
            )
        discount_amount = requested_discount
        final_amount = round(total_amount - discount_amount, 2)
        paid_amount = round(paid_amount, 2)
        if paid_amount < final_amount:
            missing = final_amount - paid_amount
            flash(f'Falta pagar {format_brl(missing)}.', 'danger')
            return render_template(
                'sales/form.html',
                products=products,
                payment_methods=PAYMENT_METHODS,
                form_state=form_state,
            )

        machine_fee_total = card_fee_total(company, payments, final_amount, paid_amount)

        sale = Sale(
            total_amount=total_amount,
            discount_amount=discount_amount,
            final_amount=final_amount,
            payment_status='paid',
            user_id=tenant_actor_user_id(),
            company_id=company.id,
            cash_register_id=cash_register.id,
        )
        tenant_db = tenant_session()
        tenant_db.add(sale)
        tenant_db.flush()

        try:
            for product, quantity, line_total in selected_items:
                stock_product, units_per_sale = stock_source_for_product(product)
                decrease_stock(
                    tenant_db,
                    stock_product,
                    units_per_sale * quantity,
                    movement_type='sale',
                    source_type='sale',
                    user_id=tenant_actor_user_id(),
                    source_id=sale.id,
                    unit_cost=stock_product.cost_price,
                    reason=f'Baixa da venda #{sale.id}',
                    notes=f'Produto vendido: {product.name}',
                    allow_negative_stock=company.allow_negative_stock,
                )
                unit_cost_price = product.cost_price or 0.0
                item_fee = machine_fee_total * (line_total / total_amount) if total_amount > 0 else 0.0
                tenant_db.add(SaleItem(
                    sale_id=sale.id,
                    product_id=product.id,
                    quantity=quantity,
                    unit_price=product.sale_price,
                    unit_cost_price=unit_cost_price,
                    total_price=line_total,
                    profit_amount=round((((product.sale_price or 0.0) - unit_cost_price) * quantity) - item_fee, 2),
                ))
        except StockMovementError as error:
            tenant_db.rollback()
            flash(str(error), 'danger')
            return render_template(
                'sales/form.html',
                products=products,
                payment_methods=PAYMENT_METHODS,
                form_state=form_state,
            )

        for method, amount in payments:
            tenant_db.add(Payment(sale_id=sale.id, method=method, amount=amount))

        record_audit_event(
            'sale_completed',
            'sale',
            sale.id,
            f'Venda #{sale.id} concluída no valor de {format_brl(final_amount)}.',
            new_values={
                'sale_id': sale.id,
                'subtotal': total_amount,
                'discount': discount_amount,
                'final_amount': final_amount,
                'paid_amount': paid_amount,
                'cash_register_id': cash_register.id,
                'payments': {method: amount for method, amount in payments},
                'items': [
                    {'product_id': product.id, 'name': product.name, 'quantity': quantity, 'total': line_total}
                    for product, quantity, line_total in selected_items
                ],
            },
            company_id=company.id,
            db_session=tenant_db,
        )

        tenant_db.commit()
        change_amount = max(paid_amount - final_amount, 0.0)
        if stock_warnings:
            flash(f'Estoque insuficiente permitido. Saldo após a venda: {", ".join(stock_warnings)}', 'warning')
        flash(f'Venda finalizada com sucesso. Troco: {format_brl(change_amount)}.', 'success')
        return redirect(url_for('main.sale_detail', sale_id=sale.id))

    return render_template(
        'sales/form.html',
        products=products,
        payment_methods=PAYMENT_METHODS,
        form_state=form_state,
    )


@main_bp.route('/vendas/<int:sale_id>')
@login_required
@permission_required('can_manage_sales')
def sale_detail(sale_id):
    sale = tenant_get_or_404(Sale, sale_id)
    paid_amount = sum(payment.amount for payment in sale.payments)
    change_amount = max(paid_amount - sale.final_amount, 0.0)
    return render_template(
        'sales/detail.html',
        sale=sale,
        sale_profit=sale_profit(sale),
        sale_item_profit=sale_item_profit,
        paid_amount=paid_amount,
        change_amount=change_amount,
        payment_methods=PAYMENT_METHODS,
    )


@main_bp.route('/caixa')
@login_required
@permission_required('can_manage_cash_register')
def cash_register():
    current_cash_register = open_cash_register()
    if current_cash_register:
        current_cash_register = tenant_query(CashRegister).options(
            selectinload(CashRegister.sales).selectinload(Sale.payments),
            selectinload(CashRegister.sales).selectinload(Sale.items).selectinload(SaleItem.product),
        ).filter_by(id=current_cash_register.id).first()
    closed_registers = tenant_query(CashRegister).options(
        selectinload(CashRegister.sales).selectinload(Sale.payments),
        selectinload(CashRegister.sales).selectinload(Sale.items).selectinload(SaleItem.product),
    ).filter_by(status='closed').order_by(CashRegister.closed_at.desc()).limit(10).all()
    show_cash_financials = can_view_cash_financials()
    user_ids = {item.user_id for item in closed_registers if item.user_id}
    responsible_users = {
        user.id: user.full_name or user.username
        for user in tenant_session().query(User).filter(User.id.in_(user_ids)).all()
    } if user_ids else {}
    cash_history = {}
    for item in closed_registers:
        sales = sorted(item.sales, key=lambda sale: sale.created_at or datetime.min, reverse=True)
        totals, payment_totals, _ = build_sales_report(sales)
        expected_amount = cash_register_expected_amount(item)
        cash_history[item.id] = {
            'responsible': responsible_users.get(item.user_id, 'Usuário não identificado'),
            'sales': sales,
            'sales_count': len(sales),
            'total_sold': totals['final'],
            'payment_totals': payment_totals,
            'expected_amount': expected_amount,
            'difference': round((item.closing_amount or 0.0) - expected_amount, 2),
        }
    current_cash_snapshot = build_cash_register_snapshot(current_cash_register) if current_cash_register else None
    return render_template(
        'cash_register.html',
        cash_register=current_cash_register,
        cash_register_profit=cash_register_profit(current_cash_register) if show_cash_financials else 0,
        cash_register_expected_amount=cash_register_expected_amount(current_cash_register) if show_cash_financials else 0,
        closed_register_profits={item.id: cash_register_profit(item) for item in closed_registers} if show_cash_financials else {},
        closed_registers=closed_registers,
        cash_history=cash_history,
        current_cash_snapshot=current_cash_snapshot,
        payment_methods=PAYMENT_METHODS,
        show_cash_financials=show_cash_financials,
    )


@main_bp.route('/caixa/<int:cash_register_id>')
@login_required
@permission_required('can_manage_cash_register')
def cash_register_detail(cash_register_id):
    selected_cash_register = tenant_query(CashRegister).options(
        selectinload(CashRegister.sales).selectinload(Sale.payments),
        selectinload(CashRegister.sales).selectinload(Sale.items).selectinload(SaleItem.product),
    ).filter_by(id=cash_register_id).first()
    if not selected_cash_register:
        abort(404)
    sales = sorted(
        selected_cash_register.sales,
        key=lambda sale: sale.created_at or datetime.min,
        reverse=True,
    )
    totals, payment_totals, top_products = build_sales_report(sales)
    timeline = build_sale_timeline(sales)
    return render_template(
        'cash_register_detail.html',
        cash_register=selected_cash_register,
        totals=totals,
        payment_totals=payment_totals,
        top_products=top_products,
        sale_timeline=timeline,
        peak_hours=cash_register_peak_hours(selected_cash_register),
        payment_methods=PAYMENT_METHODS,
        cash_register_profit=cash_register_profit(selected_cash_register),
        cash_register_total_sold=cash_register_total_sold(selected_cash_register),
        show_cash_financials=can_view_cash_financials(),
    )


@main_bp.route('/caixa/abrir', methods=['POST'])
@login_required
@permission_required('can_manage_cash_register')
def open_cash_register_route():
    if open_cash_register():
        flash('Já existe um caixa aberto.', 'warning')
        return redirect(url_for('main.cash_register'))

    cash_register = CashRegister(
        opening_amount=parse_money(request.form.get('opening_amount')),
        status='open',
        user_id=tenant_actor_user_id(),
        company_id=current_tenant_company().id,
    )
    tenant_db = tenant_session()
    tenant_db.add(cash_register)
    tenant_db.flush()
    record_audit_event(
        'cash_register_opened',
        'cash_register',
        cash_register.id,
        f'Caixa #{cash_register.id} aberto.',
        new_values={'opening_amount': cash_register.opening_amount, 'status': cash_register.status},
        company_id=current_tenant_company().id,
        db_session=tenant_db,
    )
    tenant_db.commit()
    flash('Caixa aberto com sucesso.', 'success')
    return redirect(url_for('main.cash_register'))


@main_bp.route('/caixa/fechar', methods=['POST'])
@login_required
@permission_required('can_manage_cash_register')
def close_cash_register_route():
    cash_register = open_cash_register()
    if not cash_register:
        flash('Não há caixa aberto para fechar.', 'warning')
        return redirect(url_for('main.cash_register'))

    closing_amount = round(parse_money(request.form.get('closing_amount')), 2)
    expected_amount = cash_register_expected_amount(cash_register)
    if closing_amount != expected_amount:
        difference = round(abs(expected_amount - closing_amount), 2)
        if not can_view_cash_financials():
            flash('Valor de fechamento não confere. Solicite a conferência de um usuário autorizado.', 'danger')
        elif closing_amount < expected_amount:
            flash(f'Falta {format_brl(difference)} para fechar o caixa. Valor esperado: {format_brl(expected_amount)}.', 'danger')
        else:
            flash(f'O valor está excedido em {format_brl(difference)}. Valor esperado: {format_brl(expected_amount)}.', 'danger')
        return redirect(url_for('main.cash_register'))

    cash_register.closing_amount = closing_amount
    cash_register.closed_at = datetime.now(timezone.utc)
    cash_register.status = 'closed'
    record_audit_event(
        'cash_register_closed',
        'cash_register',
        cash_register.id,
        f'Caixa #{cash_register.id} fechado.',
        new_values={
            'closing_amount': cash_register.closing_amount,
            'expected_amount': expected_amount,
            'closed_at': cash_register.closed_at,
            'status': cash_register.status,
        },
        company_id=current_tenant_company().id,
        db_session=tenant_session(),
    )
    tenant_session().commit()
    flash('Caixa fechado com sucesso.', 'success')
    return redirect(url_for('main.cash_register'))
