"""route size_json to text

Revision ID: c37396f6713e
Revises: a7f3c9d21e55
Create Date: 2026-08-24 11:32:17.161149

FU-provenance size_json (Phase 4) is unbounded JSON text; the old VARCHAR(1000)
cap could truncate multi-fixture breakdowns. Edited autogenerate output: the
spurious labor_rates create-table op was dropped (pre-existing model/migration
drift, not this wave's concern), and alter_column runs in batch mode because
SQLite has no ALTER COLUMN support (copy-and-move strategy).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c37396f6713e'
down_revision: Union[str, Sequence[str], None] = 'a7f3c9d21e55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "routes",
        "size_json",
        existing_type=sa.String(length=1000),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "routes",
        "size_json",
        existing_type=sa.Text(),
        type_=sa.String(length=1000),
        existing_nullable=True,
    )