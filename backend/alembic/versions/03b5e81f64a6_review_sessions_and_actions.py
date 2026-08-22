"""review sessions and actions

Revision ID: 03b5e81f64a6
Revises: 420e9452af98
Create Date: 2026-08-23 01:15:50.536331

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "03b5e81f64a6"
down_revision: Union[str, Sequence[str], None] = "420e9452af98"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "review_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("sheet_label", sa.String(length=200), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_review_sessions_project_id_projects"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_sessions")),
    )
    op.create_table(
        "review_actions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("confidence_tier", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["review_sessions.id"],
            name=op.f("fk_review_actions_session_id_review_sessions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_actions")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("review_actions")
    op.drop_table("review_sessions")
