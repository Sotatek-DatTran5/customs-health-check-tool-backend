"""add ai_result_data to request_files

Revision ID: d8401f8b3887
Revises: 59f07c49c27f
Create Date: 2026-04-08 14:01:53.852962

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd8401f8b3887'
down_revision: Union[str, None] = '59f07c49c27f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('request_files', sa.Column('ai_result_data', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('request_files', 'ai_result_data')
