"""v3 conformance schema: layers, schedule_blocks, text_annotations + layer_id FKs

Revision ID: a7f3c9d21e55
Revises: 5bf57251ec38
Create Date: 2026-08-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7f3c9d21e55"
down_revision: Union[str, Sequence[str], None] = "5bf57251ec38"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "layers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sheet_id", sa.Uuid(), nullable=False),
        sa.Column("ocg_name", sa.String(length=100), nullable=False),
        sa.Column("classified_discipline", sa.String(length=50), nullable=False),
        sa.Column("human_override_discipline", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(["sheet_id"], ["sheets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sheet_id", "ocg_name"),
    )
    op.create_table(
        "schedule_blocks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sheet_id", sa.Uuid(), nullable=False),
        sa.Column("block_type", sa.String(length=30), nullable=False),
        sa.Column("page_region_json", sa.String(length=500), nullable=False),
        sa.Column("entries_json", sa.Text(), nullable=False),
        sa.Column(
            "source_quality",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'layered_vector'"),
        ),
        sa.ForeignKeyConstraint(["sheet_id"], ["sheets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "text_annotations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sheet_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("bbox_json", sa.String(length=200), nullable=False),
        sa.Column("ocg_layer", sa.String(length=100), nullable=True),
        sa.Column("component_id", sa.Uuid(), nullable=True),
        sa.Column("route_id", sa.Uuid(), nullable=True),
        sa.Column("space_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["sheet_id"], ["sheets.id"]),
        sa.ForeignKeyConstraint(["component_id"], ["components.id"]),
        sa.ForeignKeyConstraint(["route_id"], ["routes.id"]),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    
    # Add layer_id column and FK to components, routes, spaces
    for table_name in ("components", "routes", "spaces"):
        op.add_column(table_name, sa.Column("layer_id", sa.Uuid(), nullable=True))
        op.create_foreign_key(
            f"fk_{table_name}_layer_id_layers",
            table_name,
            "layers",
            ["layer_id"],
            ["id"],
            ondelete="SET NULL"
        )
    
    op.add_column(
        "sheets",
        sa.Column(
            "source_quality",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'layered_vector'"),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("sheets", "source_quality")
    for table_name in ("spaces", "routes", "components"):
        op.drop_constraint(
            f"fk_{table_name}_layer_id_layers",
            table_name,
            type_="foreignkey"
        )
        op.drop_column(table_name, "layer_id")
    op.drop_table("text_annotations")
    op.drop_table("schedule_blocks")
    op.drop_table("layers")