"""add index on request_files.ai_task_id

Revision ID: 00f002f03b4c
Revises: d8401f8b3887
Create Date: 2026-04-09 18:08:31.690902

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '00f002f03b4c'
down_revision: Union[str, None] = 'd8401f8b3887'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(op.f('ix_request_files_ai_task_id'), 'request_files', ['ai_task_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_request_files_ai_task_id'), table_name='request_files')
