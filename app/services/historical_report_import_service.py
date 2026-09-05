import csv
import hashlib
import io
import json
import re
import zipfile
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from xml.etree import ElementTree

from sqlalchemy.exc import IntegrityError

from app.models import HistoricalDailyReport, HistoricalReportImportBatch, Sale
from app.money import money_decimal


IMPORT_SHEET = 'Importacao_Relatorios'
EXPECTED_HEADERS = (
    'data',
    'quantidade_vendas',
    'faturamento',
    'lucro_bruto',
    'ticket_medio',
    'origem',
)
DEFAULT_SOURCE = 'Importação histórica'
MAX_IMPORT_ROWS = 10000
TICKET_WARNING_TOLERANCE = Decimal('0.01')
XML_NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
REL_NS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
PACKAGE_REL_NS = '{http://schemas.openxmlformats.org/package/2006/relationships}'


class HistoricalImportError(ValueError):
    pass


def _column_index(reference):
    letters = ''.join(char for char in reference if char.isalpha())
    index = 0
    for letter in letters:
        index = index * 26 + ord(letter.upper()) - ord('A') + 1
    return index - 1


def _cell_text(cell, shared_strings):
    if cell.find(f'{XML_NS}f') is not None:
        raise HistoricalImportError('A aba de importação não pode conter fórmulas.')
    inline = cell.find(f'{XML_NS}is/{XML_NS}t')
    value_node = cell.find(f'{XML_NS}v')
    if inline is not None:
        return inline.text or ''
    if value_node is None:
        return ''
    value = value_node.text or ''
    if cell.attrib.get('t') == 's':
        try:
            return shared_strings[int(value)]
        except (ValueError, IndexError):
            return ''
    return value


def _xlsx_rows(content):
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as error:
        raise HistoricalImportError('O arquivo XLSX está corrompido ou não é uma planilha válida.') from error

    with archive:
        names = set(archive.namelist())
        if any(name.lower().endswith(('.bin', '.vba', '.exe', '.js')) for name in names):
            raise HistoricalImportError('Arquivos com macros ou conteúdo executável não são permitidos.')
        required = {'xl/workbook.xml', 'xl/_rels/workbook.xml.rels'}
        if not required.issubset(names):
            raise HistoricalImportError('O arquivo XLSX não possui uma estrutura válida.')

        workbook_root = ElementTree.fromstring(archive.read('xl/workbook.xml'))
        relation_root = ElementTree.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
        relations = {
            relation.attrib['Id']: relation.attrib['Target']
            for relation in relation_root.findall(f'{PACKAGE_REL_NS}Relationship')
        }
        target = None
        for sheet in workbook_root.iter(f'{XML_NS}sheet'):
            if sheet.attrib.get('name') == IMPORT_SHEET:
                target = relations.get(sheet.attrib.get(f'{REL_NS}id'))
                break
        if not target:
            raise HistoricalImportError(f'A planilha precisa conter a aba {IMPORT_SHEET}.')
        sheet_path = target.lstrip('/')
        if not sheet_path.startswith('xl/'):
            sheet_path = f'xl/{sheet_path}'
        if sheet_path not in names:
            raise HistoricalImportError(f'Não foi possível ler a aba {IMPORT_SHEET}.')

        shared_strings = []
        if 'xl/sharedStrings.xml' in names:
            shared_root = ElementTree.fromstring(archive.read('xl/sharedStrings.xml'))
            for item in shared_root.iter(f'{XML_NS}si'):
                shared_strings.append(''.join(node.text or '' for node in item.iter(f'{XML_NS}t')))

        date_1904 = False
        workbook_pr = workbook_root.find(f'{XML_NS}workbookPr')
        if workbook_pr is not None:
            date_1904 = workbook_pr.attrib.get('date1904') in {'1', 'true', 'True'}

        sheet_root = ElementTree.fromstring(archive.read(sheet_path))
        raw_rows = []
        for row in sheet_root.iter(f'{XML_NS}row'):
            values = []
            for cell in row.findall(f'{XML_NS}c'):
                index = _column_index(cell.attrib.get('r', ''))
                while len(values) <= index:
                    values.append('')
                values[index] = _cell_text(cell, shared_strings)
            if any(str(value).strip() for value in values):
                raw_rows.append((int(row.attrib.get('r', len(raw_rows) + 1)), values))

    return raw_rows, date_1904


def _csv_rows(content):
    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError as error:
        raise HistoricalImportError('O arquivo CSV deve usar codificação UTF-8.') from error
    sample = text[:4096]
    delimiter = ';' if sample.count(';') > sample.count(',') else ','
    return [(index, row) for index, row in enumerate(csv.reader(io.StringIO(text), delimiter=delimiter), 1)], False


def _parse_date(value, date_1904=False):
    if value is None or str(value).strip() == '':
        raise ValueError('campo obrigatório vazio')
    raw = str(value).strip()
    if re.fullmatch(r'\d+(?:\.\d+)?', raw):
        serial = Decimal(raw)
        if serial <= 0 or serial != serial.to_integral_value():
            raise ValueError('data real do Excel inválida')
        base = date(1904, 1, 1) if date_1904 else date(1899, 12, 30)
        try:
            return base + timedelta(days=int(serial))
        except OverflowError as error:
            raise ValueError('data fora do intervalo permitido') from error
    for pattern in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(raw, pattern).date()
        except ValueError:
            pass
    raise ValueError('use AAAA-MM-DD, DD/MM/AAAA ou uma data real do Excel')


def _parse_decimal(value, *, required, nonnegative):
    if value is None or str(value).strip() == '':
        if required:
            raise ValueError('campo obrigatório vazio')
        return None
    raw = str(value).strip().replace('R$', '').replace('\u00a0', '').replace(' ', '')
    if ',' in raw:
        raw = raw.replace('.', '').replace(',', '.')
    try:
        parsed = Decimal(raw)
    except InvalidOperation as error:
        raise ValueError('valor decimal inválido') from error
    if not parsed.is_finite():
        raise ValueError('valor decimal inválido')
    if nonnegative and parsed < 0:
        raise ValueError('o valor não pode ser negativo')
    return parsed.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _parse_count(value):
    if value is None or str(value).strip() == '':
        raise ValueError('campo obrigatório vazio')
    try:
        parsed = Decimal(str(value).strip().replace(',', '.'))
    except InvalidOperation as error:
        raise ValueError('informe um número inteiro') from error
    if not parsed.is_finite() or parsed != parsed.to_integral_value():
        raise ValueError('informe um número inteiro')
    if parsed < 0:
        raise ValueError('a quantidade não pode ser negativa')
    return int(parsed)


def _serialize_row(row):
    return {
        **row,
        'data': row['data'].isoformat() if isinstance(row.get('data'), date) else row.get('data'),
        'faturamento': str(row['faturamento']) if isinstance(row.get('faturamento'), Decimal) else row.get('faturamento'),
        'lucro_bruto': str(row['lucro_bruto']) if isinstance(row.get('lucro_bruto'), Decimal) else row.get('lucro_bruto'),
        'ticket_medio': str(row['ticket_medio']) if isinstance(row.get('ticket_medio'), Decimal) else row.get('ticket_medio'),
    }


def deserialize_row(row):
    return {
        **row,
        'data': date.fromisoformat(row['data']),
        'faturamento': Decimal(row['faturamento']),
        'lucro_bruto': Decimal(row['lucro_bruto']) if row.get('lucro_bruto') is not None else None,
        'ticket_medio': Decimal(row['ticket_medio']),
    }


def preview_historical_import(content, filename, db_session, company_id):
    suffix = Path(filename or '').suffix.lower()
    if suffix not in {'.xlsx', '.csv'}:
        raise HistoricalImportError('Formato inválido. Envie uma planilha XLSX ou CSV.')
    raw_rows, date_1904 = _xlsx_rows(content) if suffix == '.xlsx' else _csv_rows(content)
    if not raw_rows:
        raise HistoricalImportError('A planilha está vazia.')
    headers = tuple(str(value).strip() for value in raw_rows[0][1])
    if headers != EXPECTED_HEADERS:
        raise HistoricalImportError(
            'Cabeçalhos inválidos. Use, nesta ordem: ' + ', '.join(EXPECTED_HEADERS) + '.'
        )
    if len(raw_rows) - 1 > MAX_IMPORT_ROWS:
        raise HistoricalImportError(f'O arquivo excede o limite de {MAX_IMPORT_ROWS} linhas.')

    parsed_rows = []
    seen_dates = set()
    for line_number, values in raw_rows[1:]:
        values = list(values[:len(EXPECTED_HEADERS)])
        values.extend([''] * (len(EXPECTED_HEADERS) - len(values)))
        if not any(str(value).strip() for value in values):
            continue
        row = {'linha': line_number, 'errors': [], 'warnings': [], 'status': 'valid'}
        for index, (field, parser) in enumerate((
            ('data', lambda value: _parse_date(value, date_1904)),
            ('quantidade_vendas', _parse_count),
            ('faturamento', lambda value: _parse_decimal(value, required=True, nonnegative=True)),
            ('lucro_bruto', lambda value: _parse_decimal(value, required=False, nonnegative=False)),
        )):
            try:
                row[field] = parser(values[index])
            except ValueError as error:
                row[field] = values[index]
                row['errors'].append({'field': field, 'value': str(values[index]), 'message': str(error)})

        row['origem'] = str(values[5] or '').strip()[:120] or DEFAULT_SOURCE
        if not row['errors']:
            calculated = (
                row['faturamento'] / row['quantidade_vendas']
                if row['quantidade_vendas'] else Decimal('0.00')
            ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            row['ticket_medio'] = calculated
            try:
                informed = _parse_decimal(values[4], required=False, nonnegative=False)
            except ValueError as error:
                row['warnings'].append({'field': 'ticket_medio', 'value': str(values[4]), 'message': str(error)})
            else:
                if informed is not None and abs(informed - calculated) > TICKET_WARNING_TOLERANCE:
                    row['warnings'].append({
                        'field': 'ticket_medio',
                        'value': str(values[4]),
                        'message': f'O valor oficial calculado é {calculated:.2f}.',
                    })
            if row['data'] in seen_dates:
                row['errors'].append({'field': 'data', 'value': row['data'].isoformat(), 'message': 'data duplicada no arquivo'})
                row['status'] = 'duplicate'
            seen_dates.add(row['data'])

        if row['errors'] and row['status'] != 'duplicate':
            row['status'] = 'invalid'
        parsed_rows.append(row)

    valid_dates = [row['data'] for row in parsed_rows if not row['errors']]
    existing = {
        item.report_date
        for item in db_session.query(HistoricalDailyReport).filter(
            HistoricalDailyReport.company_id == company_id,
            HistoricalDailyReport.report_date.in_(valid_dates),
        ).all()
    } if valid_dates else set()
    real_sale_dates = set()
    if valid_dates:
        start_at = datetime.combine(min(valid_dates), time.min)
        end_at = datetime.combine(max(valid_dates) + timedelta(days=1), time.min)
        for created_at, in db_session.query(Sale.created_at).filter(
            Sale.company_id == company_id,
            Sale.valid_filter(),
            Sale.created_at >= start_at,
            Sale.created_at < end_at,
        ).all():
            if created_at:
                real_sale_dates.add(created_at.date())

    for row in parsed_rows:
        if row['errors']:
            continue
        if row['data'] in real_sale_dates:
            row['errors'].append({'field': 'data', 'value': row['data'].isoformat(), 'message': 'já existem vendas reais do SkyGest nesta data'})
            row['status'] = 'invalid'
        elif row['data'] in existing:
            row['status'] = 'existing'

    valid_rows = [row for row in parsed_rows if not row['errors']]
    revenue = sum((row['faturamento'] for row in valid_rows), Decimal('0.00'))
    sales_count = sum(row['quantidade_vendas'] for row in valid_rows)
    known_profit = [row['lucro_bruto'] for row in valid_rows if row['lucro_bruto'] is not None]
    summary = {
        'filename': Path(filename).name,
        'file_hash': hashlib.sha256(content).hexdigest(),
        'rows': [_serialize_row(row) for row in parsed_rows],
        'total_rows': len(parsed_rows),
        'valid_rows': len(valid_rows),
        'invalid_rows': len(parsed_rows) - len(valid_rows),
        'duplicate_rows': sum(row['status'] == 'duplicate' for row in parsed_rows),
        'existing_rows': sum(row['status'] == 'existing' for row in parsed_rows),
        'first_date': min(valid_dates).isoformat() if valid_dates else None,
        'last_date': max(valid_dates).isoformat() if valid_dates else None,
        'sales_count': sales_count,
        'revenue': str(money_decimal(revenue)),
        'gross_profit': str(money_decimal(sum(known_profit, Decimal('0.00')))) if known_profit else None,
        'profit_complete': len(known_profit) == len(valid_rows),
        'average_ticket': str(money_decimal(revenue / sales_count)) if sales_count else '0.00',
    }
    return summary


def import_preview_rows(preview, db_session, company_id, user_id, strategy, idempotency_key):
    if strategy not in {'ignore', 'update'}:
        raise HistoricalImportError('Estratégia de importação inválida.')
    previous = db_session.query(HistoricalReportImportBatch).filter_by(
        company_id=company_id,
        idempotency_key=idempotency_key,
    ).first()
    if previous:
        return previous

    rows = [deserialize_row(row) for row in preview['rows'] if not row['errors']]
    if not rows:
        raise HistoricalImportError('Não há linhas válidas para importar.')
    dates = [row['data'] for row in rows]
    start_at = datetime.combine(min(dates), time.min)
    end_at = datetime.combine(max(dates) + timedelta(days=1), time.min)
    real_dates = {
        created_at.date()
        for created_at, in db_session.query(Sale.created_at).filter(
            Sale.company_id == company_id,
            Sale.valid_filter(),
            Sale.created_at >= start_at,
            Sale.created_at < end_at,
        ).all()
        if created_at
    }
    if real_dates.intersection(dates):
        raise HistoricalImportError('Uma ou mais datas passaram a possuir vendas reais. Gere uma nova prévia.')

    batch = HistoricalReportImportBatch(
        company_id=company_id,
        user_id=user_id,
        filename=preview['filename'],
        file_hash=preview['file_hash'],
        source=next((row['origem'] for row in rows if row['origem']), DEFAULT_SOURCE),
        strategy=strategy,
        status='processing',
        valid_rows=len(rows),
        invalid_rows=preview['invalid_rows'],
        period_start=min(dates),
        period_end=max(dates),
        idempotency_key=idempotency_key,
    )
    db_session.add(batch)
    db_session.flush()
    inserted = updated = ignored = 0
    for row in rows:
        report = db_session.query(HistoricalDailyReport).filter_by(
            company_id=company_id,
            report_date=row['data'],
        ).first()
        if report and strategy == 'ignore':
            ignored += 1
            continue
        if report:
            updated += 1
        else:
            inserted += 1
            report = HistoricalDailyReport(company_id=company_id, report_date=row['data'])
            db_session.add(report)
        report.sales_count = row['quantidade_vendas']
        report.revenue = row['faturamento']
        report.gross_profit = row['lucro_bruto']
        report.average_ticket = row['ticket_medio']
        report.source = row['origem']
        report.batch_id = batch.id
        report.user_id = user_id

    batch.inserted_rows = inserted
    batch.updated_rows = updated
    batch.ignored_rows = ignored
    batch.status = 'completed'
    try:
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    return batch


def save_preview(preview, directory, token, company_id, user_id):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f'{token}.json'
    payload = {'company_id': company_id, 'user_id': user_id, 'created_at': datetime.now(timezone.utc).isoformat(), 'preview': preview}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    return path


def load_preview(directory, token, company_id, user_id, *, delete=False):
    if not re.fullmatch(r'[a-f0-9]{32}', token or ''):
        raise HistoricalImportError('Prévia inválida ou expirada.')
    path = Path(directory) / f'{token}.json'
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as error:
        raise HistoricalImportError('Prévia inválida ou expirada. Envie o arquivo novamente.') from error
    if payload.get('company_id') != company_id or payload.get('user_id') != user_id:
        raise HistoricalImportError('A prévia não pertence ao usuário ou à empresa autenticada.')
    created_at = datetime.fromisoformat(payload['created_at'])
    if datetime.now(timezone.utc) - created_at > timedelta(hours=1):
        path.unlink(missing_ok=True)
        raise HistoricalImportError('A prévia expirou. Envie o arquivo novamente.')
    if delete:
        path.unlink(missing_ok=True)
    return payload['preview']
