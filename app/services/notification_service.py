import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError

from app.models import Notification, NotificationPreference, Payable, Product
from app.money import format_brl
from app.time_utils import business_today, utc_isoformat


SEVERITIES = ('info', 'success', 'warning', 'critical')
SEVERITY_RANK = {value: index for index, value in enumerate(SEVERITIES)}
CATEGORIES = ('stock', 'payables', 'cash_register', 'sales', 'security', 'administration', 'subscription', 'backup')
DEFAULT_EMAIL_TYPES = {
    'product_out_of_stock', 'product_negative_stock', 'stock_movement_failed',
    'payable_overdue', 'cash_register_mismatch', 'backup_failed',
    'subscription_expiring', 'subscription_expired', 'consecutive_login_failures',
    'permissions_changed', 'product_import_failed',
}


def utcnow():
    return datetime.now(timezone.utc)


def safe_text(value, maximum):
    return str(value or '').strip()[:maximum]


def safe_metadata(value):
    if not isinstance(value, dict):
        value = {}
    encoded = json.dumps(value, ensure_ascii=False, default=str)
    if len(encoded) > 8000:
        encoded = json.dumps({'truncated': True}, ensure_ascii=False)
    return encoded


def notification_data(notification):
    try:
        metadata = json.loads(notification.metadata_json or '{}')
    except (TypeError, ValueError):
        metadata = {}
    return {
        'id': notification.id,
        'notification_type': notification.notification_type,
        'category': notification.category,
        'severity': notification.severity,
        'title': notification.title,
        'message': notification.message,
        'entity_type': notification.entity_type or '',
        'entity_id': notification.entity_id,
        'action_url': notification.action_url or '',
        'is_read': bool(notification.is_read),
        'read_at': utc_isoformat(notification.read_at),
        'is_dismissed': bool(notification.is_dismissed),
        'email_status': notification.email_status or 'not_requested',
        'metadata': metadata,
        'created_at': utc_isoformat(notification.created_at),
        'expires_at': utc_isoformat(notification.expires_at),
    }


def preference_for(db_session, company_id, user_id, notification_type='*', create=False):
    preference = db_session.query(NotificationPreference).filter_by(
        company_id=company_id,
        user_id=user_id,
        notification_type=notification_type,
    ).first()
    if preference or not create:
        return preference
    preference = NotificationPreference(
        company_id=company_id,
        user_id=user_id,
        notification_type=notification_type,
        email_enabled=notification_type in DEFAULT_EMAIL_TYPES,
    )
    db_session.add(preference)
    db_session.flush()
    return preference


def preference_allows(preference, severity, channel='in_app'):
    if preference is None:
        return True
    enabled = {
        'in_app': preference.in_app_enabled,
        'email': preference.email_enabled,
        'desktop': preference.desktop_enabled,
    }.get(channel, True)
    return bool(enabled) and SEVERITY_RANK.get(severity, 0) >= SEVERITY_RANK.get(preference.minimum_severity, 0)


def create_notification(
    db_session,
    *,
    company_id,
    notification_type,
    category,
    severity,
    title,
    message,
    deduplication_key,
    user_id=None,
    entity_type='',
    entity_id=None,
    action_url='',
    metadata=None,
    expires_at=None,
    email_requested=None,
):
    if severity not in SEVERITIES:
        raise ValueError('Severidade de notificação inválida.')
    if category not in CATEGORIES:
        raise ValueError('Categoria de notificação inválida.')
    deduplication_key = safe_text(deduplication_key, 255)
    if not deduplication_key:
        raise ValueError('A chave de deduplicação é obrigatória.')

    existing = db_session.query(Notification).filter_by(
        company_id=company_id,
        deduplication_key=deduplication_key,
    ).first()
    if existing and not existing.is_resolved:
        return existing, False

    if existing:
        existing.user_id = user_id
        existing.notification_type = safe_text(notification_type, 80)
        existing.category = category
        existing.severity = severity
        existing.title = safe_text(title, 180)
        existing.message = safe_text(message, 1000)
        existing.entity_type = safe_text(entity_type, 80)
        existing.entity_id = entity_id
        existing.action_url = safe_text(action_url, 500)
        existing.metadata_json = safe_metadata(metadata)
        existing.expires_at = expires_at
        existing.is_read = False
        existing.read_at = None
        existing.is_dismissed = False
        existing.dismissed_at = None
        existing.is_resolved = False
        existing.resolved_at = None
        existing.email_status = 'pending' if (
            email_requested if email_requested is not None else notification_type in DEFAULT_EMAIL_TYPES
        ) else 'not_requested'
        existing.email_error = ''
        db_session.flush()
        return existing, True

    notification = Notification(
        company_id=company_id,
        user_id=user_id,
        notification_type=safe_text(notification_type, 80),
        category=category,
        severity=severity,
        title=safe_text(title, 180),
        message=safe_text(message, 1000),
        entity_type=safe_text(entity_type, 80),
        entity_id=entity_id,
        action_url=safe_text(action_url, 500),
        deduplication_key=deduplication_key,
        metadata_json=safe_metadata(metadata),
        expires_at=expires_at,
        email_status='pending' if (email_requested if email_requested is not None else notification_type in DEFAULT_EMAIL_TYPES) else 'not_requested',
    )
    try:
        with db_session.begin_nested():
            db_session.add(notification)
            db_session.flush()
    except IntegrityError:
        existing = db_session.query(Notification).filter_by(
            company_id=company_id,
            deduplication_key=deduplication_key,
        ).first()
        if existing:
            return existing, False
        raise
    return notification, True


def visible_query(db_session, company_id, user_id):
    now = utcnow()
    query = db_session.query(Notification).filter(
        Notification.company_id == company_id,
        or_(Notification.user_id.is_(None), Notification.user_id == user_id),
        Notification.is_dismissed.is_(False),
        Notification.is_resolved.is_(False),
        or_(Notification.expires_at.is_(None), Notification.expires_at > now),
    )
    preference = preference_for(db_session, company_id, user_id, '*')
    if preference and not preference.in_app_enabled:
        return query.filter(Notification.id == -1)
    if preference:
        minimum_rank = SEVERITY_RANK.get(preference.minimum_severity, 0)
        allowed_severities = SEVERITIES[minimum_rank:]
        query = query.filter(Notification.severity.in_(allowed_severities))
    return query


def get_user_notifications(db_session, company_id, user_id, *, page=1, page_size=20, category=None,
                           severity=None, is_read=None, date_from=None, date_to=None, search=''):
    query = visible_query(db_session, company_id, user_id)
    if category:
        query = query.filter(Notification.category == category)
    if severity:
        query = query.filter(Notification.severity == severity)
    if is_read is not None:
        query = query.filter(Notification.is_read.is_(is_read))
    if date_from:
        query = query.filter(Notification.created_at >= date_from)
    if date_to:
        query = query.filter(Notification.created_at <= date_to)
    if search:
        term = f'%{safe_text(search, 100)}%'
        query = query.filter(or_(Notification.title.ilike(term), Notification.message.ilike(term)))
    total = query.count()
    items = query.order_by(Notification.created_at.desc(), Notification.id.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    unread_count = visible_query(db_session, company_id, user_id).filter(Notification.is_read.is_(False)).count()
    return {'items': [notification_data(item) for item in items], 'page': page, 'page_size': page_size,
            'total': total, 'unread_count': unread_count}


def get_unread_count(db_session, company_id, user_id):
    return visible_query(db_session, company_id, user_id).filter(Notification.is_read.is_(False)).count()


def find_visible_notification(db_session, company_id, user_id, notification_id):
    return visible_query(db_session, company_id, user_id).filter(Notification.id == notification_id).first()


def mark_as_read(db_session, notification):
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = utcnow()
        db_session.flush()
    return notification


def mark_all_as_read(db_session, company_id, user_id):
    notifications = visible_query(db_session, company_id, user_id).filter(Notification.is_read.is_(False)).all()
    now = utcnow()
    for notification in notifications:
        notification.is_read = True
        notification.read_at = now
    db_session.flush()
    return len(notifications)


def dismiss_notification(db_session, notification):
    notification.is_dismissed = True
    notification.dismissed_at = utcnow()
    notification.is_read = True
    notification.read_at = notification.read_at or notification.dismissed_at
    db_session.flush()
    return notification


def resolve_notification(db_session, company_id, deduplication_key):
    notification = db_session.query(Notification).filter_by(
        company_id=company_id,
        deduplication_key=deduplication_key,
        is_resolved=False,
    ).first()
    if notification:
        notification.is_resolved = True
        notification.resolved_at = utcnow()
        db_session.flush()
    return notification


def _resolve_other_entity_notifications(db_session, company_id, entity_type, entity_id, active_key):
    now = utcnow()
    notifications = db_session.query(Notification).filter(
        Notification.company_id == company_id,
        Notification.entity_type == entity_type,
        Notification.entity_id == entity_id,
        Notification.notification_type.in_((
            'product_out_of_stock', 'product_low_stock',
            'payable_overdue', 'payable_due_today', 'payable_due_soon',
        )),
        Notification.is_resolved.is_(False),
        Notification.deduplication_key != active_key,
    ).all()
    for notification in notifications:
        notification.is_resolved = True
        notification.resolved_at = now


def sync_operational_notifications(db_session, company_id):
    """Materializa no tenant os mesmos alertas operacionais exibidos pela Web."""
    products = db_session.query(Product).filter(
        Product.company_id == company_id,
        Product.active.is_(True),
    ).all()
    for product in products:
        quantity = product.effective_stock_quantity or 0
        minimum = product.min_stock_quantity or 0
        active_key = ''
        if minimum > 0 and quantity <= minimum:
            is_out = quantity <= 0
            alert_type = 'product_out_of_stock' if is_out else 'product_low_stock'
            active_key = f'{alert_type}:{company_id}:{product.id}'
            create_notification(
                db_session,
                company_id=company_id,
                notification_type=alert_type,
                category='stock',
                severity='critical' if is_out else 'warning',
                title='Produto esgotado' if is_out else 'Estoque baixo',
                message=(
                    f'{product.name} está sem estoque. Mínimo: {minimum} un.' if is_out else
                    f'{product.name} está com {quantity} un. Mínimo: {minimum} un.'
                ),
                deduplication_key=active_key,
                entity_type='product',
                entity_id=product.id,
                action_url='/products',
                metadata={'stock_quantity': quantity, 'min_stock_quantity': minimum},
            )
        _resolve_other_entity_notifications(db_session, company_id, 'product', product.id, active_key)

    today = business_today()
    alert_limit = today + timedelta(days=3)
    payables = db_session.query(Payable).filter(
        Payable.company_id == company_id,
        Payable.paid.is_(False),
        Payable.due_date <= alert_limit,
    ).all()
    active_payable_ids = set()
    for payable in payables:
        active_payable_ids.add(payable.id)
        amount = format_brl(payable.amount or 0)
        if payable.due_date < today:
            days = (today - payable.due_date).days
            alert_type, severity, title = 'payable_overdue', 'critical', 'Conta vencida'
            message = f'{payable.description} venceu há {days} dia{"s" if days != 1 else ""}. Valor: {amount}.'
        elif payable.due_date == today:
            alert_type, severity, title = 'payable_due_today', 'warning', 'Conta vence hoje'
            message = f'{payable.description} vence hoje. Valor: {amount}.'
        else:
            days = (payable.due_date - today).days
            alert_type, severity, title = 'payable_due_soon', 'info', 'Conta próxima do vencimento'
            message = f'{payable.description} vence em {days} dia{"s" if days != 1 else ""}. Valor: {amount}.'
        active_key = f'{alert_type}:{payable.id}:{payable.due_date.isoformat()}'
        create_notification(
            db_session,
            company_id=company_id,
            notification_type=alert_type,
            category='payables',
            severity=severity,
            title=title,
            message=message,
            deduplication_key=active_key,
            entity_type='payable',
            entity_id=payable.id,
            action_url='/payables',
            metadata={'amount': str(payable.amount or 0), 'due_date': payable.due_date.isoformat()},
        )
        _resolve_other_entity_notifications(db_session, company_id, 'payable', payable.id, active_key)

    stale_payables = db_session.query(Notification).filter(
        Notification.company_id == company_id,
        Notification.entity_type == 'payable',
        Notification.is_resolved.is_(False),
    ).all()
    now = utcnow()
    for notification in stale_payables:
        if notification.entity_id not in active_payable_ids:
            notification.is_resolved = True
            notification.resolved_at = now
    db_session.flush()
