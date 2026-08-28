"""standardize subscription plans

Revision ID: central_0007
Revises: central_0006
Create Date: 2026-08-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'central_0007'
down_revision: Union[str, Sequence[str], None] = 'central_0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text(
        "UPDATE companies SET subscription_plan = 'Basic' "
        "WHERE subscription_plan IS NULL OR subscription_plan = '' OR subscription_plan = 'Essencial'"
    ))
    connection.execute(sa.text(
        "UPDATE companies SET subscription_plan = 'Ultimate' "
        "WHERE subscription_plan IN ('Profissional', 'Premium')"
    ))
    connection.execute(sa.text(
        "UPDATE activation_keys SET plan = 'Basic' WHERE plan = 'Essencial'"
    ))
    connection.execute(sa.text(
        "UPDATE activation_keys SET plan = 'Ultimate' WHERE plan IN ('Profissional', 'Premium')"
    ))


def downgrade() -> None:
    pass
