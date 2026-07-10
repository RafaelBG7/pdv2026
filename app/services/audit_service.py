import json
from datetime import date, datetime
from decimal import Decimal

from flask import current_app, g, has_request_context, request
from flask_login import current_user

from app.extensions import db
from app.models import AuditLog
from app.tenant import current_tenant_company


SENSITIVE_KEYS = {
    'password',
    'password_hash',
    'current_password',
    'new_password',
    'confirm_password',
    'token',
    'secret',
    'secret_key',
    'api_key',
    'activation_key',
    'mail_smtp_password',
    'mysql_password',
}


AUDIT_ACTION_LABELS = {
    'login_success': 'Login realizado',
    'login_failed': 'Falha no login',
    'logout': 'Logout',
    'user_created': 'Usuário criado',
    'user_updated': 'Usuário atualizado',
    'user_permissions_updated': 'Permissões atualizadas',
    'password_changed': 'Senha alterada',
    'email_change_requested': 'Troca de e-mail solicitada',
    'email_changed': 'E-mail alterado',
    'company_created': 'Adega criada',
    'company_updated': 'Adega atualizada',
    'company_activated': 'Adega ativada',
    'company_deactivated': 'Adega inativada',
    'company_accessed_by_master': 'Acesso master iniciado',
    'company_access_ended': 'Acesso master encerrado',
    'company_deleted': 'Adega excluída',
    'subscription_updated': 'Assinatura atualizada',
    'activation_key_generated': 'Key gerada',
    'activation_key_applied': 'Key aplicada',
    'product_created': 'Produto criado',
    'product_updated': 'Produto atualizado',
    'product_activated': 'Produto ativado',
    'product_deactivated': 'Produto inativado',
    'product_deleted': 'Produto excluído',
    'category_created': 'Categoria criada',
    'category_updated': 'Categoria atualizada',
    'category_deleted': 'Categoria excluída',
    'products_imported': 'Produtos importados',
    'stock_entry': 'Entrada de estoque',
    'stock_adjustment': 'Ajuste de estoque',
    'stock_sale': 'Baixa por venda',
    'stock_import': 'Estoque importado',
    'stock_return': 'Devolução ao estoque',
    'sale_created': 'Venda criada',
    'sale_completed': 'Venda concluída',
    'cash_register_opened': 'Caixa aberto',
    'cash_register_closed': 'Caixa fechado',
    'payable_created': 'Conta criada',
    'payable_paid': 'Conta paga',
    'payable_reopened': 'Conta reaberta',
    'settings_updated': 'Configurações atualizadas',
    'financial_fees_updated': 'Taxas financeiras atualizadas',
    'backup_generated': 'Backup gerado',
    'backup_schedule_updated': 'Agenda de backup atualizada',
    'logs_cleared': 'Logs limpos',
    'data_exported': 'Dados exportados',
}


ENTITY_LABELS = {
    'auth': 'Autenticação',
    'user': 'Usuário',
    'company': 'Adega',
    'activation_key': 'Key',
    'product': 'Produto',
    'category': 'Categoria',
    'stock_movement': 'Estoque',
    'sale': 'Venda',
    'cash_register': 'Caixa',
    'payable': 'Conta a pagar',
    'settings': 'Configurações',
    'backup': 'Backup',
    'logs': 'Logs',
    'export': 'Exportação',
}


def mask_sensitive_value(key, value):
    key = (key or '').lower()
    text = str(value or '')
    if 'activation_key' in key:
        compact = text.replace('-', '')
        if len(compact) <= 4:
            return '****'
        return f'****{compact[-4:]}'
    if key in SENSITIVE_KEYS or any(sensitive in key for sensitive in SENSITIVE_KEYS):
        return '[protegido]'
    return value


def json_default(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def sanitize_payload(payload):
    if not payload:
        return {}
    if isinstance(payload, dict):
        return {
            key: sanitize_payload(mask_sensitive_value(key, value))
            for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [sanitize_payload(item) for item in payload]
    return payload


def serialize_payload(payload):
    sanitized = sanitize_payload(payload)
    if not sanitized:
        return ''
    return json.dumps(sanitized, ensure_ascii=False, sort_keys=True, default=json_default)


def changed_values(old_values, new_values):
    old_values = old_values or {}
    new_values = new_values or {}
    old_diff = {}
    new_diff = {}
    for key in sorted(set(old_values) | set(new_values)):
        old_value = old_values.get(key)
        new_value = new_values.get(key)
        if old_value != new_value:
            old_diff[key] = old_value
            new_diff[key] = new_value
    return old_diff, new_diff


def request_ip_address():
    if not has_request_context():
        return ''
    remote_addr = request.remote_addr or ''
    forwarded_for = request.headers.get('X-Forwarded-For', '')
    if forwarded_for and remote_addr in {'127.0.0.1', '::1'}:
        return forwarded_for.split(',', 1)[0].strip()
    return remote_addr


def record_audit_event(
    action,
    entity_type,
    entity_id=None,
    description=None,
    old_values=None,
    new_values=None,
    company_id=None,
    user=None,
    db_session=None,
):
    session = db_session or db.session
    try:
        actor = user
        if actor is None and has_request_context() and current_user.is_authenticated:
            actor = current_user

        company = current_tenant_company() if has_request_context() and current_user.is_authenticated else None
        resolved_company_id = company_id if company_id is not None else (company.id if company else None)
        route = (request.endpoint or request.path) if has_request_context() else ''

        audit_log = AuditLog(
            company_id=resolved_company_id,
            user_id=getattr(actor, 'id', None),
            user_name=getattr(actor, 'username', '') or '',
            user_role=getattr(actor, 'role', '') or '',
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description or AUDIT_ACTION_LABELS.get(action, action),
            old_values=serialize_payload(old_values),
            new_values=serialize_payload(new_values),
            ip_address=request_ip_address(),
            user_agent=request.headers.get('User-Agent', '') if has_request_context() else '',
            request_id=getattr(g, 'request_id', '') if has_request_context() else '',
            route=route,
            http_method=request.method if has_request_context() else '',
        )
        session.add(audit_log)
        return audit_log
    except Exception as error:
        current_app.logger.error('Falha ao registrar auditoria: %s', error, exc_info=True)
        return None


def audit_action_label(action):
    return AUDIT_ACTION_LABELS.get(action, action)


def entity_label(entity_type):
    return ENTITY_LABELS.get(entity_type, entity_type)
