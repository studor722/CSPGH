"""add_is_outlier_to_observation

Revision ID: d1874b9ea9d1
Revises: 
Create Date: 2026-11-04 16:34:31.506182

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1874b9ea9d1'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add is_outlier column and standardize uq_observation constraint."""
    op.add_column(
        "observation",
        sa.Column("is_outlier", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    # Update unique constraint from (country_iso3, indicator_id, year, sex, age_group)
    # to the canonical 4-column natural key (country_iso3, indicator_id, year, sex)
    op.drop_constraint("uq_observation", "observation", type_="unique")
    op.create_unique_constraint(
        "uq_observation",
        "observation",
        ["country_iso3", "indicator_id", "year", "sex"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_observation", "observation", type_="unique")
    op.create_unique_constraint(
        "uq_observation",
        "observation",
        ["country_iso3", "indicator_id", "year", "sex", "age_group"],
    )
    op.drop_column("observation", "is_outlier")
