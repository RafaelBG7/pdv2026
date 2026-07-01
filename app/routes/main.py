from datetime import date, datetime, time, timedelta, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import CashRegister, Payment, Product, Sale, SaleItem

main_bp = Blueprint('main', __name__)
PAYMENT_METHODS = {
    'money': 'Dinheiro',
    'pix': 'Pix',
    'debit': 'Débito',
    'credit': 'Crédito',
}


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


def parse_quantity(value):
    try:
        return max(int(value or 0), 0)
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
    return CashRegister.query.filter_by(status='open').order_by(CashRegister.opened_at.desc()).first()


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


@main_bp.route('/')
@main_bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', open_cash_register=open_cash_register())


@main_bp.route('/vendas')
@login_required
def sales():
    sales = Sale.query.order_by(Sale.created_at.desc()).all()
    return render_template(
        'sales/index.html',
        sales=sales,
        payment_methods=PAYMENT_METHODS,
        open_cash_register=open_cash_register(),
    )


@main_bp.route('/relatorios')
@login_required
def reports():
    selected_period = request.args.get('period', 'daily')
    start_date = parse_date(request.args.get('start_date'))
    end_date = parse_date(request.args.get('end_date'))
    period, start, end, start_datetime, end_datetime, label = report_period_range(
        selected_period,
        start_date=start_date,
        end_date=end_date,
    )
    sales = Sale.query.filter(
        Sale.created_at >= start_datetime,
        Sale.created_at < end_datetime,
    ).order_by(Sale.created_at.desc()).all()
    totals, payment_totals, top_products = build_sales_report(sales)
    chart_data = build_sales_chart(period, start, end, sales)

    return render_template(
        'reports/index.html',
        period=period,
        period_label=label,
        start_date=start,
        end_date=end,
        sales=sales,
        totals=totals,
        chart_data=chart_data,
        payment_totals=payment_totals,
        top_products=top_products,
        payment_methods=PAYMENT_METHODS,
        sale_profit=sale_profit,
    )


@main_bp.route('/vendas/nova', methods=['GET', 'POST'])
@login_required
def new_sale():
    cash_register = open_cash_register()
    if not cash_register:
        flash('Abra o caixa antes de registrar uma venda.', 'warning')
        return redirect(url_for('main.cash_register'))

    products = Product.query.filter_by(active=True).order_by(Product.name.asc()).all()
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
        total_amount = 0.0

        for product_id, quantity_value in zip(product_ids, quantities):
            quantity = parse_quantity(quantity_value)
            if not product_id or quantity <= 0:
                continue

            product = db.session.get(Product, int(product_id))
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
            stock_product = db.session.get(Product, stock_product_id)
            if stock_product.stock_quantity < required_quantity:
                flash(f'Estoque insuficiente para {stock_product.name}.', 'danger')
                return render_template(
                    'sales/form.html',
                    products=products,
                    payment_methods=PAYMENT_METHODS,
                    form_state=form_state,
                )

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
        discount_amount = min(parse_money(request.form.get('discount_amount')), total_amount)
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

        sale = Sale(
            total_amount=total_amount,
            discount_amount=discount_amount,
            final_amount=final_amount,
            payment_status='paid',
            user_id=current_user.id,
            cash_register_id=cash_register.id,
        )
        db.session.add(sale)
        db.session.flush()

        for product, quantity, line_total in selected_items:
            stock_product, units_per_sale = stock_source_for_product(product)
            stock_product.stock_quantity -= units_per_sale * quantity
            unit_cost_price = product.cost_price or 0.0
            db.session.add(SaleItem(
                sale_id=sale.id,
                product_id=product.id,
                quantity=quantity,
                unit_price=product.sale_price,
                unit_cost_price=unit_cost_price,
                total_price=line_total,
                profit_amount=round(((product.sale_price or 0.0) - unit_cost_price) * quantity, 2),
            ))

        for method, amount in payments:
            db.session.add(Payment(sale_id=sale.id, method=method, amount=amount))

        db.session.commit()
        change_amount = max(paid_amount - final_amount, 0.0)
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
def sale_detail(sale_id):
    sale = db.get_or_404(Sale, sale_id)
    paid_amount = sum(payment.amount for payment in sale.payments)
    change_amount = max(paid_amount - sale.final_amount, 0.0)
    return render_template(
        'sales/detail.html',
        sale=sale,
        sale_profit=sale_profit(sale),
        paid_amount=paid_amount,
        change_amount=change_amount,
        payment_methods=PAYMENT_METHODS,
    )


@main_bp.route('/caixa')
@login_required
def cash_register():
    current_cash_register = open_cash_register()
    closed_registers = CashRegister.query.filter_by(status='closed').order_by(CashRegister.closed_at.desc()).limit(10).all()
    return render_template(
        'cash_register.html',
        cash_register=current_cash_register,
        cash_register_profit=cash_register_profit(current_cash_register),
        cash_register_expected_amount=cash_register_expected_amount(current_cash_register),
        closed_register_profits={item.id: cash_register_profit(item) for item in closed_registers},
        closed_registers=closed_registers,
    )


@main_bp.route('/caixa/abrir', methods=['POST'])
@login_required
def open_cash_register_route():
    if open_cash_register():
        flash('Já existe um caixa aberto.', 'warning')
        return redirect(url_for('main.cash_register'))

    cash_register = CashRegister(
        opening_amount=parse_money(request.form.get('opening_amount')),
        status='open',
        user_id=current_user.id,
    )
    db.session.add(cash_register)
    db.session.commit()
    flash('Caixa aberto com sucesso.', 'success')
    return redirect(url_for('main.cash_register'))


@main_bp.route('/caixa/fechar', methods=['POST'])
@login_required
def close_cash_register_route():
    cash_register = open_cash_register()
    if not cash_register:
        flash('Não há caixa aberto para fechar.', 'warning')
        return redirect(url_for('main.cash_register'))

    closing_amount = round(parse_money(request.form.get('closing_amount')), 2)
    expected_amount = cash_register_expected_amount(cash_register)
    if closing_amount != expected_amount:
        difference = round(abs(expected_amount - closing_amount), 2)
        if closing_amount < expected_amount:
            flash(f'Falta {format_brl(difference)} para fechar o caixa. Valor esperado: {format_brl(expected_amount)}.', 'danger')
        else:
            flash(f'O valor está excedido em {format_brl(difference)}. Valor esperado: {format_brl(expected_amount)}.', 'danger')
        return redirect(url_for('main.cash_register'))

    cash_register.closing_amount = closing_amount
    cash_register.closed_at = datetime.now(timezone.utc)
    cash_register.status = 'closed'
    db.session.commit()
    flash('Caixa fechado com sucesso.', 'success')
    return redirect(url_for('main.cash_register'))
