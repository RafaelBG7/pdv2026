from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db


class HistoricalReportImportBatch(db.Model):
    __tablename__ = 'historical_report_import_batches'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_hash = db.Column(db.String(64), nullable=False)
    source = db.Column(db.String(120), nullable=False, default='Importação histórica')
    strategy = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='completed')
    valid_rows = db.Column(db.Integer, nullable=False, default=0)
    invalid_rows = db.Column(db.Integer, nullable=False, default=0)
    inserted_rows = db.Column(db.Integer, nullable=False, default=0)
    updated_rows = db.Column(db.Integer, nullable=False, default=0)
    ignored_rows = db.Column(db.Integer, nullable=False, default=0)
    period_start = db.Column(db.Date, nullable=True)
    period_end = db.Column(db.Date, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    idempotency_key = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    reports = db.relationship('HistoricalDailyReport', back_populates='batch')

    __table_args__ = (
        db.UniqueConstraint('company_id', 'idempotency_key', name='uq_historical_batch_company_request'),
    )


class HistoricalDailyReport(db.Model):
    __tablename__ = 'historical_daily_reports'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False, index=True)
    report_date = db.Column(db.Date, nullable=False, index=True)
    sales_count = db.Column(db.Integer, nullable=False)
    revenue = db.Column(db.Numeric(18, 2), nullable=False, default=Decimal('0.00'))
    gross_profit = db.Column(db.Numeric(18, 2), nullable=True)
    average_ticket = db.Column(db.Numeric(18, 2), nullable=False, default=Decimal('0.00'))
    source = db.Column(db.String(120), nullable=False, default='Importação histórica')
    batch_id = db.Column(db.Integer, db.ForeignKey('historical_report_import_batches.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    batch = db.relationship('HistoricalReportImportBatch', back_populates='reports')

    __table_args__ = (
        db.UniqueConstraint('company_id', 'report_date', name='uq_historical_report_company_date'),
        db.CheckConstraint('sales_count >= 0', name='ck_historical_report_sales_count_nonnegative'),
        db.CheckConstraint('revenue >= 0', name='ck_historical_report_revenue_nonnegative'),
    )
