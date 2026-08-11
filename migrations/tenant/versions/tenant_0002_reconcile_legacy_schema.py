"""Reconcile tenant databases created before Alembic was introduced."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from migrations.central.versions.central_0002_reconcile_legacy_schema import (
    upgrade as reconcile_legacy_schema,
)


revision = 'tenant_0002'
down_revision = 'tenant_0001'
branch_labels = None
depends_on = None


def upgrade():
    reconcile_legacy_schema()


def downgrade():
    raise RuntimeError('A reconciliação de schemas legados não possui downgrade destrutivo.')
