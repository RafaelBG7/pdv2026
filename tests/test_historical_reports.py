import io
import logging
import tempfile
import unittest
import uuid
import zipfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.models import (
    CashRegister,
    Company,
    HistoricalDailyReport,
    HistoricalReportImportBatch,
    Product,
    Sale,
    StockMovement,
    User,
)
from app.routes.main import build_sales_chart, build_sales_report, merge_historical_report_totals
from app.services.historical_report_import_service import (
    HistoricalImportError,
    import_preview_rows,
    preview_historical_import,
)


class TestConfig:
    TESTING = True
    SECRET_KEY = 'historical-test-secret'
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    MAIL_SUPPRESS_SEND = True
    API_ALLOW_INSECURE_AUTH = True
    RATELIMIT_ENABLED = False
    RATELIMIT_STORAGE_URI = 'memory://'


def csv_bytes(*rows, headers='data;quantidade_vendas;faturamento;lucro_bruto;ticket_medio;origem'):
    return ('\n'.join((headers, *rows)) + '\n').encode()


def xlsx_bytes(*rows):
    cells = []
    headers = ('data', 'quantidade_vendas', 'faturamento', 'lucro_bruto', 'ticket_medio', 'origem')
    all_rows = (headers, *rows)
    for row_number, row in enumerate(all_rows, 1):
        row_cells = []
        for index, value in enumerate(row):
            column = chr(ord('A') + index)
            if isinstance(value, (int, float)):
                row_cells.append(f'<c r="{column}{row_number}"><v>{value}</v></c>')
            else:
                row_cells.append(f'<c r="{column}{row_number}" t="inlineStr"><is><t>{value}</t></is></c>')
        cells.append(f'<row r="{row_number}">{"".join(row_cells)}</row>')
    sheet = '<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + ''.join(cells) + '</sheetData></worksheet>'
    workbook = '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Importacao_Relatorios" sheetId="1" r:id="rId1"/></sheets></workbook>'
    relationships = '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>'
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        archive.writestr('xl/workbook.xml', workbook)
        archive.writestr('xl/_rels/workbook.xml.rels', relationships)
        archive.writestr('xl/worksheets/sheet1.xml', sheet)
    return output.getvalue()


class HistoricalReportTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        TestConfig.LOG_DIR = Path(self.temp_dir.name) / 'logs'
        TestConfig.BACKUP_DIR = Path(self.temp_dir.name) / 'backups'
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.client.post('/login', data={'username': 'master', 'password': 'master123'})

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            for handler in list(self.app.logger.handlers):
                if getattr(handler, 'baseFilename', None):
                    self.app.logger.removeHandler(handler)
                    handler.close()
            logging.shutdown()
        self.temp_dir.cleanup()

    def company_id(self):
        return User.query.filter_by(username='master').one().company_id

    def preview(self, content, filename='historico.csv', company_id=None):
        return preview_historical_import(content, filename, db.session, company_id or self.company_id())

    def import_rows(self, preview, strategy='ignore', company_id=None, user_id=None, key=None):
        user = User.query.filter_by(username='master').one()
        return import_preview_rows(
            preview,
            db.session,
            company_id or user.company_id,
            user_id or user.id,
            strategy,
            key or uuid.uuid4().hex,
        )

    def test_valid_csv_parses_supported_dates_brazilian_money_and_calculates_ticket(self):
        with self.app.app_context():
            preview = self.preview(csv_bytes(
                '2025-01-02;2;1.234,56;-10,25;617,28;NEX',
                '03/01/2025;0;0,00;;;',
            ))
            self.assertEqual(preview['valid_rows'], 2)
            self.assertEqual(preview['sales_count'], 2)
            self.assertEqual(preview['revenue'], '1234.56')
            self.assertEqual(preview['average_ticket'], '617.28')
            self.assertEqual(preview['rows'][1]['ticket_medio'], '0.00')
            self.assertIsNone(preview['rows'][1]['lucro_bruto'])
            self.assertEqual(preview['rows'][1]['origem'], 'Importação histórica')

    def test_valid_xlsx_accepts_excel_serial_date(self):
        with self.app.app_context():
            preview = self.preview(xlsx_bytes((45659, 4, 100, 25, 25, 'NEX')), 'historico.xlsx')
            self.assertEqual(preview['rows'][0]['data'], '2025-01-02')
            self.assertEqual(preview['valid_rows'], 1)

    def test_missing_or_changed_header_is_rejected(self):
        with self.app.app_context():
            for headers in (
                'data;quantidade_vendas;faturamento;lucro_bruto;ticket_medio',
                'data;vendas;faturamento;lucro_bruto;ticket_medio;origem',
            ):
                with self.subTest(headers=headers):
                    with self.assertRaises(HistoricalImportError):
                        self.preview(csv_bytes('2025-01-01;1;10;2;10;NEX', headers=headers))

    def test_invalid_fields_negative_count_duplicate_date_and_empty_required_are_reported(self):
        with self.app.app_context():
            preview = self.preview(csv_bytes(
                '31/02/2025;1;10;2;10;NEX',
                '2025-01-02;-1;10;2;10;NEX',
                '2025-01-03;1;;2;10;NEX',
                '2025-01-04;1;10;2;10;NEX',
                '2025-01-04;2;20;4;10;NEX',
            ))
            self.assertEqual(preview['invalid_rows'], 4)
            self.assertEqual(preview['duplicate_rows'], 1)
            messages = str(preview['rows'])
            self.assertIn('use AAAA-MM-DD', messages)
            self.assertIn('quantidade não pode ser negativa', messages)
            self.assertIn('campo obrigatório vazio', messages)

    def test_ticket_informed_is_only_a_warning_and_calculated_value_wins(self):
        with self.app.app_context():
            preview = self.preview(csv_bytes('2025-01-02;3;100,00;20;99,99;NEX'))
            row = preview['rows'][0]
            self.assertEqual(row['ticket_medio'], '33.33')
            self.assertEqual(len(row['warnings']), 1)
            batch = self.import_rows(preview)
            report = HistoricalDailyReport.query.filter_by(batch_id=batch.id).one()
            self.assertEqual(report.average_ticket, Decimal('33.33'))

    def test_real_sale_on_same_date_blocks_import_without_operational_changes(self):
        with self.app.app_context():
            company_id = self.company_id()
            sale = Sale(company_id=company_id, created_at=datetime(2025, 1, 2, 12), final_amount=Decimal('10.00'))
            db.session.add(sale)
            db.session.commit()
            counts_before = (Product.query.count(), StockMovement.query.count(), CashRegister.query.count(), Sale.query.count())
            preview = self.preview(csv_bytes('2025-01-02;2;100;20;50;NEX'))
            self.assertEqual(preview['invalid_rows'], 1)
            with self.assertRaises(HistoricalImportError):
                self.import_rows(preview)
            self.assertEqual(counts_before, (Product.query.count(), StockMovement.query.count(), CashRegister.query.count(), Sale.query.count()))

    def test_existing_date_can_be_ignored_or_updated(self):
        with self.app.app_context():
            first = self.preview(csv_bytes('2025-01-02;2;100;20;50;NEX'))
            self.import_rows(first)
            second = self.preview(csv_bytes('2025-01-02;4;240;80;60;Outro'))
            self.assertEqual(second['existing_rows'], 1)
            ignored = self.import_rows(second, 'ignore')
            self.assertEqual(ignored.ignored_rows, 1)
            self.assertEqual(HistoricalDailyReport.query.one().revenue, Decimal('100.00'))
            updated = self.import_rows(second, 'update')
            self.assertEqual(updated.updated_rows, 1)
            self.assertEqual(HistoricalDailyReport.query.one().revenue, Decimal('240.00'))

    def test_idempotency_prevents_duplicate_request(self):
        with self.app.app_context():
            preview = self.preview(csv_bytes('2025-01-02;2;100;20;50;NEX'))
            key = uuid.uuid4().hex
            first = self.import_rows(preview, key=key)
            second = self.import_rows(preview, key=key)
            self.assertEqual(first.id, second.id)
            self.assertEqual(HistoricalDailyReport.query.count(), 1)
            self.assertEqual(HistoricalReportImportBatch.query.count(), 1)

    def test_company_isolation_uses_authenticated_company_scope(self):
        with self.app.app_context():
            company = Company(name='Outra empresa')
            db.session.add(company)
            db.session.flush()
            user = User(username='outro-admin', role='admin', company_id=company.id)
            user.set_password('SenhaForte123')
            db.session.add(user)
            db.session.commit()
            preview = self.preview(csv_bytes('2025-01-02;2;100;20;50;NEX'), company_id=company.id)
            self.import_rows(preview, company_id=company.id, user_id=user.id)
            self.assertEqual(HistoricalDailyReport.query.filter_by(company_id=company.id).count(), 1)
            self.assertEqual(HistoricalDailyReport.query.filter_by(company_id=self.company_id()).count(), 0)

    def test_period_totals_use_sum_revenue_over_sum_sales_and_profit_incomplete_is_explicit(self):
        with self.app.app_context():
            rows = [
                HistoricalDailyReport(report_date=date(2025, 1, 1), sales_count=2, revenue=Decimal('100'), gross_profit=Decimal('30')),
                HistoricalDailyReport(report_date=date(2025, 1, 2), sales_count=8, revenue=Decimal('900'), gross_profit=None),
            ]
            totals, _, _ = build_sales_report([])
            merged = merge_historical_report_totals(totals, rows)
            self.assertEqual(merged['average_ticket'], Decimal('100.00'))
            self.assertIsNone(merged['profit'])
            self.assertFalse(merged['profit_complete'])
            chart = build_sales_chart('annual', date(2025, 1, 1), date(2025, 12, 31), [], rows)
            self.assertEqual(chart[0]['total'], Decimal('1000.00'))

    def test_transaction_rolls_back_on_critical_commit_error(self):
        with self.app.app_context():
            preview = self.preview(csv_bytes('2025-01-02;2;100;20;50;NEX'))
            original_commit = db.session.commit
            with patch.object(db.session, 'commit', side_effect=RuntimeError('falha crítica')):
                with self.assertRaises(RuntimeError):
                    self.import_rows(preview)
            self.assertEqual(HistoricalDailyReport.query.count(), 0)
            self.assertEqual(HistoricalReportImportBatch.query.count(), 0)
            original_commit()

    def test_web_flow_download_preview_confirm_and_history(self):
        response = self.client.get('/relatorios/importacao/modelo')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, (Path(self.app.root_path) / 'static/files/modelo_importacao_relatorios_skygest.xlsx').read_bytes())
        response = self.client.post(
            '/relatorios/importacao/previsualizar',
            data={'spreadsheet': (io.BytesIO(csv_bytes('2025-01-02;2;100;20;50;NEX')), 'historico.csv')},
            content_type='multipart/form-data',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('Pré-visualização'.encode(), response.data)
        token = response.data.decode().split('name="preview_token" value="', 1)[1].split('"', 1)[0]
        key = response.data.decode().split('name="idempotency_key" value="', 1)[1].split('"', 1)[0]
        response = self.client.post('/relatorios/importacao/confirmar', data={
            'preview_token': token,
            'idempotency_key': key,
            'strategy': 'ignore',
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Importação concluída'.encode(), response.data)
        with self.app.app_context():
            self.assertEqual(HistoricalDailyReport.query.count(), 1)

    def test_production_environment_hides_feature(self):
        self.app.config['ENVIRONMENT'] = 'production'
        self.assertEqual(self.client.get('/relatorios/importacao/').status_code, 404)


if __name__ == '__main__':
    unittest.main()
