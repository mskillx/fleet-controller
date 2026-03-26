"""Add version column to device_stats

Revision ID: 003
Revises: 002
Create Date: 2025-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('device_stats', sa.Column('version', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('device_stats', 'version')
