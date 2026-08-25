"""Preserve audit history when companies or users are deleted."""

from migrations.central.versions.central_0003_audit_foreign_keys_set_null import (
    _replace_foreign_key,
)


revision = 'tenant_0005'
down_revision = 'tenant_0004'
branch_labels = None
depends_on = None


def upgrade():
    _replace_foreign_key('company_id', 'companies', 'SET NULL')
    _replace_foreign_key('user_id', 'users', 'SET NULL')


def downgrade():
    _replace_foreign_key('company_id', 'companies', None)
    _replace_foreign_key('user_id', 'users', None)
