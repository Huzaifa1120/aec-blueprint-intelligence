"""add_ondelete_set_null_to_review_actions_boq_item_fk

Revision ID: bd22e11a6b67
Revises: 02ee603e4d03
Create Date: 2026-09-03 12:15:18.087255

Fix: Add ON DELETE SET NULL to review_actions.boq_item_id FK so that
deleting boq_items (during sheet replacement) doesn't fail when
review_actions reference them.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'bd22e11a6b67'
down_revision: Union[str, Sequence[str], None] = '02ee603e4d03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop existing FK and recreate with ON DELETE SET NULL
    op.drop_constraint(
        'fk_review_actions_boq_item_id_boq_items',
        'review_actions',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'fk_review_actions_boq_item_id_boq_items',
        'review_actions',
        'boq_items',
        ['boq_item_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Revert to original FK without ON DELETE clause (RESTRICT)
    op.drop_constraint(
        'fk_review_actions_boq_item_id_boq_items',
        'review_actions',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'fk_review_actions_boq_item_id_boq_items',
        'review_actions',
        'boq_items',
        ['boq_item_id'],
        ['id']
    )