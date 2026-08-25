"""estimate source_quality

Revision ID: 2ba5156bafc3
Revises: b41f7c2da9e3
Create Date: 2026-08-25

Spec v3 §7.12 conformance: the Estimate carries the run's input-quality
verdict so persisted BOQ rows can serve ``source_quality`` exactly as the
live response did. Server default backfills legacy rows honestly.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2ba5156bafc3'
down_revision: Union[str, Sequence[str], None] = 'b41f7c2da9e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('estimates') as batch_op:
        batch_op.add_column(
            sa.Column(
                'source_quality',
                sa.String(length=20),
                nullable=False,
                server_default='layered_vector',
            )
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('estimates') as batch_op:
        batch_op.drop_column('source_quality')
