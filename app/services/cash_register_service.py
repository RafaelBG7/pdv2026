from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func

from app.models import CashRegister, Company, Payment, Sale, User
from app.services.audit_service import record_audit_event
from app.time_utils import utc_isoformat


PAYMENT_METHODS = {
    'money': 'Dinheiro',
    'pix': 'Pix',
    'debit': 'Débito',
    'credit': 'Crédito',
}
MONEY_QUANTUM = Decimal('0.01')


class CashRegisterOperationError(Exception):
    def __init__(self, message, code, status_code=409, field=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.field = field


def money_decimal(value):
    return Decimal(str(value or 0)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def money_value(value):
    return float(money_decimal(value))


def money_text(value):
    return f'{money_decimal(value):.2f}'.replace('.', ',')


def timestamp_value(value):
    return utc_isoformat(value)


def lock_company_scope(db_session, company_id):
    # Serializa abertura/fechamento para evitar dois caixas simultâneos.
    db_session.query(Company.id).filter(Company.id == company_id).with_for_update().first()


def find_open_cash_register(db_session, company_id, for_update=False):
    query = db_session.query(CashRegister).filter(
        CashRegister.company_id == company_id,
        CashRegister.status == 'open',
    )
    if for_update:
        query = query.with_for_update()
    return query.order_by(CashRegister.opened_at.desc(), CashRegister.id.desc()).first()


def cash_register_expected_amount(db_session, company_id, cash_register):
    sales_total = db_session.query(
        func.coalesce(func.sum(Sale.final_amount), 0.0),
    ).filter(
        Sale.company_id == company_id,
        Sale.cash_register_id == cash_register.id,
        Sale.valid_filter(),
    ).scalar()
    return money_decimal(cash_register.opening_amount) + money_decimal(sales_total)


def open_cash_register(db_session, company_id, user, opening_amount, client='windows_native'):
    lock_company_scope(db_session, company_id)
    current = find_open_cash_register(db_session, company_id, for_update=True)
    if current is not None:
        raise CashRegisterOperationError(
            f'O caixa #{current.id} já está aberto.',
            'cash_register_already_open',
        )

    cash_register = CashRegister(
        opening_amount=money_value(opening_amount),
        status='open',
        user_id=user.id,
        company_id=company_id,
    )
    db_session.add(cash_register)
    db_session.flush()
    record_audit_event(
        'cash_register_opened',
        'cash_register',
        cash_register.id,
        f'Caixa #{cash_register.id} aberto via {"Web" if client == "web" else "aplicativo Windows"}.',
        new_values={
            'opening_amount': money_value(opening_amount),
            'status': cash_register.status,
            'client': client,
        },
        company_id=company_id,
        user=user,
        db_session=db_session,
    )
    return cash_register


def close_cash_register(
    db_session,
    company_id,
    user,
    cash_register_id,
    closing_amount,
    can_view_financials,
    closed_at,
    client='windows_native',
):
    lock_company_scope(db_session, company_id)
    cash_register = find_open_cash_register(db_session, company_id, for_update=True)
    if cash_register is None:
        raise CashRegisterOperationError(
            'Não há caixa aberto para fechar.',
            'cash_register_not_open',
        )
    if cash_register.id != cash_register_id:
        raise CashRegisterOperationError(
            'O caixa aberto mudou. Atualize a tela antes de continuar.',
            'cash_register_changed',
        )

    expected_amount = cash_register_expected_amount(db_session, company_id, cash_register)
    received_amount = money_decimal(closing_amount)
    if received_amount != expected_amount:
        difference = abs(expected_amount - received_amount)
        if not can_view_financials:
            message = 'Valor de fechamento não confere. Solicite a conferência de um usuário autorizado.'
        elif received_amount < expected_amount:
            message = (
                f'Falta R$ {money_text(difference)} para fechar o caixa. '
                f'Valor esperado: R$ {money_text(expected_amount)}.'
            )
        else:
            message = (
                f'O valor está excedido em R$ {money_text(difference)}. '
                f'Valor esperado: R$ {money_text(expected_amount)}.'
            )
        raise CashRegisterOperationError(
            message,
            'cash_register_amount_mismatch',
            422,
            'closing_amount',
        )

    cash_register.closing_amount = money_value(received_amount)
    cash_register.closed_at = closed_at
    cash_register.status = 'closed'
    record_audit_event(
        'cash_register_closed',
        'cash_register',
        cash_register.id,
        f'Caixa #{cash_register.id} fechado via {"Web" if client == "web" else "aplicativo Windows"}.',
        new_values={
            'closing_amount': money_value(received_amount),
            'expected_amount': money_value(expected_amount),
            'closed_at': closed_at,
            'status': cash_register.status,
            'client': client,
        },
        company_id=company_id,
        user=user,
        db_session=db_session,
    )
    return cash_register


def build_cash_register_snapshot(
    db_session,
    company_id,
    can_view_financials,
    recent_limit=10,
):
    current = find_open_cash_register(db_session, company_id)
    recent = (
        db_session.query(CashRegister)
        .filter(
            CashRegister.company_id == company_id,
            CashRegister.status == 'closed',
        )
        .order_by(CashRegister.closed_at.desc(), CashRegister.id.desc())
        .limit(recent_limit)
        .all()
    )
    cash_registers = ([current] if current is not None else []) + recent
    cash_register_ids = [item.id for item in cash_registers]

    sales_metrics = {}
    payment_totals = {}
    valid_payment_totals = {}
    cancellation_metrics = {}
    if cash_register_ids:
        sales_metrics = {
            cash_register_id: {
                'sales_count': int(sales_count or 0),
                'sales_total': money_decimal(sales_total),
            }
            for cash_register_id, sales_count, sales_total in (
                db_session.query(
                    Sale.cash_register_id,
                    func.count(Sale.id),
                    func.coalesce(func.sum(Sale.final_amount), 0.0),
                )
                .filter(
                    Sale.company_id == company_id,
                    Sale.cash_register_id.in_(cash_register_ids),
                )
                .group_by(Sale.cash_register_id)
                .all()
            )
        }
        for cash_register_id, method, amount in (
            db_session.query(
                Sale.cash_register_id,
                Payment.method,
                func.coalesce(func.sum(Payment.amount), 0.0),
            )
            .join(Payment, Payment.sale_id == Sale.id)
            .filter(
                Sale.company_id == company_id,
                Sale.cash_register_id.in_(cash_register_ids),
            )
            .group_by(Sale.cash_register_id, Payment.method)
            .all()
        ):
            payment_totals.setdefault(cash_register_id, {})[method] = money_value(amount)

        cancellation_metrics = {
            cash_register_id: {
                'sales_count': int(sales_count or 0),
                'sales_total': money_decimal(sales_total),
            }
            for cash_register_id, sales_count, sales_total in (
                db_session.query(
                    Sale.cash_register_id,
                    func.count(Sale.id),
                    func.coalesce(func.sum(Sale.final_amount), 0.0),
                )
                .filter(
                    Sale.company_id == company_id,
                    Sale.cash_register_id.in_(cash_register_ids),
                    Sale.status == 'cancelled',
                )
                .group_by(Sale.cash_register_id)
                .all()
            )
        }
        for cash_register_id, method, amount in (
            db_session.query(
                Sale.cash_register_id,
                Payment.method,
                func.coalesce(func.sum(Payment.amount), 0.0),
            )
            .join(Payment, Payment.sale_id == Sale.id)
            .filter(
                Sale.company_id == company_id,
                Sale.cash_register_id.in_(cash_register_ids),
                Sale.valid_filter(),
            )
            .group_by(Sale.cash_register_id, Payment.method)
            .all()
        ):
            valid_payment_totals.setdefault(cash_register_id, {})[method] = money_value(amount)

    user_ids = {item.user_id for item in cash_registers if item.user_id}
    users = {
        user.id: user.full_name or user.username
        for user in db_session.query(User).filter(
            User.company_id == company_id,
            User.id.in_(user_ids),
        ).all()
    } if user_ids else {}

    def serialize(cash_register):
        metrics = sales_metrics.get(cash_register.id, {
            'sales_count': 0,
            'sales_total': Decimal('0.00'),
        })
        cancelled = cancellation_metrics.get(cash_register.id, {
            'sales_count': 0,
            'sales_total': Decimal('0.00'),
        })
        original_sales_total = metrics['sales_total']
        valid_sales_total = original_sales_total - cancelled['sales_total']
        preserve_closed_history = cash_register.status == 'closed'
        sales_total = original_sales_total if preserve_closed_history else valid_sales_total
        sales_count = (
            metrics['sales_count']
            if preserve_closed_history
            else metrics['sales_count'] - cancelled['sales_count']
        )
        opening_amount = money_decimal(cash_register.opening_amount)
        expected_amount = opening_amount + sales_total
        adjusted_expected_amount = opening_amount + valid_sales_total
        closing_amount = money_decimal(cash_register.closing_amount)
        visible_payment_totals = (
            payment_totals if preserve_closed_history else valid_payment_totals
        )
        return {
            'id': cash_register.id,
            'status': cash_register.status,
            'opened_at': timestamp_value(cash_register.opened_at),
            'closed_at': timestamp_value(cash_register.closed_at),
            'responsible_user': users.get(cash_register.user_id, 'Usuário não identificado'),
            'sales_count': sales_count,
            'cancelled_sales_count': cancelled['sales_count'],
            'opening_amount': money_value(opening_amount) if can_view_financials else None,
            'closing_amount': (
                money_value(closing_amount)
                if can_view_financials and cash_register.status == 'closed'
                else None
            ),
            'sales_total': money_value(sales_total) if can_view_financials else None,
            'cancelled_sales_total': (
                money_value(cancelled['sales_total']) if can_view_financials else None
            ),
            'valid_sales_total': money_value(valid_sales_total) if can_view_financials else None,
            'expected_amount': money_value(expected_amount) if can_view_financials else None,
            'adjusted_expected_amount': (
                money_value(adjusted_expected_amount) if can_view_financials else None
            ),
            'difference': (
                money_value(closing_amount - expected_amount)
                if can_view_financials and cash_register.status == 'closed'
                else None
            ),
            'payment_totals': [
                {
                    'method': method,
                    'label': label,
                    'amount': visible_payment_totals.get(cash_register.id, {}).get(method, 0.0),
                }
                for method, label in PAYMENT_METHODS.items()
            ] if can_view_financials else [],
        }

    return {
        'permissions': {
            'can_view_financials': bool(can_view_financials),
        },
        'current_register': serialize(current) if current is not None else None,
        'recent_registers': [serialize(item) for item in recent],
    }
