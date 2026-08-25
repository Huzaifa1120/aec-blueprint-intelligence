"""accuracy conformance schema

Revision ID: c9ecd9a0db87
Revises: c37396f6713e
Create Date: 2026-08-25 07:52:50.441906

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9ecd9a0db87'
down_revision: Union[str, Sequence[str], None] = 'c37396f6713e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: autogenerate also emitted a labor_rates create here (model/DB drift,
    # known gotcha) — deliberately excluded: that table is not part of the
    # migrated chain (tests/test_migrations.py EXPECTED set excludes it).
    op.add_column('boq_items', sa.Column('source_bbox_json', sa.Text(), nullable=True))
    op.add_column('estimates', sa.Column('data_quality_json', sa.Text(), nullable=True))
    op.add_column('estimates', sa.Column('scale_status', sa.String(length=20), nullable=True))
    op.add_column('estimates', sa.Column('source_pdf_path', sa.String(length=500), nullable=True))
    # Batch mode: SQLite has no ALTER ADD CONSTRAINT support (copy-and-move strategy)
    with op.batch_alter_table('review_actions') as batch_op:
        batch_op.add_column(sa.Column('boq_item_id', sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column('reason', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('corrected_value', sa.Float(), nullable=True))
        batch_op.create_foreign_key(
            'fk_review_actions_boq_item_id_boq_items',
            'boq_items',
            ['boq_item_id'],
            ['id'],
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('review_actions') as batch_op:
        batch_op.drop_constraint(
            'fk_review_actions_boq_item_id_boq_items', type_='foreignkey'
        )
        batch_op.drop_column('corrected_value')
        batch_op.drop_column('reason')
        batch_op.drop_column('boq_item_id')
    op.drop_column('estimates', 'source_pdf_path')
    op.drop_column('estimates', 'scale_status')
    op.drop_column('estimates', 'data_quality_json')
    op.drop_column('boq_items', 'source_bbox_json')
