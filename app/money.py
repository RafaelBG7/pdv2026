from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


MONEY_QUANTUM = Decimal('0.01')
PERCENT_QUANTUM = Decimal('0.0001')
MAX_MONEY = Decimal('9999999999.99')


def decimal_value(raw_value, *, quantum=MONEY_QUANTUM, default=Decimal('0')):
    """Convert stored/calculated values through text and quantize deterministically."""
    if raw_value is None or raw_value == '':
        raw_value = default
    if isinstance(raw_value, bool):
        raise ValueError('invalid_decimal')
    try:
        value = Decimal(str(raw_value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError('invalid_decimal') from error
    if not value.is_finite():
        raise ValueError('invalid_decimal')
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def money_decimal(raw_value):
    return decimal_value(raw_value, quantum=MONEY_QUANTUM)


def percent_decimal(raw_value):
    return decimal_value(raw_value, quantum=PERCENT_QUANTUM)


def _normalized_money_decimal(raw_value, *, positive=False, enforce_maximum=True):
    """Normalize monetary values without losing decimal precision."""
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
    if enforce_maximum and value > MAX_MONEY:
        raise ValueError('money_out_of_range')
    return value


def parse_money_decimal(raw_value, *, positive=False):
    """Parse user input and enforce the supported per-transaction range."""
    return _normalized_money_decimal(raw_value, positive=positive)


def money_json(value):
    # Stored legacy values and aggregate totals can exceed the limit applied to
    # one new transaction. Output serialization must remain read-only and must
    # not make an otherwise valid listing endpoint fail completely.
    return format(
        _normalized_money_decimal(value or 0, enforce_maximum=False),
        '.2f',
    )


def format_brl(value):
    amount = _normalized_money_decimal(value or 0, enforce_maximum=False)
    whole, cents = format(amount, ',.2f').split('.')
    return f'R$ {whole.replace(",", ".")},{cents}'
