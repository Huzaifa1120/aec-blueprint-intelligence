"""add size_json and derivation provenance columns

Revision ID: 5bf57251ec38
Revises: 03b5e81f64a6
Create Date: 2026-08-23 06:54:38.397187

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5bf57251ec38'
down_revision: Union[str, Sequence[str], None] = '03b5e81f64a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('boq_items', sa.Column('derivation_json', sa.String(length=2000), nullable=True))
    op.add_column('boq_items', sa.Column('size_source', sa.String(length=20), nullable=True))
    op.add_column('routes', sa.Column('size_json', sa.String(length=1000), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('routes', 'size_json')
    op.drop_column('boq_items', 'size_source')
    op.drop_column('boq_items', 'derivation_json')
