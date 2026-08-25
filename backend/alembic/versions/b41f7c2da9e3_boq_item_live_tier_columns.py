"""boq item live tier columns

Revision ID: b41f7c2da9e3
Revises: c9ecd9a0db87
Create Date: 2026-08-25

T3-review ruling: persisted BoqItem rows must carry the live confidence tier
(DERIVED/ASSUMED) the API response actually showed, not the row-level
MEASURED status. Adds nullable tier + score columns; legacy rows stay NULL
and the payload builder falls back to the measurement status.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b41f7c2da9e3'
down_revision: Union[str, Sequence[str], None] = 'c9ecd9a0db87'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'boq_items', sa.Column('confidence_status', sa.String(length=20), nullable=True)
    )
    op.add_column('boq_items', sa.Column('confidence_score', sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('boq_items', 'confidence_score')
    op.drop_column('boq_items', 'confidence_status')
