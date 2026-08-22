from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


MONEY_QUANTUM = Decimal('0.01')
MAX_MONEY = Decimal('9999999999.99')


def parse_money_decimal(raw_value, *, positive=False):
    """Parse canonical JSON numbers or pt-BR monetary text without using float."""
    if isinstance(raw_value, bool) or raw_value is None:
        raise ValueError('missing_money')

    text = str(raw_value).strip()
    if not text:
        raise ValueError('missing_money')

    text = text.replace('R$', '').replace('\u00a0', '').replace(' ', '')
    if ',' in text:
        text = text.replace('.', '').replace(',', '.')

    try:
        value = Decimal(text)
    except InvalidOperation as error:
        raise ValueError('invalid_money') from error

    if not value.is_finite():
        raise ValueError('invalid_money')
    value = value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    if value < 0 or (positive and value <= 0):
        raise ValueError('invalid_money')
    if value > MAX_MONEY:
        raise ValueError('money_out_of_range')
    return value


def money_json(value):
    return format(parse_money_decimal(value or 0), '.2f')


def format_brl(value):
    amount = parse_money_decimal(value or 0)
    whole, cents = format(amount, ',.2f').split('.')
    return f'R$ {whole.replace(",", ".")},{cents}'
