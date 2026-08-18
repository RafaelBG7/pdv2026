import os
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_BUSINESS_TIMEZONE = 'America/Sao_Paulo'


def business_timezone():
    name = os.environ.get('BUSINESS_TIMEZONE', DEFAULT_BUSINESS_TIMEZONE).strip()
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_BUSINESS_TIMEZONE)


def as_utc(value):
    """Normaliza datas persistidas: valores sem fuso no banco representam UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def utc_isoformat(value):
    normalized = as_utc(value)
    if normalized is None:
        return None
    return normalized.isoformat().replace('+00:00', 'Z')


def to_business_datetime(value):
    normalized = as_utc(value)
    return normalized.astimezone(business_timezone()) if normalized else None


def business_today():
    return datetime.now(timezone.utc).astimezone(business_timezone()).date()


def business_date_range_utc(start_date, end_date):
    """Converte um intervalo inclusivo de datas comerciais para limites UTC do banco."""
    zone = business_timezone()
    start = datetime.combine(start_date, time.min, tzinfo=zone)
    end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=zone)
    return (
        start.astimezone(timezone.utc).replace(tzinfo=None),
        end.astimezone(timezone.utc).replace(tzinfo=None),
    )
