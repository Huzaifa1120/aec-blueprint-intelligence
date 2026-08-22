"""add source_quality to components routes spaces

Revision ID: 91ac44162757
Revises: 3ce37f7feb3c
Create Date: 2026-08-22 20:34:08.392666

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "91ac44162757"
down_revision: Union[str, Sequence[str], None] = "3ce37f7feb3c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "components",
        sa.Column(
            "source_quality",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'layered_vector'"),
        ),
    )
    op.add_column(
        "routes",
        sa.Column(
            "source_quality",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'layered_vector'"),
        ),
    )
    op.add_column(
        "spaces",
        sa.Column(
            "source_quality",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'layered_vector'"),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("spaces", "source_quality")
    op.drop_column("routes", "source_quality")
    op.drop_column("components", "source_quality")
