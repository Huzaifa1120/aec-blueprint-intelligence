"""drawing quality assessments and reexport requests

Revision ID: 420e9452af98
Revises: 91ac44162757
Create Date: 2026-08-22 22:10:32.818003

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '420e9452af98'
down_revision: Union[str, Sequence[str], None] = '91ac44162757'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: autogenerate also detected a 'labor_rates' table from concurrent
    # work — hand-stripped here; its owner will ship its own migration.
    op.create_table('drawing_quality_assessments',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('drawing_id', sa.Uuid(), nullable=True),
    sa.Column('file_name', sa.String(length=500), nullable=False),
    sa.Column('verdict', sa.String(length=20), nullable=False),
    sa.Column('metrics_json', sa.String(length=2000), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['drawing_id'], ['drawings.id'], name=op.f('fk_drawing_quality_assessments_drawing_id_drawings')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_drawing_quality_assessments'))
    )
    op.create_table('reexport_requests',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('drawing_id', sa.Uuid(), nullable=True),
    sa.Column('message', sa.String(length=1000), nullable=False),
    sa.Column('requested_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['drawing_id'], ['drawings.id'], name=op.f('fk_reexport_requests_drawing_id_drawings')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_reexport_requests'))
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('reexport_requests')
    op.drop_table('drawing_quality_assessments')
