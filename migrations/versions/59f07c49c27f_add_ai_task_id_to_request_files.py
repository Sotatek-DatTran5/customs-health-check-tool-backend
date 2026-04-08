"""add ai_task_id to request_files

Revision ID: 59f07c49c27f
Revises: 001_initial
Create Date: 2026-04-08 11:00:57.928091

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '59f07c49c27f'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('request_files', sa.Column('ai_task_id', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('request_files', 'ai_task_id')
