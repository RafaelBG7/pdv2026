import csv
import io
import uuid
from decimal import Decimal
from pathlib import Path

from flask import Blueprint, Response, abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.models import HistoricalReportImportBatch
from app.security.rate_limit import authenticated_identity_key, configured_limit
from app.extensions import limiter
from app.services.audit_service import record_audit_event
from app.services.historical_report_import_service import (
    HistoricalImportError,
    import_preview_rows,
    load_preview,
    preview_historical_import,
    save_preview,
)
from app.tenant import current_tenant_company, tenant_session


historical_reports_bp = Blueprint('historical_reports', __name__, url_prefix='/relatorios/importacao')


def _ensure_available():
    environment = (current_app.config.get('ENVIRONMENT') or current_app.config.get('APP_ENV') or 'development').lower()
    if environment == 'production':
        abort(404)
    if current_user.role not in ('admin', 'master'):
        abort(403)
    company = current_tenant_company()
    if not company:
        abort(403)
    return company


def _preview_directory():
    return Path(current_app.instance_path) / 'historical-report-previews'


def _batches(company_id):
    return tenant_session().query(HistoricalReportImportBatch).filter_by(
        company_id=company_id,
    ).order_by(HistoricalReportImportBatch.created_at.desc()).limit(50).all()


@historical_reports_bp.get('/')
@login_required
def index():
    company = _ensure_available()
    return render_template(
        'historical_reports/import.html',
        preview=None,
        preview_token=None,
        idempotency_key=None,
        batches=_batches(company.id),
    )


@historical_reports_bp.get('/modelo')
@login_required
def download_template():
    _ensure_available()
    template_path = Path(current_app.root_path) / 'static' / 'files' / 'modelo_importacao_relatorios_skygest.xlsx'
    if not template_path.exists():
        abort(404)
    return send_file(
        template_path,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='modelo_importacao_relatorios_skygest.xlsx',
    )


@historical_reports_bp.post('/previsualizar')
@login_required
@limiter.limit(configured_limit('RATELIMIT_IMPORT', '5 per hour'), key_func=authenticated_identity_key)
def preview():
    company = _ensure_available()
    uploaded = request.files.get('spreadsheet')
    if not uploaded or not uploaded.filename:
        flash('Selecione uma planilha XLSX ou CSV.', 'danger')
        return redirect(url_for('historical_reports.index'))
    content = uploaded.read()
    if not content:
        flash('O arquivo enviado está vazio.', 'danger')
        return redirect(url_for('historical_reports.index'))
    try:
        preview_data = preview_historical_import(content, uploaded.filename, tenant_session(), company.id)
    except (HistoricalImportError, ValueError) as error:
        flash(str(error), 'danger')
        return redirect(url_for('historical_reports.index'))
    token = uuid.uuid4().hex
    save_preview(preview_data, _preview_directory(), token, company.id, current_user.id)
    return render_template(
        'historical_reports/import.html',
        preview=preview_data,
        preview_token=token,
        idempotency_key=uuid.uuid4().hex,
        batches=_batches(company.id),
        Decimal=Decimal,
    )


@historical_reports_bp.post('/confirmar')
@login_required
@limiter.limit(configured_limit('RATELIMIT_IMPORT', '5 per hour'), key_func=authenticated_identity_key)
def confirm():
    company = _ensure_available()
    token = request.form.get('preview_token', '')
    idempotency_key = request.form.get('idempotency_key', '')
    strategy = request.form.get('strategy', 'ignore')
    try:
        if uuid.UUID(idempotency_key).hex != idempotency_key:
            raise HistoricalImportError('Identificador da requisição inválido.')
        preview_data = load_preview(_preview_directory(), token, company.id, current_user.id)
        batch = import_preview_rows(
            preview_data,
            tenant_session(),
            company.id,
            current_user.id,
            strategy,
            idempotency_key,
        )
        load_preview(_preview_directory(), token, company.id, current_user.id, delete=True)
    except (HistoricalImportError, ValueError, IntegrityError) as error:
        tenant_session().rollback()
        flash(str(error) or 'Não foi possível concluir a importação.', 'danger')
        return redirect(url_for('historical_reports.index'))

    record_audit_event(
        'historical_reports_imported',
        'historical_report_import_batch',
        batch.id,
        f'Histórico importado: {batch.inserted_rows} inserido(s), {batch.updated_rows} atualizado(s), {batch.ignored_rows} ignorado(s).',
        new_values={
            'inserted': batch.inserted_rows,
            'updated': batch.updated_rows,
            'ignored': batch.ignored_rows,
            'period_start': batch.period_start,
            'period_end': batch.period_end,
        },
        company_id=company.id,
        db_session=tenant_session(),
    )
    tenant_session().commit()
    flash(
        f'Importação concluída: {batch.inserted_rows} inserido(s), '
        f'{batch.updated_rows} atualizado(s) e {batch.ignored_rows} ignorado(s).',
        'success',
    )
    return redirect(url_for('historical_reports.index'))


@historical_reports_bp.get('/erros/<token>.csv')
@login_required
def error_report(token):
    company = _ensure_available()
    try:
        preview_data = load_preview(_preview_directory(), token, company.id, current_user.id)
    except HistoricalImportError as error:
        flash(str(error), 'danger')
        return redirect(url_for('historical_reports.index'))
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['linha', 'data', 'campo', 'valor_recebido', 'motivo'])
    for row in preview_data['rows']:
        for error in row['errors']:
            writer.writerow([row['linha'], row.get('data', ''), error['field'], error['value'], error['message']])
    return Response(
        '\ufeff' + output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename="erros_importacao_relatorios.csv"'},
    )
