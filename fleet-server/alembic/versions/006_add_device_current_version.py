"""Add current_version column to devices table

Revision ID: 006
Revises: 005
Create Date: 2026-03-31 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('devices') as batch_op:
        batch_op.add_column(sa.Column('current_version', sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('devices') as batch_op:
        batch_op.drop_column('current_version')
